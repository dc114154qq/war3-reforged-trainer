"""Data-only game adapters. Importing a pack never imports executable code."""

from __future__ import annotations

from dataclasses import dataclass
from copy import deepcopy
from functools import lru_cache, cached_property
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from types import MappingProxyType
import hashlib
import json
import os
import re
import struct
import tempfile

SCHEMA_VERSION = 5
BRIDGE_PROFILE_VERSION = 3
PROFILE_ROOT = Path(__file__).resolve().parent / "profiles"
_ACTIVE = ContextVar("war3_game_profile", default=None)


class ProfileError(ValueError):
    pass


def version_tuple(version):
    if not isinstance(version, str) or not re.fullmatch(r"\d+\.\d+\.\d+\.\d+", version):
        raise ProfileError("Game version must contain four numeric components")
    result = tuple(map(int, version.split(".")))
    if any(part > 65535 for part in result):
        raise ProfileError("Game version component exceeds executable version range")
    return result


def _freeze(value):
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def _plain(value):
    if hasattr(value, "items"):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    return value


@dataclass(frozen=True)
class GameProfile:
    data: object
    digest: str

    @property
    def id(self):
        return self.data["id"]

    @cached_property
    def fingerprint(self):
        f = self.data["fingerprint"]
        return f["machine"], f["timestamp"], f["image_size"]

    @cached_property
    def bridge_layout(self):
        from war3_layout_schema import bridge_layout
        return MappingProxyType(bridge_layout(self.data))

    def section(self, name):
        return self.bridge_layout if name == "bridge_layout" else self.data[name]

    @cached_property
    def _checks(self):
        return MappingProxyType(
            {
                name: tuple((row["rva"], bytes.fromhex(row["bytes"])) for row in rows)
                for name, rows in self.data["checks"].items()
            }
        )

    def checks(self, name):
        return self._checks[name]

    @cached_property
    def registry_metadata(self):
        """Bind immutable adapter data once; process memory is never cached here."""
        registry = self.section("registry")
        handle_layout = tuple(registry[key] for key in
            ("primary", "alternate", "count", "stride", "slot_owner", "owner_handle"))
        unit_layout = tuple(registry[key] for key in
            ("object_handle", "owner_tag", "owner_data", "unit_tag", "owner_handle"))
        return (self.section("registry"), self.section("players"),
                self.section("addresses"), self.fingerprint,
                self.checks("resolver")[0][1], self.checks("game_state")[-1],
                handle_layout, unit_layout)

    def to_dict(self):
        return _plain(self.data)

    def selection_report(self):
        return {"mode": "exact", "actual_game_version": self.data["game_version"],
                "adapter_game_version": self.data["game_version"],
                "adapter_source_id": self.id, "build_distance": 0,
                "borrowed": False}

    @cached_property
    def adapter(self):
        from war3_game_adapter import GameAdapter
        return GameAdapter(self)

    def require_module(self, name):
        module = self.data["modules"].get(name)
        if module is None or not module["enabled"]:
            raise ProfileError("Adapter capability disabled: " + name)
        # The pack selects an existing bundled algorithm and declares the
        # target fingerprint. Data-only relocation needs no new Python/C code.
        # Instruction-patching modules retain their separate fingerprint gate.
        from war3_version_modules import validate_implementation, known_implementation
        if (
            tuple(module["fingerprint"]) != self.fingerprint
            or not known_implementation(name, module["implementation"])
            or (name == "talent_icons" and
                not validate_implementation(name, module["implementation"], self.fingerprint))
        ):
            raise ProfileError(
                "Version-specific module needs separate adaptation: " + name
            )

    def bridge_bytes(self):
        values = self.section("bridge_layout")
        return struct.pack(
            "<" + "I" * (2 + len(values)),
            BRIDGE_PROFILE_VERSION,
            8 + len(values) * 4,
            *values.values(),
        )


@dataclass(frozen=True)
class BorrowedGameProfile(GameProfile):
    """Runtime choice authorized by the user; never a validated/importable pack."""
    source: GameProfile

    def require_module(self, name):
        # Reuse the selected bundled implementation, including its normal
        # per-operation guards. No separate all-capability preflight is added.
        if name == "talent_icons":
            return super().require_module(name)
        return self.source.require_module(name)

    def selection_report(self):
        actual, source = self.data["game_version"], self.source.data["game_version"]
        return {"mode": "nearest", "actual_game_version": actual,
                "adapter_game_version": source, "adapter_source_id": self.source.id,
                "build_distance": abs(version_tuple(actual)[3] - version_tuple(source)[3]),
                "borrowed": True}


