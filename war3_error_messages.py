"""User explanations are separate from the complete technical execution log."""
import re

BUSINESS_REASONS = {
    ('extension',222): ('本次要处理的英雄未能在执行时的选中列表中唯一匹配，已停止该英雄的本步操作；本步尚未读取背包容量，不能据此判断背包或天赋缺失。','The requested hero did not uniquely match the selection at execution time. This step stopped before reading inventory capacity; it does not prove missing inventory or talents.'),
    ('ability',25): ('游戏拒绝添加本次能力组件，具体原因未确认；已停止本次补齐，请保留诊断日志。','The game rejected adding this ability component. The cause is unconfirmed; this addition stopped. Keep the diagnostic log.'),
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
    ('direct_cast',344): ('游戏未创建全屏技能实例，本次未施放；具体拒绝原因未确认。','The game did not create the full-screen ability; its rejection cause is unconfirmed.'),
    ('direct_cast',354): ('施法后的原单位或技能实例未通过校验，本次后处理未完成；可以重新选择目标再操作。','The original casting unit or ability no longer passed identity checks. This request could not finish; a new request can use a freshly selected target.'),
    ('direct_cast',355): ('全屏技能的临时法力参数未通过读回，未继续施放。','Temporary mana-cost parameters failed readback; casting stopped.'),
    ('direct_cast',356): ('全屏技能的临时冷却参数未通过读回，未继续施放。','Temporary cooldown parameters failed readback; casting stopped.'),
    ('direct_cast',359): ('游戏未按要求清除本次技能的临时冷却，未继续施放。','The temporary cooldown did not clear as requested; casting stopped.'),
    ('unit_bindings',3): ('校验期间选中单位数量发生变化，未执行后续修改；请重新选择后重试。','Selection count changed; no subsequent write was performed. Reselect and retry.'),
    ('unit_bindings',4): ('单位对象与原生选中列表的对应校验未通过，未执行后续修改；旧日志未区分具体校验步骤，请重新读取并选择目标。','The object-to-native-selection check failed before subsequent writes. This legacy status does not distinguish the validation step; refresh and select the target.'),
    ('unit_bindings',5): ('单位身份查询发生异常，具体原因尚未确认；请保留诊断日志。','Unit identity querying raised an exception; the exact cause is unconfirmed. Keep the diagnostic log.'),
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
    ('equipment_effect',386): ('游戏拒绝装备该物品。具体战役限制尚未确认。','The game rejected the equipment request; the campaign restriction is not confirmed.'),
    ('equipment_effect',387): ('游戏执行装备请求后，没有在装备栏读回该物品；可能被战役脚本移走或删除。','The item was not found in equipment after the request; a campaign script may have moved or removed it.'),
    ('equipment_effect',389): ('扩展背包已满，或待卸下的物品已不在原槽位。','The extended bag is full or the source equipment changed.'),
    ('equipment_effect',395): ('游戏拒绝把创建的物品转入扩展背包。','The game rejected transfer into the extended bag.'),
    ('item_safety',411): ('当前地图没有可创建的该物品定义，或游戏拒绝创建；未开始背包转移。','The item is unavailable or creation was rejected; no bag transfer began.'),
    ('item_safety',414): ('本次临时物品清理未通过验证，详情已记录；可重新读取后继续操作。','Temporary item cleanup was not verified and was logged. Refresh the current state for a new request.'),
    ('item',63): ('游戏未能创建该物品；当前地图可能未注册它，具体原因仍需核对地图数据。','The game could not create this item; its definition may be absent from the map.'),
    ('direct_cast',353): ('技能请求未完成；具体施放条件尚未确认。','The skill request did not complete; the casting restriction is not yet confirmed.'),
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
        exc=exc.__cause__ or exc.__context__

def describe_error(exc, language='zh'):
    """Use recorded evidence, never treat a generic WinError as a root cause."""
    chain=list(_chain(exc))
    from war3_object_tables import DefinitionError
    definition_error=next((entry for entry in chain if isinstance(entry,DefinitionError)),None)
    if definition_error is not None:
        return dict(category='extension_definitions',operation='extension_definitions',
                    reason=(str(definition_error) if language=='zh' else
                            'Campaign/map definition processing stopped. See the processing log for the specific file or object conflict.'),
                    reason_confirmed=True,
                    recovery=('原文件已保留，可检查提示和处理日志后重新选择文件。' if language=='zh' else
                              'The original file is preserved. Review the message and processing log, then choose the file again.'),
                    business_error=None)
    discovery = next((getattr(e, 'discovery_report', None) for e in chain
                      if isinstance(getattr(e, 'discovery_report', None), dict)), None)
    if discovery is not None:
        return dict(category='automatic_discovery', operation='adapter',
                    reason=(discovery['reason'] if language == 'zh' else
                            'Automatic version discovery did not confirm the required data. See the diagnostic log.'),
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
    operation=report.get('operation','')
    reason=None;category='unknown';confirmed=False
    business=report.get('business_status') or report.get(operation+'_status') or {}
    code=business.get('error')
    # Historical EXEs included this exact native error but omitted its decoded
    # status. Explain the known branch without inventing an inventory snapshot.
    if code is None and operation=='extension' and re.search(r'3\.0 extension incomplete: error=222,',text):code=222
    world=report.get('world_status') or {}
    if operation=='world' and world.get('action') in (3,4) and world.get('error'):
        reason=('游戏迷雾接口调用失败，开图状态未确认。具体失败位置已记录在日志中。',
                'The game fog interface failed; reveal state was not confirmed. The failing native location is recorded in the log.')
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
    business_operation='clone' if operation in ('clone_bound','clone_state') else operation
    if (business_operation,code) in BUSINESS_REASONS:
        reason=BUSINESS_REASONS[(business_operation,code)];category='business';confirmed=True
    if report.get('batch_failures'):
        causes=report['batch_failures']
        prefix=report.get('batch_summary','')
        reason=((prefix+'。\n\n' if prefix else '')+'批量操作有失败项：'+'；'.join(c['reason'] for c in causes[:3]),
                'Some batch operations failed. See the diagnostic log.')
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
    elif reason is None and winerror==5:
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
    elif reason is None and dispatch.get('transport_error'):
        reason=('连接游戏的执行通道失败，尚未确认具体系统原因。','The game execution channel failed; the exact system cause is not yet confirmed.');category='transport'
    elif reason is None and 'Multiple Warcraft III clients are open' in text:
        reason=('检测到多个 Warcraft III 游戏进程，请在 PID 栏填写要连接的游戏进程编号。','Multiple Warcraft III game clients are running. Enter the intended game PID.');category='multiple_clients';confirmed=True
    elif reason is None and ('Unknown game build' in text or 'Unsupported game' in text or 'Unknown game fingerprint' in text or 'Unknown or ambiguous game build' in text):
        reason=('当前游戏构建尚未适配；未使用旧地址执行该操作。','This game build is not adapted; old addresses were not used.');category='unsupported_build';confirmed=True
    elif reason is None and any(word in text.lower() for word in ('no selected units','selection is empty','no selected unit')):
        reason=('没有读到选中单位，请先在游戏中选中目标。','No selected unit was found. Select a target in the game.');category='selection';confirmed=True
    elif reason is None and 'classic selection identity validation failed' in text:
        reason=('选中单位未通过读取校验。旧日志未记录具体失败步骤，暂不能确定原因；请使用新版本重试并保留日志。','The selected unit did not pass read validation. This older log lacks the failed step; retry with the new version and keep the log.');category='selection_identity'
    if reason is None:
        # Retain a concise existing Chinese validation message, strip all
        # report/stack/address tails. Never show raw technical notes in a dialog.
        raw=str(exc).split('; engine24268=',1)[0].split('\n',1)[0]
        raw=re.sub(r'[（(]ATal\+0x[0-9a-fA-F]+[）)]','',raw)
        raw=re.sub(r'^[A-Za-z][A-Za-z0-9 /_-]*:\s*(?=[\u4e00-\u9fff])','',raw)
        raw=raw.split('；失败详情：',1)[0]
        raw=re.split(r'(?:error=|engine24268=|0x[0-9a-fA-F]+|\{\s*["\'])',raw,maxsplit=1)[0].rstrip('：:;； ,')
        if re.search('[\u4e00-\u9fff]',raw) and len(raw)<=200:
            reason=(raw,'The operation did not complete. See the diagnostic log for details.');category='validation'
        else:
            reason=('本次操作未完成，具体原因尚未确认。请保留诊断日志。','The operation did not complete; the exact cause is not confirmed. Keep the diagnostic log.')
    recovered=business.get('session_continuable') is True
    if recovered and business.get('no_write_rejection'):
        suffix=('本步在写入前停止，执行通道已清理；之前已完成的操作保留。','This step stopped before writing and the channel was cleaned up. Previously completed operations are retained.')
    elif recovered and business.get('read_only_rejection'):
        suffix=('该查询未写入游戏，可继续其他操作；此属性暂未读出。','This query did not write to the game. Other operations can continue; this statistic is unavailable.')
    elif recovered:
        suffix=('已验证回滚，可继续其他操作。','Rollback was verified; other operations can continue.')
    elif report.get('independent_operations_allowed') is True:
        suffix=('本次操作未确认成功，详情已记录，可继续新的操作。',
                'This operation was not confirmed and was logged. New independent requests remain available.')
    elif report.get('session',{}).get('uncertain') or report.get('verification',{}).get('uncertain'):
        suffix=('本次执行状态未确认，已保留日志；下一次操作重新读取当前状态。','This execution remains unconfirmed and was logged. The next request reads the current state again.')
    elif report.get('ok') or not report:
        suffix=('','')
    elif business.get('cleanup')==0 and dispatch.get('cleanup_verified'):
        suffix=('执行通道已清理；这不代表功能已成功。','The execution channel was cleaned up; this does not confirm game success.')
    else:suffix=('','')
    index=1 if language=='en' else 0
    return dict(category=category,operation=operation,reason=reason[index],
                reason_confirmed=confirmed,recovery=suffix[index],business_error=code)

def format_error(exc, language='zh'):
    diagnosis=describe_error(exc,language)
    lines=[diagnosis['reason']]
    if diagnosis['recovery']:lines.append(diagnosis['recovery'])
    path=getattr(exc,'diagnostic_log_path',None)
    if path:
        lines.append(('Diagnostic log: ' if language=='en' else '诊断日志：')+str(path))
    elif getattr(exc,'log_write_error',None):
        lines.append('The diagnostic log could not be saved.' if language=='en' else '诊断日志未能保存，请检查日志目录。')
    return '\n\n'.join(lines)
