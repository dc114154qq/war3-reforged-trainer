"""Published 2.0.9 feature/API equivalence for the 2.1.0 structure migration."""
import ast
from functools import lru_cache
from pathlib import Path
import subprocess

BASELINE = '873af7140f6af95f826565d8ae0397f840022b32'


@lru_cache(None)
def source(path):
    return subprocess.check_output(['git','show',BASELINE+':'+path],encoding='utf-8')


def methods(text,name=None):
    return {m.name:m for c in ast.parse(text).body if isinstance(c,ast.ClassDef)
            and (name is None or c.name==name) for m in c.body if isinstance(m,ast.FunctionDef)}


def facades():
    return {k:v for p in Path('war3_services').glob('facade_*.py')
            for k,v in methods(p.read_text(encoding='utf-8')).items()}


def test_all_released_trainer_methods_and_signatures_are_preserved():
    before=methods(source('war3_reforged_trainer.py'),'War3Trainer')
    after=methods(Path('war3_reforged_trainer.py').read_text(encoding='utf-8'),'War3Trainer')
    after.update(facades())
    assert len(before)==471
    assert before.keys() <= after.keys()
    for name,method in before.items():
        assert ast.dump(method.args)==ast.dump(after[name].args),name


def test_moved_feature_bodies_only_change_at_reviewed_architecture_boundaries():
    before=methods(source('war3_reforged_trainer.py'),'War3Trainer')
    moved=facades()
    assert len(moved)==390
    differences={name for name,method in moved.items()
                 if ast.dump(method)!=ast.dump(before[name])}
    assert differences=={
        '_engine_instance_24268',                 # shared session
        '_indexed_resource_cache_for_player',    # external backend
        '_item_objects_from_handles',            # typed ItemRef
        '_write_basic_unit_values_to_candidate', # guarded external backend
        '_write_inventory_slot_field',           # no cross-operation retry on timeout
    }


def test_native_service_parameters_and_protocol_builders_match_209():
    before=methods(source('war3_engine_24268.py'),'Engine24268')
    count=0
    for name in ('units','abilities','items','extensions','world'):
        for method_name,method in methods(Path('war3_services',name+'.py').read_text(encoding='utf-8')).items():
            assert ast.dump(method)==ast.dump(before[method_name]),method_name
            count+=1
    assert count==28


def test_hotkey_definitions_and_dispatch_unchanged():
    for name in ('war3_hotkey_model.py','war3_hotkey_engine.py','war3_hotkey_native.py'):
        assert ast.dump(ast.parse(source(name)))==ast.dump(ast.parse(Path(name).read_text(encoding='utf-8'))),name
