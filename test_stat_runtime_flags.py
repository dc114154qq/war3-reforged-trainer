import ctypes
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def read_flag():
    library = ctypes.WinDLL(str(Path(__file__).parent / "analysis/build-stat-runtime-flags-fixture/engine-hero-fixture.dll"))
    function = library.BridgeStatRuntimeFlagTest
    function.argtypes = [ctypes.c_uint32]
    function.restype = ctypes.c_uint32
    return function


@pytest.mark.parametrize("scenario,expected", [(0, 1), (1, 0), (2, 274),
    (3, 274), (4, 274), (5, 274), (6, 274)])
def test_runtime_flag_rejects_retired_ambiguous_or_wrong_identity(read_flag, scenario, expected):
    assert read_flag(scenario) == expected
