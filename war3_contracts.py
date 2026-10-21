"""Shared data and scalar conversion contracts; no UI or process access."""
from __future__ import annotations
from dataclasses import dataclass,field,replace
from decimal import Decimal,InvalidOperation
from typing import Callable,Iterable,Iterator
import math,struct
from war3_ability_fields import AbilityFieldSpec
from war3_item_fields import ItemFieldSpec
@dataclass(frozen=True)
class Region:
    base: int
    size: int
    protect: int
    typ: int


@dataclass(frozen=True)
class ResourceCache:
    gold_address: int
    lumber_address: int
    gold: int
    lumber: int
    food_used_address: int = 0
    food_cap_address: int = 0
    food_limit_address: int = 0
    food_used: int = 0
    food_cap: int = 0
    food_limit: int = 0
    block_start_kind: int = 0
    source: str = ""
    owner_key: int = 0
    header_value: int = 0
    player_value: int = 0
    score: int = 0
    player_handle: int | None = None
    process_id: int = 0


@dataclass(frozen=True)
class ResourceProperty:
    kind: int
    address: int
    value: int
    owner_key: int


@dataclass(frozen=True)
class LocalPlayerResources:
    player_id: int
    gold: int
    lumber: int
    food_used: int
    food_cap: int


@dataclass(frozen=True)
class UnitCandidate:
    base: int
    score: int
    hp_current_address: int
    hp_max_address: int
    mp_current_address: int
    mp_max_address: int
    note: str
    hp_regen_address: int = 0
    mp_regen_address: int = 0
    owner_address: int = 0
    handle: int = 0
    unit_address: int = 0
    x_address: int = 0
    y_address: int = 0
    position_property_address: int = 0
    selection_source: str = ""
    selection_slot_address: int = 0
    unit_type_id: int = 0

    # Keep the immutable native result attached to the candidate that it
    # actually described. Other threads may replace the latest-session tuple.
    native_snapshot: PersistentNativeUnitSnapshot | None = field(default=None, compare=False, repr=False)

    @property
    def hp_visible_address(self) -> int:
        return self.hp_max_address

    @property
    def mp_visible_address(self) -> int:
        return self.mp_max_address


@dataclass(frozen=True)
class VisibleUnitPanel:
    current_hp: int
    max_hp: int
    current_mp: int
    max_mp: int
    hp_text: str
    mp_text: str


@dataclass(frozen=True)
class UnitMemoryField:
    key: str
    label: str
    value_type: str
    value: int | float | str
    address: int
    category: str
    write_address: int = 0
    write_type: str = ""
    write_base: float = 0.0
    note: str = ""
    extra_writes: tuple[tuple[int, str], ...] = ()
    native_write: bool = False
    native_component_identity: tuple[int, int] = (0, 0)

    @property
    def writable(self) -> bool:
        return self.native_write or bool(self.write_address and self.write_type)

    def value_text(self) -> str:
        if self.value_type == "rawcode":
            return format_rawcode(int(self.value))
        if self.value_type in {"u64", "ptr"}:
            return f"0x{int(self.value):x}"
        if isinstance(self.value, float):
            return format_editable_float32(self.value)
        return str(self.value)


@dataclass(frozen=True)
class InventoryItem:
    slot: int
    handle: int
    handle_address: int
    item_address: int = 0
    rawcode: int = 0
    rawcode_address: int = 0
    mirror_rawcode: int = 0
    mirror_rawcode_address: int = 0
    ability_rawcode: int = 0
    ability_rawcode_address: int = 0
    charges: int = 0
    charges_address: int = 0
    native_slot: bool = False

    @property
    def rawcode_text(self) -> str:
        return format_rawcode(self.rawcode) if self.rawcode else ""


@dataclass(frozen=True)
class AbilityInstance:
    slot: int
    wrapper_address: int
    data_address: int
    wrapper_vtable: int
    data_vtable: int
    wrapper_tag_address: int
    wrapper_tag: int
    handle: int
    class_rawcode: int
    rawcode: int
    rawcode_address: int
    mirror_rawcode_address: int = 0
    data_cache_address: int = 0
    data_cache_pointer: int = 0

    @property
    def class_text(self) -> str:
        return format_rawcode(self.class_rawcode) if self.class_rawcode else ""

    @property
    def rawcode_text(self) -> str:
        return format_rawcode(self.rawcode) if self.rawcode else ""


