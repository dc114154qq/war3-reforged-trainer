"""Internal function discovery must respect x64 instruction boundaries."""
import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from war3_reforged_trainer import War3Trainer


def discover(kind, code, base=0x1000, executable=True):
    trainer = War3Trainer.__new__(War3Trainer)
    trainer._is_executable_image_address = (
        Mock(side_effect=executable) if callable(executable) else Mock(return_value=executable)
    )
    memory = Mock()
    memory.read.return_value = code
    result = getattr(trainer, '_rel32_' + kind + '_in_function')(
        memory, base, max_bytes=len(code))
    memory.read.assert_called_once_with(base, len(code))
    return result


@pytest.mark.parametrize('kind,opcode', [('calls', 'e8'), ('jumps', 'e9')])
def test_opcode_inside_immediate_is_not_a_branch(kind, opcode):
    # mov eax, imm32; nop; actual relative branch; ret
    code = bytes.fromhex('b8' + opcode + '00000090' + opcode + '05000000c3')
    assert discover(kind, code) == [0x1010]


@pytest.mark.parametrize('kind,opcode', [('calls', 'e8'), ('jumps', 'e9')])
def test_c3_operand_after_prefix_does_not_end_function(kind, opcode):
    code = bytes.fromhex('90' * 17 + '448bc3' + opcode + '05000000c3')
    assert discover(kind, code) == [0x101e]


@pytest.mark.parametrize('kind,opcode', [('calls', 'e8'), ('jumps', 'e9')])
@pytest.mark.parametrize('end', ['c3', 'c21000'])
def test_early_return_excludes_neighboring_functions(kind, opcode, end):
    assert discover(kind, bytes.fromhex(end + opcode + '00000000')) == []


@pytest.mark.parametrize('kind,opcode', [('calls', 'e8'), ('jumps', 'e9')])
def test_signed_relative_target_and_executable_validation(kind, opcode):
    code = bytes.fromhex(opcode + 'f6ffffffc3')
    assert discover(kind, code) == [0xffb]
    assert discover(kind, code, executable=False) == []
    assert discover(kind, code[:3]) == []  # incomplete rel32


CONTRACTS = json.loads((Path(__file__).parent / 'tools/native-call-contracts-23745.json').read_text())['contracts']


@pytest.mark.parametrize('contract', CONTRACTS, ids=lambda row: row['name'])
@pytest.mark.parametrize('base', [0, 0x7ff700000000])
def test_captured_23745_call_order_preserved_at_different_module_bases(contract, base):
    assert discover(contract['kind'], bytes.fromhex(contract['code']),
                    base + contract['rva'],
                    executable=lambda _regions, target: base+0x1000 <= target < base+0xdd20000
                    ) == [base+rva for rva in contract['targets']]
