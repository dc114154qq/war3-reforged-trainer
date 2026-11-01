"""Portable talent plans; optional restoration never rolls back completed gear."""
from contextlib import contextmanager, nullcontext
from copy import deepcopy


def _code(value, *, empty=False):
    if empty and value == '':return value
    if type(value) is not str or len(value)!=4 or any(not 33<=ord(c)<=126 for c in value):
        raise ValueError('Invalid saved talent ID')
    return value


def validate_talents(value):
    if value is None:return None
    if type(value) is not dict or set(value)!={'controller','controller_level','remaining_points','tiers'}:
        raise ValueError('Invalid saved talent fields')
    controller=_code(value['controller'])
    level=value['controller_level'];points=value['remaining_points'];rows=value['tiers']
    if type(level) is not int or not 1<=level<=100000:
        raise ValueError('Invalid saved talent controller level')
    if not isinstance(rows,(list,tuple)) or not 1<=len(rows)<=6:
        raise ValueError('Invalid saved talent tier count')
    if type(points) is not int or not 0<=points<=len(rows)*3:
        raise ValueError('Invalid saved talent points')
    tiers=[]
    for row in rows:
        if type(row) is not dict or set(row)!={'choices','native_choice','selected'}:
            raise ValueError('Invalid saved talent tier fields')
        choices=row['choices'];selected=row['selected'];native=_code(row['native_choice'],empty=True)
        if not isinstance(choices,(list,tuple)) or not 1<=len(choices)<=3:
            raise ValueError('Invalid saved talent options')
        choices=[_code(code) for code in choices]
        if len(set(choices))!=len(choices) or native and native not in choices:
            raise ValueError('Saved native talent is outside its tier')
        if not isinstance(selected,(list,tuple)) or len(selected)>len(choices):
            raise ValueError('Invalid saved talent selection')
        effects=[]
        for effect in selected:
            if type(effect) is not dict or set(effect)!={'rawcode','level'}:
                raise ValueError('Invalid saved talent effect')
            code=_code(effect['rawcode']);rank=effect['level']
            if code not in choices or type(rank) is not int or not 1<=rank<=100000:
                raise ValueError('Invalid saved talent effect level')
            effects.append(dict(rawcode=code,level=rank))
        if len({e['rawcode'] for e in effects})!=len(effects):
            raise ValueError('Duplicate saved talent effect')
        if native and native not in {e['rawcode'] for e in effects}:
            raise ValueError('Saved native talent has no corresponding effect')
        tiers.append(dict(choices=choices,native_choice=native,selected=effects))
    if points+sum(bool(row['native_choice']) for row in tiers)>sum(len(row['choices']) for row in tiers):
        raise ValueError('Saved native talent points exceed the tree capacity')
    return dict(controller=controller,controller_level=level,remaining_points=points,tiers=tiers)


class _SilentTrace:
    def record(self,*args,**kwargs):pass
    def summary(self):return {}


@contextmanager
def _trace(host,operation,target,name):
    from war3_game_session import GameSession
    if not isinstance(getattr(host,'_game_session',None),GameSession):
        yield _SilentTrace();return
    from war3_backend import Win10ReadLogger
    from war3_services.operation_trace import BackpackTrace
    class TalentLoadoutTrace(BackpackTrace):
        prefix='loadout-talents';event_name='loadout_talent_phase'
        source_inputs=('loadout_talents.py','facade_extensions.py')
    with TalentLoadoutTrace(host,Win10ReadLogger,dict(operation=operation,target_unit=target,name=name)) as trace:
        yield trace


def _reason(exc):
    from war3_error_messages import describe_error
    value=describe_error(exc)
    return value['reason'],value['category']


def _display_source(snapshot):
    return deepcopy({key:snapshot.get(key) for key in
        ('target_unit','abilities','bag_size','bag','equipment','talent_definitions')})


def remember_display_state(snapshot,state):
    """Presentation-only readback of this request, never a mutation cache."""
    snapshot['loadout_talent_display_state']=dict(source=_display_source(snapshot),state=deepcopy(state))
    snapshot.pop('loadout_talent_display_error',None)


