"""User explanations are separate from the complete technical execution log."""
import re

BUSINESS_REASONS = {
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
    report=next((getattr(e,'report') for e in chain if isinstance(getattr(e,'report',None),dict)),{})
    dispatch=report.get('dispatch') or {}
    text='\n'.join(str(e) for e in chain)
    operation=report.get('operation','')
    reason=None;category='unknown';confirmed=False
    business=report.get('business_status') or report.get(operation+'_status') or {}
    code=business.get('error')
    if (operation,code) in BUSINESS_REASONS:
        reason=BUSINESS_REASONS[(operation,code)];category='business';confirmed=True
    if report.get('batch_failures'):
        causes=report['batch_failures']
        reason=('批量操作有失败项：'+'；'.join(c['reason'] for c in causes[:3]),
                'Some batch operations failed. See the diagnostic log.')
        category='batch';confirmed=all(c.get('reason_confirmed') for c in causes)
    winerror=next((getattr(e,'winerror',None) for e in chain if getattr(e,'winerror',None) is not None),None)
    if reason is None and winerror==5:
        reason=('Windows 拒绝访问目标进程。请核对修改器和游戏的权限级别。','Windows denied access to the game process. Check both applications’ privilege levels.');category='access';confirmed=True
    elif reason is None and any(word in text.lower() for word in ('signature differs','signature mismatch','abi differs','abi mismatch')):
        reason=('当前游戏接口与适配数据不一致；该操作未通过接口校验。','The game interface differs from the adapter; interface validation failed.');category='interface';confirmed=True
    elif reason is None and ('execution unresolved' in text or 'retained resources' in text or 'Session is not writable' in text):
        reason=('上一次操作的执行或清理状态未确认，已阻止重复写入。请保存日志并重新启动游戏后连接。','The previous execution or cleanup remains uncertain. Save the log, restart the game, and reconnect.');category='uncertain_session';confirmed=True
    elif reason is None and dispatch.get('transport_error'):
        reason=('连接游戏的执行通道失败，尚未确认具体系统原因。','The game execution channel failed; the exact system cause is not yet confirmed.');category='transport'
    elif reason is None and ('Unknown game build' in text or 'Unsupported game' in text or 'Unknown game fingerprint' in text):
        reason=('当前游戏构建尚未适配；未使用旧地址执行该操作。','This game build is not adapted; old addresses were not used.');category='unsupported_build';confirmed=True
    elif reason is None and any(word in text.lower() for word in ('no selected units','selection is empty','no selected unit')):
        reason=('没有读到选中单位，请先在游戏中选中目标。','No selected unit was found. Select a target in the game.');category='selection';confirmed=True
    if reason is None:
        # Retain a concise existing Chinese validation message, strip all
        # report/stack/address tails. Never show raw technical notes in a dialog.
        raw=str(exc).split('; engine24268=',1)[0].split('\n',1)[0]
        raw=raw.split('；失败详情：',1)[0]
        raw=re.split(r'(?:error=|engine24268=|0x[0-9a-fA-F]+|\{\s*["\'])',raw,maxsplit=1)[0].rstrip('：:;； ,')
        if re.search('[\u4e00-\u9fff]',raw) and len(raw)<=200:
            reason=(raw,'The operation did not complete. See the diagnostic log for details.');category='validation'
        else:
            reason=('本次操作未完成，具体原因尚未确认。请保留诊断日志。','The operation did not complete; the exact cause is not confirmed. Keep the diagnostic log.')
    recovered=business.get('session_continuable') is True
    if recovered:
        suffix=('已验证回滚，可继续其他操作。','Rollback was verified; other operations can continue.')
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
