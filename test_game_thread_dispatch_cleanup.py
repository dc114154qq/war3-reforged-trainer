"""Release gates do not depend on a running game or a live hook."""
import importlib.util
from pathlib import Path
import pytest
s=importlib.util.spec_from_file_location('dispatch_probe',Path(__file__).parent/'analysis/verify-game-thread-dispatch.py')
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)


@pytest.mark.parametrize('complete,sent,hook,stage,detached,active,expected',[
 (True,True,99,3,1,0,True),
 (False,True,99,3,1,0,False),
 (True,False,99,3,1,0,False),
 (True,True,99,2,1,0,False),
 (True,True,99,3,0,0,False),
 (True,True,99,3,1,1,False),
 (True,False,0,2,0,0,True),
 (False,False,0,0,0,0,False),
])
def test_release_requires_finished_worker_and_detached_acknowledged_callback(complete,sent,hook,stage,detached,active,expected):
 assert m.can_release(complete,sent,dict(hook=hook,stage=stage,detached=detached,active=active)) is expected
