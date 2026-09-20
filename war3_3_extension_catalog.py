"""Shipped Warcraft III 3.0.0.24268 talent controllers and tier choices."""

TALENT_CONTROLLERS = {
    "AThg": ("人类加雷克", (("GT3a", "GT3b", "GT3c"), ("GT1a", "GT1b", "GT1c"),
                            ("GT2a", "GT2b", "GT2c"), ("GT4a", "GT4b", "GT4c"))),
    "AThl": ("人类兰登", (("LT1a", "LT1b", "LT1c"), ("LT2a", "LT2b", "LT2c"),
                            ("LT3a", "LT3b", "LT3c"), ("LT4a", "LT4b", "LT4c"))),
    "AThi": ("人类伊拉斯塔", (("IT1a", "IT1b", "IT1c"), ("IT2a", "IT2b", "IT2c"),
                              ("IT3a", "IT3b", "IT3c"), ("IT4a", "IT4b", "IT4c"))),
    "ATug": ("亡灵加雷克", (("UT1a", "UT1b", "UT1c"), ("UT2a", "UT2b", "UT2c"),
                            ("UT5a", "UT5b", "UT6a"), ("UT3a", "UT3b", "UT3c"),
                            ("UT4a", "UT4b", "UT4c"), ("UT5c", "UT6b", "UT6c"))),
    "ATua": ("亡灵安雅", (("AT1a", "AT1b", "AT1c"), ("AT2a", "AT2b", "AT2c"),
                           ("AT5a", "AT5b", "AT5c"), ("AT3a", "AT3b", "AT3c"),
                           ("AT4a", "AT4b", "AT4c"), ("AT6a", "AT6b", "AT6c"))),
    "ATul": ("亡灵列奥尼德", (("BT1a", "BT1b", "BT1c"), ("BT2a", "BT2b", "BT2c"),
                              ("BT5a", "BT5b", "BT5c"), ("BT3a", "BT3b", "BT3c"),
                              ("BT4a", "BT4b", "BT4c"), ("BT6a", "BT6b", "BT6c"))),
}

TALENT_PROBE_RAWCODES = tuple(
    dict.fromkeys(
        rawcode
        for controller, (_name, tiers) in TALENT_CONTROLLERS.items()
        for rawcode in (controller, *(choice for tier in tiers for choice in tier))
    )
)

EQUIPMENT_SLOT_NAMES = (
    "头部", "胸部", "手套", "靴子", "戒指", "戒指 2", "主手", "副手", "饰品",
)

# GetItemEquipmentType returns the public equipmentType enum from common.j.
EQUIPMENT_SLOT_TYPES = (1, 2, 3, 4, 5, 5, 6, 7, 8)
EQUIPMENT_TYPE_NAMES = {
    0: "非装备",
    1: "头部",
    2: "胸部",
    3: "手套",
    4: "靴子",
    5: "戒指",
    6: "主手",
    7: "副手",
    8: "饰品",
    9: "任意槽",
}

# Official 3.0 framework items. Adding one is the engine-supported way to
# attach the expanded inventory/equipment UI to an older campaign hero.
OFFICIAL_FRAMEWORK_ITEMS = {
    "ebhg": ("人类加雷克背包", "AThg"),
    "ebhl": ("人类兰登背包", "AThl"),
    "ebhi": ("人类伊拉斯塔背包", "AThi"),
    "ebug": ("亡灵加雷克背包", "ATug"),
    "ebua": ("亡灵安雅背包", "ATua"),
    "ebul": ("亡灵列奥尼德背包", "ATul"),
}

# Cross-map fallback. These are stock, globally loaded item-passive abilities;
# none references a campaign trigger or a named hero ability. The trainer owns
# point accounting while the selected effects remain real unit abilities.
GENERIC_TALENT_TIERS = (
    (("AIs1", "力量 +1"), ("AIa1", "敏捷 +1"), ("AIi1", "智力 +1")),
    (("AIs2", "力量 +2"), ("AIa2", "敏捷 +2"), ("AIi2", "智力 +2")),
    (("AIs3", "力量 +3"), ("AIa3", "敏捷 +3"), ("AIi3", "智力 +3")),
    (("AIlf", "生命上限 +150"), ("AImb", "魔法上限 +100"), ("AId1", "护甲 +1")),
    (("AIat", "攻击力 +3"), ("AIms", "移动速度 +60"), ("AIsx", "攻击速度 +18%")),
    (("AIs6", "力量 +6"), ("AIa6", "敏捷 +6"), ("AIi6", "智力 +6")),
)

GENERIC_TALENT_RAWCODES = tuple(
    rawcode for tier in GENERIC_TALENT_TIERS for rawcode, _label in tier
)
