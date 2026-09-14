"""Load only the telemetry probe via Windows loader, independently of message hooks.

No game handlers are called. Addresses are resolved by owning module and RVA.
A timeout never terminates the thread or frees memory it may still be reading.
"""
import argparse
import ctypes as c
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import runpy
import struct
import subprocess
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from war3_reforged_trainer import enable_debug_privilege
import pefile

helper = runpy.run_path(str(ROOT / 'analysis/verify-engine-hook-transport.py'))
k, api = helper['k'], helper['api']
P, U, Z = c.c_void_p, c.c_ulong, c.c_size_t
open_process = api(k, 'OpenProcess', P, U, c.c_int, U)
close = api(k, 'CloseHandle', c.c_int, P)
alloc = api(k, 'VirtualAllocEx', P, P, P, Z, U, U)
free = api(k, 'VirtualFreeEx', c.c_int, P, P, Z, U)
write = api(k, 'WriteProcessMemory', c.c_int, P, P, P, Z, c.POINTER(Z))
read = api(k, 'ReadProcessMemory', c.c_int, P, P, P, Z, c.POINTER(Z))
create_thread = api(k, 'CreateRemoteThread', P, P, P, Z, P, P, U, c.POINTER(U))
wait = api(k, 'WaitForSingleObject', U, P, U)
exit_code = api(k, 'GetExitCodeThread', c.c_int, P, c.POINTER(U))
protect = api(k, 'VirtualProtectEx', c.c_int, P, P, Z, U, c.POINTER(U))
flush = api(k, 'FlushInstructionCache', c.c_int, P, P, Z)
get_module = api(k, 'GetModuleHandleExW', c.c_int, U, P, c.POINTER(P))
current_process = api(k, 'GetCurrentProcess', P)


def bytes_at(handle, address, size):
    buffer, actual = c.create_string_buffer(size), Z()
    if not read(handle, address, buffer, size, c.byref(actual)) or actual.value != size:
        raise c.WinError(c.get_last_error())
    return buffer.raw


def entrypoint(memory, name):
    local = c.cast(getattr(k, name), P).value
    module, filename = P(), c.create_unicode_buffer(1024)
    if not get_module(6, local, c.byref(module)):
        raise c.WinError(c.get_last_error())
    if not helper['module_name'](current_process(), module, filename, len(filename)):
        raise c.WinError(c.get_last_error())
    remote = helper['module_base'](memory, filename.value)
    if not remote:
        raise RuntimeError('System module missing: ' + filename.value)
    address = remote + local - module.value
    if bytes_at(memory.handle, address, 16) != c.string_at(local, 16):
        raise RuntimeError('System entry prefix differs for ' + name)
    return address, {'module': filename.value, 'rva': hex(local - module.value)}


def invoke(handle, entry, argument, timeout):
    tid = U()
    thread = create_thread(handle, None, 0, entry, argument, 0, c.byref(tid))
    if not thread:
        return {'created': False, 'error': c.get_last_error(), 'completed': False}
    result = {'created': True, 'tid': tid.value, 'completed': False}
    try:
        status = wait(thread, timeout)
        result['wait_status'] = hex(status)
        result['completed'] = status == 0
        if status == 0:
            code = U()
            if exit_code(thread, c.byref(code)):
                result['exit_code_low32'] = hex(code.value)
            else:
                result['exit_query_error'] = c.get_last_error()
        elif status == 0xffffffff:
            result['wait_error'] = c.get_last_error()
    finally:
        close(thread)
    return result


# x64 Windows thread function: RCX -> parameter block. No game addresses.
# Save nonvolatile RBX, reserve shadow space with aligned RSP, call LoadLibraryW
# and GetLastError, write result/stage, restore stack, return zero.
ENTRY_CODE = bytes.fromhex(
    '53 48 83 ec 20 48 89 cb'
    ' c7 43 18 01 00 00 00'
    ' 48 8b 0b ff 53 08 48 89 43 20'
    ' ff 53 10 89 43 28 c7 43 18 02 00 00 00'
    ' 31 c0 48 83 c4 20 5b c3'
)


def marked_load(handle, path, load_address, error_address, timeout):
    code = block = None
    pending = False
    result = {'created': False, 'completed': False, 'stage': None}
    try:
        block = alloc(handle, None, 48, 0x3000, 4)
        code = alloc(handle, None, len(ENTRY_CODE), 0x3000, 4)
        if not block or not code:
            raise c.WinError(c.get_last_error())
        payload = struct.pack('<QQQIIQII', path, load_address, error_address, 0, 0, 0, 0, 0)
        for address, blob in ((block, payload), (code, ENTRY_CODE)):
            buffer, written = c.create_string_buffer(blob), Z()
            if not write(handle, address, buffer, len(blob), c.byref(written)) or written.value != len(blob):
                raise c.WinError(c.get_last_error())
        old = U()
        if not protect(handle, code, len(ENTRY_CODE), 0x20, c.byref(old)):
            raise c.WinError(c.get_last_error())
        if not flush(handle, code, len(ENTRY_CODE)):
            raise c.WinError(c.get_last_error())
        result.update(invoke(handle, code, block, timeout))
        pending = result['created'] and not result['completed']
        values = struct.unpack('<QQQIIQII', bytes_at(handle, block, 48))
        result.update(stage=values[3], module_result=hex(values[5]), loader_last_error=values[6],
                      marker_code_address=hex(code), marker_block_address=hex(block))
    except Exception as exc:
        result['marker_error'] = str(exc)
    finally:
        result['marker_allocations_freed'] = False
        if not pending:
            ok = True
            for address in (code, block):
                if address:
                    ok = bool(free(handle, address, 0, 0x8000)) and ok
            result['marker_allocations_freed'] = ok
    return result


