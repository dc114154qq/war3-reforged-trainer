"""Malformed field descriptors cannot turn native identity into raw writes."""
from dataclasses import replace
from unittest.mock import Mock
import pytest
import war3_reforged_trainer as module
from test_native_snapshot_binding import make_snapshot, make_candidate


@pytest.mark.parametrize('cls',[module.War3Trainer,module.BackupReadWar3Trainer])
@pytest.mark.parametrize('bad',[
    module.UnitMemoryField('unknown','unknown','i32',1,0x123000,'test',write_address=0x123000,write_type='i32'),
    module.UnitMemoryField('unknown','unknown','i32',1,0,'test',native_write=True),
    module.UnitMemoryField('armor','armor','f32',1,0,'test',native_write=True),
    module.UnitMemoryField('skill1_name','skill1_name','rawcode',0x41303031,0,'test',native_write=True),
    module.UnitMemoryField('intelligence_total','intelligence_total','i32',30,0,'test',native_write=True),
])
def test_unbound_second_field_prevents_first_native_mutation(cls,bad):
    subject=cls.__new__(cls);candidate=make_candidate(make_snapshot());memory=Mock()
    hp=module.UnitMemoryField('hp_current','hp','f32',100,0,'basic',native_write=True)
    subject._unit_fields_from_candidate=Mock(return_value=[hp,bad])
    for name in ('_write_basic_unit_values_to_candidate','_write_native_component_fields','_run_native_helper_ops',
                 '_write_memory_value','_read_memory_value'):
        setattr(subject,name,Mock(side_effect=AssertionError('Mutation before full route validation')))
    with pytest.raises(RuntimeError,match='Native field has no bound setter'):
        subject._write_unit_fields_to_candidate(memory,candidate,[module.MemoryWriteSpec('hp_current',0,'',150),
                                                                  module.MemoryWriteSpec(bad.key,0,'',1)])
    subject._write_basic_unit_values_to_candidate.assert_not_called();subject._write_memory_value.assert_not_called()
    assert not memory.mock_calls


def test_original_non_native_descriptor_path_is_not_reclassified():
    subject=module.War3Trainer.__new__(module.War3Trainer)
    candidate=replace(make_candidate(make_snapshot()),native_snapshot=None,selection_source='memory')
    subject._last_persistent_native_snapshots=()
    field=module.UnitMemoryField('legacy','legacy','i32',1,0x123000,'test',write_address=0x123000,write_type='i32')
    subject._unit_fields_from_candidate=Mock(return_value=[field])
    subject._write_memory_value=Mock();subject._read_memory_value=Mock(return_value=7)
    memory=Mock()
    assert subject._write_unit_fields_to_candidate(memory,candidate,[module.MemoryWriteSpec('legacy',0,'',7)])[0].value==7
    subject._write_memory_value.assert_called_once_with(memory,0x123000,'i32',7)
