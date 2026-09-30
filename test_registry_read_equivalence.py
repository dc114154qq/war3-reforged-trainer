"""Read-for-read comparison with the experimental compatibility baseline."""
import json
import struct
import subprocess
import sys
import types
from pathlib import Path

import pytest
from test_object_registry import RegistryFixture
from war3_game_profile import load_profile, profile_scope
from war3_object_registry import ObjectRegistry24268
from war3_classic_selection import read_player_selection
from test_classic_player_selection import Memory


@pytest.fixture(scope='module')
def baseline_registry():
    source=subprocess.check_output(['git','show','129c389:war3_object_registry.py'],encoding='utf-8')
    module=types.ModuleType('experimental_registry_baseline')
    exec(compile(source,'experimental_registry_baseline.py','exec'),module.__dict__)
    return module.ObjectRegistry24268


class TracedMemory(RegistryFixture):
    def __init__(self, profile, alternate, fault):
        self.trace=[];self.fault=fault;self.read_number=0
        super().__init__(0x190000000)
        r=profile.section('registry');addresses=profile.section('addresses')
        nt=bytearray(self.read(self.base+0x80,0x58))
        struct.pack_into('<H',nt,4,profile.fingerprint[0])
        struct.pack_into('<I',nt,8,profile.fingerprint[1])
        struct.pack_into('<I',nt,0x50,profile.fingerprint[2])
        self.put(self.base+0x80,nt)
        for checks in ('resolver','game_state'):
            for rva,data in profile.checks(checks):self.put(self.base+rva,data)
        self.put(self.base+addresses['registry_root'],struct.pack('<Q',self.root))
        table=self.alternate if alternate else self.table
        table_data=bytearray(r['count']+4)
        struct.pack_into('<Q',table_data,0,table)
        struct.pack_into('<I',table_data,r['count'],4)
        self.put(self.root+r['alternate' if alternate else 'primary'],table_data)
        self.handle=(99<<32)|3|(0x80000000 if alternate else 0)
        self.owner,self.unit=0x700000,0x600000
        slot=bytearray(r['stride'])
        struct.pack_into('<I',slot,0,0xfffffffe)
        struct.pack_into('<Q',slot,r['slot_owner'],self.owner)
        self.put(table+3*r['stride'],slot)
        for address,value in ((self.owner+r['owner_handle'],self.handle),
                (self.owner+r['owner_tag'],r['unit_tag']),
                (self.owner+r['owner_data'],self.unit),
                (self.unit+r['object_handle'],self.handle)):
            self.put(address,struct.pack('<Q',value))
        self.layout=r;self.root_address=self.base+addresses['registry_root']
        self.trace=[];self.read_number=0

    def read(self,address,size):
        self.trace.append((address,size));self.read_number+=1
        if hasattr(self,'layout') and self.read_number==10:
            if self.fault=='generation':
                self.put(self.owner+self.layout['owner_handle'],struct.pack('<Q',self.handle+(1<<32)))
            elif self.fault=='root':
                self.put(self.root_address,struct.pack('<Q',self.root+0x10000))
            elif self.fault=='destroyed':
                self.put(self.owner+self.layout['owner_tag'],struct.pack('<Q',0))
        return super().read(address,size)


@pytest.fixture(params=('3.0.0.24268','3.0.1.24323','relocated-layout'))
def profile(request,tmp_path):
    if request.param!='relocated-layout':return load_profile(Path('profiles')/(request.param+'.json'))
    data=load_profile('profiles/3.0.0.24268.json').to_dict()
    r=data['registry']
    r.update(primary=0x28,alternate=0x90,count=0x20,stride=32,slot_owner=16,
        owner_handle=0x38,owner_tag=0x30,owner_data=0xb0,object_handle=0x28)
    data['addresses']['registry_root']+=0x100
    for name in ('primary','alternate','stride','slot_owner','owner_handle','owner_data','object_handle'):
        data['bridge_layout'][name]=r[name]
    data['bridge_layout']['table_count']=r['count']
    data['bridge_layout']['registry_root_rva']=data['addresses']['registry_root']
    path=tmp_path/'relocated.json';path.write_text(json.dumps(data),encoding='utf-8')
    return load_profile(path)


