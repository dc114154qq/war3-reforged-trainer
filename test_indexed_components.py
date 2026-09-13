import struct
import unittest

from war3_reforged_trainer import War3Trainer


class Memory:
    def __init__(self): self.data = {}
    def put(self, a, b): self.data.update({a+i:v for i,v in enumerate(b)})
    def read(self, a, n):
        try: return bytes(self.data[a+i] for i in range(n))
        except KeyError as e: raise OSError("unmapped") from e
    def read_u64(self,a): return struct.unpack("<Q",self.read(a,8))[0]


def fixture(hero=True):
    m=Memory();t=object.__new__(War3Trainer);o=0x300000
    t.COMPONENT_NAMES={v:k for k,v in t.COMPONENT_TAGS.items()}
    t._sane_heap_ptr=lambda x: 0x10000 <= x < 0x800000000000 and x%8==0
    for index,name in ((1,"move"),(2,"attack"),(3,"hero" if hero else "inventory"),(4,"inventory" if hero else "move")):
        w=o+0x158*index;d=0x500000+index*0x100;tag=t.COMPONENT_TAGS[name]
        m.put(w,struct.pack("<Q",0x7ff724c59d20));m.put(w+0x18,struct.pack("<Q",tag));m.put(w+0x50,struct.pack("<Q",o));m.put(w+0x90,struct.pack("<Q",d));m.put(d,struct.pack("<Q",0x7ff724d29678))
    return t,m,o


class IndexedComponentTests(unittest.TestCase):
    def test_optional_hero_shifts_inventory_but_both_are_found(self):
        for hero in (False, True):
            with self.subTest(hero=hero):
                t,m,o=fixture(hero)
                rows=list(t._iter_indexed_owner_component_wrappers(m,o))
                self.assertEqual({name for name,_,_ in rows},{"move","attack","inventory"}|({"hero"} if hero else set()))

    def test_wrong_owner_or_vtable_is_rejected(self):
        t,m,o=fixture(True);w=o+0x158
        m.put(w+0x50,struct.pack("<Q",0x301000))
        self.assertNotIn("move", {name for name,_,_ in t._iter_indexed_owner_component_wrappers(m,o)})
        m.put(w+0x50,struct.pack("<Q",o));m.put(w,struct.pack("<Q",0x1234))
        self.assertNotIn("move", {name for name,_,_ in t._iter_indexed_owner_component_wrappers(m,o)})


if __name__ == "__main__": unittest.main()
