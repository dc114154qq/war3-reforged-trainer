"""Copy up to 384 bytes of named registered native entries on the current game thread."""
import argparse,json,os,runpy,sys,struct,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from capstone import Cs,CS_ARCH_X86,CS_MODE_64
from war3_reforged_trainer import ProcessMemory,find_war3
from war3_object_registry import ObjectRegistry24268
from war3_thread_context import GameThreadContext24268
from war3_native_table import NativeTable24268
from war3_native_preflight import inspect_entries
from war3_code_observation import inspect_code_observation

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--pid',type=int,required=True)
    ap.add_argument('--image',type=Path,required=True);ap.add_argument('--names',nargs='+',required=True)
    ap.add_argument('--output',type=Path,required=True);args=ap.parse_args();result=dict(ok=False,entries={})
    try:
        hwnd,pid=find_war3(args.pid)
        dispatch=runpy.run_path(str(ROOT/'analysis/verify-game-thread-dispatch.py'))['inspect']
        with ProcessMemory(pid) as m:
            registry=ObjectRegistry24268.attach(m);ctx=GameThreadContext24268(m,registry.base,hwnd,pid)
            for name in args.names:
                mode=ctx.read_mode(m);context5=m.read_u64(mode.tls+0x38)
                entries=NativeTable24268(m,context5).require(name)
                mapping=inspect_entries(m,registry.base,entries,True,span=384)
                if NativeTable24268(m,context5).require(name)!=entries:raise ValueError('Native entry changed')
                address=entries[name].handler
                payload=struct.pack('<2Q2I',address,mode.tls,384,0)+bytes(384)
                d=dispatch(pid,hwnd,mode.thread_id,args.image.resolve(),query_mode='code_read',
                    tls_index=mode.tls_index,work_payload=payload)
                row=dict(address=hex(address),signature=entries[name].signature,mapping=mapping,dispatch=d)
                result['entries'][name]=row
                if not (d.get('callback_verified') and d.get('query_completed') and d.get('work_freed') and d.get('block_freed') and d.get('image_unmap_status')=='0x0'):
                    raise ValueError('Code query or cleanup failed: '+name)
                work=bytes.fromhex(d['work_result_hex']);copied=struct.unpack_from('<I',work,20)[0]
                if copied!=384:raise ValueError('Incomplete code copy')
                row['code_hex']=work[24:].hex()
                row.update(inspect_code_observation(payload,work))
                row['disasm']=[f'{i.address:x} {i.mnemonic} {i.op_str}' for i in Cs(CS_ARCH_X86,CS_MODE_64).disasm(work[24:],address)]
            result['ok']=True
    except Exception:result['error']=traceback.format_exc()
    finally:
        tmp=args.output.with_suffix('.tmp');tmp.write_text(json.dumps(result,indent=2));os.replace(tmp,args.output)
    print(json.dumps(dict(ok=result['ok'],output=str(args.output),error=result.get('error'))))
    return 0 if result['ok'] else 1
if __name__=='__main__':raise SystemExit(main())
