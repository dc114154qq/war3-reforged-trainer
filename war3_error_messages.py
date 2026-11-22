"""User explanations are separate from the complete technical execution log."""
import re
from errno import ENOSPC
from json import JSONDecodeError
from zipfile import BadZipFile

from war3_artifact_plan import ArtifactPlanError
from war3_native_error_messages import NATIVE_REASONS


_OPERATION_GROUPS = (
    (('close',), '退出修改器', 'Close trainer'),
    (('get_ui_notifications','scheduled_desktop_update','report_frontend_state'), '接收界面消息', 'Receive desktop messages'),
    (('get_system_status',), '刷新连接状态', 'Read connection status'),
    (('cancel_discovery',), '停止版本自动识别', 'Stop version discovery'),
    (('get_resource_snapshot','select_resource_group'), '读取玩家资源组', 'Read player resource group'),
    (('get_selected_unit_snapshot','get_unit_candidates_snapshot'), '刷新单位列表', 'Refresh the unit list'),
    (('get_locks','value_lock_tick'), '读取或应用数值锁定', 'Read or apply value locks'),
    (('ally_health_lock_tick',), '持续锁定我方生命', 'Keep allied units healed'),
    (('rapid_build_tick',), '持续快速建造或升级', 'Keep buildings and upgrades fast'),
    (('get_backpack_definition_progress','cancel_backpack_definitions'), '查看或停止补齐背包定义', 'Read or stop backpack definition processing'),
    (('get_map_catalog_progress','cancel_map_catalog'), '查看或停止地图数据读取', 'Read or stop map data processing'),
    (('get_map_script_progress','cancel_map_scripts'), '查看或停止地图脚本处理', 'Read or stop map script processing'),
    (('get_elephant_parameters','get_map_script_options','get_all_hotkeys','get_artifact_plan'), '读取功能设置', 'Read feature settings'),
    (('refresh_ability_fields',), '刷新技能字段', 'Refresh ability fields'),
    (('refresh_item_fields',), '刷新物品字段', 'Refresh item fields'),
    (('equipment_effect_refresh',), '刷新装备效果', 'Refresh equipment effects'),
    (('export_loadouts',), '导出套装方案', 'Export loadouts'),
    (('import_loadouts',), '导入套装方案', 'Import loadouts'),
    (('elephant_batch','ability_bundle','talent_batch'), '批量处理选中单位', 'Process selected units'),
    (('equipment_probe','legacy_equipment_probe'), '检查装备兼容性', 'Check equipment compatibility'),
    (('cooldown_probe',), '检查技能冷却兼容性', 'Check cooldown compatibility'),
    (('connect_process', 'initial_connect', 'adapter'), '连接游戏', 'Connect to game'),
    (('desktop_initialize', 'desktop_startup'), '启动修改器', 'Start trainer'),
    (('set_hotkeys_enabled', 'initialize_hotkeys', 'set_hotkey_check', 'set_all_hotkeys_checks'), '设置全局快捷键', 'Set global hotkeys'),
    (('trigger_hotkey',), '执行全局快捷键', 'Run global hotkey'),
    (('refresh_resources', 'set_resource', 'add_resource', 'add_resource_lock'), '处理玩家资源', 'Process player resources'),
    (('gold_mines', 'gold_mine'), '处理金矿', 'Process gold mines'),
    (('read_selected_unit', 'read_all_selected_units', 'read_selection_candidate', 'read_native_selection', 'refresh_unit_candidates', 'selection', 'unit_bindings'), '读取选中单位', 'Read selected units'),
    (('write_selected_unit', 'write_unit_field', 'hero', 'hero_attributes', 'unit_stats'), '修改所选单位', 'Edit selected unit'),
    (('add_unit_field_lock', 'apply_locks_once', 'remove_lock', 'background_guard'), '处理数值锁定', 'Process value locks'),
    (('read_ability_fields', 'ability_definition'), '读取技能字段', 'Read ability fields'),
    (('write_ability_field',), '修改技能字段', 'Edit ability field'),
    (('ability_field',), '处理技能字段', 'Process ability fields'),
    (('ability',), '处理单位技能', 'Process unit abilities'),
    (('read_item_fields', 'read_item_effect_fields'), '读取物品字段', 'Read item fields'),
    (('write_item_field', 'write_item_effect_field'), '修改物品字段', 'Edit item field'),
    (('item_field', 'item_effect'), '处理物品字段', 'Process item fields'),
    (('refresh_item_effect_fields',), '刷新物品字段', 'Refresh item fields'),
    (('read_unit_fields',), '读取单位字段', 'Read unit fields'),
    (('write_unit_field_value',), '修改单位字段', 'Edit unit field'),
    (('unit_field', 'unit_field_hero_int'), '处理单位字段', 'Process unit fields'),
    (('batch_read_units',), '读取批量修改目标', 'Read batch edit targets'),
    (('batch_write_units',), '批量修改单位', 'Batch edit units'),
    (('refresh_extension_status',), '读取 3.0 扩展状态', 'Read 3.0 extensions'),
    (('extension_bag_action', 'extension', 'item_ability'), '处理扩展背包', 'Process extended backpack'),
    (('extension_equipment_action', 'equipment', 'equipment_effect'), '处理扩展装备', 'Process extended equipment'),
    (('extension_talent_action', 'talent_order', 'talent_probe', 'talent_icon_control'), '处理英雄天赋', 'Process hero talents'),
    (('loadout', 'loadout_selection', 'restore_loadout', 'restore_all_loadouts', 'restore_all_loadouts_with_backpack', 'restore_loadout_with_backpack'), '恢复套装', 'Restore loadout'),
    (('save_loadout', 'save_all_loadouts', 'save_all_loadouts_with_backpack', 'save_loadout_with_backpack'), '保存套装', 'Save loadout'),
    (('add_official_backpack',), '添加官方背包', 'Add official backpack'),
    (('prepare_backpack_definitions', 'start_backpack_definitions', 'start_backpack_definitions_batch', 'extension_definitions'), '补齐背包定义', 'Fill in backpack definitions'),
    (('map_object_catalog', 'start_map_catalog', 'search_map_catalog', 'get_map_catalog_entry'), '读取自定义地图数据', 'Read custom map data'),
    (('export_map_catalog',), '导出自定义地图数据', 'Export custom map data'),
    (('map_script_tools', 'start_map_scripts'), '写入地图功能脚本', 'Write map scripts'),
    (('scan_archive_directory', 'read_archive_file', 'read_live_heroes', 'scan_rpg_codes_memory', 'parse_rpg_codes_text', 'save_extraction'), '读取存档或存档代码', 'Read saves or save codes'),
    (('save_artifact_plan', 'restore_default_artifact_plan'), '保存神器方案', 'Save artifact plan'),
    (('six_artifacts', 'apply_artifact_plan'), '一键添加神器', 'Add artifact items'),
    (('execute_elephant_action', 'prewarm_elephant'), '执行大象功能', 'Run Elephant action'),
    (('clone', 'clone_bound', 'clone_state'), '复制单位', 'Duplicate units'),
    (('direct_cast', 'world_cast', 'world_effect', 'effect'), '施放全屏技能或效果', 'Cast map-wide ability or effect'),
    (('item', 'item_catalog', 'item_safety'), '处理物品', 'Process items'),
    (('stat_details', 'attack_speed'), '处理单位属性', 'Process unit stats'),
    (('unit_action', 'spawn', 'bulk'), '执行单位操作', 'Run unit action'),
    (('position', 'position_target', 'mouse', 'screen_mouse'), '读取坐标或移动单位', 'Read coordinates or move units'),
    (('world', 'game_speed', 'camera', 'map_bounds', 'map_flags', 'terrain'), '处理地图或游戏状态', 'Process map or game state'),
    (('choose_definition_file', 'choose_definition_files', 'choose_definition_folder'), '打开文件选择窗口', 'Open file picker'),
    (('set_ui_language', 'save_map_script_options', 'set_hotkey_parameter', 'set_elephant_parameter'), '保存修改器设置', 'Save trainer settings'),
    (('search_3_equipment', 'search_id_catalog', 'search_3_hero_skills'), '检索典籍数据', 'Search reference data'),
)
_OPERATIONS = {key: (zh, en) for keys, zh, en in _OPERATION_GROUPS for key in keys}
_GENERIC_MESSAGES = frozenset((
    '', '操作未完成', '操作失败', '未知原因', '未知错误', 'unknown reason', 'unknown error',
    'the operation did not complete', 'operation failed',
))


