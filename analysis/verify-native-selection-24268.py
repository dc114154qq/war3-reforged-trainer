"""Build fresh selection arguments from the target; optionally dispatch once."""
import argparse
import json
import os
from pathlib import Path
import runpy
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from war3_reforged_trainer import ProcessMemory, find_war3
from war3_object_registry import ObjectRegistry24268
from war3_thread_context import GameThreadContext24268
from war3_native_table import NativeTable24268
from war3_selection_protocol import SIGNATURES, build_work, decode_work
from war3_native_preflight import inspect_entries


def run(pid, image, preflight_only, allow_image_noaccess=False, probe_local_player=False, delivery_mode="sent"):
    hwnd, pid = find_war3(pid)
    with ProcessMemory(pid) as memory:
        registry = ObjectRegistry24268.attach(memory)
        context = GameThreadContext24268(memory, registry.base, hwnd, pid)
        mode = context.read_mode(memory)
        # Require a valid current player and map before constructing callbacks.
        player = registry.local_player_for_mode(memory, mode.value)
        context5 = memory.read_u64(mode.tls + 0x38)
        table = NativeTable24268(memory, context5)
        entries = table.require(*(name for name, _ in SIGNATURES))
        payload = build_work(entries)
        checked = {'GetLocalPlayer': entries['GetLocalPlayer']} if probe_local_player else entries
        mappings = inspect_entries(memory, registry.base, checked, allow_image_noaccess)
        fresh = context.read_mode(memory)
        if (fresh.tls != mode.tls or fresh.value != mode.value
                or memory.read_u64(fresh.tls + 0x38) != context5):
            raise RuntimeError('Native context changed during preflight')
        current = NativeTable24268(memory, context5).require(*entries)
        if current != entries or inspect_entries(memory, registry.base, checked, allow_image_noaccess) != mappings:
            raise RuntimeError('Native registrations changed during preflight')
        result = dict(pid=pid, preflight_only=preflight_only, player_object=hex(player),
                      tls_index=mode.tls_index, thread_id=mode.thread_id,
                      work_size=len(payload), mappings=mappings, probe_local_player=probe_local_player, signatures={n: e.signature for n, e in entries.items()})
        if preflight_only:
            return dict(result, ok=True, game_handlers_called=False)
        dispatch = runpy.run_path(str(ROOT / 'analysis/verify-game-thread-dispatch.py'))
        if probe_local_player:
            evidence = dispatch['inspect'](pid, hwnd, mode.thread_id, image.resolve(),
                query_mode='native', tls_index=mode.tls_index,
                native_address=entries['GetLocalPlayer'].handler,delivery_mode=delivery_mode)
            state = evidence.get('after_send', {})
            result['dispatch'] = evidence
            result['player_handle'] = state.get('query_result')
            return dict(result, ok=bool(evidence.get('callback_verified')
                and evidence.get('query_completed') and evidence.get('block_freed')
                and evidence.get('image_unmap_status') == '0x0'
                and state.get('tls_value') == hex(mode.tls)
                and 0 < int(state.get('query_result', '0'), 16) <= 0xffffffff))
        evidence = dispatch['inspect'](pid, hwnd, mode.thread_id, image.resolve(),
                                       query_mode='selection', tls_index=mode.tls_index,
                                       work_payload=payload,delivery_mode=delivery_mode)
        result['dispatch'] = evidence
        if not (evidence.get('callback_verified') and evidence.get('query_completed')
                and evidence.get('work_freed') and evidence.get('block_freed')
                and evidence.get('image_unmap_status') == '0x0'):
            return dict(result, ok=False)
        result['selection'] = decode_work(bytes.fromhex(evidence['work_result_hex']),
                                          int(evidence['after_send']['query_result'], 16))
        return dict(result, ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pid', type=int, required=True)
    parser.add_argument('--image', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--preflight-only', action='store_true')
    parser.add_argument('--allow-image-noaccess', action='store_true', help='Diagnostic opt-in for registered entries inside verified executable image sections; does not change protection')
    parser.add_argument('--probe-local-player', action='store_true', help='Call only GetLocalPlayer, without group allocation or game-data writes')
    parser.add_argument('--delivery-mode',choices=['sent','posted'],default='sent')
    args = parser.parse_args()
    start = time.perf_counter()
    try:
        result = run(args.pid, args.image, args.preflight_only, args.allow_image_noaccess, args.probe_local_player, args.delivery_mode)
    except Exception:
        result = dict(ok=False, pid=args.pid, error=traceback.format_exc())
    result['elapsed_ms'] = (time.perf_counter() - start) * 1000
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix('.tmp')
    temporary.write_text(json.dumps(result, indent=2), encoding='utf8')
    os.replace(temporary, args.output)
    print(json.dumps(dict(ok=result['ok'], output=str(args.output.resolve()),
                          elapsed_ms=result['elapsed_ms'])))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
