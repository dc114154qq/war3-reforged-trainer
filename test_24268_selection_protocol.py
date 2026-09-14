import struct
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

import pytest
from war3_native_table import LiveNativeEntry
from war3_selection_protocol import SIGNATURES, build_work, validate_work, decode_work
from test_game_thread_dispatch_cleanup import m as dispatch


def entries():
    return {n: LiveNativeEntry(n, s, 0x10000 + i * 0x50, 0x100000 + i * 0x100)
            for i, (n, s) in enumerate(SIGNATURES)}


@pytest.mark.parametrize('index', range(8))
def test_every_native_requires_exact_signature(index):
    table = entries(); name = SIGNATURES[index][0]
    table[name] = replace(table[name], signature='()V')
    with pytest.raises(ValueError):
        build_work(table)


@pytest.mark.parametrize('size', [0, 1, 80, 96, 479, 481, 4096])
def test_truncated_work_stops_before_image_or_process_access(size):
    with pytest.raises(ValueError, match='480'):
        dispatch.inspect(1, 2, 3, Path('must-not-open.dll'), query_mode='selection',
                         work_payload=bytes(size))


def test_payload_order_and_zeroed_results():
    table = entries(); work = build_work(table)
    assert len(work) == 480
    assert struct.unpack_from('<8Q', work) == tuple(table[n].handler for n, _ in SIGNATURES)
    assert not any(work[64:])


@pytest.mark.parametrize('bad', [0, 1, 0x800000000000])
def test_bad_pointer_rejected(bad):
    table = entries(); name = SIGNATURES[0][0]
    table[name] = replace(table[name], handler=bad)
    with pytest.raises(ValueError): build_work(table)


def test_reused_output_rejected():
    work = bytearray(build_work(entries())); work[80] = 1
    with pytest.raises(ValueError, match='zero'): validate_work(work)


@pytest.mark.parametrize('count', [0, 1, 15, 24])
def test_complete_results(count):
    work = bytearray(build_work(entries()))
    struct.pack_into('<2Q4I', work, 64, 0x100008, 0x100010, count, 0, 1, 0)
    for i in range(count): struct.pack_into('<QIi', work, 96+i*16, 0x100100+i, 0x68666f6f, 0)
    assert len(decode_work(work, count)['rows']) == count


@pytest.mark.parametrize('error,destroyed,count', [(5,1,0), (0,0,0), (0,1,25)])
def test_error_cleanup_and_count_are_not_success(error, destroyed, count):
    work = bytearray(480)
    struct.pack_into('<2Q4I', work, 64, 1, 2, count, error, destroyed, 0)
    with pytest.raises(ValueError): decode_work(work, count)


def test_old_binary_without_abi_marker_never_opens_process(monkeypatch):
    symbol = lambda n: type('Symbol', (), dict(name=n, address=0x1000))()
    pe = Mock()
    pe.DIRECTORY_ENTRY_EXPORT.symbols = [symbol(b'ProbeInstallLocalHook')]
    monkeypatch.setattr(dispatch.pefile, 'PE', Mock(return_value=pe))
    opener = Mock(side_effect=AssertionError('process opened'))
    monkeypatch.setitem(dispatch.p, 'open_process', opener)
    with pytest.raises(ValueError, match='ABI'):
        dispatch.inspect(1,2,3,Path('old.dll'),query_mode='selection',work_payload=build_work(entries()))
    opener.assert_not_called()