@dataclass(frozen=True)
class UnitSelectionSummary:
    candidate: UnitCandidate
    refs: int
    known_hits: int
    region_base: int
    hp_text: str
    mp_text: str
    position: tuple[float, float] | None
    components: tuple[str, ...]
    inventory: tuple[str, ...]
    ability_count: int
    hero: bool


def selection_confidence_text(summary: "UnitSelectionSummary") -> str:
    note = summary.candidate.note
    if note.startswith("remembered_identity=") or note.startswith("manual_candidate"):
        return "已验证"
    if note.startswith("selected_handle=") or note.startswith("selected_unit_slot=") or summary.known_hits >= 2:
        return "强"
    if note.startswith("global_unit_scan"):
        return "扫描"
    return "候选"


@dataclass(frozen=True)
class MemoryWriteSpec:
    label: str
    address: int
    value_type: str
    value: int | float | str


@dataclass(frozen=True)
class NativeHandler:
    name: str
    record_address: int
    handler_address: int


@dataclass(frozen=True)
class NativeAbilityInternals:
    find_address: int
    begin_address: int
    add_address: int
    end_address: int
    refresh_address: int
    remove_address: int


@dataclass(frozen=True)
class NativeHelperOpResult:
    kind: int
    result: int
    last_error: int = 0
    arg0: int = 0
    arg1: int = 0
    extra_results: tuple[int, ...] = ()


@dataclass(frozen=True)
class PersistentNativeUnitSnapshot:
    handle: int
    unit_address: int
    owner: int
    owner_id: int
    type_id: int
    hp: float
    hp_max: float
    mp: float
    mp_max: float
    x: float
    y: float
    move_speed: float
    hero_level: int
    hero_xp: int
    strength: int
    agility: int
    intelligence: int
    item_ids: tuple[int, ...]
    item_charges: tuple[int, ...]
    item_handles: tuple[int, ...]
    item_addresses: tuple[int, ...]
    ability_ids: tuple[int, ...]
    ability_levels: tuple[int, ...]
    full_handle: int = 0
    owner_address: int = 0

    base_strength: int = 0
    base_agility: int = 0
    base_intelligence: int = 0
    item_full_handles: tuple[int, ...] = (0,) * 6
    hp_property: int = 0
    mp_property: int = 0
    hp_regen: float | None = None
    mp_regen: float | None = None
    component_mask: int = 0


@dataclass(frozen=True)
class SelectedAbilityFieldContext:
    candidate: UnitCandidate
    unit_handle: int
    ability_handle: int
    ability_rawcode: int
    effect_class: int
    effect_class_verified: bool
    effect_class_note: str
    current_level: int
    handlers: dict[str, NativeHandler]
    ability_identity: tuple[int, int, int] = (0, 0, 0)

    @property
    def unit_identity(self) -> tuple[int, int, int]:
        return (
            self.candidate.handle,
            self.candidate.owner_address,
            self.candidate.unit_address,
        )


@dataclass(frozen=True)
class AbilityFieldValue:
    spec: AbilityFieldSpec
    value: bool | int | float | None
    status: str
    note: str = ""

    def value_text(self) -> str:
        if self.value is None:
            return ""
        if self.spec.value_kind == "boolean":
            return "true" if bool(self.value) else "false"
        if self.spec.value_kind == "real":
            return format_editable_float32(float(self.value))
        return str(int(self.value))


@dataclass(frozen=True)
class AbilityFieldSnapshot:
    ability_rawcode: int
    effect_class: int
    current_level: int
    requested_level: int
    fields: tuple[AbilityFieldValue, ...]
    unit_identity: tuple[int, int, int] = (0, 0, 0)
    effect_class_verified: bool = True
    effect_class_note: str = ""
    win10_compat: bool = False
    ability_identity: tuple[int, int, int] = (0, 0, 0)


@dataclass(frozen=True)
class ItemFieldContext:
    candidate: UnitCandidate
    slot: int
    item_handle: int
    item_rawcode: int
    handlers: dict[str, NativeHandler]
    item_identity: tuple[int, int, int] = (0, 0, 0)

    @property
    def unit_identity(self) -> tuple[int, int, int]:
        return (
            self.candidate.handle,
            self.candidate.owner_address,
            self.candidate.unit_address,
        )


@dataclass(frozen=True)
class ItemFieldValue:
    spec: ItemFieldSpec
    value: bool | int | float | None
    status: str
    note: str = ""

    def value_text(self) -> str:
        if self.value is None:
            return ""
        if self.spec.value_kind == "boolean":
            return "true" if bool(self.value) else "false"
        if self.spec.value_kind == "real":
            return format_editable_float32(float(self.value))
        return str(int(self.value))


