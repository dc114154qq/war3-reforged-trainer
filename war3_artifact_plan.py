"""Six inventory codes and per-user persistence; no UI or game access."""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import tempfile
import threading


# Display order is inventory slots 1..6. Execution retains the original 6..1
# order so the default request is identical to the published fixed preset.
DEFAULT_ARTIFACT_CODES = ('klmm', 'srtl', 'shdt', 'crdt', 'frhg', 'nspi')


class ArtifactPlanError(ValueError):
    def __init__(self, reason, *, slot=None, path=None):
        self.reason, self.slot, self.path = reason, slot, path
        super().__init__(self.message('zh'))

    def message(self, language='zh'):
        english = language == 'en'
        if self.reason == 'code':
            return (f'Slot {self.slot}: enter a four-character item code (case-sensitive).'
                    if english else f'槽位 {self.slot}：请填写4位物品代码，区分大小写。')
        if self.reason == 'save':
            return (f'The plan was not saved. Check that this file is writable: {self.path}'
                    if english else f'方案尚未保存，请检查配置文件是否可写：{self.path}')
        if self.reason == 'load':
            return (f'The saved plan could not be read. Edit the plan or restore defaults before applying. The original file is preserved: {self.path}'
                    if english else f'已保存的方案读取失败，请修改方案或恢复默认后再执行。当前显示默认方案，原文件已保留：{self.path}')
        return ('The plan must contain six item codes.' if english else '装备方案需要填写六个物品代码。')


@dataclass(frozen=True)
class ArtifactPlan:
    codes: tuple[str, ...] = DEFAULT_ARTIFACT_CODES

    def __post_init__(self):
        if not isinstance(self.codes, (tuple, list)) or len(self.codes) != 6:
            raise ArtifactPlanError('count')
        cleaned = []
        for slot, code in enumerate(self.codes, 1):
            if not isinstance(code, str):
                raise ArtifactPlanError('code', slot=slot)
            code = code.strip()
            if len(code) != 4 or any(not 33 <= ord(char) <= 126 for char in code):
                raise ArtifactPlanError('code', slot=slot)
            cleaned.append(code)
        object.__setattr__(self, 'codes', tuple(cleaned))

    @property
    def replacements(self):
        # Pass integer FourCC values so codes such as '0xAB' keep their exact
        # four bytes instead of being parsed as a hexadecimal numeric string.
        return tuple((slot, int.from_bytes(self.codes[slot].encode('ascii'), 'big'))
                     for slot in range(5, -1, -1))


def artifact_plan_path():
    return Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'War3Trainer' / 'preferences' / 'six-artifacts.json'


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate preference key')
        result[key] = value
    return result


class ArtifactPlanStore:
    def __init__(self, path=None):
        self.path = Path(path) if path is not None else artifact_plan_path()

    def load(self):
        try:
            with self.path.open('rb') as stream:
                raw = stream.read(4097)
        except FileNotFoundError:
            return ArtifactPlan(), False
        if len(raw) > 4096:
            raise ValueError('Artifact preference exceeds its size limit')
        data = json.loads(raw.decode('utf-8-sig'), object_pairs_hook=_unique_keys)
        if (not isinstance(data, dict) or set(data) != {'schema', 'codes'} or
                type(data['schema']) is not int or data['schema'] != 1):
            raise ValueError('Unsupported artifact preference schema')
        return ArtifactPlan(data['codes']), True

    def save(self, plan):
        if type(plan) is not ArtifactPlan:
            raise TypeError('Expected an immutable ArtifactPlan')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        pending = None
        try:
            fd, pending = tempfile.mkstemp(prefix=self.path.name + '.', suffix='.tmp', dir=self.path.parent)
            with os.fdopen(fd, 'w', encoding='utf8', newline='\n') as stream:
                json.dump(dict(schema=1, codes=plan.codes), stream, ensure_ascii=False, indent=2)
                stream.write('\n')
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(pending, self.path)
        finally:
            if pending is not None and os.path.exists(pending):
                os.unlink(pending)


class ArtifactPlanSettings:
    """Publish immutable saved snapshots to workers without touching Tk."""
    def __init__(self, store=None):
        self.store = store if store is not None else ArtifactPlanStore()
        self._lock = threading.RLock()
        self.error = None
        self.load_error = None
        try:
            self._plan, self.saved = self.store.load()
        except (OSError, ValueError, UnicodeError) as exc:
            self._plan, self.saved = ArtifactPlan(), False
            self.load_error = ArtifactPlanError('load', path=self.store.path)
            self.load_error.__cause__ = exc

    @property
    def displayed_plan(self):
        with self._lock:
            return self._plan

    def update(self, codes):
        with self._lock:
            try:
                plan = ArtifactPlan(codes)
                if plan != self._plan or not self.saved:
                    try:
                        self.store.save(plan)
                    except OSError as exc:
                        raise ArtifactPlanError('save', path=self.store.path) from exc
            except ArtifactPlanError as exc:
                self.error = exc
                raise
            self._plan, self.saved = plan, True
            self.error = self.load_error = None
            return plan

    def snapshot(self):
        with self._lock:
            error = self.error or self.load_error
            if error is not None:
                raise ArtifactPlanError(error.reason, slot=error.slot, path=error.path) from error
            return self._plan
