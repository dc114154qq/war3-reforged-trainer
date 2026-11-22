"""Player-facing descriptions of recorded Warcraft operation status codes."""

# A status code only has meaning inside its operation. Groups describe the
# same observed check, including codes which can have several internal causes.
_REQUEST = ('修改器没能准备好这项操作所需的游戏接口或参数。', 'The trainer could not prepare the game interface or parameters for this operation.')
_SELECTION = ('没有读到完整的选中单位列表。请回到地图中重新选中目标，再读取一次。', 'The selection could not be read in full. Return to the map, reselect the targets, and read the selection again.')
_TARGET = ('执行时没能在当前选择中找到唯一对应的单位。请重新选中目标，再读取一次。', 'The intended unit could not be uniquely matched in the current selection. Reselect it and read the selection again.')
_IDENTITY = ('读取后目标单位发生变化，修改器停在了这一步。请重新读取目标。', 'The target unit changed after it was read. Refresh the target before trying again.')
_BAG_READ = ('未能完整读取扩展背包或装备栏。请先重新读取扩展状态。', 'The extended backpack or equipment slots could not be read in full. Refresh extension status first.')
_BAG_CHANGED = ('物品已不在原来的背包位置，或无法确认只有这一件对应物品。请重新读取扩展状态。', 'The item moved from its original bag position or could not be matched uniquely. Refresh extension status.')
_CLASSIC_READ = ('未能完整读取普通物品栏。请重新选中单位并读取一次。', 'The classic inventory could not be read in full. Reselect the unit and read it again.')
_CREATE_ITEM = ('游戏没有返回符合所填物品代码的新物品。请核对代码是否在这张地图中可用。', 'The game did not return a new item matching the requested code. Check whether that code is available on this map.')
_FIELD = ('这项字段或等级未通过检查。请重新读取字段列表，再选择字段和等级。', 'The field or level failed validation. Reload the field list and select the field and level again.')
_REJECT_FIELD = ('游戏拒绝写入所选字段。', 'The game rejected the selected field write.')
_READBACK_FIELD = ('写入后读到的字段值与填写的目标值不同。请重新读取确认当前值。', 'The field value read after writing differs from the requested value. Read the field again to check its current value.')
_COORDINATES = ('没有读到可用的游戏坐标。请把鼠标移到地图画面内，再试一次。', 'No usable game coordinates were read. Move the mouse over the map and try again.')
_CAST = ('游戏拒绝执行这次施法指令。', 'The game rejected this cast order.')
_READ_HERO = ('所选单位中没有可处理的英雄。请选中至少一个英雄后再试。', 'There is no eligible hero in the selection. Select at least one hero and try again.')
_CAST_SETUP = ('没能读到这次施法所需的技能或游戏接口。请重新选中英雄，读取当前单位后再试。', 'The required ability or game interface was unavailable. Reselect and reload the hero before trying again.')
_CAST_CLEANUP = ('施法结束后没能核对临时技能或范围已恢复。请先读取英雄当前状态。', 'Temporary abilities or range could not be verified as restored after casting. Read the hero’s current state first.')

