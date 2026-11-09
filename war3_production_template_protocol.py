"""Building-bound production-template ABI for current Warcraft III engine.

The bridge never edits object definitions globally.  A binding stores one concrete
building handle and watches for newly-created matching unit instances near that
building; only those instances receive the captured runtime field template.
"""
from __future__ import annotations
import math, struct
from war3_selection_protocol import SIGNATURES as SELECTION_SIGNATURES, build_work as build_selection, validate_work as validate_selection

ACTION_BIND = 1
ACTION_SCAN = 2
ACTION_APPLY = 3
ACTION_REMOVE_STOCK = 4
MAX_FIELDS = 32
MAX_ABILITIES = 16
MAX_TARGETS = 32
MAX_SCAN_ROWS = 128

# Selection is needed only for BIND/REMOVE_STOCK, but its handlers are always
# supplied to keep the work ABI fixed and easy to validate.
EXTRA_SIGNATURES = (
    ("AddUnitToStock", "(Hunit;III)V"),
    ("RemoveUnitFromStock", "(Hunit;I)V"),
    ("GetOwningPlayer", "(Hunit;)Hplayer;"),
    ("CreateGroup", "()Hgroup;"),
    ("GroupEnumUnitsOfPlayer", "(Hgroup;Hplayer;Hboolexpr;)V"),
    ("FirstOfGroup", "(Hgroup;)Hunit;"),
    ("GroupRemoveUnit", "(Hgroup;Hunit;)B"),
    ("DestroyGroup", "(Hgroup;)V"),
    ("GetUnitTypeId", "(Hunit;)I"),
    ("GetUnitX", "(Hunit;)R"),
    ("GetUnitY", "(Hunit;)R"),
    ("UnitAddAbility", "(Hunit;I)B"),
    ("SetUnitAbilityLevel", "(Hunit;II)I"),
)
FIELD_SIGNATURES = tuple(
    (f"Blz{verb}Unit{weapon}{kind}Field",
     f"(Hunit;Hunit{weapon.lower()}{kind.lower()}field;" + ("I" if weapon else "") + (value if verb == "Set" else "") + ")" + ("B" if verb == "Set" else value))
    for verb in ("Get", "Set") for weapon in ("", "Weapon") for kind, value in (("Boolean", "B"), ("Integer", "I"), ("Real", "R"))
)
SIGNATURES = tuple(dict.fromkeys(SELECTION_SIGNATURES + EXTRA_SIGNATURES + FIELD_SIGNATURES))

# Layout mirrors tools/war3_bridge_production_template.h.
HEADER = 480
HANDLERS = len(EXTRA_SIGNATURES) + len(FIELD_SIGNATURES)
POINTER_BYTES = (HANDLERS + 1) * 8
META = HEADER + POINTER_BYTES
FIELD_OFFSET = META + 64
ABILITY_OFFSET = FIELD_OFFSET + MAX_FIELDS * 16
TARGET_OFFSET = ABILITY_OFFSET + MAX_ABILITIES * 8
ROW_OFFSET = TARGET_OFFSET + MAX_TARGETS * 8
WORK_SIZE = ROW_OFFSET + MAX_SCAN_ROWS * 8
ABI = struct.pack("<3I", 0x24268120, 216, WORK_SIZE)


def _entry(entries, name, signature):
    entry = entries.get(name)
    if entry is None or entry.name != name or entry.signature != signature:
        raise ValueError("生产模板 native 缺失或签名不符：" + name)
    return entry.handler


def _field(row):
    if type(row) not in (tuple, list) or len(row) != 4 or any(type(x) is not int for x in row):
        raise ValueError("生产模板字段描述无效")
    fid, kind, weapon, bits = row
    if not 0 < fid <= 0xffffffff or kind not in (0, 1, 2) or weapon not in (0, 1, 2) or not 0 <= bits <= 0xffffffff:
        raise ValueError("生产模板字段超出范围")
    if kind == 0 and bits not in (0, 1):
        raise ValueError("生产模板布尔字段无效")
    if kind == 2 and not math.isfinite(struct.unpack("<f", struct.pack("<I", bits))[0]):
        raise ValueError("生产模板实数字段无效")
    return tuple(row)


