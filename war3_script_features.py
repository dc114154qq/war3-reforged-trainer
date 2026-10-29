"""Immutable map-script options. No game process or desktop dependencies."""
from dataclasses import asdict, dataclass
from pathlib import Path
import json
import os
import re
import tempfile

FEATURES = {
    'resources': '资源与金矿', 'hero': '英雄成长与复活', 'units': '单位状态与移动',
    'abilities': '技能、光环与被动', 'items': '物品与六神器方案',
    'automatic': '自动回血、回魔与清冷却', 'world': '视野、时间与科技',
}
DEFAULT_CODES = ('klmm', 'srtl', 'shdt', 'crdt', 'frhg', 'nspi')
# These are protected identities, not dependencies or functionality added by this module.
PROTECTED_ABILITIES = ('AInv', 'AIni', 'AEqu', 'ASpc', 'ATug', 'ATua', 'ATui', 'ATul', 'ATuu')
PROTECTED_ITEMS = ('ebhg', 'ebhl', 'ebhi', 'ebug', 'ebua', 'ebul')


@dataclass(frozen=True)
class ScriptOptions:
    prefix: str = '-mx'
    features: tuple[str, ...] = tuple(FEATURES)
    artifact_codes: tuple[str, ...] = DEFAULT_CODES
    resource_amount: int = 10000

    def __post_init__(self):
        if not isinstance(self.prefix, str) or not re.fullmatch(r'-[a-z][a-z0-9]{1,9}', self.prefix):
            raise ValueError('命令前缀请填写短横线和 2 到 10 位小写字母或数字，例如 -mx。')
        if not isinstance(self.features, (tuple, list)) or not self.features or any(x not in FEATURES for x in self.features):
            raise ValueError('请至少选择一类有效功能。')
        if len(set(self.features)) != len(self.features):
            raise ValueError('功能选择存在重复项。')
        object.__setattr__(self, 'features', tuple(x for x in FEATURES if x in self.features))
        if (not isinstance(self.artifact_codes, (tuple, list)) or len(self.artifact_codes) != 6 or
                any(not isinstance(x, str) or not re.fullmatch(r'[A-Za-z0-9_]{4}', x) for x in self.artifact_codes)):
            raise ValueError('六神器方案需要六个 4 位字母/数字物品代码，区分大小写。')
        if any(x in PROTECTED_ITEMS for x in self.artifact_codes):
            raise ValueError('六神器方案不能包含背包载体，请填写普通物品代码。')
        object.__setattr__(self, 'artifact_codes', tuple(self.artifact_codes))
        if type(self.resource_amount) is not int or not 1 <= self.resource_amount <= 100000000:
            raise ValueError('默认资源数量必须是 1 到 100000000 的整数。')

    def data(self):
        value = asdict(self)
        value['features'] = list(self.features)
        value['artifact_codes'] = list(self.artifact_codes)
        return value

    @classmethod
    def parse(cls, data=None):
        if data is None:
            return cls()
        if not isinstance(data, dict) or set(data) - set(cls.__dataclass_fields__):
            raise ValueError('地图功能方案包含无法识别的设置。')
        return cls(**data)


class ScriptOptionStore:
    def __init__(self, path=None):
        self.path = Path(path) if path else Path(os.environ.get('LOCALAPPDATA', Path.home()/'AppData/Local'))/'War3Trainer/map-script-options.json'

    def load(self):
        if not self.path.exists():
            return ScriptOptions()
        if self.path.stat().st_size > 16384:
            raise ValueError('地图功能方案文件过大，请检查保存的设置。')
        return ScriptOptions.parse(json.loads(self.path.read_text(encoding='utf-8-sig')))

    def save(self, options):
        if type(options) is not ScriptOptions:
            raise TypeError('Expected ScriptOptions')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, pending = tempfile.mkstemp(prefix='map-script-', suffix='.tmp', dir=self.path.parent)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump(options.data(), stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(pending, self.path)
        finally:
            Path(pending).unlink(missing_ok=True)
        return options