_GROUPS = {
    'extension': (
        ((220,), _REQUEST), ((221,), _SELECTION),
        ((223,), ('游戏没有把指定物品创建到英雄身上。请核对物品代码和物品栏状态。', 'The game did not create the requested item on the hero. Check the item code and inventory state.')),
        ((241,), ('指定的背包格已经没有物品。请重新读取扩展状态。', 'The selected backpack slot is now empty. Refresh extension status.')),
        ((224,), ('要卸下的装备已不在原装备位。请刷新装备栏。', 'The equipment to unequip is no longer in its original slot. Refresh equipment.')),
        ((225,), ('游戏执行卸下后返回了别的物品，或原装备仍在原位。请刷新背包和装备栏核对。', 'Unequipping returned a different item or left the original item equipped. Refresh the bag and equipment to check.')),
        ((232,), ('当前英雄的背包容量未通过检查。请先读取扩展状态，确认是否已有可用背包。', 'Backpack capacity failed validation. Refresh extension status and check that the hero has a usable backpack.')),
        ((226, 244, 258, 261, 264, 279), _BAG_READ),
        ((227, 230), ('待操作物品已经失效，或物品实际代码与请求不符。请重新读取物品。', 'The item is no longer valid or its code differs from the requested code. Reload the item.')),
        ((228,), ('游戏拒绝把这件物品交给当前英雄。请检查英雄能否携带该物品。', 'The game refused to give the item to the current hero. Check whether the hero can carry it.')),
        ((229, 234, 242), ('操作中没能在背包或装备栏找到唯一对应的物品。请刷新扩展状态核对位置。', 'The item could not be uniquely located in the backpack or equipment. Refresh extension status to check its location.')),
        ((231, 245), ('没有在装备栏读到预期结果。请刷新装备栏，确认物品当前的位置。', 'The equipment readback did not match the expected result. Refresh equipment to check the item’s current location.')),
        ((233,), ('扩展背包没有可用空格。请确认背包已开通，并腾出一格再卸下装备。', 'The extended backpack has no free slot. Verify that the bag is available and free a slot before unequipping.')),
        ((235, 237, 275, 259), _BAG_CHANGED),
        ((238, 250, 273, 274, 282, 283, 289, 290), _REQUEST),
        ((239, 243), ('操作后物品仍留在扩展背包里。请刷新背包后核对。', 'The item was still in the extended backpack after the operation. Refresh the bag to check its state.')),
        ((240,), ('背包里没有读到该物品和填写的使用次数同时匹配。请刷新背包确认当前次数。', 'The item and requested charges could not both be matched in the bag. Refresh the backpack to check the current charges.')),
        ((248,), ('修改装备类型后，游戏没有按指定类型识别这件物品。请刷新物品状态。', 'The game did not recognize the requested equipment type after the change. Refresh the item state.')),
        ((254,), ('游戏返回的天赋控制器与所选英雄不对应。请重新读取天赋。', 'The talent controller returned by the game does not belong to the selected hero. Reload talents.')),
        ((255,), ('修改器没有找到当前天赋对应的游戏处理记录。请重新读取天赋选项。', 'The trainer could not find the game record for this talent. Reload the talent choices.')),
        ((257,), ('游戏处理天赋选项后，没有读到预期的天赋记录。请重新读取天赋，核对当前状态。', 'The expected talent record was missing after the game processed the choice. Reload talents to check the current state.')),
        ((260, 263, 267), ('物品的装备类型未能写入或恢复到预期值。请刷新物品状态后核对。', 'The item’s equipment type could not be set or restored to the expected value. Refresh the item to check its state.')),
        ((262,), ('撤回装备时，游戏返回了与本次操作不一致的物品。请刷新装备栏。', 'The game returned a different item while undoing the equip attempt. Refresh equipment.')),
        ((265, 266), ('尝试恢复后，背包或装备位置与操作前不同。请刷新扩展状态，查看当前物品位置。', 'After the restore attempt, bag or equipment slots differ from their original state. Refresh extension status to check current item locations.')),
        ((268, 269, 270, 271, 272, 2761, 2762, 2763, 2765, 2767, 277), ('未能核对这件物品及其装备技能。请重新读取背包，再选择物品。', 'The item or its equipment ability could not be verified. Refresh the bag and select the item again.')),
        ((278, 285), ('游戏拒绝把这件物品装入装备栏。请检查目标部位和任意槽状态。', 'The game refused to equip this item. Check the target slot and the any-slot setting.')),
        ((280, 286, 287), ('装备后没有在预期部位读到这件物品。请刷新装备栏查看它实际所在的位置。', 'The item was not found in the expected equipment slot. Refresh equipment to check where it actually landed.')),
        ((281,), ('本次指定部位装备未完成，修改器尝试恢复原来的物品位置。请刷新扩展状态核对。', 'Equipping in the requested slot did not complete. The trainer attempted to restore the original item positions. Refresh extension status to verify them.')),
    ),
    'unit_field': (
        ((910,), _REQUEST), ((911,), _FIELD), ((912,), _SELECTION),
        ((913,), _IDENTITY), ((914,), _TARGET),
        ((915,), ('目标数值或游戏返回的原值不是可用的有限数值，未开始写入。', 'The requested or current value was not a usable finite number. The write did not start.')),
        ((916,), ('游戏拒绝修改这个单位字段，核对后仍是原值。', 'The game rejected this unit field write, and the original value was verified.')),
        ((917,), ('游戏未保留目标数值，已经核对原值仍在。', 'The game did not keep the requested value. The original value was verified.')),
        ((918,), ('游戏返回的数值和目标不符，也未能确认原值已恢复。请重新读取该字段。', 'The value did not match the request and restoration of the original value could not be verified. Read the field again.')),
        ((919,), ('当前单位的武器或单位身份未通过检查，未继续写入。请重新选择并读取单位。', 'The current weapon or unit identity failed validation. No further write was attempted. Reselect and reload the unit.')),
    ),
    'unit_field_hero_int': (
        ((920,), ('目标智力在保留当前加成的情况下无法达到。请提高目标总值，或先检查英雄的智力加成。', 'The requested intelligence cannot be reached while preserving current bonuses. Increase the requested total or check the hero’s bonuses.')),
        ((921,), ('当前选中的是普通单位。只有英雄能修改英雄智力。', 'The selected unit is not a hero. Hero intelligence can only be changed on heroes.')),
    ),
    'ability_definition': (((710,), _REQUEST), ((711,), ('本次查询提交的技能编号或查询记录无效。请核对技能代码后重试。', 'The submitted ability ID or query row was invalid. Check the ability code and try again.'))),
    'ability': (
        ((20,), _REQUEST), ((21,), _SELECTION), ((22,), _IDENTITY), ((32,), _TARGET),
        ((23, 24), ('单位的技能实例与读取到的技能等级或请求编号对不上。请重新读取该单位和技能。', 'The unit’s ability instance does not match the observed level or requested ID. Reload the unit and ability.')),
        ((26, 33), ('游戏没有保留请求的技能等级。请重新读取实际等级，确认它是否在该技能支持的范围内。', 'The game did not retain the requested ability level. Read the live level and check the ability’s supported range.')),
        ((27, 30), ('游戏拒绝移除技能，或移除后仍读到该技能。请重新读取技能列表。', 'The game rejected removing the skill or the skill was still present afterward. Reload abilities.')),
        ((28,), ('临时技能未能按预期移除或恢复。请重新读取单位技能。', 'The temporary ability could not be removed or restored as expected. Reload the unit’s abilities.')),
    ),
    'ability_field': (
        ((90,), _REQUEST), ((91,), _FIELD), ((92,), _SELECTION),
        ((93,), _IDENTITY), ((96,), _TARGET),
        ((94,), ('选中的单位当前没有这项技能，无法修改它的实时字段。请重新读取单位或选择持有该技能的单位。', 'The selected unit does not currently have this skill. Load the unit again or select a unit that has the skill to edit its live fields.')),
        ((95,), ('游戏返回的技能当前等级无效，字段无法继续读取。请刷新技能。', 'The game reported an invalid current skill level. Reload the skill before editing its fields.')),
    ),
    'item_field': (
        ((100,), _REQUEST), ((101,), _FIELD), ((102,), _SELECTION),
        ((103, 104), ('原物品栏或所选格没有读到可修改的物品。请重新选择物品格并读取。', 'The chosen inventory or slot did not contain an item that could be edited. Reselect the slot and read it again.')),
        ((105,), _TARGET),
    ),
    'item_effect': (
        ((470,), _SELECTION),
        ((471, 478), ('物品原来的持有者、槽位或技能在操作中无法重新核对。请重新读取物品字段。', 'The item’s original owner, slot or ability could not be reverified. Reload item fields.')),
        ((472,), ('游戏返回的物品附带技能列表不完整，读不出可用字段。请重新读取物品。', 'The item’s attached ability list was incomplete. Reload the item.')),
        ((473, 474), ('所选附带技能已不在原位置或已变更。请重新读取物品技能列表。', 'The selected attached ability moved or changed. Reload the item’s ability list.')),
        ((475,), _FIELD), ((476,), _REJECT_FIELD), ((477,), _READBACK_FIELD),
        ((479,), ('字段当前值已经与上次读取不同。请重新读取后再修改。', 'The field changed since it was read. Reload it before editing.')),
    ),
    'item_ability': (
        ((440,), _REQUEST), ((441,), _TARGET), ((442,), _CLASSIC_READ),
        ((448, 450, 452), ('安装背包能力时无法核对英雄身份。请重新选择英雄并读取。', 'The hero’s identity could not be verified while attaching the backpack ability. Reselect and reload the hero.')),
        ((449, 451, 453, 454, 456), ('安装背包能力时无法核对物品身份或代码。请重新读取物品栏。', 'The item’s identity or code could not be verified while attaching the backpack ability. Refresh the inventory.')),
        ((455,), ('背包物品已离开原来的普通物品格。请重新读取物品栏。', 'The backpack item is no longer in its original classic slot. Refresh the inventory.')),
    ),
    'item': (
        ((40, 66), _REQUEST), ((41,), _SELECTION), ((67,), _TARGET),
        ((42, 43, 44, 50, 54), _CLASSIC_READ),
        ((45, 51, 55, 56, 59, 65, 68), ('普通物品栏中的原物品、数量或位置发生变化。请重新读取物品栏。', 'An original item, its charges or its slot changed. Refresh the classic inventory.')),
        ((46, 49), ('物品使用次数没有变成填写的数值。请刷新物品栏确认当前值。', 'The item charges did not match the request. Refresh the inventory to check the current value.')),
        ((47, 48, 57, 58, 62), _CREATE_ITEM),
        ((52,), ('游戏创建了物品，但没在普通物品栏中找到它。请查看物品栏及单位脚下。', 'The game created the item but it was not found in the classic inventory. Check the inventory and the ground near the unit.')),
        ((53, 69), ('撤回后未能核对普通物品栏和操作前一致。请刷新检查物品。', 'The classic inventory could not be verified against its original state after the undo attempt. Refresh to check the items.')),
        ((60, 64), ('游戏在复制或创建物品时发生异常。请刷新物品栏确认结果。', 'The game raised an exception while copying or creating the item. Refresh the inventory to check the result.')),
    ),
    'item_catalog': (
        ((87,), _REQUEST),
        ((6,), ('临时测试物品的身份已经失效，游戏未能用原记录找到它。', 'The temporary test item is no longer valid and could not be found using its original record.')),
        ((13, 234, 487, 1059), ('游戏的物品目录结构未通过读取校验，无法完整列出当前地图物品。', 'The game’s item directory failed validation and could not be listed in full.')),
        ((31,), _CREATE_ITEM),
    ),
    'equipment': (
        ((201,), _SELECTION), ((202,), _TARGET), ((203, 204), ('游戏没能创建对应物品，或该物品没有有效的装备部位。请核对物品代码和类型。', 'The item could not be created or had no valid equipment slot. Check its item code and type.')),
        ((205, 206), _BAG_READ),
        ((207, 208), ('新物品未能唯一对应到一个装备部位。请刷新装备栏。', 'The new item could not be matched to one equipment slot. Refresh equipment.')),
        ((209, 210, 213, 214), ('操作时其他装备或普通物品栏发生变化。请刷新查看当前物品。', 'Other equipment or the classic inventory changed during this operation. Refresh to check the current items.')),
        ((211,), ('要卸下的物品已不在装备栏。请重新读取装备栏。', 'The item to unequip is no longer equipped. Refresh the equipment slots.')),
        ((212,), ('卸下后读到的装备部位没有变成预期状态。请刷新装备栏。', 'The slot did not reach the expected state after unequipping. Refresh the equipment slots.')),
    ),
    'item_safety': (
        ((410,), _TARGET), ((412,), _CREATE_ITEM), ((415,), ('读取不到英雄当前位置，未尝试创建物品。', 'The hero’s location could not be read, so item creation was not attempted.')),
        ((413, 416), ('游戏返回的物品装备类型超出了可处理范围。', 'The item’s equipment type returned by the game is outside the supported range.')),
    ),
    'equipment_effect': (
        ((380,), _TARGET), ((382, 391), _BAG_READ),
        ((383,), ('物品的装备类别和读取时不同。请重新读取这一件物品。', 'The equipment classification changed after reading. Reload this item.')),
        ((384,), ('这件物品的附带技能超过单次读取上限，无法完整核对。', 'The item exceeds the per-request ability limit and cannot be fully verified.')),
        ((388,), ('装备过程中，原装备位或目标部位的状态变化。请刷新后检查物品实际所在部位。', 'The source or destination equipment slot changed during the move. Refresh to check where the item is equipped.')),
        ((390,), ('游戏没能完成卸下装备。请查看背包是否有空位，并重新读取装备栏。', 'The game did not finish unequipping the item. Check for space in the bag and refresh equipment.')),
        ((392, 397, 398), ('转入背包前，普通物品栏或原物品位置未通过核对。请重新读取物品栏。', 'The classic inventory or original item position could not be verified before transfer. Refresh the inventory.')),
        ((393,), ('这件物品已经在扩展背包或装备栏中，未继续转入。请重新读取扩展状态。', 'This item is already present in the extended bag or equipment slots. Refresh extension status.')),
        ((394,), ('扩展背包已满，无法移入这件物品。请先腾出一格。', 'The extended backpack is full. Free a slot before moving this item.')),
        ((396,), ('转移后，普通物品栏仍然返回这件物品。请刷新两个物品栏核对位置。', 'The classic inventory still reported the item after the transfer. Refresh both inventories to check its location.')),
        ((400,), ('转移后物品的“允许丢弃”状态与转移前不同。请重新读取该物品。', 'The item’s droppable setting changed during transfer. Reload the item.')),
    ),
    'stat_details': (
        ((260, 265), _REQUEST), ((262,), _SELECTION), ((263,), _TARGET),
        ((261,), ('3.0 属性值超出可填写范围，请输入 -1000000 到 1000000 之间的有效数值。', 'Enter a valid 3.0 stat value from -1000000 to 1000000.')),
        ((264, 270), ('游戏未返回完整的属性总值。请重新读取单位属性核对实际值。', 'The game did not return the full combined stat value. Reload the unit’s stats.')),
        ((272,), ('切换属性计算方式时，游戏拒绝清除原计算方式的数值。请重新读取属性。', 'While changing the stat mode, the game refused to clear the previous mode’s value. Reload the stat.')),
        ((276,), ('可触发暴击的技能或装备超过单次处理上限，无法完整修改。', 'There are too many critical-hit sources to apply this change completely.')),
        ((277,), ('游戏返回了无效的暴击率或暴击倍率。请重新读取属性和装备。', 'The game reported an invalid critical chance or multiplier. Reload stats and equipment.')),
    ),
    'hero': (
        ((10,), _REQUEST), ((11,), _SELECTION), ((12, 14), _IDENTITY), ((13,), _READ_HERO),
        ((15,), ('游戏返回的英雄等级与填写的等级不同。请重新读取英雄等级。', 'The hero level read by the game differs from the requested level. Reload the hero.')),
        ((16,), ('游戏拒绝降低英雄等级。请重新读取当前等级。', 'The game refused to reduce the hero level. Reload its current level.')),
    ),
    'hero_attributes': (
        ((90,), _REQUEST), ((91,), _SELECTION), ((92, 94), _IDENTITY), ((93,), _READ_HERO), ((95,), _READBACK_FIELD),
    ),
    'attack_speed': (
        ((100,), _REQUEST), ((101,), _IDENTITY), ((107,), _SELECTION), ((108, 109), _TARGET),
        ((102,), ('游戏返回的武器间隔或攻速倍率无效，当前无法按攻速计算。请重新读取单位。', 'The attack interval or speed multiplier is invalid. Reload the unit before changing attack speed.')),
        ((103, 104), ('所填攻速或换算后的攻击间隔超出范围。请调整目标攻速。', 'The requested attack speed or resulting attack interval is out of range. Adjust the target speed.')),
        ((105, 106), _READBACK_FIELD),
    ),
    'clone': (
        ((797,), ('复制之前没能确认游戏能识别副本所需的技能和物品。未开始创建副本。', 'The game interfaces could not verify the skills and items required for duplication. No duplicate was created.')),
    ),
    'unit_bindings': (((1,), _IDENTITY), ((2,), _SELECTION)),
    'talent_icon_control': (
        ((1,), _REQUEST),
        ((2,), ('游戏没有接受天赋图标显示组件的初始化，安装未完成。', 'The game did not accept initialization of the talent icon display component. Installation did not complete.')),
        ((3,), ('游戏没有确认天赋图标显示组件已完整卸载。', 'The game did not confirm full removal of the talent icon display component.')),
    ),
    'talent_order': (
        ((285,), _REQUEST), ((286,), _SELECTION), ((287,), _TARGET),
        ((288,), ('这个英雄没有启用本次请求所需的天赋控制器。请先读取天赋状态。', 'This hero does not have the required active talent controller. Reload the talent state first.')),
        ((289,), ('游戏未接受本次天赋选择，或未读到该天赋已经生效。请重新读取天赋确认。', 'The game did not accept the talent choice, or its activation could not be read back. Reload talents to check.')),
    ),
    'talent_probe': (
        ((280,), _REQUEST), ((281,), _SELECTION), ((284,), _TARGET),
        ((282,), ('游戏没有创建符合指定类型的临时测试英雄。','The game did not create a test hero of the requested type.')),
        ((283,), ('临时测试英雄没有成功获得测试背包或天赋控制器。','The test hero did not receive the required backpack or talent controller.')),
    ),
    'equipment_probe': (
        ((501,), _TARGET),
        ((502,), ('游戏没有创建临时测试单位。','The game did not create a temporary test unit.')),
        ((503,), ('测试单位没有成功获得 30 格扩展背包。','The test unit did not receive a 30-slot extended backpack.')),
        ((504, 505), ('游戏未返回可核对的测试单位、普通物品栏或装备栏。','The test unit or its inventory/equipment could not be verified.')),
        ((506, 507), ('测试物品没进入预期格子，或物品代码未通过核对。','The test item was missing from its expected slot or its code did not match.')),
        ((508,), ('测试物品没有成功转入扩展背包。','The test item could not be transferred to the extended backpack.')),
        ((509,), ('测试物品没有成功穿到预期部位。','The test item could not be equipped in the expected slot.')),
        ((510,), ('测试物品卸下后的槽位或装备类别与预期不同。','The test item had an unexpected slot or equipment type after unequipping.')),
        ((511,), ('测试物品丢弃后仍保留在物品栏，或没有找到对应物品。','The discarded test item remained in inventory or could not be matched.')),
        ((512,), ('拾取测试物品后没有在预期物品格读到它。','The test item did not appear in the expected slot after pickup.')),
        ((513,), ('测试物品的背包状态修复没有通过读回。','The repaired test item failed backpack readback.')),
    ),
    'cooldown_probe': (
        ((1,), _REQUEST), ((2,), _SELECTION), ((3,), _TARGET), ((5,), _CAST_SETUP),
        ((10,), ('用于测试的技能已存在于目标身上。为保留原冷却，本次测试未开始。','The test ability already exists on the target. The test stopped before changing its original cooldown.')),
    ),
    'direct_cast': (
        ((50,), ('这次技能的施法方式与当前操作不匹配，游戏没有发出施法指令。', 'The selected casting mode is unsupported for this action. No cast order was issued.')),
        ((340,), _REQUEST), ((341,), _SELECTION), ((342,), ('找不到本次施法用的英雄。请重新选择可施法的英雄。', 'No casting hero was found. Reselect a hero that can cast.')),
        ((343, 345, 346, 347, 351), ('施法前没能核对英雄或临时技能的状态，未完成施法。请重新选中英雄。', 'The hero or temporary skill could not be verified before casting. Reselect the hero.')),
        ((348,), ('施法范围超出了可用范围，请检查填写的数值。', 'The cast radius is outside the supported range. Check the entered value.')),
        ((349,), ('游戏没有保留本次施法需要的临时范围数值，未继续施法。', 'The game did not retain the temporary cast radius. Casting stopped.')),
        ((350,), _COORDINATES),
        ((357, 358), ('施法前没能读到有效的当前冷却状态，未继续施法。', 'A valid current cooldown could not be read before casting. Casting stopped.')),
    ),
    'game_speed': (
        ((360,), _REQUEST),
        ((361,), ('游戏返回了修改器无法识别的速度档位。', 'The game reported a speed setting that the trainer does not recognize.')),
        ((362,), ('游戏没有切换到要求的速度档位。请重新读取游戏速度。', 'The game did not switch to the requested speed setting. Reload the current game speed.')),
        ((363,), ('当前游戏的速度锁没有解除，修改器未继续切换档位。', 'The game’s speed lock did not release. The trainer did not continue switching speeds.')),
        ((364,), ('速度操作结束后，没能核对游戏速度锁恢复到了原状态。', 'The original speed-lock state could not be verified afterward.')),
        ((365,), ('目标速度没有生效，也未确认原档位已恢复。请重新读取游戏速度。', 'The requested speed did not take effect and the old setting could not be verified. Reload the current game speed.')),
    ),
    'unit_stats': (
        ((251, 254), _REQUEST), ((255,), _SELECTION), ((256,), _IDENTITY), ((265,), _TARGET),
        ((252,), ('护甲必须填写有效的有限数值。', 'Armor must be a valid finite number.')),
        ((253,), ('所填护甲类型超出游戏支持的范围。请从列表中重新选择。', 'The armor type is out of range. Choose one from the list.')),
        ((257, 258), ('游戏返回的护甲、护甲类型或智力原值异常。请重新读取单位。', 'The game reported an invalid existing armor, armor type, or intelligence value. Reload the unit.')),
        ((259,), ('当前不是英雄，无法修改英雄智力。', 'The selected unit is not a hero and has no hero intelligence to modify.')),
        ((260,), _REJECT_FIELD),
        ((261, 262), ('在保留当前加成时，基础智力无法设置到目标总值所需的范围。请调整目标数值。', 'The base intelligence needed for the requested total is outside the valid range when keeping current bonuses. Adjust the requested value.')),
        ((263, 264), _READBACK_FIELD),
    ),
    'gold_mine': (
        ((480,), _REQUEST), ((486,), _SELECTION),
        ((481, 488), ('本次要读取的金矿或单位超过单次处理上限。可以选中一部分金矿再处理。', 'The map exceeds the per-request mine or unit limit. Select a smaller group of mines and try again.')),
        ((482,), ('游戏返回的剩余金矿金额无效。', 'The game returned an invalid remaining gold amount.')),
        ((483, 484), ('金矿的身份、归属或剩余金额在修改前已变化。请重新读取。', 'The mine’s identity, owner or gold amount changed before the write. Read it again.')),
        ((485,), ('金矿剩余金币没有变成目标值。请重新读取金矿确认。', 'The remaining gold did not match the requested amount. Read the mine again to verify it.')),
        ((487, 489), ('没能完整遍历地图中的单位。可以改为选中金矿再读取。', 'Map-wide unit enumeration did not complete. Try selecting the mines and reading the selection.')),
    ),
    'unit_action': (
        ((60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 77), _REQUEST),
        ((71,), _SELECTION), ((72,), _IDENTITY), ((79,), _COORDINATES),
        ((73,), ('游戏未切换到要求的无敌状态。请重新读取单位。', 'The requested invulnerability state did not take effect. Reload the unit.')),
        ((74,), ('游戏未切换到要求的暂停状态。请重新读取单位。', 'The requested pause state did not take effect. Reload the unit.')),
        ((75,), ('移动后游戏返回了无效的单位位置。请重新读取单位位置。', 'The game returned an invalid unit position after moving it. Reload the unit’s position.')),
        ((76,), ('游戏未把单位转给预期玩家。请重新读取单位归属。', 'The game did not assign the unit to the intended player. Reload its owner.')),
        ((78,), ('游戏拒绝修改英雄的剩余技能点。请重新读取英雄确认当前点数。', 'The game rejected the hero’s skill-point change. Reload the hero to check the current points.')),
    ),
    'bulk': (
        ((140,), _REQUEST),
        ((141, 142, 143), ('批量处理时没能完整取得指定范围内的单位列表。请刷新后核对已处理的单位。', 'The unit list for the requested range could not be fully processed. Refresh to check which units were affected.')),
        ((144,), ('这次批量操作没有读到已完成的目标。请检查地图中是否有符合条件的单位。', 'No completed targets were reported. Check whether the map has units that meet the operation’s requirements.')),
    ),
    'mouse': (((100,), _REQUEST), ((101, 102), _COORDINATES)),
    'screen_mouse': (((100,), _REQUEST),),
    'camera': (((100,), _REQUEST),),
    'map_bounds': (
        ((100,), _REQUEST),
        ((101, 102), ('没有读到有效的地图边界。请等地图加载完成后再读取。', 'No valid map bounds were available. Wait for the map to finish loading and try again.')),
    ),
    'terrain': (
        ((100,), _REQUEST),
        ((101, 102), ('游戏没有返回这个坐标的有效地面高度。请将鼠标移到地图内的可见地面后再试。', 'The game did not return a valid ground height for these coordinates. Move the mouse over visible ground and try again.')),
    ),
    'position': (
        ((80,), _REQUEST), ((81,), _SELECTION), ((82, 85), _TARGET),
        ((83,), ('读取或写入单位位置后，游戏没有返回可用的坐标。请重新读取单位位置。', 'The game did not return usable unit coordinates during position readback. Reload the current position.')),
    ),
    'spawn': (
        ((90,), _REQUEST),
        ((91,), ('游戏中没有找到负责创建单位的玩家。请确认已经进图。', 'No player was found for unit creation. Enter a map first.')),
        ((92, 93), ('游戏未能创建并确认指定单位。请核对该单位代码在当前地图是否可用，再检查目标位置。', 'Unit creation could not be verified. Check the unit code on this map and inspect the target location.')),
    ),
    'world': (
        ((80, 81), _REQUEST),
        ((82,), ('没有找到这次操作对应的本地玩家。请确认已经进图。', 'The local player for this operation could not be found. Enter a map first.')),
    ),
    'world_cast': (
        ((320,), _REQUEST), ((322,), _SELECTION), ((323, 324), _TARGET),
        ((321,), ('没有读到可以施法的本地玩家。请确认已经进图。', 'No local player could be read for casting. Enter a map first.')),
        ((325,), ('施法范围超出了可用范围，请检查填写的数值。', 'The cast radius is outside the supported range. Check the entered value.')),
        ((326, 327), ('游戏未能添加或读回本次施法所需的技能。', 'The ability required for this cast could not be added or read back.')),
        ((328,), ('游戏没有保留本次施法需要的临时范围数值。', 'The game did not retain the temporary cast radius.')),
        ((329,), _CAST), ((330,), _IDENTITY),
        ((331, 332), ('施法后的临时技能或范围没有恢复到原状态。请重新读取施法单位。', 'The temporary ability or cast radius did not return to its original state. Reload the casting unit.')),
        ((333, 334), ('没能从地图中选出这次施法可用的目标。', 'No usable target for this cast could be obtained from the map.')),
    ),
    'effect': (
        ((150,), _REQUEST), ((151,), _COORDINATES), ((152,), _SELECTION),
        ((153, 167), _TARGET), ((154, 155, 156, 157, 163, 164, 165), _CAST_SETUP),
        ((158,), ('施法后未读到原来的技能实例。请重新读取施法单位。', 'The original ability instance was not found after casting. Reload the casting unit.')),
        ((159, 161, 162), _CAST_CLEANUP),
        ((160,), ('临时施法范围无效，或游戏没有按请求保留这个范围。', 'The temporary cast radius was invalid or was not retained by the game.')),
    ),
    'world_effect': (
        ((170, 321), _REQUEST),
        ((171,), ('没有读到本地玩家。请确认地图已经加载，且当前在游戏中。', 'The local player could not be read. Verify that the map is loaded and active.')),
        ((172,), ('没找到可以执行本次全图操作的单位。请确认地图里还有可用的目标。', 'No unit was available to perform this map-wide operation. Check that eligible targets remain.')),
        ((174, 175, 176, 177, 178, 309, 310), _CAST_SETUP),
        ((179, 180), ('本次没有完整遍历地图单位。请先检查哪些单位已经生效。', 'Map-wide unit enumeration did not complete. Check which units were affected.')),
        ((185, 306, 307), _CAST_CLEANUP),
        ((305,), ('施法目标次数超过了本次允许的数量。请调小数量。', 'This request exceeds the number of casts allowed. Reduce the count.')),
        ((308,), ('游戏返回的本次施法记录与施法单位不一致。请重新读取单位。', 'The cast record did not correspond to the casting unit. Reload the unit.')),
        ((311,), ('没有任何目标接受本次全图施法指令。', 'No target accepted the map-wide cast order.')),
        ((312,), ('用于施法的单位已持有同编号的技能。请重新读取技能状态。', 'The casting unit already has a skill with the same ID. Reload its skill state.')),
        ((313, 314), ('游戏没有按要求写入或保留全图施法范围。', 'The game did not accept or retain the map-wide cast radius.')),
        ((320,), ('游戏没有返回全图功能所需的当前地图状态。请进图后重新读取。', 'The game did not return the map state required for this action. Enter a map and try again.')),
    ),
}

