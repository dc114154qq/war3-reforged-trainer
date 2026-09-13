import struct
import unittest

from test_classic_player_selection import Memory
from war3_native_table import NativeTable24268
from war3_object_registry import ObjectIdentityError


def fixture(count=2):
    m=Memory(); context=0x300000; table=context+0x28; terminal=(table+0x10)|1
    names=[(0x500000+i*0x100,0x510000+i*0x100,0x700000+i*0x100) for i in range(count)]
    for i,(name,sig,handler) in enumerate(names):
        node=0x400000+i*0x200; nxt=0x400000+(i+1)*0x200 if i+1<count else terminal
        m.put(node+0x20,struct.pack('<Q',nxt));m.put(node+0x28,struct.pack('<Q',name));m.put(node+0x30,struct.pack('<Q',handler));m.put(node+0x40,struct.pack('<Q',sig));m.put(name,b'Fn'+str(i).encode()+b'\0');m.put(sig,b'(I)V\0')
    m.put(table+0x18,struct.pack('<Q',0x400000));return m,context


class NativeTableTests(unittest.TestCase):
    def test_reads_bounded_entries_and_requires_names(self):
        m,c=fixture();t=NativeTable24268(m,c);self.assertEqual(len(t.entries),2);self.assertEqual(t.require('Fn0')['Fn0'].signature,'(I)V')
        with self.assertRaises(ObjectIdentityError):t.require('Missing')

    def test_cycle_duplicate_bad_handler_and_bound_are_rejected(self):
        for fault in ('cycle','bad_handler','empty_name'):
            with self.subTest(fault=fault):
                m,c=fixture()
                if fault=='cycle':m.put(0x400000+0x20,struct.pack('<Q',0x400000))
                elif fault=='bad_handler':m.put(0x400000+0x30,struct.pack('<Q',0))
                else:m.put(0x500000,b'\0')
                with self.assertRaises(ObjectIdentityError):NativeTable24268(m,c)

    def test_head_change_is_rejected(self):
        m,c=fixture();original=m.read
        def read(a,n):
            value=original(a,n)
            if a==c+0x28+0x18:m.put(a,struct.pack('<Q',0x400200))
            return value
        m.read=read
        with self.assertRaises(ObjectIdentityError):NativeTable24268(m,c)


if __name__=='__main__':unittest.main()