def display_state(snapshot):
    value=snapshot.get('loadout_talent_display_state')
    if value is None:return None
    if value.get('source')!=_display_source(snapshot):
        raise RuntimeError('天赋显示快照与本次英雄或装备不一致，请重新读取扩展状态')
    return deepcopy(value['state'])


def prepare_display_state(host,snapshot):
    """Capture while the per-hero binding is active, before returning to UI."""
    if snapshot.get('loadout_talent_display_state') or not hasattr(host,'talent_state_24268'):return
    try:
        remember_display_state(snapshot,host.talent_state_24268(snapshot))
    except Exception as exc:
        snapshot['loadout_talent_display_error']=dict(message=str(exc),report=getattr(exc,'report',None))


def capture_talents(host,snapshot,name):
    """A failed optional read must not discard an otherwise valid gear plan."""
    result=dict(operation='save',status='not_present',succeeded=0,already=0,skipped=[])
    with _trace(host,'save',int(snapshot['target_unit']),name) as trace:
        try:
            session=getattr(host,'_game_session',None);epoch=getattr(session,'epoch',None)
            state=host.talent_state_24268(snapshot)
            remember_display_state(snapshot,state)
            if getattr(session,'epoch',None)!=epoch:raise RuntimeError('保存天赋期间地图发生变化')
            trace.record('read',state=state)
            if not state['controller']:
                if state.get('anomalies'):raise RuntimeError('；'.join(state['anomalies']))
                snapshot['loadout_talents']=result
                return None,''
            if state.get('point_source')!='ATal+0x11c':
                raise RuntimeError('没有读到真实天赋点数，本次只保存装备')
            rows=[]
            for row in state['tiers']:
                native=row.get('native_choice','')
                if row.get('native_record_present') and not native:
                    raise RuntimeError(f"第 {int(row['index'])+1} 层原生天赋记录无法识别，本次只保存装备")
                effects=[]
                for code in row['selected']:
                    rank=snapshot.get('abilities',{}).get(int.from_bytes(code.encode('ascii'),'big'),0)
                    effects.append(dict(rawcode=code,level=rank))
                rows.append(dict(choices=list(row['choices']),native_choice=native,selected=effects))
            data=validate_talents(dict(controller=state['controller'],controller_level=state['controller_level'],
                remaining_points=state['remaining_points'],tiers=rows))
            result.update(status='saved',succeeded=sum(len(r['selected']) for r in rows),remaining_points=data['remaining_points'])
            snapshot['loadout_talents']=result;trace.record('saved',talents=data,result=result)
            return data,''
        except Exception as exc:
            reason,category=_reason(exc)
            from war3_error_messages import describe_error
            result.update(status='skipped',skipped=[dict(phase='read',reason=reason,category=category,
                reason_en=describe_error(exc,'en')['reason'])])
            snapshot['loadout_talents']=result
            trace.record('capture_skipped',reason=str(exc),execution_report=getattr(exc,'report',None),result=result)
            return None,reason
        finally:
            result['operation_trace']=trace.summary()
            trace.result_summary=result['operation_trace']


class _TargetChanged(RuntimeError):pass