def borrow_profile(source, fingerprint, game_version):
    if (source.data["status"] != "validated" or len(fingerprint) != 3
            or fingerprint[0] != source.fingerprint[0]
            or version_tuple(game_version)[:2] != version_tuple(source.data["game_version"])[:2]):
        raise ProfileError("Invalid source for automatic adapter selection")
    data = source.to_dict()
    data["game_version"] = game_version
    data["fingerprint"] = dict(zip(("machine", "timestamp", "image_size"), fingerprint))
    data["status"] = "borrowed"
    data["id"] = source.id + "-for-" + game_version
    encoded = json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    return BorrowedGameProfile(_freeze(data), hashlib.sha256(encoded).hexdigest(), source)


def _no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ProfileError("Duplicate adapter key: " + key)
        result[key] = value
    return result


def _read_json(path):
    raw = Path(path).read_bytes()
    if len(raw) > 2 * 1024 * 1024:
        raise ProfileError("Adapter exceeds 2 MiB")
    return json.loads(raw, object_pairs_hook=_no_duplicates)


def _validate_shape(value, template, key="profile"):
    if type(value) is not type(template):
        raise ProfileError("Adapter value type differs: " + key)
    if isinstance(template, dict):
        if value.keys() != template.keys():
            raise ProfileError("Adapter keys differ: " + key)
        for name in template:
            _validate_shape(value[name], template[name], key + "." + name)
    elif isinstance(template, list):
        if len(value) != len(template):
            raise ProfileError("Adapter list size differs: " + key)
        for i, item in enumerate(template):
            _validate_shape(value[i], item, key + "." + str(i))
    elif isinstance(template, int) and not isinstance(template, bool):
        if not 0 <= value <= 0xFFFFFFFFFFFFFFFF:
            raise ProfileError("Adapter integer out of range: " + key)


