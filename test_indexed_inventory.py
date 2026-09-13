import struct
import unittest

from war3_reforged_trainer import War3Trainer


class Memory:
    def __init__(self): self.data={}
    def put(self,a,b): self.data.update({a+i:v for i,v in enumerate(b)})
    def read(self,a,n):
        try:return bytes(self.data[a+i] for i in range(n))
        except KeyError as e:raise OSError("unmapped") from e
    def read_u64(self,a):return struct.unpack("<Q",self.read(a,8))[0]
    def read_u32(self,a):return struct.unpack("<I",self.read(a,4))[0]


class Registry:
    def __init__(self, owners):self.owners=owners
    def resolve_handle(self,m,h):return self.owners[h]


class IndexedInventoryTests(unittest.TestCase):
    def test_full_handle_resolves_item_without_region_scan(self):
        m=Memory();t=object.__new__(War3Trainer);t._classic_object_registry=None;t._item_object_cache={}
        t._sane_heap_ptr=lambda x:0x10000<=x<0x800000000000 and x%8==0
        t._looks_like_vtable=lambda x:0x700000000000<=x<=0x7fffffffffff
        h=0x982600009800;owner=0x300000;item=0x400000
        t._classic_object_registry=Registry({h:owner})
        m.put(owner+0x18,struct.pack("<Q",t.ITEM_OWNER_TAG));m.put(owner+0x20,struct.pack("<Q",h));m.put(owner+0x90,struct.pack("<Q",item))
        m.put(item,struct.pack("<Q",0x7ff724c59d20));m.put(item+0x18,struct.pack("<Q",h));m.put(item+0x70,struct.pack(">I",0x49363058));m.put(item+0x178,struct.pack(">I",0x49363058))
        self.assertEqual(t._item_objects_from_handles(m,[h],0),{h:item})

    def test_bad_item_tag_backlink_or_mirror_is_rejected(self):
        for field in (0x18,0x20,0x178):
            with self.subTest(field=hex(field)):
                m=Memory();t=object.__new__(War3Trainer);t._classic_object_registry=None;t._item_object_cache={};t._sane_heap_ptr=lambda x:True;t._looks_like_vtable=lambda x:True
                h=0x982600009800;owner=0x300000;item=0x400000;t._classic_object_registry=Registry({h:owner})
                m.put(owner+0x18,struct.pack("<Q",t.ITEM_OWNER_TAG));m.put(owner+0x20,struct.pack("<Q",h));m.put(owner+0x90,struct.pack("<Q",item));m.put(item,struct.pack("<Q",1));m.put(item+0x18,struct.pack("<Q",h));m.put(item+0x70,struct.pack(">I",0x49363058));m.put(item+0x178,struct.pack(">I",0x49363058))
                if field == 0x20:
                    m.put(owner+field,struct.pack("<Q",0))
                else:
                    m.put(item+field,struct.pack("<Q",0) if field!=0x178 else struct.pack(">I",0x49363158))
                self.assertEqual(t._item_objects_from_handles(m,[h],0),{})


if __name__ == "__main__":unittest.main()
