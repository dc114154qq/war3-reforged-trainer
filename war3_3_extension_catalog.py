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

# Official 3.0 campaign backpack items. Each item supplies the expanded
# inventory/equipment abilities and exactly one stock ATal controller.
OFFICIAL_BACKPACKS = {
    "ebhg": ("人类加雷克", "AThg"),
    "ebhl": ("人类兰登", "AThl"),
    "ebhi": ("人类伊拉斯塔", "AThi"),
    "ebug": ("亡灵加雷克", "ATug"),
    "ebua": ("亡灵安雅", "ATua"),
    "ebul": ("亡灵列奥尼德", "ATul"),
}
