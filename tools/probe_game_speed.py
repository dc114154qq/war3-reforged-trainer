"""Exercise native tiers and restore the initial speed even after a failed tier."""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from war3_reforged_trainer import War3Trainer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pid', type=int, required=True)
    parser.add_argument('--image', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    trainer = War3Trainer(args.pid)
    engine = trainer._engine_instance_24268()
    engine.image = args.image.resolve()
    result = {'tiers': []}
    original = None
    timer = None
    from war3_world_effect_protocol import SIGNATURES as EFFECT_SIGNATURES, build_work
    import struct
    timer_signatures = (('CreateTimer', '()Htimer;'), ('TimerStart', '(Htimer;RBC)V'),
                        ('TimerGetElapsed', '(Htimer;)R'), ('DestroyTimer', '(Htimer;)V'))
    def timer_action(action):
        def build(entries, tls):
            payload = bytearray(build_work(entries, tls, 0xfffffff9, 1,
                success_limit=action, resolver=engine._effect_resolver))
            for offset, (name, signature) in zip((480,496,504,512), timer_signatures):
                if entries[name].signature != signature:
                    raise ValueError('Timer ABI differs: '+name)
                struct.pack_into('<Q', payload, offset, entries[name].handler)
            if timer is not None:
                struct.pack_into('<Q', payload, 488, timer)
            return bytes(payload)
        def decode(payload, _count):
            error = struct.unpack_from('<I', payload, 640)[0]
            if error:
                raise RuntimeError(f'Timer diagnostic failed: {error}')
            if action==0:
                return struct.unpack_from('<Q', payload, 32)[0]
            if action==1:
                return struct.unpack_from('<f', payload, 624)[0]
        return engine._execute('world_effect', tuple(n for n,_ in EFFECT_SIGNATURES+timer_signatures),
            build, decode, {'diagnostic_timer':action})
    def measure():
        before = timer_action(1)
        started = time.perf_counter()
        time.sleep(1)
        after = timer_action(1)
        return {'game_seconds':after-before, 'wall_seconds':time.perf_counter()-started}
    try:
        result['before'] = engine.game_speed()
        original = result['before']['after']
        timer = timer_action(0)
        for tier in range(5):
            row = {'target': tier}
            try:
                row['set'] = engine.game_speed(1, tier)
                time.sleep(0.25)
                row['readback'] = engine.game_speed()
            except Exception as exc:
                row['error'] = str(exc).split('; engine24268=')[0]
                row['report'] = getattr(exc, 'report', {})
            row['timing'] = measure()
            result['tiers'].append(row)
    finally:
        try:
            if timer is not None:
                timer_action(2)
            if original is not None:
                result['restored'] = engine.game_speed(1, original)
        except Exception as exc:
            result['restore_error'] = str(exc)
        trainer.close()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        pending = args.output.with_suffix('.tmp')
        pending.write_text(json.dumps(result, indent=2), encoding='utf-8')
        pending.replace(args.output)
    print(json.dumps({k: v for k, v in result.items() if k != 'tiers'}))
    for row in result['tiers']:
        print(json.dumps({k: v for k, v in row.items() if k != 'report'}))


if __name__ == '__main__':
    main()
