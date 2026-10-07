"""Data-only game adapters. Importing a pack never imports executable code."""

from __future__ import annotations

from dataclasses import dataclass
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

SCHEMA_VERSION = 3
BRIDGE_PROFILE_VERSION = 1
PROFILE_ROOT = Path(__file__).resolve().parent / "profiles"
_ACTIVE = ContextVar("war3_game_profile", default=None)


class ProfileError(ValueError):
    pass


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

    def section(self, name):
        return self.data[name]

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

    def require_module(self, name):
        module = self.data["modules"].get(name)
        if module is None or not module["enabled"]:
            raise ProfileError("Adapter capability disabled: " + name)
        # Code-dependent extensions cannot be retargeted by merely renaming a pack.
        from war3_version_modules import validate_implementation
        if (
            tuple(module["fingerprint"]) != self.fingerprint
            or not validate_implementation(name, module["implementation"], self.fingerprint)
        ):
            raise ProfileError(
                "Version-specific module needs separate adaptation: " + name
            )

    def bridge_bytes(self):
        values = self.data["bridge_layout"]
        return struct.pack(
            "<" + "I" * (2 + len(values)),
            BRIDGE_PROFILE_VERSION,
            8 + len(values) * 4,
            *values.values(),
        )


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
    for group in data["checks"].values():
        for row in group:
            code = bytes.fromhex(row["bytes"])
            if not code or not 0 <= row["rva"] < row["rva"] + len(code) <= size:
                raise ProfileError("Invalid adapter code check")
    for key, value in data["bridge_layout"].items():
        if not 0 <= value <= 0xFFFFFFFF or (key.endswith("_rva") and value >= size):
            raise ProfileError("Invalid bridge layout: " + key)
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

    def select(self, fingerprint):
        matches = {
            p.digest: p
            for p in self.profiles
            if p.fingerprint == tuple(fingerprint) and p.data["status"] == "validated"
        }
        if len(matches) != 1:
            raise ProfileError(
                "Unknown or ambiguous game build: " + repr(tuple(fingerprint))
            )
        return next(iter(matches.values()))