class _Guard:
    def __init__(self,host,snapshot):
        from war3_game_session import GameSession,ObjectAddress
        self.host=host;self.target=int(snapshot['target_unit'])
        session=getattr(host,'_game_session',None)
        self.session=session if isinstance(session,GameSession) else None
        self.original_inventory=deepcopy({k:snapshot[k] for k in ('bag_size','bag','equipment')})
        self.epoch=getattr(session,'epoch',None);self.ref=None
        if self.session is not None:
            self.engine=host._engine_instance_24268()
            from war3_services.talent_definitions import bound_target
            with bound_target(host,snapshot,self.engine) as (memory,registry,candidate,_profile):
                self.ref=session.bind_unit(memory,registry,ObjectAddress(candidate.unit_address))
        elif getattr(host,'pid',0):
            raise _TargetChanged('天赋恢复缺少已验证的游戏会话，已跳过天赋')

    def check(self,snapshot):
        if int(snapshot.get('target_unit',0))!=self.target:
            raise _TargetChanged('天赋恢复目标已经变化，已停止后续天赋操作')
        if any(snapshot.get(k)!=v for k,v in self.original_inventory.items()):
            raise _TargetChanged('天赋恢复期间背包或装备发生变化，已保留物品并停止后续天赋操作')
        if self.session is not None:
            from war3_game_session import NativeHandle
            if self.session.epoch!=self.epoch:raise _TargetChanged('天赋恢复期间地图发生变化，已停止后续天赋操作')
            try:
                self.session.require_write()
                # A batch can keep several heroes selected. Validate this
                # exact object's membership, without requiring it to be the
                # only selected unit. Full identity checks remain mandatory.
                if self.engine.bind_unit_refs((self.ref,),strict_selection=False)!=((NativeHandle(self.target),self.ref),):
                    raise _TargetChanged('天赋恢复期间英雄身份发生变化，已停止后续天赋操作')
            except Exception as exc:raise _TargetChanged(str(exc)) from exc


