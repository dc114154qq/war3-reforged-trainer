"""User explanations are separate from the complete technical execution log."""
import re

BUSINESS_REASONS = {
    ('unit_bindings',3): ('校验期间选中单位数量发生变化，未执行后续修改；请重新选择后重试。','Selection count changed; no subsequent write was performed. Reselect and retry.'),
    ('unit_bindings',4): ('游戏执行句柄与读取到的单位对象不一致，未执行后续修改；请重新读取目标。','The native handle does not match the read object; no subsequent write was performed. Refresh the target.'),
    ('unit_bindings',5): ('单位身份查询发生异常，具体原因尚未确认；请保留诊断日志。','Unit identity querying raised an exception; the exact cause is unconfirmed. Keep the diagnostic log.'),
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
    ('equipment_effect',402): ('销毁前的原生卸下未完成，物品状态未确认；已停止后续写入。','Native removal before destruction did not complete; the item state is uncertain and later writes are blocked.'),
    ('equipment_effect',403): ('销毁后的背包或装备状态读取失败，结果未确认；请保留日志。','Inventory readback after destruction failed; the result remains unconfirmed. Keep the log.'),
    ('equipment_effect',404): ('游戏执行删除后仍存在物品或槽位引用，销毁未通过验证；请保留日志并重启游戏。','The game still retains the item or a slot reference; destruction verification failed. Keep the log and restart the game.'),
    ('stat_details',274): ('3.0 属性能力的运行时分类或对象身份校验失败，未确认属性修改成功。','The runtime stat classification or object identity check failed; the write was not confirmed.'),
    ('stat_details',268): ('游戏未接受当前属性的模式转换，未确认修改成功。','The game rejected the stat mode conversion; the write was not confirmed.'),
    ('stat_details',269): ('游戏拒绝写入当前属性值，未确认修改成功。','The game rejected the stat value write; success was not confirmed.'),
    ('stat_details',271): ('游戏读回的属性值与目标不一致，本次修改未确认成功。','The stat readback differs from the requested value; the write was not confirmed.'),
    ('stat_details',273): ('属性修改后的恢复未通过验证，已停止后续写入；请保留日志并重启游戏。','Stat rollback could not be verified; later writes are blocked. Keep the log and restart the game.'),
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
    ('item_safety',414): ('检查用临时物品的清理未通过验证；已停止后续写入。','Temporary item cleanup could not be verified; later writes are blocked.'),
    ('item',63): ('游戏未能创建该物品；当前地图可能未注册它，具体原因仍需核对地图数据。','The game could not create this item; its definition may be absent from the map.'),
    ('direct_cast',353): ('技能请求未完成；具体施放条件尚未确认。','The skill request did not complete; the casting restriction is not yet confirmed.'),
}

def loadout_batch_error(summary, batch):
    exc=RuntimeError(summary+'; '+repr(batch.get('failures',())))
    exc.report={'operation':'loadout','batch_failures':tuple(batch.get('failure_explanations',()))}
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
    operation=report.get('operation','')
    reason=None;category='unknown';confirmed=False
    business=report.get('business_status') or report.get(operation+'_status') or {}
    code=business.get('error')
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
    business_operation='clone' if operation=='clone_bound' else operation
    if (business_operation,code) in BUSINESS_REASONS:
        reason=BUSINESS_REASONS[(business_operation,code)];category='business';confirmed=True
    if report.get('batch_failures'):
        causes=report['batch_failures']
        reason=('批量操作有失败项：'+'；'.join(c['reason'] for c in causes[:3]),
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
        reason=('上一次操作的执行或清理状态未确认，已阻止重复写入。请保存日志并重新启动游戏后连接。','The previous execution or cleanup remains uncertain. Save the log, restart the game, and reconnect.');category='uncertain_session';confirmed=True
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
        raw=re.sub(r'^[A-Za-z][A-Za-z0-9 /_-]*:\s*(?=[\u4e00-\u9fff])','',raw)
        raw=raw.split('；失败详情：',1)[0]
        raw=re.split(r'(?:error=|engine24268=|0x[0-9a-fA-F]+|\{\s*["\'])',raw,maxsplit=1)[0].rstrip('：:;； ,')
        if re.search('[\u4e00-\u9fff]',raw) and len(raw)<=200:
            reason=(raw,'The operation did not complete. See the diagnostic log for details.');category='validation'
        else:
            reason=('本次操作未完成，具体原因尚未确认。请保留诊断日志。','The operation did not complete; the exact cause is not confirmed. Keep the diagnostic log.')
    recovered=business.get('session_continuable') is True
    if recovered and business.get('read_only_rejection'):
        suffix=('该查询未写入游戏，可继续其他操作；此属性暂未读出。','This query did not write to the game. Other operations can continue; this statistic is unavailable.')
    elif recovered:
        suffix=('已验证回滚，可继续其他操作。','Rollback was verified; other operations can continue.')
    elif report.get('independent_operations_allowed') is True:
        suffix=('本次操作未确认成功，执行通道已清理，可继续其他操作。',
                'This operation was not confirmed; the channel was cleaned up and other operations remain available.')
    elif report.get('session',{}).get('uncertain') or report.get('verification',{}).get('uncertain'):
        suffix=('执行状态未确认，请勿重复此操作；重新启动游戏后连接。','Execution remains uncertain. Do not repeat the operation; restart the game and reconnect.')
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