def classify_load(result, module):
    if result.get('created') and not result.get('completed'):
        return 'pending_load_thread_no_forced_cleanup'
    if not result.get('created'):
        return 'thread_creation_failed'
    if 'stage' in result:
        if result['stage'] == 0:
            return 'entry_not_observed'
        if result['stage'] != 2:
            return 'entry_incomplete_or_unreadable'
        if not int(result.get('module_result', '0'), 16):
            return 'loader_returned_null'
        if not module:
            return 'loader_result_not_in_module_list'
    return 'loaded' if module else 'module_not_loaded'


def inspect(pid, dll, timeout, marker=False):
    # Probe export must be present; do not load unrelated libraries through this tool.
    data = dll.read_bytes()
    pe = pefile.PE(data=data)
    if pe.FILE_HEADER.Machine != 0x8664:
        raise ValueError('Probe must be x64')
    exports = {s.name: s.address for s in pe.DIRECTORY_ENTRY_EXPORT.symbols}
    if not {b'probe_local_state', b'ProbeGetMessage', b'ProbeCallWndProc'} <= exports.keys():
        raise ValueError('Expected telemetry probe exports')
    report = {'pid': pid, 'dll': str(dll), 'dll_sha256': hashlib.sha256(data).hexdigest(),
              'calls_game_handlers': False, 'writes_game_objects': False, 'allocation_freed': False}
    handle = allocation = None
    argument_in_use = False
    try:
        enable_debug_privilege()
        handle = open_process(0x43a, False, pid)
        if not handle:
            raise c.WinError(c.get_last_error())
        memory = SimpleNamespace(handle=handle)
        if helper['module_base'](memory, dll.name):
            raise RuntimeError('Probe already loaded; no reference count changes attempted')
        load_address, report['load_entry'] = entrypoint(memory, 'LoadLibraryW')
        unload_address, report['unload_entry'] = entrypoint(memory, 'FreeLibrary')
        payload = str(dll).encode('utf-16le') + b'\0\0'
        allocation = alloc(handle, None, len(payload), 0x3000, 4)
        if not allocation:
            raise c.WinError(c.get_last_error())
        report['path_allocation'] = hex(allocation)
        buffer, written = c.create_string_buffer(payload), Z()
        if not write(handle, allocation, buffer, len(payload), c.byref(written)) or written.value != len(payload):
            raise c.WinError(c.get_last_error())
        if marker:
            error_address, report['last_error_entry'] = entrypoint(memory, 'GetLastError')
            result = marked_load(handle, allocation, load_address, error_address, timeout)
        else:
            result = invoke(handle, load_address, allocation, timeout)
        report['load_thread'] = result
        argument_in_use = result['created'] and not result['completed']
        if argument_in_use:
            report['state'] = 'pending_load_thread_no_forced_cleanup'
            return report
        base = helper['module_base'](memory, dll.name)
        report['module_after_load'] = hex(base) if base else None
        report['state'] = classify_load(result, base)
        if base:
            try:
                telemetry = struct.unpack('<12I', bytes_at(handle, base + exports[b'probe_local_state'], 48))
                report['telemetry'] = dict(zip(helper['FIELDS'], telemetry))
                report['attach_pid_matches'] = report['telemetry']['attach_pid'] == pid
            finally:
                report['unload_thread'] = invoke(handle, unload_address, base, timeout)
                if report['unload_thread']['completed']:
                    report['module_after_unload'] = helper['module_base'](memory, dll.name)
    except Exception as exc:
        report['error'] = str(exc)
    finally:
        if handle:
            if allocation and not argument_in_use:
                report['allocation_freed'] = bool(free(handle, allocation, 0, 0x8000))
            close(handle)
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    target = ap.add_mutually_exclusive_group(required=True)
    target.add_argument('--pid', type=int)
    target.add_argument('--local-host', type=Path)
    ap.add_argument('--dll', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--timeout-ms', type=int, default=3000)
    ap.add_argument('--entry-marker', action='store_true', help='Capture entry stage and immediate loader last error')
    args = ap.parse_args()
    child = None
    try:
        if args.local_host:
            child = subprocess.Popen([str(args.local_host.resolve())], stdout=subprocess.PIPE,
                                     text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            pid, tid, hwnd = map(int, child.stdout.readline().split())
            assert pid == child.pid
        else:
            pid = args.pid
        report = inspect(pid, args.dll.resolve(), args.timeout_ms, args.entry_marker)
        report['captured_utc'] = datetime.now(timezone.utc).isoformat()
        report['local_host'] = bool(child)
        temporary = args.output.with_suffix('.tmp')
        temporary.write_text(json.dumps(report, indent=2), encoding='utf-8')
        os.replace(temporary, args.output)
        print(json.dumps(report))
        if child:
            assert report.get('attach_pid_matches') and report.get('module_after_unload') is None
            assert report.get('allocation_freed') and report.get('unload_thread', {}).get('completed')
    finally:
        if child:
            helper['post_thread'](tid, 0x12, 0, 0)
            child.wait(timeout=5)


if __name__ == '__main__':
    main()
