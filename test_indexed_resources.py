import struct
import unittest
from dataclasses import replace
from unittest.mock import Mock
from war3_reforged_trainer import War3Trainer
from war3_player_resources import PLAYER_TAG, PROPERTY_TAG

class Memory:
    def __init__(self): self.data = {}; self.writes = []
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def put(self, a, b): self.data.update({a+i:v for i,v in enumerate(b)})
    def read(self, a, n):
        try: return bytes(self.data[a+i] for i in range(n))
        except KeyError as e: raise OSError('unmapped') from e
    def read_u64(self,a): return struct.unpack('<Q',self.read(a,8))[0]
    def read_i32(self,a): return struct.unpack('<i',self.read(a,4))[0]
    def write_i32(self,a,v): self.writes.append((a,v)); self.put(a,struct.pack('<i',v))

class Registry:
    def __init__(self): self.mapping = {}; self.player_list = []
    def resolve_handle(self, memory, handle): return self.mapping[handle]
    def players(self, memory): return self.player_list[:]

def fixture():
    memory=Memory(); trainer=object.__new__(War3Trainer); registry=Registry()
    trainer._classic_object_registry=registry; trainer._native_selection_unavailable=True; trainer.pid=123
    trainer._process_memory=Mock(return_value=memory)
    trainer._query_native_table_handlers=Mock(side_effect=AssertionError('Legacy helper used'))
    trainer._resource_property_groups=Mock(side_effect=AssertionError('Region scan used'))
    for slot in range(28):
        player=0x400000+slot*0x100; owner=0x500000+slot*0x200; array=0x600000+slot*0x200
        registry.player_list.append(player); registry.mapping[slot]=owner
        memory.put(player+0x18,struct.pack('<Q',slot))
        memory.put(owner+0x18,struct.pack('<Q',PLAYER_TAG)); memory.put(owner+0x90,struct.pack('<Q',player))
        memory.put(owner+0xA0,struct.pack('<QQQQIIII',array,256,array,256,8,32,26,0))
        pointers=[]
        for state in range(26):
            prop=0x700000+slot*0x10000+state*0x100; pointers.append(prop)
            record=bytearray(0xBC); kind=1+slot*40+state
            struct.pack_into('<Q',record,0,PROPERTY_TAG); struct.pack_into('<Q',record,8,(kind<<32)|kind)
            struct.pack_into('<Q',record,0x38,owner); struct.pack_into('<I',record,0x64,state)
            # Distinct values expose gold/lumber/header/food confusion.
            value={0:3,1:24900+slot*10,2:23750,3:7,4:72,5:35,6:100}.get(state,0)
            struct.pack_into('<i',record,0xB8,value); memory.put(prop+0x18,record)
        # Capacity tail deliberately contains unmapped pointers; only count entries are live.
        memory.put(array,struct.pack('<32Q',*(pointers+[0xBAD000]*6)))
    return trainer,memory,registry.player_list[0]

class IndexedResourceTests(unittest.TestCase):
    def test_semantic_fields_all_players_and_public_refresh(self):
        t,m,p=fixture(); caches=t.list_resource_caches()
        self.assertEqual(len(caches),28)
        self.assertEqual((caches[0].gold,caches[0].lumber,caches[0].food_cap,caches[0].food_used,caches[0].food_limit),(2490,2375,72,35,100))
        for slot,c in enumerate(caches):
            self.assertEqual(t.read_resource_cache_addresses(c).player_value,slot)
        self.assertEqual(caches[0].player_handle,0)
        self.assertEqual([c.player_value for c in t.list_resource_caches(current_gold=2491)],[1])

    def test_public_write_uses_semantic_fields_only(self):
        t,m,p=fixture(); c=t.list_resource_caches()[0]
        new=t.write_resource_cache(c,target_gold=2501,target_lumber=2360,target_food_cap=80,target_food_used=36)
        self.assertEqual((new.gold,new.lumber,new.food_cap,new.food_used),(2501,2360,80,36))
        self.assertEqual(m.writes,[(c.gold_address,25010),(c.lumber_address,23600),(c.food_used_address,36),(c.food_cap_address,80)])
        self.assertEqual(m.read_i32(0x700000+0xD0),3)
        self.assertEqual(m.read_i32(0x700300+0xD0),7)
        self.assertEqual(m.read_i32(c.food_limit_address),100)

    def test_stale_process_generation_and_address_rejected_before_write(self):
        for field,value in [('process_id',456),('player_handle',900),('owner_key',0xDEAD000),('gold_address',0xBAD000)]:
            with self.subTest(field=field):
                t,m,p=fixture(); c=t.list_resource_caches()[0]
                with self.assertRaises(RuntimeError): t.write_resource_cache(replace(c,**{field:value}),target_gold=4000)
                self.assertEqual(m.writes,[])

    def test_invalid_later_target_prevents_first_write(self):
        t,m,p=fixture();c=t.list_resource_caches()[0]
        with self.assertRaises(ValueError):t.write_resource_cache(c,target_gold=1,target_food_cap=1001)
        self.assertEqual(m.writes,[])

    def test_missing_or_duplicate_or_wrong_owner_fails_complete_list(self):
        for offset,value,fmt in [(0x18,0,'Q'),(0x7C,1,'I'),(0x50,0xBAD000,'Q')]:
            with self.subTest(offset=offset):
                t,m,p=fixture();m.put(0x700200+offset,struct.pack('<'+fmt,value))
                with self.assertRaises(RuntimeError):t.list_resource_caches()

    def test_local_shortcut_and_validation_avoid_native(self):
        t,m,p=fixture();c=t.list_resource_caches()[1]
        t._classic_local_resource_cache=Mock(return_value=c)
        self.assertEqual(t.locate_local_player_resource_cache().player_value,1)
        self.assertEqual(t.validate_local_player_resource_cache(c).player_value,1)
        with self.assertRaises(RuntimeError):t.validate_local_player_resource_cache(t.list_resource_caches()[0])

    def test_public_locate_uses_indexed_local_cache_on_30(self):
        t,m,p=fixture();c=t.list_resource_caches()[1]
        t._classic_local_resource_cache=Mock(return_value=c)
        result=t.locate_resource_cache(c.gold,c.lumber,c.food_used,c.food_cap)
        self.assertEqual(result.player_value,1)
        t._query_native_table_handlers.assert_not_called()

if __name__=='__main__':unittest.main()