def build_work(entries, tls, *, action, unit_rawcode, building_handle=0, building_rawcode=0,
               radius_bits=0, stock_current=1, stock_max=99, fields=(), abilities=(), targets=()):
    if action not in (ACTION_BIND, ACTION_SCAN, ACTION_APPLY, ACTION_REMOVE_STOCK):
        raise ValueError("生产模板动作无效")
    if type(unit_rawcode) is not int or not 0 < unit_rawcode <= 0xffffffff:
        raise ValueError("生产模板单位 ID 无效")
    fields = tuple(_field(x) for x in fields)
    abilities = tuple((int(code), int(level)) for code, level in abilities)
    targets = tuple(int(x) for x in targets)
    if len(fields) > MAX_FIELDS or len(abilities) > MAX_ABILITIES or len(targets) > MAX_TARGETS:
        raise ValueError("生产模板条目过多")
    if any(not 0 < code <= 0xffffffff or not 1 <= level <= 100000 for code, level in abilities):
        raise ValueError("生产模板技能无效")
    if any(not 0 < x < 0x8000000000000000 for x in targets):
        raise ValueError("生产模板目标句柄无效")
    if action in (ACTION_SCAN, ACTION_APPLY) and (not building_handle or not building_rawcode):
        raise ValueError("生产模板缺少建筑绑定")
    if action == ACTION_APPLY and not targets:
        raise ValueError("生产模板没有新单位目标")
    if action == ACTION_BIND and (stock_current < 0 or stock_max < 0 or stock_current > 0xffffffff or stock_max > 0xffffffff):
        raise ValueError("生产库存参数无效")

    payload = bytearray(build_selection(entries))
    pointers = [_entry(entries, n, s) for n, s in EXTRA_SIGNATURES + FIELD_SIGNATURES]
    payload.extend(struct.pack(f"<{len(pointers)+1}Q", *pointers, tls))
    payload.extend(struct.pack("<4Q8I", building_handle, 0, 0, 0,
        unit_rawcode, building_rawcode, action, radius_bits, stock_current, stock_max,
        len(fields), len(abilities)))
    for row in fields:
        payload.extend(struct.pack("<4I", *row))
    payload.extend(bytes(ABILITY_OFFSET - len(payload)))
    for code, level in abilities:
        payload.extend(struct.pack("<2I", code, level))
    payload.extend(bytes(TARGET_OFFSET - len(payload)))
    for handle in targets:
        payload.extend(struct.pack("<Q", handle))
    payload.extend(bytes(WORK_SIZE - len(payload)))
    validate_work(bytes(payload))
    return bytes(payload)


def validate_work(payload):
    if len(payload) != WORK_SIZE:
        raise ValueError("生产模板协议长度不符")
    validate_selection(payload[:480])
    pointers = struct.unpack_from(f"<{HANDLERS+1}Q", payload, HEADER)
    if any(not 0x10000 <= p < 0x800000000000 for p in pointers[:-1]):
        raise ValueError("生产模板 native 指针无效")
    if not 0x10000 <= pointers[-1] < 0x800000000000 or pointers[-1] % 8:
        raise ValueError("生产模板线程上下文无效")
    building, owner, group, _reserved_q, rawcode, building_rawcode, action, radius_bits, current, maximum, field_count, ability_count = struct.unpack_from("<4Q8I", payload, META)
    if action not in (ACTION_BIND, ACTION_SCAN, ACTION_APPLY, ACTION_REMOVE_STOCK) or not rawcode:
        raise ValueError("生产模板请求头无效")
    if field_count > MAX_FIELDS or ability_count > MAX_ABILITIES:
        raise ValueError("生产模板数量无效")
    if owner or group or _reserved_q:
        raise ValueError("生产模板输出区必须清零")
    for i in range(field_count):
        _field(struct.unpack_from("<4I", payload, FIELD_OFFSET + i*16))
    if any(payload[FIELD_OFFSET + field_count*16:ABILITY_OFFSET]):
        raise ValueError("生产模板字段尾部必须清零")
    for i in range(ability_count):
        code, level = struct.unpack_from("<2I", payload, ABILITY_OFFSET + i*8)
        if not code or not level:
            raise ValueError("生产模板技能无效")


def decode_work(payload, expected_count):
    if len(payload) != WORK_SIZE:
        raise ValueError("生产模板返回长度不符")
    building, owner, group, result_q, rawcode, building_rawcode, action, radius_bits, current, maximum, field_count, ability_count = struct.unpack_from("<4Q8I", payload, META)
    # result_q packs: low32 error, high32 count/changed depending on action.
    error = result_q & 0xffffffff
    count = (result_q >> 32) & 0xffffffff
    if error:
        messages = {1:"需要只选中一座建筑",2:"建筑身份已变化",3:"创建临时单位组失败",4:"扫描单位过多",5:"目标单位身份已变化",6:"字段写入被游戏拒绝",7:"字段读回不一致",8:"技能添加或等级设置失败",10:"当前选中的不是建筑"}
        raise ValueError("生产模板：" + messages.get(error, f"操作失败（{error}）"))
    rows = [struct.unpack_from("<Q", payload, ROW_OFFSET + i*8)[0] for i in range(min(count, MAX_SCAN_ROWS))]
    return dict(action=action, building=building, building_rawcode=building_rawcode,
                owner=owner, unit_rawcode=rawcode, count=count, rows=rows,
                fields=field_count, abilities=ability_count, stock_current=current, stock_max=maximum)
