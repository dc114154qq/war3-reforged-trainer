"""Verify world-group membership of a JASS unit after the prior callback completed."""
import argparse,json,os,runpy,sys,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from war3_reforged_trainer import ProcessMemory,find_war3
from war3_object_registry import ObjectRegistry24268
from war3_thread_context import GameThreadContext24268
from war3_native_table import NativeTable24268
from war3_native_preflight import inspect_entries
from war3_lifecycle_protocol import MEMBERSHIP_SIGNATURES,build_membership,decode_membership

def run(pid,image,unit):
    hwnd,pid=find_war3(pid)
    with ProcessMemory(pid) as m:
        registry=ObjectRegistry24268.attach(m);context=GameThreadContext24268(m,registry.base,hwnd,pid)
        mode=context.read_mode(m);context5=m.read_u64(mode.tls+0x38)
        entries=NativeTable24268(m,context5).require(*(n for n,_ in MEMBERSHIP_SIGNATURES))
        work=build_membership(entries,unit,mode.tls)
        mappings=inspect_entries(m,registry.base,entries,True)
        fresh=context.read_mode(m)
        if (fresh.tls!=mode.tls or fresh.value!=mode.value or m.read_u64(fresh.tls+0x38)!=context5
            or NativeTable24268(m,context5).require(*entries)!=entries):raise ValueError('Membership context changed')
        evidence=runpy.run_path(str(ROOT/'analysis/verify-game-thread-dispatch.py'))['inspect'](
            pid,hwnd,mode.thread_id,image.resolve(),query_mode='unit_membership',
            tls_index=mode.tls_index,work_payload=work)
    result=dict(pid=pid,unit=unit,mappings=mappings,dispatch=evidence,ok=False)
    if evidence.get('query_completed') and evidence.get('work_result_hex'):
        try: result['membership']=decode_membership(bytes.fromhex(evidence['work_result_hex']))
        except ValueError as exc:
            result['decode_error']=str(exc)
            return result
        result['ok']=bool(evidence.get('callback_verified') and evidence.get('work_freed') and
            evidence.get('block_freed') and evidence.get('image_unmap_status')=='0x0')
    return result

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--pid',type=int,required=True)
    ap.add_argument('--image',type=Path,required=True);ap.add_argument('--unit',type=lambda s:int(s,0),required=True)
    ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    try:r=run(args.pid,args.image,args.unit)
    except Exception:r=dict(ok=False,error=traceback.format_exc())
    tmp=args.output.with_suffix('.tmp');tmp.write_text(json.dumps(r,indent=2));os.replace(tmp,args.output)
    print(json.dumps({k:v for k,v in r.items() if k not in ('dispatch','mappings')}))
    return 0 if r['ok'] else 1
if __name__=='__main__':raise SystemExit(main())
