import struct
import unittest
from unittest.mock import Mock
from war3_reforged_trainer import War3Trainer
from test_indexed_resources import Memory

class Registry:
    def __init__(self,owner,unit):self.owner=owner;self.unit=unit;self.handles={}
    def resolve_unit(self,memory,unit):
        if unit!=self.unit:raise RuntimeError('wrong unit')
        return (0x1234,self.owner)
    def resolve_handle(self,memory,handle):return self.handles[handle]

def fixture(hero=True):
    m=Memory();t=object.__new__(War3Trainer);o=0x300000;u=0x400000
    t._classic_object_registry=r=Registry(o,u);t._native_selection_unavailable=True
    t._iter_owner_component_wrappers=Mock(side_effect=AssertionError('Region scan used'))
    t._components_from_unit_object=Mock(side_effect=AssertionError('Old layout used'))
    # Real intrusive links, deliberately far apart and unrelated to allocator stride.
    names=['move','attack']+(['hero'] if hero else [])+['inventory']
    wrappers=[0x5A0000,0xB05000,0x812000,0xDEB000][:len(names)]
    m.put(o+0x90,struct.pack('<Q',u));m.put(o+0xD8,struct.pack('<Q',wrappers[0]+0x38))
    prev=o+0xD0
    for index,(name,w) in enumerate(zip(names,wrappers)):
        d=0x1000000+index*0x1000;r.handles[index]=w;raw=bytearray(0x80)
        struct.pack_into('<QQ',raw,0,t.COMPONENT_TAGS[name],index)
        nxt=wrappers[index+1]+0x38 if index+1<len(wrappers) else 0
        struct.pack_into('<QQ',raw,0x20,prev,nxt);struct.pack_into('<Q',raw,0x38,o)
        struct.pack_into('<Q',raw,0x78,d);m.put(w+0x18,raw);m.put(d+0x68,struct.pack('<Q',u));prev=w+0x38
    return t,m,o,wrappers

class IndexedComponentTests(unittest.TestCase):
    def test_nonadjacent_hero_and_nonhero_use_no_old_layout_or_scan(self):
        for hero in (True,False):
            t,m,o,wrappers=fixture(hero)
            self.assertEqual(set(t._selected_components(m,o)),{'move','attack','inventory'}|({'hero'} if hero else set()))

    def test_owner_generation_backlink_cycle_and_data_faults_fail_whole_read(self):
        for offset,value in [(0x50,0xBAD000),(0x38,0),(0x40,0x5A0038),(0x90,0xBAD000)]:
            with self.subTest(offset=offset):
                t,m,o,ws=fixture();m.put(ws[0]+offset,struct.pack('<Q',value))
                with self.assertRaises((RuntimeError,OSError)):t._selected_components(m,o)
        t,m,o,ws=fixture();t._classic_object_registry.handles[0]=0xBAD000
        with self.assertRaises(RuntimeError):t._selected_components(m,o)

    def test_component_removed_between_reads_is_not_kept_from_cache(self):
        t,m,o,ws=fixture();self.assertIn('hero',t._selected_components(m,o))
        m.put(ws[1]+0x40,struct.pack('<Q',ws[3]+0x38));m.put(ws[3]+0x38,struct.pack('<Q',ws[1]+0x38))
        self.assertNotIn('hero',t._selected_components(m,o))

    def test_changed_list_between_traversals_is_rejected(self):
        t,m,o,ws=fixture();read=m.read;calls=0
        def changing(a,n):
            nonlocal calls
            if a==o+0xD8:
                calls+=1
                if calls==3:m.put(a,struct.pack('<Q',0))
            return read(a,n)
        m.read=changing
        with self.assertRaises(RuntimeError):t._selected_components(m,o)

if __name__=='__main__':unittest.main()