def operation_name(operation, language='zh'):
    return _OPERATIONS.get(operation, ('执行修改器操作', 'Run trainer action'))[language == 'en']


class CompletedWithWarning(RuntimeError):
    """A write was verified and a subsequent read/confirmation failed."""
    def __init__(self, cause):
        super().__init__(str(cause))
        self.__cause__ = cause

BUSINESS_REASONS = {
    ('extension',222): ('本次要处理的英雄未能在执行时的选中列表中唯一匹配，已停止该英雄的本步操作；本步尚未读取背包容量，不能据此判断背包或天赋缺失。','The requested hero did not uniquely match the selection at execution time. This step stopped before reading inventory capacity; it does not prove missing inventory or talents.'),
    ('ability',25): ('游戏拒绝给所选单位添加该技能。请确认技能代码在当前地图可用，再检查这个单位是否能使用它。','The game rejected adding this ability to the selected unit. Check that its code is available on this map and that the unit can use it.'),
    ('ability',29): ('能力调用后的等级读回与请求不一致，本次补齐未确认成功；请保留诊断日志。','The ability level readback differs from the request. This addition is unconfirmed; keep the diagnostic log.'),
    ('ability',34): ('技能实例或技能编号在操作期间变化，本次添加已停止。','The ability instance or ID changed during this operation.'),
    ('ability',35): ('已找到技能实例，但游戏未按要求激活或设置等级；本次添加未确认成功。','An ability instance exists, but its activation or level readback did not match.'),
    ('ability',36): ('游戏返回已添加，但没有读回对应技能实例；本次添加未确认成功。','The game accepted the addition but no matching ability instance was found.'),
    ('ability',37): ('当前技能列表超过检查范围，或存在多个同编号实例；已停止添加，避免修改错误对象。','The ability list exceeds the inspection bound or has multiple matching instances; addition stopped.'),
    ('item_ability',443): ('背包物品的能力列表不完整或含重复对象，已停止本次挂载，避免重复添加。','The item ability list is incomplete or contains duplicate objects; attachment stopped.'),
    ('item_ability',444): ('背包物品的能力查询与列表不一致，或同编号实例不唯一；已停止本次挂载。','The item ability lookup disagrees with its list, or multiple instances match; attachment stopped.'),
    ('item_ability',445): ('背包物品未读回所需能力，物品能力挂载未确认成功；已停止本次修复。','The required ability was not found on the backpack item; attachment remains unconfirmed.'),
    ('item_ability',446): ('挂载能力期间，背包物品的身份或经典栏发生变化；已停止后续修复。','The backpack item identity or classic inventory changed during attachment.'),
    ('item_ability',447): ('挂载能力后，背包物品原有的能力读回变化；已停止后续修复。','An existing item ability changed after attachment.'),
    ('direct_cast',344): ('游戏没有在选中英雄身上创建施法所需的临时技能，本次未施放。','The game did not create the temporary ability on the selected hero, so this cast did not start.'),
    ('direct_cast',354): ('施法后的原单位或技能实例未通过校验，本次后处理未完成；可以重新选择目标再操作。','The original casting unit or ability no longer passed identity checks. This request could not finish; a new request can use a freshly selected target.'),
    ('direct_cast',355): ('全屏技能的临时法力参数未通过读回，未继续施放。','Temporary mana-cost parameters failed readback; casting stopped.'),
    ('direct_cast',356): ('全屏技能的临时冷却参数未通过读回，未继续施放。','Temporary cooldown parameters failed readback; casting stopped.'),
    ('direct_cast',359): ('游戏未按要求清除本次技能的临时冷却，未继续施放。','The temporary cooldown did not clear as requested; casting stopped.'),
    ('unit_bindings',3): ('校验期间选中单位数量发生变化，未执行后续修改；请重新选择后重试。','Selection count changed; no subsequent write was performed. Reselect and retry.'),
    ('unit_bindings',4): ('单位对象与原生选中列表的对应校验未通过，未执行后续修改；旧日志未区分具体校验步骤，请重新读取并选择目标。','The object-to-native-selection check failed before subsequent writes. This legacy status does not distinguish the validation step; refresh and select the target.'),
    ('unit_bindings',5): ('游戏在核对所选单位时发生异常。请重新选择并读取目标。','The game encountered an exception while verifying the selected unit. Reselect and reload the target.'),
    ('unit_bindings',6): ('读取到的单位对象已失效或与对象表不一致，未执行后续修改；请刷新单位列表。','The read unit is stale or differs from the object registry. No subsequent write was performed; refresh the unit list.'),
    ('unit_bindings',7): ('目标单位未在当前原生选中列表中匹配，未执行后续修改；请在游戏中选中该单位后重新读取。','The target did not match the current native selection. No subsequent write was performed; select it in the game and refresh.'),
    ('unit_bindings',8): ('目标单位的原生句柄对应关系不唯一，未执行后续修改；请重新选择目标并保留日志。','The target-to-native-handle mapping is ambiguous. No subsequent write was performed; reselect the target and keep the log.'),
    ('clone',780): ('复制所需的装备或天赋接口未通过检查，未开始创建副本。', 'The inventory or talent interfaces failed validation before creation.'),
    ('clone',781): ('原单位的物品栏容量异常，未开始复制。', 'Source inventory capacity is invalid.'),
    ('clone',782): ('原单位的物品位置或数量未通过检查，已停止复制。', 'Source item location or charges failed validation.'),
    ('clone',783): ('原单位的技能身份未通过检查，已停止复制。', 'Source ability identity failed validation.'),
    ('clone',784): ('原单位的天赋控制器或选择记录异常，已停止复制。', 'Source talent controller or records failed validation.'),
    ('clone',785): ('复制期间原单位的物品发生变化，已停止复制。', 'Source inventory changed during copying.'),
    ('clone',786): ('游戏返回了已有物品实例，已停止复制并保留原物品。', 'The game returned an existing item; the original is preserved.'),
    ('clone',787): ('副本的经典物品栏容量与原单位不同，复制未完成。', 'Clone classic inventory capacity differs from the source.'),
    ('clone',788): ('地图在副本创建时额外生成了物品，与原单位布局冲突，复制未完成。', 'Creation triggers supplied conflicting items.'),
    ('clone',789): ('复制的物品未进入对应经典栏，已停止并清理本次副本。', 'A copied item did not enter the requested classic slot.'),
    ('clone',790): ('副本的扩展背包容量与原单位不同，复制未完成。', 'Extended inventory capacities differ.'),
    ('clone',791): ('复制的装备未进入对应部位，复制未完成。', 'A copied item did not enter its equipment slot.'),
    ('clone',792): ('复制的物品未进入对应扩展背包格，复制未完成。', 'A copied item did not enter its extended bag slot.'),
    ('clone',793): ('副本的天赋控制器身份不匹配，复制未完成。', 'Clone talent controller identity differs.'),
    ('clone',794): ('副本天赋选择未找到对应的新技能实例，复制未完成。', 'A clone talent record has no matching new ability instance.'),
    ('clone',795): ('副本天赋点数或选择记录读回不同，复制未完成。', 'Clone talent points or records failed readback.'),
    ('clone',796): ('复制结束后的物品位置或数量与原单位不同，复制未完成。', 'Final copied inventory differs from the source.'),
    ('clone',60): ('复制单位所需的游戏接口未通过校验，未开始复制。','The required clone interfaces failed validation; no copy began.'),
    ('clone',61): ('没有读到完整的选中单位列表，未开始复制；请重新选择单位后重试。','The selection could not be fully read; reselect the units and retry.'),
    ('clone',62): ('选中单位的身份、归属或位置已失效，未开始复制；请重新选择单位后重试。','The selected unit identity, owner or position is invalid; no copy began.'),
    ('clone',63): ('游戏未创建符合原单位类型和归属的副本，复制未完成。','The game did not create a clone with the expected type and owner.'),
    ('clone',64): ('副本的英雄等级未按原单位读回，复制未完成。','The clone hero level differs from the original.'),
    ('clone',65): ('原单位含当前未能复制的技能组件，已取消本次复制。','The source contains a skill component that could not be copied.'),
    ('clone',66): ('游戏拒绝给副本添加原单位的技能，复制未完成。','The game rejected adding a source skill to the clone.'),
    ('clone',67): ('副本的技能等级未按原单位读回，复制未完成。','The clone skill level differs from the original.'),
    ('clone',68): ('副本的物品创建或类型检查失败，复制未完成。','The clone item creation or type validation failed.'),
    ('clone',69): ('副本的物品数量未按原物品读回，复制未完成。','The copied item charge count differs from the original.'),
    ('clone',70): ('原单位的物品技能未能完整读取，复制未完成。','The source item skills could not be fully read.'),
    ('clone',71): ('副本的剩余技能点未按原英雄读回，复制未完成。','The clone unspent skill points differ from the original.'),
    ('clone',72): ('复制期间原单位发生变化，已停止复制，未继续操作失效对象。','A source unit changed during copying; stale objects were not used.'),
    ('clone',73): ('复制时游戏接口发生异常，未确认复制成功；具体原因请保留日志核对。','A native exception occurred during copying; success was not confirmed.'),
    ('clone',74): ('复制失败后的临时单位或物品未能确认清理完成，请保留日志并重新连接重启后的游戏。','Temporary clone cleanup could not be confirmed; keep the log and reconnect after restarting the game.'),
    ('clone',75): ('原单位的技能数量超过本次复制可完整处理的范围，已取消复制，避免生成缺少技能的副本。','The source skill count exceeds the complete-copy limit; the copy was cancelled.'),
    ('clone',76): ('游戏返回的对象不是新副本，已停止复制以保护原单位。','The returned object was not a new clone; copying stopped to protect the originals.'),
    ('clone',77): ('开始复制时的选中单位已变化，已停止本轮复制；不会改用后来选中的对象。','The original selection changed; this copy stopped without using newly selected objects.'),
    ('world',84): ('游戏未按目标经验倍率读回，本次修改未确认成功。','The experience-rate readback differs from the request; the write was not confirmed.'),
    ('equipment_effect',406): ('装备实例分类修复后未通过原生读回，未确认修复成功。','Native readback did not confirm the repaired equipment classification.'),
    ('equipment_effect',407): ('待修复物品的槽位、归属或分类已变化，未修改该物品。','The source slot, ownership or classification changed; the item was not modified.'),
    ('equipment_effect',405): ('旧物品的原生移除或重新入包未通过验证，未确认修复成功；请保留日志。','Native removal or reinsertion of the inherited item could not be verified. Keep the log.'),
    ('equipment_effect',401): ('待销毁的物品不再唯一属于所选英雄，未执行删除。','The destruction target is no longer uniquely owned by the selected hero; no deletion was issued.'),
    ('equipment_effect',402): ('销毁前的原生卸下未完成，本次物品状态未确认；详情已记录，可重新读取后操作。','Native removal before destruction did not complete. This item state is unconfirmed; refresh it before a new request.'),
    ('equipment_effect',403): ('销毁后的背包或装备状态读取失败，结果未确认；请保留日志。','Inventory readback after destruction failed; the result remains unconfirmed. Keep the log.'),
    ('equipment_effect',404): ('游戏执行删除后仍存在物品或槽位引用，销毁未通过验证；请保留日志并重启游戏。','The game still retains the item or a slot reference; destruction verification failed. Keep the log and restart the game.'),
    ('stat_details',274): ('3.0 属性能力的运行时分类或对象身份校验失败，未确认属性修改成功。','The runtime stat classification or object identity check failed; the write was not confirmed.'),
    ('stat_details',266): ('游戏拒绝添加本次属性所需的技能组件，未开始属性值写入；具体地图限制尚未确认。','The game rejected adding the skill component required for this statistic before any stat value write. The specific map restriction is unconfirmed.'),
    ('stat_details',267): ('游戏接受了技能添加请求，但未读回所需属性组件；本次修改未确认成功，请保留日志。','The game accepted adding the skill, but the required stat component was not read back. Success is unconfirmed; keep the log.'),
    ('stat_details',268): ('游戏未接受当前属性的模式转换，未确认修改成功。','The game rejected the stat mode conversion; the write was not confirmed.'),
    ('stat_details',269): ('游戏拒绝写入当前属性值，未确认修改成功。','The game rejected the stat value write; success was not confirmed.'),
    ('stat_details',271): ('游戏读回的属性值与目标不一致，本次修改未确认成功。','The stat readback differs from the requested value; the write was not confirmed.'),
    ('stat_details',273): ('本次属性恢复未通过验证，详情已记录；新的操作会重新读取当前状态。','This stat restoration was not verified and was logged. New requests read the current state again.'),
    ('stat_details',275): ('当前单位没有可触发的暴击来源，请先增加对应暴击几率或装备暴击物品。','No triggering critical source exists. Add the matching chance or critical equipment first.'),
    ('world',3221225477): ('迷雾原生接口发生未识别的访问异常，开／关图状态未确认；未自动重试。','An unrecognized fog-native fault occurred; the fog state is unconfirmed and no automatic replay was attempted.'),
    ('world',83): ('游戏读回的迷雾状态与请求不一致，未将本次开／关图标为成功。','The fog readback did not match the request; the operation was not marked successful.'),
    ('equipment_effect',381): ('装备或物品实例已变化，身份校验未通过。','Equipment or item identity changed.'),
    ('equipment_effect',385): ('物品不在原背包槽，或目标装备槽已被占用。','The source item moved or the destination slot is occupied.'),
    ('equipment_effect',386): ('游戏拒绝装备这件物品。请检查目标部位是否空闲，以及物品是否符合该装备位。','The game rejected the equip request. Check that the target slot is free and accepts this item.'),
    ('equipment_effect',387): ('游戏执行装备请求后，装备栏没有返回这件物品。请刷新背包和装备栏核对它的位置。','The item could not be read back in the equipment slots after the request. Refresh the bag and equipment to check its location.'),
    ('equipment_effect',389): ('扩展背包已满，或待卸下的物品已不在原槽位。','The extended bag is full or the source equipment changed.'),
    ('equipment_effect',395): ('游戏拒绝把创建的物品转入扩展背包。','The game rejected transfer into the extended bag.'),
    ('item_safety',411): ('当前地图没有可创建的该物品定义，或游戏拒绝创建；未开始背包转移。','The item is unavailable or creation was rejected; no bag transfer began.'),
    ('item_safety',414): ('本次临时物品清理未通过验证，详情已记录；可重新读取后继续操作。','Temporary item cleanup was not verified and was logged. Refresh the current state for a new request.'),
    ('item',63): ('游戏未能创建该物品；当前地图可能未注册它，具体原因仍需核对地图数据。','The game could not create this item; its definition may be absent from the map.'),
    ('direct_cast',353): ('游戏拒绝执行这次施法指令。请确认选中的英雄仍可行动，鼠标在地图画面内。','The game rejected this cast order. Check that the selected hero can act and that the mouse is over the map.'),
}