NATIVE_REASONS = {
    (operation, code): reason
    for operation, groups in _GROUPS.items()
    for codes, reason in groups
    for code in codes
}

# A field-protocol offset identifies which row failed, not a separate cause.
for _operation, _first_rejection, _count in (('ability_field', 97, 32), ('item_field', 106, 20)):
    NATIVE_REASONS.update({
        (_operation, code): _REJECT_FIELD
        for code in range(_first_rejection, _first_rejection + _count)
    })
    NATIVE_REASONS.update({
        (_operation, code): _READBACK_FIELD
        for code in range(130, 130 + _count)
    })

for _operation, _first, _reason in (
    ('ability', 100, ('游戏在添加技能时中断。请先重新读取单位技能。', 'The game was interrupted while adding the skill. Reload unit abilities first.')),
    ('ability', 200, ('游戏在读取技能等级时中断。请先重新读取单位技能。', 'The game was interrupted while reading the ability level. Reload unit abilities first.')),
    ('ability', 300, ('游戏在设置技能等级时中断。请重新读取技能实际等级。', 'The game was interrupted while setting the ability level. Reload the current ability level.')),
    ('ability', 400, ('游戏在移除原技能时中断。请先重新读取单位技能。', 'The game was interrupted while removing the original ability. Reload unit abilities first.')),
    ('ability', 500, ('游戏在重新添加技能时中断。请先重新读取单位技能。', 'The game was interrupted while re-adding the ability. Reload unit abilities first.')),
    ('item', 100, ('游戏在创建物品时中断。请查看物品栏和单位脚下，确认是否已经生成物品。', 'The game was interrupted during item creation. Check the inventory and the ground near the unit.')),
    ('item', 200, ('游戏在设置新物品使用次数时中断。请先读回物品栏实际结果。', 'The game was interrupted while setting charges on a new item. Read the actual inventory before trying again.')),
    ('item', 400, ('游戏在修改已有物品的使用次数时中断。请先读取当前次数。', 'The game was interrupted while changing an existing item’s charges. Read the current charges first.')),
):
    NATIVE_REASONS.update({(_operation, code): _reason for code in range(_first, _first + 24)})
