from unittest.mock import patch

import pytest

import war3_integrity as module


def test_matching_integrity_is_accepted():
    with patch.object(module, "process_integrity", side_effect=[
        {"pid": 10, "name": "medium", "rid": 0x2000},
        {"pid": 20, "name": "medium", "rid": 0x2000},
    ]):
        result = module.require_matching_integrity(20)
    assert result["matched"] is True


def test_mismatched_integrity_is_rejected_before_bridge():
    with patch.object(module, "process_integrity", side_effect=[
        {"pid": 10, "name": "high", "rid": 0x3000},
        {"pid": 20, "name": "medium", "rid": 0x2000},
    ]):
        with pytest.raises(RuntimeError, match="完整性级别不一致"):
            module.require_matching_integrity(20)


def test_unknown_integrity_does_not_block_legacy_access_diagnostics():
    with patch.object(module, "process_integrity", side_effect=[
        {"pid": 10, "error": 5},
        {"pid": 20, "name": "medium", "rid": 0x2000},
    ]):
        result = module.require_matching_integrity(20)
    assert result["matched"] is None