def loadout_batch_error(summary, batch):
    exc=RuntimeError(summary+'; '+repr(batch.get('failures',())))
    exc.report={'operation':'loadout','batch_summary':summary,
                'batch_failures':tuple(batch.get('failure_explanations',())),
                'batch_results':batch}
    return exc

def summarize_skips(snapshot, language='zh'):
    entries=snapshot.get('loadout_item_skips',())
    if not entries:
        entries=[entry for _,entry in snapshot.get('loadout_batch',{}).get('item_skips',())]
    if not entries:return ''
    codes=tuple(dict.fromkeys(int(e['rawcode']).to_bytes(4,'big').decode('ascii','replace') for e in entries))
    shown=', '.join(codes[:5])
    if len(codes)>5:shown+=' ...'
    return (f'; skipped protected legacy items: {shown}' if language=='en' else
            f'；已跳过不可丢弃的旧式物品：{shown}，其余操作可继续')

def _chain(exc):
    seen=set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc));yield exc
        exc=exc.__cause__ or (None if exc.__suppress_context__ else exc.__context__)

def _dispatch_reason(report):
    dispatch = report.get('dispatch') or {}
    if not dispatch:
        return None
    fault = dispatch.get('fault') or {}
    if fault:
        return ('game_exception', ('游戏在处理请求时发生异常，修改器没有拿到完整结果。请先重新读取游戏状态。',
                                   'The game raised an exception while processing the request. The result was incomplete. Refresh the game state first.'))
    stage = dispatch.get('failure_stage')
    stage_names = {
        'open_game': ('连接游戏进程', 'opening the game process'),
        'prepare_system_apis': ('准备与游戏通信所需的 Windows 接口', 'preparing the Windows interfaces for game communication'),
        'load_component': ('加载修改器的游戏通信组件', 'loading the trainer’s game communication component'),
        'prepare_request': ('准备本次操作的数据', 'preparing the request data'),
        'start_request': ('启动游戏内的请求处理', 'starting request handling in the game'),
        'send_request': ('向游戏窗口发送请求', 'sending the request to the game window'),
        'read_result': ('读取游戏返回结果', 'reading the game response'),
        'finish_request': ('关闭本次游戏请求并核对结果', 'finishing the request and verifying the result'),
    }
    if dispatch.get('error') and stage in stage_names:
        zh_stage,en_stage=stage_names[stage]
        winerror=dispatch.get('winerror')
        if winerror==299:
            return ('partial_game_io',(f'“{zh_stage}”时，Windows 只完成了部分数据传输。请重新连接，先读取当前结果。',
                f'Windows transferred only part of the data while {en_stage}. Reconnect and read the current result first.'))
        if winerror==5:
            return ('transport_access',(f'Windows 拒绝执行“{zh_stage}”。请核对修改器和游戏的运行权限。',
                f'Windows denied access while {en_stage}. Check how the trainer and game were launched.'))
        if winerror in (2,3,126):
            return ('transport_component',(f'“{zh_stage}”时，Windows 没有找到所需文件、路径或组件。请重新打开游戏和完整的修改器文件。',
                f'Windows could not find a required file, path or component while {en_stage}. Reopen the game and the complete trainer.'))
        code=f'（Windows 错误代码 {winerror}）' if winerror else ''
        en_code=f' (Windows error {winerror})' if winerror else ''
        return ('transport_stage',(f'请求在“{zh_stage}”这一步中断{code}。请重新连接并检查当前结果。',
            f'The request stopped while {en_stage}{en_code}. Reconnect and check the current result.'))
    installation=dispatch.get('after_install') or {}
    if installation.get('stage')==2 and not installation.get('hook'):
        winerror=installation.get('last_error')
        if winerror:
            reason=(f'游戏通信还没建立，Windows 未启用本次窗口消息接收（错误代码 {winerror}）。请求没有发出。',
                    f'Windows did not enable the game window message receiver (error {winerror}). The request was not sent.')
        else:
            reason=('游戏没有成功启用本次窗口消息接收，请求没有发出。请回到地图后重新连接。',
                    'The game message receiver did not start. The request was not sent. Return to the map and reconnect.')
        return 'game_message_setup',reason
    for delivery in (dispatch.get('send'),dispatch.get('post'),dispatch.get('post_thread')):
        if not delivery:
            continue
        if delivery.get('enqueued',delivery.get('completed')) is False:
            if delivery.get('error')==1460:
                return ('game_window_timeout',('游戏窗口没有在等待时间内回应。请回到地图让游戏继续运行，再核对结果。',
                    'The game window did not respond in time. Return to the map and verify the current result.'))
            if delivery.get('error')==1400:
                return ('game_window_closed',('原游戏窗口已失效。请切到当前游戏窗口，再点连接游戏。',
                    'The original game window is no longer available. Switch to the current game window and reconnect.'))
            return ('game_message_delivery',('Windows 没有把请求成功送到游戏窗口。请重新连接游戏。',
                'Windows could not deliver the request to the game window. Reconnect to the game.'))
    if dispatch.get('allocations_retained') or dispatch.get('cleanup_verified') is False and dispatch.get('callback_exited') is True:
        return ('cleanup', ('本次请求结束后，修改器没能确认游戏中的临时操作已退出或清理完毕。请先读取当前结果。',
                            'The trainer could not verify that the temporary game operation had exited or been cleaned up. Read the current result first.'))
    if dispatch.get('callback_received') is True and dispatch.get('callback_exited') is False:
        return ('callback_incomplete', ('游戏收到了请求，但在等待时间内没有处理完。请回到地图中，先读取当前结果。',
                                        'The game received the request but did not finish in time. Return to the map and read the current result first.'))
    if dispatch.get('callback_received') is True and dispatch.get('query_completed') is False:
        return ('response_incomplete', ('游戏收到了请求，但没有返回完整结果。请重新读取当前状态后核对。',
                                        'The game received the request but did not return a complete result. Refresh the current state to check it.'))
    if dispatch.get('callback_received') is False:
        return ('callback_not_received', ('在等待时间内没有收到游戏响应。请确认游戏仍在地图中运行，然后重新读取。',
                                          'No game response arrived in time. Check that the game is running in a map, then read the state again.'))
    if dispatch.get('transport_error') or dispatch.get('error'):
        return ('transport', ('向游戏发送请求或接收结果时出错，未取得完整响应。请重新连接游戏后读取当前状态。',
                              'An error occurred while sending the request or receiving its result. Reconnect and read the current state.'))
    return None