def restore_talents(host,saved,completed_equipment):
    """Restore native selections and every additional same-tier effect independently."""
    from war3_game_session import GameSession,session_scope
    report=dict(operation='restore',status='not_saved',succeeded=0,already=0,skipped=[],points_granted=0)
    result=completed_equipment
    data=saved.get('talents')
    if data is None:
        if saved.get('talent_capture_error'):
            report.update(status='skipped',skipped=[dict(phase='saved_read',reason=saved['talent_capture_error'],
                reason_en='Talents could not be read when this plan was saved. Save it again to include talents.')])
        prepare_display_state(host,result)
        result['loadout_talents']=report;return result
    target=int(result['target_unit']);session=getattr(host,'_game_session',None)
    lock=session.lock if isinstance(session,GameSession) else nullcontext()
    scope=session_scope(session) if isinstance(session,GameSession) else nullcontext()
    with _trace(host,'restore',target,saved.get('name','')) as trace,lock,scope:
        try:
            data=validate_talents(data);guard=_Guard(host,result)
            current=result;live_state=None;definition_signature=None
            def read():
                nonlocal current,live_state,definition_signature
                fresh=host.extension_snapshot_24268(target)
                guard.check(fresh)
                state=host.talent_state_24268(fresh)
                remember_display_state(fresh,state)
                if state['controller']!=data['controller']:
                    raise _TargetChanged('当前英雄的天赋树与方案不同，已跳过天赋并保留装备')
                if state.get('point_source')!='ATal+0x11c':
                    raise _TargetChanged('没有读到真实天赋点数，已跳过天赋并保留装备')
                signature=tuple(tuple(row['choices']) for row in state['tiers'])
                if definition_signature is not None and signature!=definition_signature:
                    raise _TargetChanged('天赋恢复期间选项定义发生变化，已停止后续天赋操作')
                definition_signature=signature;current=fresh;live_state=state
                return state
            def skip(phase,tier=-1,code='',exc=None,reason=''):
                category='validation'
                if exc is not None:reason,category=_reason(exc)
                from war3_error_messages import describe_error
                english=describe_error(exc,'en')['reason'] if exc else {
                    'definition':'The options in this tier differ from the saved plan; this tier was skipped.',
                    'native_choice':'The native selection conflicts with this tier or no point is available; the existing state was retained.',
                }.get(phase,'This optional talent step was skipped; other verified steps continued.')
                row=dict(phase=phase,tier=tier,rawcode=code,reason=reason,reason_en=english,category=category)
                report['skipped'].append(row)
                trace.record('skipped',entry=row,exception=str(exc) if exc else '',execution_report=getattr(exc,'report',None))
            def run(phase,tier,code,callback,verified):
                try:
                    guard.check(current)
                    trace.record('step_begin',step=phase,tier=tier,rawcode=code,
                        before_state=live_state,saved=data,automatic_replay=False)
                    callback();state=read()
                    if not verified(state):raise RuntimeError('天赋操作后的实际读回与方案不一致')
                    trace.record('step_verified',step=phase,tier=tier,rawcode=code,after_state=state,
                        effect_level=int(current.get('abilities',{}).get(int.from_bytes(code.encode('ascii'),'big'),0)) if code else None)
                    return state
                except _TargetChanged:raise
                except Exception as exc:
                    skip(phase,tier,code,exc=exc)
                    # No replay. A fresh read revalidates the next independent
                    # operation and observes any partial/completed mutation.
                    read()
                    return None
            state=read();trace.record('before',saved=data,state=state)
            valid=[]
            for index,row in enumerate(data['tiers']):
                if index>=len(state['tiers']) or tuple(row['choices'])!=tuple(state['tiers'][index]['choices']):
                    skip('definition',index,reason='当前地图这一层的天赋选项与方案不同，已跳过该层')
                else:valid.append(index)
            if valid and int(state['controller_level'])<data['controller_level']:
                run('controller_level',-1,data['controller'],
                    lambda:host.ability_batch_24268(data['controller'],3,data['controller_level'],target_unit=target),
                    lambda s:int(s['controller_level'])>=data['controller_level'])
                state=live_state
            missing_native=sum(bool(data['tiers'][i]['native_choice']) and
                not state['tiers'][i].get('native_record_present') and
                data['tiers'][i]['native_choice'] not in state['tiers'][i]['selected'] for i in valid)
            target_points=data['remaining_points']+missing_native
            if not valid:target_points=int(state['remaining_points'])
            cap=sum(len(row['choices']) for row in state['tiers'])
            for _ in range(min(max(0,target_points-int(state['remaining_points'])),cap)):
                previous=int(state['remaining_points'])
                outcome=run('points',-1,'',lambda:host.grant_talent_point_24268(target_unit=target),
                    lambda s:int(s['remaining_points'])==previous+1)
                state=live_state
                if outcome is None:break
                report['points_granted']+=1
            for index in valid:
                row=data['tiers'][index];native=row['native_choice']
                if native:
                    state=live_state;live=state['tiers'][index]
                    if live.get('native_choice')==native:report['already']+=1
                    elif live.get('native_record_present'):
                        skip('native_choice',index,native,reason='这一层已原生选择其他天赋，已保留现有选择并跳过冲突项')
                    elif native in live['selected']:
                        # The native order helper intentionally does not issue
                        # an order for an effect that already exists. Removing
                        # it here would discard user state; retain it instead.
                        skip('native_choice',index,native,reason='这一层已有效果但缺少原生选择记录；已保留效果，跳过原生登记')
                    elif int(state['remaining_points'])<1:
                        skip('native_choice',index,native,reason='当前可用天赋点不足，已跳过原生选择')
                    elif run('native_choice',index,native,
                            lambda:host.select_native_talent_24268(data['controller'],index,native,target_unit=target),
                            lambda s:s['tiers'][index].get('native_choice')==native) is not None:
                        report['succeeded']+=1
                for effect in row['selected']:
                    code=effect['rawcode'];rank=effect['level'];state=live_state
                    level=int(current.get('abilities',{}).get(int.from_bytes(code.encode('ascii'),'big'),0))
                    if code==native:
                        if state['tiers'][index].get('native_choice')!=native:continue
                    elif level>=rank:
                        report['already']+=1;continue
                    else:
                        if not level:
                            outcome=run('extra_choice',index,code,
                                lambda:host.add_talent_choice_24268(data['controller'],index,code,target_unit=target),
                                lambda s:code in s['tiers'][index]['selected'])
                            if outcome is None:continue
                            level=int(current.get('abilities',{}).get(int.from_bytes(code.encode('ascii'),'big'),0))
                        if level>=rank:report['succeeded']+=1;continue
                    if level<rank:
                        outcome=run('effect_level',index,code,
                            lambda:host.ability_batch_24268(code,3,rank,target_unit=target),
                            lambda s:int(current.get('abilities',{}).get(int.from_bytes(code.encode('ascii'),'big'),0))>=rank)
                        if outcome is not None and code!=native:report['succeeded']+=1
            state=read()
            for index in valid:
                for effect in data['tiers'][index]['selected']:
                    code=effect['rawcode']
                    if int(current.get('abilities',{}).get(int.from_bytes(code.encode('ascii'),'big'),0))<effect['level']:
                        if not any(e.get('rawcode')==code and e.get('tier')==index for e in report['skipped']):
                            skip('final_readback',index,code,reason='恢复结束时该天赋效果或等级未吻合，已保留其余恢复结果')
            if state['remaining_points']<data['remaining_points'] and not any(e['phase']=='points' for e in report['skipped']):
                skip('points',reason='剩余天赋点尚未恢复到方案值，已保留完成的天赋')
            report.update(status='partial' if report['skipped'] else 'restored',remaining_points=state['remaining_points'],
                saved_remaining_points=data['remaining_points'],points_preserved=int(state['remaining_points'])>data['remaining_points'])
            # Copy all completed equipment diagnostics into the fresh snapshot.
            for key,value in completed_equipment.items():
                if key.startswith('loadout_'):current[key]=value
            result=current
        except Exception as exc:
            reason,category=_reason(exc)
            from war3_error_messages import describe_error
            report['skipped'].append(dict(phase='stopped',reason=reason,category=category,
                reason_en=describe_error(exc,'en')['reason']))
            report['status']='partial' if report['succeeded'] else 'skipped'
            report['state_unavailable']=True
            if 'current' in locals():
                for key,value in completed_equipment.items():
                    if key.startswith('loadout_'):current[key]=value
                result=current
            trace.record('stopped',exception=str(exc),execution_report=getattr(exc,'report',None),result=report)
        trace.record('complete',result=report,equipment_retained=True,automatic_replay=False)
        report['operation_trace']=trace.summary();result['loadout_talents']=report
        trace.result_summary=report['operation_trace']
    return result


