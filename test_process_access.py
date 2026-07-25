import ctypes
from types import SimpleNamespace

import pytest

import war3_reforged_trainer as trainer


def test_process_memory_retries_after_enabling_debug_privilege(monkeypatch):
    calls = []

    def open_process(access, inherit, pid):
        calls.append((access, inherit, pid))
        ctypes.set_last_error(trainer.ERROR_ACCESS_DENIED if len(calls) == 1 else 0)
        return None if len(calls) == 1 else 1234

    fake_kernel32 = SimpleNamespace(OpenProcess=open_process)
    monkeypatch.setattr(trainer, "kernel32", fake_kernel32)
    monkeypatch.setattr(trainer, "enable_debug_privilege", lambda: True)

    pm = trainer.ProcessMemory(77, write=True)

    assert pm.handle == 1234
    assert len(calls) == 2
    expected_access = (
        trainer.PROCESS_QUERY_INFORMATION
        | trainer.PROCESS_VM_READ
        | trainer.PROCESS_VM_WRITE
        | trainer.PROCESS_VM_OPERATION
    )
    assert calls == [(expected_access, False, 77), (expected_access, False, 77)]


def test_process_memory_preserves_access_denied_when_debug_privilege_unavailable(monkeypatch):
    def open_process(_access, _inherit, _pid):
        ctypes.set_last_error(trainer.ERROR_ACCESS_DENIED)
        return None

    fake_kernel32 = SimpleNamespace(OpenProcess=open_process)
    monkeypatch.setattr(trainer, "kernel32", fake_kernel32)
    monkeypatch.setattr(trainer, "enable_debug_privilege", lambda: False)

    with pytest.raises(OSError) as error:
        trainer.ProcessMemory(77)

    assert error.value.winerror == trainer.ERROR_ACCESS_DENIED


def test_native_helper_command_retries_temporary_access_denied(monkeypatch):
    class FlakyPath:
        def __init__(self):
            self.attempts = 0
            self.chmod_calls = []

        def write_bytes(self, payload):
            self.attempts += 1
            if self.attempts < 3:
                raise PermissionError(13, "access denied")
            self.payload = payload

        def chmod(self, mode):
            self.chmod_calls.append(mode)

    path = FlakyPath()
    monkeypatch.setattr(trainer.time, "sleep", lambda _seconds: None)

    trainer.War3Trainer._write_native_helper_command(path, b"command")

    assert path.attempts == 3
    assert path.chmod_calls == [0o600]
    assert path.payload == b"command"
