"""Offline instruction-walk boundaries; no DLL loading or game process."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace as S

spec = importlib.util.spec_from_file_location('loader_cfg', Path(__file__).parent / 'analysis/trace-loader-roots.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Image:
    OPTIONAL_HEADER = S(ImageBase=0x180000000)

    def __init__(self, data, executable=True, bound=None):
        self.data, self.executable = bytes.fromhex(data), executable
        self.DIRECTORY_ENTRY_EXCEPTION = [] if bound is None else [
            S(struct=S(BeginAddress=bound[0], EndAddress=bound[1]))]

    def get_section_by_rva(self, rva):
        return S(Characteristics=0x20000000 if self.executable else 0) if 0 <= rva < len(self.data) else None

    def get_data(self, rva, length):
        return self.data[rva:rva + length]


def test_export_return_does_not_include_adjacent_function():
    result = module.walk(Image('b801000000c3534883ec20'), 0)
    assert result['instruction_count'] == 2
    assert result['calls'] == []
    assert result['stops'] == [{'rva': '0x5', 'reason': 'ret'}]


def test_call_records_target_but_does_not_inline_callee():
    result = module.walk(Image('e801000000c3b801000000c3'), 0)
    assert result['calls'] == ['0x6']
    assert result['instruction_count'] == 2


def test_conditional_branch_explores_both_paths_once():
    result = module.walk(Image('740190c3'), 0)
    assert {i['rva'] for i in result['instructions']} == {'0x0', '0x2', '0x3'}


def test_tail_jump_respects_runtime_function_boundary():
    result = module.walk(Image('eb00b801000000c3', bound=(0, 2)), 0)
    assert result['instruction_count'] == 1
    assert result['stops'][0]['reason'] == 'outside_function_range'


def test_instruction_limit_is_reported_not_success():
    result = module.walk(Image('909090c3'), 0, max_instructions=2)
    assert result['budget_exhausted']
    assert result['instruction_count'] == 2


def test_nonexecutable_data_is_not_disassembled():
    result = module.walk(Image('b801000000c3', executable=False), 0)
    assert result['instruction_count'] == 0
    assert result['stops'][0]['reason'] == 'nonexecutable'


def test_indirect_jump_is_left_unresolved():
    result = module.walk(Image('ffe090c3'), 0)
    assert result['instruction_count'] == 1
    assert result['stops'][0]['reason'] == 'indirect_branch'
