from __future__ import annotations

from dataclasses import dataclass


def rawcode_to_int(rawcode: str) -> int:
    return int.from_bytes(rawcode.encode("ascii"), "big")


@dataclass(frozen=True)
class ItemFieldSpec:
    rawcode: str
    value_kind: str
    name: str
    writable: bool = True
    runtime_supported: bool = True

    @property
    def field_id(self) -> int:
        return rawcode_to_int(self.rawcode)


ITEM_FIELD_CATALOG = (
    ItemFieldSpec("ilev", "integer", "等级"),
    ItemFieldSpec("iuse", "integer", "使用次数 / 数量"),
    ItemFieldSpec("icid", "integer", "冷却组"),
    ItemFieldSpec("ihtp", "integer", "最大生命值"),
    ItemFieldSpec("ihpc", "integer", "当前生命值"),
    ItemFieldSpec("ipri", "integer", "优先级"),
    ItemFieldSpec("iarm", "integer", "护甲类型"),
    ItemFieldSpec("iclr", "integer", "着色颜色 - 红"),
    ItemFieldSpec("iclg", "integer", "着色颜色 - 绿"),
    ItemFieldSpec("iclb", "integer", "着色颜色 - 蓝"),
    ItemFieldSpec("ical", "integer", "着色颜色 - 透明度"),
    ItemFieldSpec("isca", "real", "缩放值"),
    ItemFieldSpec("idrp", "boolean", "携带者死亡时掉落"),
    ItemFieldSpec("idro", "boolean", "可以丢弃"),
    ItemFieldSpec("iper", "boolean", "可消耗"),
    ItemFieldSpec("iprn", "boolean", "包含在随机选择中"),
    ItemFieldSpec("ipow", "boolean", "获得时自动使用"),
    ItemFieldSpec("ipaw", "boolean", "可出售给商店"),
    ItemFieldSpec("iusa", "boolean", "主动使用"),
    ItemFieldSpec("ifil", "string", "使用的模型", False, False),
)

ITEM_FIELD_BY_KEY = {
    (field.rawcode, field.value_kind): field
    for field in ITEM_FIELD_CATALOG
}