def result_messages(snapshot,language='zh'):
    """One summary/dialog for a single plan or an entire multi-hero request."""
    reports=snapshot.get('loadout_batch',{}).get('talents',())
    if not reports and snapshot.get('loadout_talents') is not None:
        reports=((snapshot.get('target_unit',0),snapshot['loadout_talents']),)
    if not reports:return '',''
    english=language=='en'
    done=sum(r.get('succeeded',0) for _,r in reports);already=sum(r.get('already',0) for _,r in reports)
    issues=[(unit,r,entry) for unit,r in reports for entry in r.get('skipped',())]
    saving=all(r.get('operation')=='save' for _,r in reports)
    available=any(r.get('status') not in ('not_present','not_saved') for _,r in reports)
    if not available:
        return (('No talents in this plan; save it again to include the current talents.' if english else
                 '方案未含天赋；重新保存可带上当前天赋。') if not saving else ''),''
    summary=(f'Talents saved: {done}; skipped steps: {len(issues)}.' if saving else
             f'Talents restored: {done}; already present: {already}; skipped steps: {len(issues)}.') if english else (
             f'天赋已保存 {done} 项及点数；跳过 {len(issues)} 项。' if saving else
             f'天赋恢复 {done} 项，已有 {already} 项，跳过 {len(issues)} 项。')
    if not issues:return summary,''
    lines=[('Equipment plans were saved; unavailable talents were skipped.' if saving else
            'Completed equipment operations were retained. The following talent steps were skipped.') if english else
           ('装备方案已保存，未能读取的天赋已跳过。' if saving else
            '已完成的装备操作均已保留；以下天赋项未能恢复，已跳过。')]
    for unit,report,entry in issues[:12]:
        tier=entry.get('tier',-1);code=entry.get('rawcode','')
        prefix=(f'Hero {unit}' if english else f'英雄 {unit}')
        if tier>=0:prefix+=(f', tier {tier+1}' if english else f'，第 {tier+1} 层')
        if code:prefix+=' '+code
        lines.append(prefix+': '+(entry.get('reason_en',entry['reason']) if english else entry['reason']))
    paths=tuple(dict.fromkeys(r.get('operation_trace',{}).get('log_path') for _,r in reports
                             if r.get('operation_trace',{}).get('log_path')))
    if paths:lines.append(('Detailed log: ' if english else '详细日志：')+paths[0])
    return summary,'\n\n'.join(lines)