@pytest.mark.parametrize('alternate',(False,True))
@pytest.mark.parametrize('fault',('none','generation','root','destroyed'))
def test_optimized_registry_preserves_reads_results_and_rejections(profile,baseline_registry,alternate,fault):
    observations=[]
    for cls in (baseline_registry,ObjectRegistry24268):
        memory=TracedMemory(profile,alternate,fault)
        with profile_scope(profile):
            try:result=('ok',cls(memory,memory.base).resolve_unit(memory,memory.unit))
            except RuntimeError as exc:result=('error',type(exc).__name__,str(exc))
        observations.append((result,memory.trace))
    assert observations[0]==observations[1]
    assert observations[1][0][0]==('ok' if fault=='none' else 'error')


def test_cached_metadata_is_immutable_and_bound_to_each_profile():
    a=load_profile('profiles/3.0.0.24268.json')
    b=load_profile('profiles/3.0.1.24323.json')
    assert a.registry_metadata is a.registry_metadata
    assert a.registry_metadata[3]!=b.registry_metadata[3]
    with pytest.raises(TypeError):a.registry_metadata[0]['stride']=99


@pytest.fixture(scope='module')
def baseline_selection():
    source=subprocess.check_output(['git','show','129c389:war3_classic_selection.py'],encoding='utf-8')
    module=types.ModuleType('experimental_selection_baseline')
    sys.modules[module.__name__]=module
    exec(compile(source,'experimental_selection_baseline.py','exec'),module.__dict__)
    return module.read_player_selection


class TracedSelection(Memory):
    def __init__(self,profile,count,mutate):
        super().__init__();self.trace=[];self.mutated=False;self.mutate=mutate
        layout=profile.section('selection')
        self.player,self.manager=0x200000,0x400000
        self.manager_slot=self.player+layout['manager']
        sentinel=(self.manager+layout['header'])|1
        nodes=[0x500000+i*0x100 for i in range(count)]
        self.put(self.manager_slot,struct.pack('<Q',self.manager))
        self.put(self.manager+layout['header'],struct.pack('<QQII',
            nodes[-1] if count else self.manager+layout['header'],nodes[0] if count else sentinel,count,0))
        for i,node in enumerate(nodes):
            self.put(node+layout['node_next'],struct.pack('<Q',nodes[i+1] if i+1<count else sentinel))
            self.put(node+layout['node_unit'],struct.pack('<Q',0x900000+i*0x1000))
        self.trigger=nodes[-1]+layout['node_next'] if count else self.manager+layout['header']
        self.changed=nodes[-1]+layout['node_unit'] if count else self.manager_slot
        self.changed_value=0xa00000 if count else self.manager+0x10000

    def read(self,address,size):
        self.trace.append((address,size));value=super().read(address,size)
        if self.mutate and not self.mutated and address==self.trigger:
            self.mutated=True;self.put(self.changed,struct.pack('<Q',self.changed_value))
        return value


@pytest.mark.parametrize('count',(0,1,24))
@pytest.mark.parametrize('mutate',(False,True))
def test_selection_binding_preserves_read_order_and_concurrent_mutation_rejection(profile,baseline_selection,count,mutate):
    observations=[]
    for reader in (baseline_selection,read_player_selection):
        memory=TracedSelection(profile,count,mutate)
        with profile_scope(profile):
            try:
                result=reader(memory,memory.player)
                value=('ok',result.player,result.manager,result.units)
            except RuntimeError as exc:value=('error',type(exc).__name__,str(exc))
        observations.append((value,memory.trace))
    assert observations[0]==observations[1]