def _fallback_reason(chain, operation, report):
    """Keep a concrete exception or observed phase when no game code is available."""
    from war3_ui_i18n import translate_ui_text

    for error in chain:
        winerror=getattr(error,'winerror',None)
        if winerror==299:
            return 'partial_game_io', ('Windows 只完成了部分游戏数据传输。请重新连接并读取当前状态。',
                'Windows transferred only part of the game data. Reconnect and read the current state.'),True
        if isinstance(error, FileNotFoundError):
            name = getattr(error, 'filename', None)
            file = f'（{name}）' if name else ''
            return 'file_missing', (f'找不到这一步需要的文件或目录{file}。请检查路径后重试。',
                                    f'A file or folder required for this step was not found. Check the path and try again. {name or ""}'.strip()), True
        if isinstance(error, IsADirectoryError) or isinstance(error, NotADirectoryError):
            return 'file_type', ('所选路径的类型不对。请确认选的是文件还是目录，然后重新选择。',
                                 'The selected path has the wrong type. Check whether a file or folder is required and select it again.'), True
        if isinstance(error, OSError) and (error.errno == ENOSPC or getattr(error, 'winerror', None) in (39, 112)):
            return 'disk_full', ('保存文件所用的磁盘空间不足。请腾出空间，或换到另一个目录。',
                                 'There is not enough disk space to save the file. Free some space or use a different folder.'), True
        if isinstance(error, PermissionError) and getattr(error,'filename',None):
            return 'file_permission', (f'Windows 不允许访问文件或目录（{error.filename}）。请检查它的读写权限。',
                                       f'Windows denied access to the file or folder ({error.filename}). Check its permissions.'), True
        if isinstance(error, TimeoutError):
            return 'timeout', (f'“{operation_name(operation)}”等待超时，未收到完整结果。请先核对当前状态。',
                               f'“{operation_name(operation, "en")}” timed out before a complete result arrived. Check the current state first.'), True
        if isinstance(error, JSONDecodeError):
            return 'invalid_json', (f'方案或配置格式有误，读取在第 {error.lineno} 行第 {error.colno} 列停止。请重新选择有效文件。',
                                    f'The plan or configuration could not be parsed at line {error.lineno}, column {error.colno}. Choose a valid file.'), True
        if isinstance(error, BadZipFile):
            return 'invalid_archive', ('无法打开该压缩文件，文件结构不完整或格式不对。请重新下载或选择原文件。',
                                       'The archive structure is invalid or incomplete. Download it again or select the original file.'), True
        if isinstance(error, ValueError) and re.match(r'(?:invalid literal for int\(\)|could not convert string to float)', str(error)):
            integer = 'for int' in str(error)
            return 'invalid_number', (('输入值无法读成整数。请填写整数后重试。' if integer else '输入值无法读成数字。请填写数值后重试。'),
                                      ('Enter a whole number and try again.' if integer else 'Enter a number and try again.')), True
        if isinstance(error, UnicodeError):
            return 'encoding', ('读取的文字编码无法识别。请检查输入文件格式或重新选择文件。',
                                'Text in the input could not be decoded. Check the format or choose another file.'), True

    for error in chain:
        raw = str(error).split('; engine24268=',1)[0].split('\n',1)[0]
        raw = re.sub(r'[（(]ATal\+0x[0-9a-fA-F]+[）)]','',raw)
        raw = re.sub(r'^[A-Za-z][A-Za-z0-9 /_-]*:\s*(?=[\u4e00-\u9fff])','',raw)
        raw = raw.split('；失败详情：',1)[0]
        raw = re.split(r"""(?:error=|engine24268=|0x[0-9a-fA-F]+|\{\s*["'])""",raw,maxsplit=1)[0].rstrip('。.:：;； ,')
        if raw.lower() in _GENERIC_MESSAGES or not 0 < len(raw) <= 240:
            continue
        if re.search('[\u4e00-\u9fff]',raw):
            return 'validation', (raw+'。', translate_ui_text(raw+'。','en')), True

    if report.get('ok') is True:
        return 'after_success', ('游戏操作已经通过核对，但保存本次操作的诊断记录时出错。请先查看当前结果。',
                                 'The game operation was verified, but saving its diagnostic record failed. Check the current result first.'), True
    if report.get('dispatch_attempted') is False:
        return 'preflight', (f'“{operation_name(operation)}”在准备阶段出错，请求还没发给游戏。',
                             f'“{operation_name(operation, "en")}” failed during preparation, before a request was sent to the game.'), True
    if (report.get('dispatch') or {}).get('query_completed') is True:
        return 'response_validation', (f'游戏处理了“{operation_name(operation)}”请求，但返回数据未通过核对。请先重新读取，确认实际结果。',
                                       f'The game processed “{operation_name(operation, "en")}”, but its response did not pass validation. Read the current result first.'), True
    root = chain[-1]
    if isinstance(root,(KeyError,IndexError,AttributeError)):
        return 'missing_value', ('修改器执行这一步时缺少所需数据。', 'The trainer was missing data required for this step.'), True
    if isinstance(root,(ValueError,TypeError,OverflowError)):
        return 'internal_value', ('修改器执行这一步时收到无法处理的数值或数据。', 'The trainer received a value or data it could not process.'), True
    return 'internal_error', ('修改器在这一步遇到程序异常，未取得可核对的结果。', 'The trainer encountered an internal exception before getting a verifiable result.'), False


