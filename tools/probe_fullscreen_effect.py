"""Read-only enemy/callback evidence using the diagnostic bridge."""
import argparse
import json
import struct
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from war3_reforged_trainer import War3Trainer
from war3_world_effect_protocol import SIGNATURES, build_work


def snapshot(engine, nearest=False):
    def decode(data, _count):
        count = struct.unpack_from('<I', data, 644)[0]
        rows = []
        for index in range(min(count, 20 if nearest else 24)):
            unit, life, x, y = struct.unpack_from('<Q3f', data, index * 20)
            rows.append(dict(unit=unit, life=life, x=x, y=y))
        error = struct.unpack_from('<I', data, 640)[0]
        if error:
            raise RuntimeError(f'Diagnostic snapshot failed: {error}')
        return dict(source=struct.unpack_from('<I', data, 624)[0], count=count, rows=rows)
    return engine._execute('world_effect', tuple(n for n, _ in SIGNATURES),
        lambda entries, tls: build_work(entries, tls, 0xfffffffd if nearest else 0xffffffff, 1,
            resolver=engine._effect_resolver), decode, dict(read_only=True))


def read_callback(engine, address):
    def build(entries, tls):
        data = bytearray(build_work(entries, tls, 0xfffffffe, 1, resolver=engine._effect_resolver))
        struct.pack_into('<Q', data, 504, address)
        return bytes(data)
    def decode(data, _count):
        error = struct.unpack_from('<I', data, 640)[0]
        if error:
            raise RuntimeError(f'Code read failed: {error}')
        return data[:128].hex()
    return engine._execute('world_effect', tuple(n for n, _ in SIGNATURES),
        build, decode, dict(read_only=True, address=hex(address)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pid', type=int, required=True)
    parser.add_argument('--image', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cast', choices=('ANmo', 'AHtc'))
    parser.add_argument('--inspect', action='store_true')
    parser.add_argument('--wide', action='store_true')
    parser.add_argument('--nearest', action='store_true')
    parser.add_argument('--hold-seconds', type=float, default=4)
    args = parser.parse_args()
    trainer = War3Trainer(args.pid)
    try:
        engine = trainer._engine_instance_24268()
        engine.image = args.image.resolve()
        result = dict(image=str(engine.image), snapshot=snapshot(engine, args.nearest), session=engine.session.snapshot())
        if args.cast:
            before = {r['unit']: r['life'] for r in result['snapshot']['rows']}
            code = int.from_bytes(args.cast.encode('ascii'), 'big')
            state = None
            try:
                state = engine.direct_cast(code, 1, mode=3 if args.cast == 'ANmo' else 4)
                result['start'] = state
                if args.inspect:
                    from capstone import Cs, CS_ARCH_X86, CS_MODE_64
                    from war3_game_profile import profile_scope
                    callbacks = {}
                    with profile_scope(engine.session.profile), engine.memory_factory(engine.pid) as memory:
                        table = memory.read_u64(state['ability_data'])
                        slots = range(0x900, 0xd00, 8) if args.wide else (0x998, 0x9a0, 0xa38, 0xa50, 0xa58, 0xa60, 0xa70, 0xa78)
                        cache = {}
                        for slot in slots:
                            address = memory.read_u64(table+slot)
                            if address in cache:
                                callbacks[hex(slot)] = dict(address=hex(address), same_as=cache[address])
                                continue
                            cache[address] = hex(slot)
                            try:
                                code_hex = read_callback(engine, address)
                                instructions = []
                                for ins in Cs(CS_ARCH_X86, CS_MODE_64).disasm(bytes.fromhex(code_hex), address):
                                    instructions.append(f'{ins.address:x} {ins.mnemonic} {ins.op_str}')
                                    if ins.mnemonic == 'ret':
                                        break
                                callbacks[hex(slot)] = dict(address=hex(address), code=code_hex, instructions=instructions)
                            except Exception as exc:
                                callbacks[hex(slot)] = dict(address=hex(address), error=str(exc))
                    result['callbacks'] = callbacks
                time.sleep(args.hold_seconds)
                result['during'] = snapshot(engine, args.nearest)
                result['state'] = engine.direct_cast(code, 3, mode=state['mode'], state=state)
            finally:
                if state is not None:
                    result['cleanup'] = engine.direct_cast(code, 2, mode=state['mode'], state=state)
            result['life_changes'] = [dict(unit=r['unit'], before=before[r['unit']], after=r['life'])
                for r in result['during']['rows'] if r['unit'] in before and r['life'] != before[r['unit']]]
        args.output.parent.mkdir(parents=True, exist_ok=True)
        pending = args.output.with_suffix('.tmp')
        pending.write_text(json.dumps(result, indent=2), encoding='utf-8')
        pending.replace(args.output)
        summary = {k: result[k] for k in ('image', 'start', 'state', 'life_changes', 'cleanup') if k in result}
        if args.inspect:
            summary['callback_candidates'] = {slot: row for slot,row in result['callbacks'].items()
                if any('movss' in ins or 'movsd' in ins or '[r8]' in ins or '[rdx]' in ins
                    for ins in row.get('instructions',()))}
        print(json.dumps(summary if args.cast else result['snapshot']))
    finally:
        trainer.close()


if __name__ == '__main__':
    main()
