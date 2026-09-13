import struct
import unittest
from types import SimpleNamespace

from war3_reforged_trainer import War3Trainer


class Memory:
    def __init__(self): self.data = {}
    def put(self, a, b): self.data.update({a+i:v for i,v in enumerate(b)})
    def read(self, a, n):
        try: return bytes(self.data[a+i] for i in range(n))
        except KeyError as e: raise OSError("unmapped") from e
    def read_u64(self,a): return struct.unpack("<Q",self.read(a,8))[0]
    def read_i32(self,a): return struct.unpack("<i",self.read(a,4))[0]


class Registry:
    def __init__(self, owner): self.owner=owner
    def resolve_handle(self, memory, handle): return self.owner


def fixture():
    memory=Memory(); trainer=object.__new__(War3Trainer); trainer._classic_object_registry=Registry(0x300000)
    trainer._sane_heap_ptr=lambda x: 0x10000 <= x < 0x800000000000 and x%8==0
    player=0x400000; prop_list=0x500000
    memory.put(player+0x18,struct.pack("<Q",0x1234)); memory.put(0x300018,struct.pack("<Q",trainer.PLAYER_COMPONENT_TAG))
    memory.put(0x3000a0,struct.pack("<Q",prop_list));memory.put(0x3000a8,struct.pack("<Q",0x80))
    for i,kind,value in ((0,41,3),(1,42,24900),(2,43,23750),(3,44,0),(4,45,0),(5,46,35),(6,47,100)):
        address=0x600000+i*0x100; memory.put(prop_list+i*8,struct.pack("<Q",address))
        memory.put(address+0x18,struct.pack("<Q",trainer.RESOURCE_PROP_TAG));memory.put(address+0x20,struct.pack("<Q",(kind<<32)|kind));memory.put(address+0x50,struct.pack("<Q",0x300000));memory.put(address+0xd0,struct.pack("<i",value))
    return trainer,memory,player


class IndexedResourceTests(unittest.TestCase):
    def test_3_0_kind_mapping_and_value_addresses(self):
        trainer,memory,player=fixture();cache=trainer._indexed_resource_cache_for_player(memory,player)
        self.assertEqual((cache.player_value,cache.gold,cache.lumber,cache.food_used,cache.food_cap),(1,2375,0,35,100))
        self.assertEqual((cache.gold_address,cache.lumber_address,cache.food_used_address,cache.food_cap_address),(0x600200+0xd0,0x600300+0xd0,0x600500+0xd0,0x600600+0xd0))

    def test_invalid_owner_link_is_discarded(self):
        trainer,memory,player=fixture();memory.put(0x600200+0x50,struct.pack("<Q",0x301000))
        self.assertIsNone(trainer._indexed_resource_cache_for_player(memory,player))

    def test_missing_block_member_is_discarded(self):
        trainer,memory,player=fixture();memory.put(0x600600+0x18,struct.pack("<Q",0))
        self.assertIsNone(trainer._indexed_resource_cache_for_player(memory,player))


if __name__ == "__main__": unittest.main()
