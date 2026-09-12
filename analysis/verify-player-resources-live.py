"""Read-only resource check against a running game; never writes player state."""
import dataclasses
import hashlib
import json
from pathlib import Path
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import war3_reforged_trainer as module

report = {'protocol': module.War3Trainer.NATIVE_HELPER_VERSION,
          'helper_sha256': hashlib.sha256((ROOT/'tools/war3_native_helper.dll').read_bytes()).hexdigest(),
          'read_only': True}
trainer = None
try:
    with patch.object(module.War3Trainer, '_start_persistent_bootstrap'), patch.object(
        module.War3Trainer, '_process_memory', side_effect=AssertionError('External memory backend forbidden')):
        trainer = module.War3Trainer(pid=int(sys.argv[1]))
        report['pid'] = trainer.pid
        start = time.perf_counter()
        caches = trainer.list_resource_caches()
        report['cold_list_seconds'] = time.perf_counter() - start
        local = trainer.locate_local_player_resource_cache(caches)
        start = time.perf_counter()
        warm = trainer.list_resource_caches()
        report['warm_list_seconds'] = time.perf_counter() - start
        assert len(caches) == len(warm) and len(caches) > 1
        assert len({c.player_value for c in caches}) == len(caches)
        assert local.player_value in {c.player_value for c in caches}
        report['local_player'] = local.player_value
        report['groups'] = [dataclasses.asdict(c) for c in warm]
        for slot in (0, 1, 12, 27):
            matches = [c for c in warm if c.player_value == slot]
            if matches:
                assert trainer.read_resource_cache_addresses(matches[0]).player_value == slot
        report['ok'] = True
except Exception as exc:
    report.update(ok=False, error=f'{type(exc).__name__}: {exc}')
finally:
    if trainer is not None:
        trainer.close()
    (ROOT/'analysis/player-resources-live.json').write_text(json.dumps(report, indent=2), encoding='utf8')
    print(json.dumps({k: v for k,v in report.items() if k != 'groups'}, indent=2), flush=True)
    if 'groups' in report: print('resource_group_count=', len(report['groups']), flush=True)
sys.exit(0 if report['ok'] else 1)
