"""Complete missing official backpack components on the same bound target."""
from __future__ import annotations
from copy import deepcopy


def _code(text):
    return int.from_bytes(text.encode('ascii'),'big')


def _failure(message,diagnostic,engine,cause=None):
    error=RuntimeError(message)
    report=dict(getattr(engine,'last_report',{}) or {})
    report.update(operation='backpack_interface',backpack_interface=deepcopy(diagnostic))
    error.report=report
    if cause is not None:raise error from cause
    raise error


def ensure_backpack_interface(host,target_unit,controller,item_rawcode,snapshot,trace=None):
    """Add absent AIni/AEqu/controller/ASpc once, with sequential readback."""
    target=int(target_unit);engine=host._engine_instance_24268()
    controller_name=int(controller).to_bytes(4,'big').decode('ascii')
    components=(('AIni',_code('AIni')),('AEqu',_code('AEqu')),
                (controller_name,int(controller)),('ASpc',_code('ASpc')))
    codes=tuple(_code(name) for name in ('AIni','AEqu','ASpc'))+(int(controller),)
    diagnostic=dict(target_unit=target,item_rawcode=int(item_rawcode),controller=int(controller),
                    entry_rawcode=_code('ASpc'),add_attempted=False,actual_open_effect_verified=False,
                    click_evidence='not_collected',attempted_components=[],added_components=[],readbacks=[])
    if int(snapshot.get('target_unit',0))!=target:
        diagnostic.update(status='target_changed',observed_target_unit=snapshot.get('target_unit'))
        _failure('背包检查期间目标单位发生变化，已停止本次链路；请重新选择持有背包的单位。',diagnostic,engine)

    def event(phase,**values):
        if trace is not None:trace.record(phase,**values)

    def read(phase):
        event(phase,target_unit=target,ability_rawcodes=codes)
        try:result=engine.extension(codes,target_unit=target)
        except Exception as exc:
            diagnostic.update(status='component_query_failed',cause=str(exc),execution_report=getattr(exc,'report',None))
            _failure('背包物品已存在，但本次组件检查未完成；尚未确认界面入口状态。已停止本次链路，请保留诊断日志。',diagnostic,engine,exc)
        if int(result.get('target_unit',0))!=target:
            diagnostic.update(status='target_changed',observed_target_unit=result.get('target_unit'))
            _failure('背包检查期间目标单位发生变化，已停止本次链路；请重新选择持有背包的单位。',diagnostic,engine)
        levels={int(code):int(level) for code,level in dict(result.get('abilities',{})).items()}
        diagnostic.update(bag_size=int(result.get('bag_size',0)),
                          ability_levels={name:levels.get(_code(name),0) for name in ('AIni','AEqu','ASpc')},
                          controller_level=levels.get(int(controller),0))
        state=dict(phase=phase,target_unit=target,bag_size=diagnostic['bag_size'],
                   component_levels={name:levels.get(code,0) for name,code in components})
        diagnostic['readbacks'].append(state)
        event(phase+'_result',components=state,bag=result.get('bag'),equipment=result.get('equipment'))
        return result,levels

    def preserve(previous,after):
        for key in ('bag','equipment'):
            old=tuple(previous.get(key,()));new=tuple(after.get(key,()))
            for index,row in enumerate(old):
                occupied=bool(row.get('handle',0)) if isinstance(row,dict) else bool(row and row[0])
                if occupied and (index>=len(new) or row!=new[index]):
                    diagnostic.update(status='storage_changed',changed_area=key,changed_slot=index)
                    _failure('补齐组件后，原有背包或装备读回发生变化；已停止后续操作，请保留诊断日志。',diagnostic,engine)
            initialized=(key=='bag' and int(previous.get('bag_size',0))==30) or (
                key=='equipment' and int(previous.get('abilities',{}).get(_code('AEqu'),0))>0)
            if initialized and old!=new:
                diagnostic.update(status='storage_changed',changed_area=key)
                _failure('补齐组件后，背包或装备读回发生变化；已停止后续操作，请保留诊断日志。',diagnostic,engine)
        if int(previous.get('bag_size',0))==30 and int(after.get('bag_size',0))!=30:
            diagnostic.update(status='storage_changed',changed_area='bag_size')
            _failure('补齐组件后，背包容量读回发生变化；已停止后续操作，请保留诊断日志。',diagnostic,engine)

    current,levels=read('components_before')
    from war3_3_extension_catalog import TALENT_CONTROLLERS
    conflicts=[name for name in TALENT_CONTROLLERS
               if _code(name)!=int(controller) and int(snapshot.get('abilities',{}).get(_code(name),0))>0]
    if conflicts:
        diagnostic.update(status='controller_conflict',conflicting_controllers=conflicts)
        _failure('当前单位已有其他官方天赋控制器，已停止补齐背包能力。请保留诊断日志。',diagnostic,engine)
    baseline=deepcopy(current)
    preserve(snapshot,current)
    # An existing storage ability with an invalid capacity is not recreated.
    if levels.get(_code('AIni'),0)>0 and diagnostic['bag_size']!=30:
        diagnostic.update(status='storage_not_initialized',failed_component='AIni')
        _failure('AIni 能力已存在，但 30 格扩展背包未生效；请保留诊断日志。',diagnostic,engine)
    for name,code in components:
        if levels.get(code,0)>0:continue
        diagnostic.update(add_attempted=True,failed_component=name)
        diagnostic['attempted_components'].append(name)
        event('component_add',target_unit=target,component=name,rawcode=code,action=1,level=0)
        try:call_result=host.ability_batch_24268(code,1,0,target_unit=target)
        except Exception as exc:
            diagnostic.update(status='entry_add_failed' if name=='ASpc' else 'component_add_failed',
                              cause=str(exc),execution_report=getattr(exc,'report',None))
            message=('游戏未确认补齐入口' if name=='ASpc' else f'游戏未确认补齐组件 {name}')
            _failure('背包物品已存在，但'+message+'。本次未重复添加，请保留诊断日志。',diagnostic,engine,exc)
        event('component_add_result',component=name,result=call_result,
              execution_report=deepcopy(getattr(engine,'last_report',{})))
        previous=current
        current,levels=read('components_after_'+name)
        preserve(previous,current)
        prior={int(k):int(v) for k,v in previous.get('abilities',{}).items()}
        lost=[label for label,value in components if prior.get(value,0)>0 and levels.get(value,0)!=prior[value]]
        if lost:
            diagnostic.update(status='existing_component_changed',changed_components=lost)
            _failure('补齐组件后，已有能力读回发生变化；已停止后续操作，请保留诊断日志。',diagnostic,engine)
        if levels.get(code,0)<=0:
            diagnostic['status']='entry_still_missing' if name=='ASpc' else 'component_still_missing'
            _failure(f'已尝试补齐背包组件 {name}，但游戏读回仍缺失；具体原因未确认。已停止后续添加，请保留诊断日志。',diagnostic,engine)
        diagnostic['added_components'].append(name)
        if name=='AIni' and diagnostic['bag_size']!=30:
            diagnostic.update(status='storage_not_initialized',failed_component='AIni')
            _failure('AIni 能力已读回，但 30 格扩展背包未生效；已停止后续添加，请保留诊断日志。',diagnostic,engine)
    preserve(baseline,current)
    diagnostic.pop('failed_component',None)
    added=diagnostic['added_components']
    diagnostic['status']=('native_entry_present' if not added else
                          'missing_native_entry_added' if added==['ASpc'] else 'missing_components_added')
    snapshot.update({key:current[key] for key in ('bag_size','bag','equipment') if key in current})
    abilities=dict(snapshot.get('abilities',{}));abilities.update(levels)
    snapshot['abilities']=abilities;snapshot['backpack_interface']=diagnostic
    return snapshot