def load_profile(path) -> GameProfile:
    template = _read_json(PROFILE_ROOT / "3.0.0.24268.json")
    data = _read_json(path)
    # Released 2.1.03 packs remain readable after this structural refactor.
    # Their pinned layout was implicit in the old compiled adapter. Upgrade
    # only the representation; module/fingerprint approval is still checked.
    if data.get("schema_version") == 4 and data.get("bridge_profile_version") == 2:
        legacy_template = {key: value for key, value in template.items() if key != "layouts"}
        _validate_shape(data, legacy_template)
        data["layouts"] = deepcopy(template["layouts"])
        data["layouts"]["ability"]["unit_owner"] = data["equipment_runtime"]["ability_owner"]
        data["schema_version"] = SCHEMA_VERSION
        data["bridge_profile_version"] = BRIDGE_PROFILE_VERSION
    # Additive data fields: older schema-5 packs retain their property-based
    # coordinates. Only a pack that explicitly supplies both unit offsets
    # opts into the direct unit-coordinate projection.
    if data.get('schema_version') == 5 and data.get('bridge_profile_version') == 3:
        unit = data.get('layouts', {}).get('unit', {})
        unit.setdefault('position_x', 0)
        unit.setdefault('position_y', 0)
    _validate_shape(data, template)
    if (
        data["schema_version"] != SCHEMA_VERSION
        or data["bridge_profile_version"] != BRIDGE_PROFILE_VERSION
    ):
        raise ProfileError("Unsupported adapter or bridge schema")
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", data["id"]):
        raise ProfileError("Invalid adapter ID")
    if data["status"] not in ("validated", "candidate"):
        raise ProfileError("Unknown adapter status")
    version_tuple(data["game_version"])
    if (
        data["fingerprint"]["machine"] != 0x8664
        or data["fingerprint"]["image_size"] < 4096
    ):
        raise ProfileError("Unsupported game image")
    size = data["fingerprint"]["image_size"]
    fog = data['fog_recovery']
    if any(not 0 < value < 0x10000 for value in fog.values()):
        raise ProfileError('Invalid fog recovery offset')
    for key,value in data['stat_runtime'].items():
        if not 0 < value < (size if key.endswith('_vtable') else 0x1000):
            raise ProfileError('Invalid stat runtime layout: '+key)
    for key,value in data['equipment_runtime'].items():
        if not 0<value<(size if key.endswith('_rva') else 0x10000):
            raise ProfileError('Invalid equipment runtime layout: '+key)
    for domain, fields in data["layouts"].items():
        if any(type(value) is not int or not 0 <= value < 0x100000
               for key, value in fields.items()
               if not key.endswith("_tag")):
            raise ProfileError("Invalid domain layout: " + domain)
    component = data["layouts"]["component_list"]
    start, snapshot_size = component["snapshot_start"], component["snapshot_size"]
    if not snapshot_size or snapshot_size > 4096 or any(
            not start <= component[key] <= start + snapshot_size - 8
            for key in ("tag", "handle", "previous", "next", "owner", "data")):
        raise ProfileError("Invalid component snapshot layout")
    offsets = sorted(component[key] for key in ("tag", "handle", "previous", "next", "owner", "data"))
    if any(right < left + 8 for left, right in zip(offsets, offsets[1:])):
        raise ProfileError("Overlapping component snapshot fields")
    record = data["layouts"]["equipment_record"]
    if not 8 <= record["stride"] <= 4096 or record["state"] + 4 > record["stride"]:
        raise ProfileError("Invalid equipment record layout")
    prop = data["layouts"]["property"]
    names = ("array", "capacity", "mirror", "mirror_capacity", "stride", "slots", "count")
    spans = sorted((prop[name], prop[name] + (8 if index < 4 else 4))
                   for index, name in enumerate(names))
    if (not 0 < prop["descriptor_size"] <= 4096
            or any(end > prop["descriptor_size"] for _, end in spans)
            or any(right[0] < left[1] for left, right in zip(spans, spans[1:]))):
        raise ProfileError("Invalid property descriptor layout")
    talent = data["layouts"]["talent"]
    point = talent["point_counter"] - talent["snapshot_start"]
    if (talent["record_stride"] < 12 or talent["record_flags"] < 8
            or talent["record_flags"] + 4 > talent["record_stride"]
            or point < 6 * talent["record_stride"]
            or point + 4 > talent["snapshot_size"]):
        raise ProfileError("Invalid talent snapshot layout")
    if data["equipment_runtime"]["ability_owner"] != data["layouts"]["ability"]["unit_owner"]:
        raise ProfileError("Equipment and ability layouts disagree")
    item = data["layouts"]["item"]
    unit = data['layouts']['unit']
    if bool(unit['position_x']) != bool(unit['position_y']) or (
        unit['position_x'] and (unit['position_x'] % 4 or unit['position_y'] % 4
                                or abs(unit['position_x'] - unit['position_y']) < 4)):
        raise ProfileError('Invalid unit coordinate projection')
    inventory = data["layouts"]["inventory"]
    if item["owner_scan_radius"] <= 0 or item["owner_scan_stride"] % 8:
        raise ProfileError("Invalid item owner scan layout")
    if inventory["slot_count"] != 6 or inventory["slot_stride"] < 8:
        raise ProfileError("Invalid classic inventory layout")
    for group in data["checks"].values():
        for row in group:
            code = bytes.fromhex(row["bytes"])
            if not code or not 0 <= row["rva"] < row["rva"] + len(code) <= size:
                raise ProfileError("Invalid adapter code check")
    for key, value in data["bridge_layout"].items():
        if not 0 <= value <= 0xFFFFFFFF or (key.endswith("_rva") and value >= size):
            raise ProfileError("Invalid bridge layout: " + key)
    if not 0 < data['bridge_layout']['ability_level_tail'] < 0x10000:
        raise ProfileError('Invalid ability setter recovery offset')
    for key, value in data["addresses"].items():
        optional_internal = key in ("speed_factor", "effective_interval", "unit_resolver")
        if not (0 <= value < size if optional_internal else 0 < value < size):
            raise ProfileError("Invalid game RVA: " + key)
    module_addresses = data["module_addresses"]
    for key, value in module_addresses.items():
        if not 0 < value < size:
            raise ProfileError("Invalid module RVA: " + key)
    # Native ABI is supplied by compiled typed wrappers, never by arbitrary JSON.
    if data["native_abi"] != template["native_abi"]:
        raise ProfileError("Native machine ABI changes require a compiled adapter")
    for name, module in data["modules"].items():
        from war3_version_modules import known_implementation
        if not known_implementation(name, module["implementation"]):
            raise ProfileError("Unknown compiled adapter module: " + name)
    if any(not 0 < data["decoder"][key] < 64 for key in ("ror", "rol")):
        raise ProfileError("Invalid decoder rotation")
    r = data["registry"]
    if (
        not 16 <= r["stride"] <= 4096
        or r["stride"] % 8
        or r["slot_owner"] + 8 > r["stride"]
    ):
        raise ProfileError("Invalid registry slot layout")
    if not 8 <= r["count"] <= 4096 or not 1 <= data["selection"]["max_count"] <= 24:
        raise ProfileError("Invalid bounded object layout")
    if not 1 <= data["players"]["max_count"] <= 64:
        raise ProfileError("Invalid player count")
    for section in ("context", "native_table", "selection", "players"):
        if any(value > 0x100000 for value in data[section].values()):
            raise ProfileError("Object offset outside bounded layout: " + section)
    aliases = {
        "registry_root_rva": data["addresses"]["registry_root"],
        "table_count": r["count"],
        **{
            k: r[k]
            for k in (
                "primary",
                "alternate",
                "stride",
                "slot_owner",
                "owner_handle",
                "owner_data",
                "object_handle",
                "object_rawcode",
            )
        },
    }
    if any(data["bridge_layout"][k] != v for k, v in aliases.items()):
        raise ProfileError("Python and bridge layouts disagree")
    encoded = json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    # Normalize field order to the single wire definition, not JSON input order.
    data["bridge_layout"] = {
        name: data["bridge_layout"][name] for name in template["bridge_layout"]
    }
    return GameProfile(_freeze(data), hashlib.sha256(encoded).hexdigest())


