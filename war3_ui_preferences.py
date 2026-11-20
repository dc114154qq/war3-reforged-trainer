"""Per-user desktop settings, separate from the game session and WebView cache."""
import json
import logging
import os
from pathlib import Path
import tempfile
from threading import RLock


_lock = RLock()
_logger = logging.getLogger(__name__)
DOWNLOAD_URL = 'https://twomengxi.xyz/'

ELEPHANT_INPUTS = frozenset({
    'hero_level', 'unit_scale', 'unit_rawcode', 'item_rawcode', 'ability_rawcode',
    'ability_level', 'tech_rawcode', 'tech_level', 'xp_rate', 'item_charges',
    'resource_amount', 'mass_clone_count', 'reinforcement_rawcode', 'preset_item_rawcode',
    'preset_tech_rawcode', 'hero_attributes', 'skill_points', 'reset_ability_rawcode',
    'auto_effect_count', 'game_speed',
})


def _preferences(data):
    if not isinstance(data, dict) or type(data.get('schema')) is not int or data['schema'] != 1:
        raise ValueError('Unsupported desktop preferences')
    result = {'schema': 1}
    for key in ('hotkeys_enabled', 'dark_mode'):
        if type(data.get(key)) is bool:
            result[key] = data[key]
    if data.get('language') in ('zh', 'en'):
        result['language'] = data['language']
    checks = data.get('hotkey_checks')
    if isinstance(checks, dict):
        result['hotkey_checks'] = {key: value for key, value in checks.items()
                                   if isinstance(key, str) and len(key) <= 64 and type(value) is bool}
    parameters = data.get('parameters')
    if isinstance(parameters, dict):
        result['parameters'] = {key: value for key, value in parameters.items()
                                if isinstance(key, str) and (key in ELEPHANT_INPUTS or key.startswith('stat_') and len(key) <= 64)
                                and isinstance(value, str) and len(value) <= 128}
    return result


class UiPreferenceStore:
    def __init__(self, path=None):
        local = Path(os.environ.get('LOCALAPPDATA') or Path.home() / 'AppData/Local')
        self.path = Path(path) if path is not None else local / 'War3Trainer/preferences/desktop.json'

    def load(self):
        try:
            with self.path.open('rb') as stream:
                raw = stream.read(65537)
            if len(raw) > 65536:
                raise ValueError('Desktop preferences are too large')
            return _preferences(json.loads(raw.decode('utf-8-sig')))
        except FileNotFoundError:
            return {'schema': 1}
        except (OSError, ValueError) as exc:
            _logger.warning('Could not read desktop preferences from %s: %s', self.path, exc)
            return {'schema': 1}

    def update(self, **changes):
        """Merge only explicitly changed settings and publish an atomic file."""
        with _lock:
            values = self.load()
            for key, value in changes.items():
                if key in ('hotkey_checks', 'parameters'):
                    values[key] = {**values.get(key, {}), **value}
                else:
                    values[key] = value
            values = _preferences(values)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, path = tempfile.mkstemp(prefix='desktop-', suffix='.tmp', dir=self.path.parent)
            pending = Path(path)
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                    json.dump(values, stream, ensure_ascii=False, indent=2)
                    stream.write('\n')
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(pending, self.path)
            finally:
                pending.unlink(missing_ok=True)