@dataclass(frozen=True)
class ItemFieldSnapshot:
    slot: int
    item_handle: int
    item_rawcode: int
    fields: tuple[ItemFieldValue, ...]
    unit_identity: tuple[int, int, int] = (0, 0, 0)
    win10_compat: bool = False
    item_identity: tuple[int, int, int] = (0, 0, 0)


@dataclass(frozen=True)
class JassSelectionProbeResult:
    unit_handle: int
    handle_id: int
    player_handle: int
    candidate: UnitCandidate | None
    note: str


@dataclass(frozen=True)
class NativeSelectionProbeResult:
    selection_manager_offset: int
    primary_list_offset: int
    alternate_list_offset: int
    is_unit_selected_handler: int
    group_enum_selected_handler: int
    candidate: UnitCandidate | None
    note: str


def format_rawcode(raw: int) -> str:
    raw &= 0xFFFFFFFF
    data = struct.pack(">I", raw)
    if all(32 <= byte < 127 for byte in data):
        return data.decode("ascii")
    return f"0x{raw:08x}"


def format_editable_float32(value: float) -> str:
    numeric = float(value)
    if not math.isfinite(numeric):
        return str(numeric)
    text = format(numeric, ".9g")
    if "e" in text.lower():
        text = format(Decimal(text), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in {"-0", ""} else text


def parse_integer_number(value: int | float | str) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value) or not value.is_integer():
            raise ValueError("not an integer")
        return int(value)
    text = str(value).strip()
    try:
        return int(text, 0)
    except ValueError:
        try:
            numeric = Decimal(text)
        except InvalidOperation as exc:
            raise ValueError("not an integer") from exc
        if not numeric.is_finite() or numeric != numeric.to_integral_value():
            raise ValueError("not an integer")
        return int(numeric)


def coerce_finite_float32(value: int | float | str) -> float:
    try:
        numeric = float(str(value).strip()) if isinstance(value, str) else float(value)
        stored = struct.unpack("<f", struct.pack("<f", numeric))[0]
    except (OverflowError, TypeError, ValueError, struct.error) as exc:
        raise ValueError("数值必须是有限且可写入的 float32") from exc
    if not math.isfinite(numeric) or not math.isfinite(stored):
        raise ValueError("数值必须是有限且可写入的 float32")
    return stored


def close_float(a: float, b: float, tolerance: float = 0.01) -> bool:
    return math.isfinite(a) and abs(a - b) <= tolerance


def parse_int(text: str, name: str) -> int:
    try:
        return parse_integer_number(text)
    except ValueError as exc:
        raise ValueError(f"{name} 必须是整数") from exc


def parse_float(text: str, name: str) -> float:
    try:
        return coerce_finite_float32(text)
    except ValueError as exc:
        raise ValueError(f"{name} 必须是数字") from exc


def parse_changed_coordinate(target_text: str, current_text: str, name: str) -> float | None:
    """Return a coordinate only when the editable target differs from its readback."""
    target_text = target_text.strip()
    if not target_text:
        return None
    target = parse_float(target_text, name)
    current_text = current_text.strip()
    if current_text:
        current = parse_float(current_text, f"当前{name}")
        if math.isclose(target, current, rel_tol=0.0, abs_tol=0.0005):
            return None
    return target


def parse_unit_identity(text: str) -> tuple[int, int, int]:
    raw_parts = [part.strip() for part in text.replace(";", ",").split(",") if part.strip()]
    values: dict[str, int] = {}
    positional: list[int] = []
    for part in raw_parts:
        if "=" in part:
            key, value = part.split("=", 1)
            key = key.strip().lower()
            if key in {"h", "handle"}:
                key = "handle"
            elif key in {"o", "owner"}:
                key = "owner"
            elif key in {"u", "unit"}:
                key = "unit"
            else:
                raise ValueError(f"未知单位身份字段：{key}")
            values[key] = int(value.strip(), 0)
        else:
            positional.append(int(part, 0))
    if positional:
        if len(positional) != 3:
            raise ValueError("--unit-identity 位置格式应为 HANDLE,OWNER,UNIT")
        values.setdefault("handle", positional[0])
        values.setdefault("owner", positional[1])
        values.setdefault("unit", positional[2])
    missing = [key for key in ("handle", "owner", "unit") if key not in values]
    if missing:
        raise ValueError("--unit-identity 缺少：" + ",".join(missing))
    return values["handle"], values["owner"], values["unit"]