def describe_error(exc, language='zh', *, operation=''):
    """Use recorded evidence, never treat a generic WinError as a root cause."""
    chain=list(_chain(exc))
    if isinstance(exc, CompletedWithWarning):
        cause = describe_error(exc.__cause__, language, operation=operation)
        if language == 'en':
            reason = 'The value was written and verified. The subsequent list refresh failed. ' + cause['reason']
            recovery = 'Read the list again to see the new value.'
        else:
            reason = '数值已经写入并核对。随后刷新列表失败。' + cause['reason']
            recovery = '请重新读取列表查看新值。'
        return {**cause, 'reason':reason, 'recovery':recovery, 'category':'post_write_refresh'}
    artifact_error=next((entry for entry in chain if isinstance(entry,ArtifactPlanError)),None)
    if artifact_error is not None:
        return dict(category='artifact_plan',operation=operation,reason=artifact_error.message(language),
                    reason_confirmed=True,recovery='',business_error=None)
    from war3_object_tables import DefinitionError
    definition_error=next((entry for entry in chain if isinstance(entry,DefinitionError)),None)
    if definition_error is not None:
        from war3_ui_i18n import translate_ui_text
        return dict(category='extension_definitions',operation='extension_definitions',
                    reason=translate_ui_text(str(definition_error),language),
                    reason_confirmed=True,
                    recovery=('原文件已保留，可检查提示和处理日志后重新选择文件。' if language=='zh' else
                              'The original file is preserved. Review the message and processing log, then choose the file again.'),
                    business_error=None)
    discovery = next((getattr(e, 'discovery_report', None) for e in chain
                      if isinstance(getattr(e, 'discovery_report', None), dict)), None)
    if discovery is not None:
        from war3_ui_i18n import translate_ui_text
        return dict(category='automatic_discovery', operation='adapter',
                    reason=translate_ui_text(discovery['reason'],language),
                    reason_confirmed=True,
                    recovery=('本次未执行游戏修改；可继续已确认功能，或重新连接后重试。' if language == 'zh' else
                              'No game modification was performed. Confirmed features remain available; reconnect to retry.'),
                    business_error=None)
    from war3_save_codes import SaveExtractionError
    save_error = next((entry for entry in chain if isinstance(entry, SaveExtractionError)), None)
    if save_error is not None:
        from war3_ui_i18n import translate_ui_text
        return dict(category='save_extraction', operation='save_extraction',
                    reason=translate_ui_text(str(save_error), language), reason_confirmed=True,
                    recovery=('文件原件及游戏状态未改动，可继续其他操作。' if language=='zh' else
                              'Source files and game state were not changed. Other operations can continue.'),
                    business_error=None)
    report=next((getattr(e,'report') for e in chain if isinstance(getattr(e,'report',None),dict)),{})
    dispatch=report.get('dispatch') or {}
    text='\n'.join(str(e) for e in chain)
    if not report.get('batch_failures') and report.get('loadout_interrupted'):
        count=len(report.get('generated',()))
        return dict(category='loadout_interrupted',operation='loadout',reason_confirmed=True,
            reason=(f'恢复期间内部读取的选中列表未能匹配本次英雄，已中止该英雄。已确认生成 {count} 件物品，均未自动删除；请检查原英雄背包。'
                    if language=='zh' else f'The internal selection did not match the restoration target. This hero stopped; {count} confirmed generated items were retained. Check the original hero inventory.'),
            recovery=('其他已完成的英雄保留恢复结果；请重新读取未完成的英雄后核对，不要连续重复恢复。' if language=='zh' else
                      'Completed heroes were retained. Refresh and inspect the unfinished hero before another restore.'),business_error=None)
    if not report.get('batch_failures') and (report.get('operation')=='loadout_selection' or 'Creation target is not uniquely selected' in text):
        return dict(category='loadout_target_selection',operation='loadout_selection',reason_confirmed=True,
            reason=('创建前的内部选中列表未能匹配本次英雄，未创建本件物品；不能据此判断背包或天赋控制器缺失。' if language=='zh' else
                    'The internal selection did not match the requested hero before creation. This item was not created; it does not indicate a missing bag or talent controller.'),
            recovery=('本次初始多选与执行时读取结果需分别核对，详细目标已记录。' if language=='zh' else
                      'The initial selection and execution-time readback are recorded separately.'),business_error=None)
    if not report.get('batch_failures') and '天赋读取目标已变化' in text:
        return dict(category='talent_display_target',operation=report.get('operation',''),reason_confirmed=True,
            reason=('本次天赋快照对应的英雄与后续读取到的选中目标不一致，未取得该英雄的实时天赋状态；这不是控制器缺失的证据。' if language=='zh' else
                    'The hero in the talent snapshot differs from the later selected target. Its live talent state was not read; this does not prove a missing controller.'),
            recovery=('已完成的装备恢复保留；请重新读取扩展状态。' if language=='zh' else
                      'Completed equipment operations were retained. Refresh the extension state.'),business_error=None)
    if not report.get('batch_failures') and ('Unit component list remained unstable after retries' in text or 'Unit component head changed while retrying' in text):
        return dict(category='component_unstable',operation=report.get('operation',''),reason_confirmed=True,
            reason=('读取期间单位的技能组件列表发生变化，本次未能取得稳定的天赋状态；这不能说明天赋控制器缺失。'
                    if language=='zh' else 'The unit ability list changed during reading. A stable talent state was unavailable; this does not prove the talent controller is missing.'),
            recovery=('请重新读取扩展状态；已完成的装备操作不会因这次读取失败而撤销。' if language=='zh' else
                      'Refresh the extension state. This read failure does not undo completed equipment operations.'),business_error=None)
    if not report.get('batch_failures') and '天赋控制器目标身份不唯一' in text:
        return dict(category='talent_target_ambiguous',operation=report.get('operation',''),reason_confirmed=True,
            reason=('旧版未能区分同类型英雄，未能确认要读取哪一个天赋控制器；不能据此判断控制器缺失。'
                    if language=='zh' else 'The older build could not distinguish same-type heroes and identify the target controller. This does not prove a missing controller.'),
            recovery=('请使用按完整单位身份绑定目标的修复版。' if language=='zh' else 'Use the fixed build that binds the complete unit identity.'),business_error=None)
    if not report.get('batch_failures') and 'Classic inventory is full; free one temporary slot before regenerating ordinary equipment' in text:
        return dict(category='classic_inventory_full',operation='loadout',reason_confirmed=True,
            reason=('经典六格物品栏已满。恢复这套方案中的普通物品需要一个临时空位，请先腾出经典物品栏的一格，再点击恢复套装。'
                    if language=='zh' else
                    'The six-slot classic inventory is full. Restoring ordinary items in this plan needs one temporary slot. Free one classic inventory slot, then restore the loadout again.'),
            recovery=('方案仍然保留，本次未创建该物品。' if language=='zh' else
                      'The saved plan is retained. This item was not created.'),business_error=None)
    operation=report.get('operation') or operation
    reason=None;category='unknown';confirmed=False
    status_kind={
        'clone_bound':'clone', 'clone_state':'clone', 'position_target':'position',
        'legacy_equipment_probe':'extension',
    }.get(operation,operation)
    business=report.get('business_status') or {}
    native_status=report.get(status_kind+'_status') or report.get('failure_observation') or {}
    code=business.get('error') or native_status.get('error')
    # Older protocol decoders also report some status codes in their exception.
    if not code and report.get('operation'):
        match=re.search(r'\berror=(\d+)\b',str(chain[-1]))
        if match:
            code=int(match[1]) or None
    # Historical EXEs included this exact native error but omitted its decoded
    # status. Explain the known branch without inventing an inventory snapshot.
    if code is None and operation=='extension' and re.search(r'3\.0 extension incomplete: error=222,',text):code=222
    world=report.get('world_status') or {}
    if operation=='world' and world.get('action') in (3,4) and world.get('error'):
        reason=('游戏未能完成战争迷雾状态的读取或切换。请先在地图里检查当前迷雾状态。',
                'The game did not finish reading or changing fog of war. Check the current fog state in the map first.')
        category='fog_native';confirmed=True
    selection=report.get('selection_failure') or {}
    stage=selection.get('stage')
    if operation=='selection':
        if stage in ('hp_missing','hp_unreadable','hp_invalid'):
            reason=('已找到选中单位，但生命值组件未能通过读取检查。未修改游戏；请保留日志并重新选中单位后重试。','The selected unit was found, but its health component could not be validated. No game write occurred. Keep the log and reselect the unit.')
            category='selection_component';confirmed=True
        elif stage in ('owner_handle','owner_unit','unit_handle','identity_unreadable','unit_changed'):
            reason=('选中单位的身份已变化或读取不完整，未修改游戏。请重新选中单位后重试。','The selected unit identity changed or could not be fully read. No game write occurred. Reselect the unit and retry.')
            category='selection_identity';confirmed=True
    reason_key=(status_kind,code)
    if reason_key in BUSINESS_REASONS or reason_key in NATIVE_REASONS:
        reason=BUSINESS_REASONS.get(reason_key) or NATIVE_REASONS[reason_key]
        category='business';confirmed=True
    if reason is None and operation=='unit_field_hero_int':
        reason=NATIVE_REASONS.get(('unit_field',code))
        if reason:category='business';confirmed=True
    if reason is None and operation=='extension' and not code and native_status.get('snapshot_valid') is False and native_status.get('completed'):
        reason=('游戏没有返回完整的扩展背包与装备状态，请重新选中英雄后读取。',
                'The game did not return a valid extended inventory snapshot. Reselect the hero and read it again.')
        category='extension_snapshot';confirmed=True
    selection_code=(report.get('native_selection_observation') or {}).get('error')
    if selection_code:
        selection_reasons={
            1:('游戏未能为本次读取准备临时单位列表。请重新选中目标再读取。','The game could not prepare a temporary selection list. Reselect the units and read again.'),
            2:('选中的单位超过单次可读取的 24 个。请分成几批再操作。','More than 24 units were selected. Split the selection and try again.'),
            4:('游戏的选中列表重复返回了同一个单位，无法准确区分目标。请重新选中。','The game returned the same unit twice in its selection. Reselect the targets.'),
            5:('当前版本没有返回完整的选中单位读取接口。请重新连接游戏。','The game did not supply the complete selection interface. Reconnect to the game.'),
        }
        if selection_code in selection_reasons:
            category,reason,confirmed='native_selection',selection_reasons[selection_code],True
    if report.get('batch_failures'):
        causes=report['batch_failures']
        prefix=report.get('batch_summary','')
        zh_causes=list(dict.fromkeys(c['reason'] for c in causes))
        en_causes=list(dict.fromkeys(c.get('reason_en') or c['reason'] for c in causes))
        reason=((prefix+'。\n\n' if prefix else '')+'\n'.join('• '+cause for cause in zh_causes),
                'Some batch targets failed.\n\n'+'\n'.join('• '+cause for cause in en_causes))
        category='batch';confirmed=all(c.get('reason_confirmed') for c in causes)
    failed_apis=[entry for entry in (dispatch.get('remote_api_resolution') or {}).values()
                 if isinstance(entry,dict) and entry.get('completed') is False]
    if reason is None and failed_apis and report.get('verification',{}).get('delivered') is False:
        reason=('游戏中的 Windows 执行接口未通过解析校验，本次请求尚未发送。缺失的接口或组件已记录在诊断日志中。',
                'A Windows API in the game did not pass target export resolution. No request was sent; the missing interface or component is recorded in the diagnostic log.')
        category='system_api_resolution';confirmed=True
    elif reason is None and 'Missing remote module apphelp.dll' in text and report.get('verification',{}).get('delivered') is False:
        reason=('修改器误用了自身兼容层的接口地址，未能找到游戏中的对应接口；本次请求尚未发送。请更新到包含此修复的版本，无需补装 DLL。',
                'The trainer used a process-local compatibility entry with no corresponding game module. No request was sent. Update the trainer; installing another DLL is not required.')
        category='system_api_resolution';confirmed=True
    winerror=next((getattr(e,'winerror',None) for e in chain if getattr(e,'winerror',None) is not None),None)
    integrity=report.get('integrity') or next((getattr(e,'integrity_report') for e in chain
        if isinstance(getattr(e,'integrity_report',None),dict)),{})
    if reason is None and '修改器与游戏完整性级别不一致' in text:
        reason=('修改器和游戏的运行权限不同。游戏若以管理员运行，请以管理员重新启动修改器后连接。','The trainer and game have different privilege levels. If the game is elevated, restart the trainer as administrator.');category='integrity';confirmed=True
        if integrity.get('trainer',{}).get('rid')==0x2000 and integrity.get('target',{}).get('rid')==0x3000:
            reason=('运行权限不同：修改器是普通权限，游戏是管理员权限。请以管理员重新启动修改器后连接；本次未向游戏发送修改。','The trainer runs normally and the game runs as administrator. Restart the trainer as administrator and reconnect; no modification was sent to the game.')
    elif reason is None and winerror==5 and not any(getattr(e,'filename',None) for e in chain):
        reason=('Windows 拒绝访问目标进程。请核对修改器和游戏的权限级别。','Windows denied access to the game process. Check both applications’ privilege levels.');category='access';confirmed=True
        if integrity.get('permitted') is True:
            reason=('Windows 拒绝访问游戏，但权限检查允许当前运行权限组合。具体系统原因尚未确认，请保留诊断日志。','Windows denied access to the game although the privilege preflight permits this combination. The exact system cause is unconfirmed; keep the diagnostic log.')
            category='access';confirmed=False
    elif reason is None and 'Item was explicitly removed' in text:
        reason=('该物品已销毁，旧物品引用已失效；请刷新背包或装备列表。','This item was destroyed and its old references are invalid. Refresh the inventory.');category='retired_item';confirmed=True
    elif reason is None and any(word in text.lower() for word in ('signature differs','signature mismatch','abi differs','abi mismatch')):
        reason=('当前游戏接口与适配数据不一致；该操作未通过接口校验。','The game interface differs from the adapter; interface validation failed.');category='interface';confirmed=True
    elif reason is None and 'native query deferred' in text:
        reason=('上次游戏回调或执行通道尚未确认清理，原生查询暂时未执行；可独立读取的单位字段仍可读取。','The previous callback or execution channel remains unresolved; native queries are deferred while independent unit fields remain readable.');category='pending_query';confirmed=True
    elif reason is None and any(s in text for s in ('execution unresolved', 'retained resources',
            'Session is not writable', 'Session has unresolved execution/resources')):
        reason=('上一次操作的执行或清理状态未确认，详情已保留在日志中；新的操作会重新读取当前状态。','The previous operation remains unconfirmed and is recorded in the log. New requests read the current state again.');category='uncertain_session';confirmed=True
    elif reason is None and 'Multiple Warcraft III clients are open' in text:
        reason=('检测到多个 Warcraft III 游戏进程，请在 PID 栏填写要连接的游戏进程编号。','Multiple Warcraft III game clients are running. Enter the intended game PID.');category='multiple_clients';confirmed=True
    elif reason is None and ('Unknown game build' in text or 'Unsupported game' in text or 'Unknown game fingerprint' in text or 'Unknown or ambiguous game build' in text):
        reason=('当前游戏构建尚未适配；未使用旧地址执行该操作。','This game build is not adapted; old addresses were not used.');category='unsupported_build';confirmed=True
    elif reason is None and any(word in text.lower() for word in ('no selected units','selection is empty','no selected unit')):
        reason=('没有读到选中单位，请先在游戏中选中目标。','No selected unit was found. Select a target in the game.');category='selection';confirmed=True
    elif reason is None and 'classic selection identity validation failed' in text:
        reason=('选中单位未通过读取校验。旧日志未记录具体失败步骤，暂不能确定原因；请使用新版本重试并保留日志。','The selected unit did not pass read validation. This older log lacks the failed step; retry with the new version and keep the log.');category='selection_identity'
    elif reason is None and any(s in text for s in ('Map changed while binding session','Map context changed','Game module changed','Process identity changed')):
        reason=('游戏进程或地图在操作期间已经切换。请连接当前游戏并重新读取目标。',
                'The game process or map changed during the operation. Connect to the current game and reload the target.');category='session_changed';confirmed=True
    elif reason is None and any(s in text for s in ('Stale object reference', 'Object destroyed or replaced', 'Item object type changed')):
        reason=('上次读取的单位或物品已经失效或被替换。请重新读取后再选目标。',
                'The previously read unit or item is stale or was replaced. Reload and reselect the target.');category='target_changed';confirmed=True
    elif reason is None and any(s in text for s in ('Game session has not been verified','Game session closed','Object binding requires a live verified session')):
        reason=('当前游戏连接已关闭或尚未通过检查。请进图后重新连接游戏。',
                'The game connection is closed or could not be verified. Enter a map and reconnect.');category='game_session';confirmed=True
    if reason is None and code == 3221225477:
        reason=('游戏在这一步访问内部数据时发生异常，没能返回完整结果。请重新读取当前状态。',
                'The game hit a memory access error during this step and did not return a complete result. Refresh the current state.')
        category='game_exception';confirmed=True
    if reason is None:
        dispatch_reason=_dispatch_reason(report)
        if dispatch_reason:
            category,reason=dispatch_reason
            confirmed=True
    if reason is None and code:
        reason=(f'游戏在“{operation_name(operation)}”时返回失败代码 {code}，没有提供更具体的说明。请先读取当前状态。',
                f'The game returned failure code {code} while running “{operation_name(operation,"en")}” without a more specific result. Read the current state first.')
        category='unmapped_status'
    if reason is None:
        category,reason,confirmed=_fallback_reason(chain,operation,report)
    recovered=business.get('session_continuable') is True
    if recovered and business.get('no_write_rejection'):
        suffix=('本步在写入前停止，执行通道已清理；之前已完成的操作保留。','This step stopped before writing and the channel was cleaned up. Previously completed operations are retained.')
    elif recovered and business.get('read_only_rejection'):
        suffix=('该查询未写入游戏，可继续其他操作；此属性暂未读出。','This query did not write to the game. Other operations can continue; this statistic is unavailable.')
    elif recovered:
        suffix=('已验证回滚，可继续其他操作。','Rollback was verified; other operations can continue.')
    elif report.get('ok') is True:
        suffix=('','')
    elif report.get('independent_operations_allowed') is True:
        suffix=('可以继续执行其他操作。','Other operations remain available.')
    elif report.get('session',{}).get('uncertain') or report.get('verification',{}).get('uncertain'):
        suffix=('本次执行状态未确认，已保留日志；下一次操作重新读取当前状态。','This execution remains unconfirmed and was logged. The next request reads the current state again.')
    elif report.get('ok') or not report:
        suffix=('','')
    elif (business or native_status).get('cleanup')==0 and dispatch.get('cleanup_verified'):
        suffix=('执行通道已清理；这不代表功能已成功。','The execution channel was cleaned up; this does not confirm game success.')
    else:suffix=('','')
    index=1 if language=='en' else 0
    return dict(category=category,operation=operation,reason=reason[index],
                reason_confirmed=confirmed,recovery=suffix[index],business_error=code)

def format_error(exc, language='zh', *, operation='', diagnosis=None):
    diagnosis=diagnosis or describe_error(exc,language,operation=operation)
    lines=[diagnosis['reason']]
    if diagnosis['recovery']:lines.append(diagnosis['recovery'])
    path=next((entry.diagnostic_log_path for entry in _chain(exc) if getattr(entry,'diagnostic_log_path',None)),None)
    if path:
        lines.append(('Diagnostic log: ' if language=='en' else '诊断日志：')+str(path))
    elif getattr(exc,'log_write_error',None):
        lines.append('The diagnostic log could not be saved.' if language=='en' else '诊断日志未能保存，请检查日志目录。')
    return '\n\n'.join(lines)