@lru_cache(maxsize=1)
def default_profile():
    return load_profile(PROFILE_ROOT / "3.0.0.24268.json")


def current_profile():
    return _ACTIVE.get() or default_profile()


@contextmanager
def profile_scope(profile):
    token = _ACTIVE.set(profile)
    try:
        yield profile
    finally:
        _ACTIVE.reset(token)


def import_profile(source, destination):
    """Explicit offline import, validated and published atomically."""
    profile = load_profile(source)
    if profile.data["status"] != "validated":
        raise ProfileError("Candidate adapters are diagnostic-only")
    directory = Path(destination)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / (profile.id + ".json")
    fd, name = tempfile.mkstemp(prefix=".adapter-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(profile.to_dict(), out, ensure_ascii=False, indent=2)
            out.write("\n")
        os.replace(name, target)
    finally:
        if os.path.exists(name):
            os.unlink(name)
    return target


def installed_profile_directory():
    return (
        Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
        / "War3Trainer"
        / "adapters"
    )


class ProfileCatalog:
    def __init__(self, directory=None):
        self.profiles = []
        self.errors = {}
        for path in sorted(PROFILE_ROOT.glob("*.json")):
            try:
                self.profiles.append(load_profile(path))
            except (ValueError, OSError) as exc:
                self.errors[str(path)] = str(exc)
        directory = (
            installed_profile_directory() if directory is None else Path(directory)
        )
        if directory.is_dir():
            for path in sorted(directory.glob("*.json")):
                try:
                    self.profiles.append(load_profile(path))
                except (ValueError, OSError) as exc:
                    self.errors[str(path)] = str(exc)

    def select(self, fingerprint, game_version=None):
        matches = {
            p.digest: p
            for p in self.profiles
            if p.fingerprint == tuple(fingerprint) and p.data["status"] == "validated"
        }
        if len(matches) == 1:
            return next(iter(matches.values()))
        if not matches and game_version is not None:
            target = version_tuple(game_version)
            candidates = {}
            for profile in self.profiles:
                if profile.data["status"] != "validated" or profile.fingerprint[0] != fingerprint[0]:
                    continue
                version = version_tuple(profile.data["game_version"])
                if version[:2] != target[:2]:
                    continue
                # Equal distance prefers the earlier build, then newer adapter revision.
                rank = (abs(version[2] - target[2]), abs(version[3] - target[3]),
                        version > target, -profile.data["adapter_version"])
                candidates[profile.digest] = (rank, profile)
            if candidates:
                rank = min(row[0] for row in candidates.values())
                nearest = [profile for key, profile in candidates.values() if key == rank]
                if len(nearest) != 1:
                    raise ProfileError("Ambiguous nearest game adapter: " + game_version)
                return borrow_profile(nearest[0], tuple(fingerprint), game_version)
        if len(matches) != 1:
            raise ProfileError(
                "Unknown or ambiguous game build: " + repr(tuple(fingerprint))
            )

    def select_for_image(self, fingerprint, module_name, module_path):
        if any(p.fingerprint == tuple(fingerprint) and p.data["status"] == "validated" for p in self.profiles):
            return self.select(fingerprint)
        # A shell, launcher or arbitrary DLL must never inherit a Warcraft adapter.
        import ntpath
        names = {str(module_name).casefold(), ntpath.basename(str(module_path)).casefold()}
        if not names <= {"warcraft iii.exe", "war3.exe"}:
            raise ProfileError("Unknown game module identity for nearest adapter selection")
        from war3_game_version import read_executable_version
        version = read_executable_version(module_path, fingerprint)
        return self.select(fingerprint, version)
