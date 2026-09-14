"""Create one temporary hero from fresh selection, raise to level 2, remove it."""
import argparse,json,os,runpy,sys,time,traceback,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from war3_reforged_trainer import ProcessMemory,find_war3
from war3_object_registry import ObjectRegistry24268
from war3_thread_context import GameThreadContext24268
from war3_native_table import NativeTable24268
from war3_native_preflight import inspect_entries
from war3_lifecycle_protocol import SIGNATURES,build_work,decode_work

def run(pid,image):
    selection=runpy.run_path(str(ROOT/'analysis/verify-native-selection-24268.py'))['run'](pid,image,False,True)
    if not selection['ok']: return dict(ok=False,selection=selection)
    heroes=[r for r in selection['selection']['rows'] if r['level']>0]
    if not heroes: raise ValueError('No selected hero; no unit created')
    hero=heroes[0]
    hwnd,pid=find_war3(pid)
    with ProcessMemory(pid) as memory:
        registry=ObjectRegistry24268.attach(memory)
        context=GameThreadContext24268(memory,registry.base,hwnd,pid)
        mode=context.read_mode(memory)
        context5=memory.read_u64(mode.tls+0x38)
        entries=NativeTable24268(memory,context5).require(*(n for n,_ in SIGNATURES))
        payload=build_work(entries,hero['handle'],hero['rawcode'],2,mode.tls)
        mappings=inspect_entries(memory,registry.base,entries,True)
        fresh=context.read_mode(memory)
        if (fresh.tls!=mode.tls or fresh.value!=mode.value
            or memory.read_u64(fresh.tls+0x38)!=context5
            or NativeTable24268(memory,context5).require(*entries)!=entries):
            raise ValueError('Lifecycle context changed before dispatch')
        dispatch=runpy.run_path(str(ROOT/'analysis/verify-game-thread-dispatch.py'))['inspect']
        evidence=dispatch(pid,hwnd,mode.thread_id,image.resolve(),query_mode='unit_lifecycle',
                         tls_index=mode.tls_index,work_payload=payload)
    result=dict(pid=pid,source=hero,mappings=mappings,dispatch=evidence)
    if evidence.get('work_result_hex'):
        result['lifecycle']=decode_work(bytes.fromhex(evidence['work_result_hex']))
    transport_ok=bool(evidence.get('callback_verified') and evidence.get('query_completed')
        and evidence.get('work_freed') and evidence.get('block_freed')
        and evidence.get('image_unmap_status')=='0x0')
    result['ok']=False
    # RemoveUnit invalidation is deferred until the game resumes after callback.
    # A same-callback type read is telemetry, not proof of removal failure/success.
    if transport_ok and result.get('lifecycle',{}).get('mutation_verified'):
        time.sleep(0.05)
        with ProcessMemory(pid) as memory:
            registry=ObjectRegistry24268.attach(memory)
            context=GameThreadContext24268(memory,registry.base,hwnd,pid)
            followups=[]
            for label,unit in [('source',hero['handle']),('temporary',result['lifecycle']['created'])]:
                mode=context.read_mode(memory)
                current=NativeTable24268(memory,memory.read_u64(mode.tls+0x38)).require('GetUnitTypeId')
                if current['GetUnitTypeId'].signature!='(Hunit;)I':raise ValueError('Type query ABI differs')
                inspect_entries(memory,registry.base,current,True)
                after=dispatch(pid,hwnd,mode.thread_id,image.resolve(),query_mode='unit',tls_index=mode.tls_index,
                    work_payload=struct.pack('<2Q',current['GetUnitTypeId'].handler,unit))
                expected=hero['rawcode'] if label=='source' else 0
                valid=bool(after.get('callback_verified') and after.get('query_completed') and
                    after.get('work_freed') and after.get('block_freed') and after.get('image_unmap_status')=='0x0'
                    and after['after_send']['query_result']==hex(expected)
                    and after['after_send']['tls_value']==hex(mode.tls))
                followups.append(dict(label=label,ok=valid,dispatch=after))
            result['after_frame']=followups
            result['ok']=all(row['ok'] for row in followups)
    return result

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--pid',type=int,required=True);ap.add_argument('--image',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    start=time.perf_counter()
    try:r=run(args.pid,args.image)
    except Exception:r=dict(ok=False,pid=args.pid,error=traceback.format_exc())
    r['elapsed_ms']=(time.perf_counter()-start)*1000
    args.output.parent.mkdir(parents=True,exist_ok=True)
    tmp=args.output.with_suffix('.tmp');tmp.write_text(json.dumps(r,indent=2));os.replace(tmp,args.output)
    print(json.dumps(dict(ok=r['ok'],elapsed_ms=r['elapsed_ms'],output=str(args.output))))
    return 0 if r['ok'] else 1
if __name__=='__main__':raise SystemExit(main())
