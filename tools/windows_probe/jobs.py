"""Experimental W1 Job Object primitives; never imported by the installer/runner.

Windows x64 only. The bindings deliberately do not offer breakaway, inherited
handles, shell launch, or a PID-based cleanup fallback.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes as w
import os
import platform
import subprocess


class UnsupportedPlatform(RuntimeError):
    """This probe cannot establish its native preconditions."""


class SpawnError(RuntimeError):
    """A created but unresumed process was terminated and waited on."""

    def __init__(self, pid: int, cause: BaseException, cleanup_confirmed: bool):
        super().__init__(f"suspended child {pid}: {cause}; reaped={cleanup_confirmed}")
        self.pid = pid
        self.cleanup_confirmed = cleanup_confirmed


class _StartupInfo(ctypes.Structure):
    _fields_ = [
        ("cb", w.DWORD), ("lpReserved", w.LPWSTR), ("lpDesktop", w.LPWSTR),
        ("lpTitle", w.LPWSTR), ("dwX", w.DWORD), ("dwY", w.DWORD),
        ("dwXSize", w.DWORD), ("dwYSize", w.DWORD), ("dwXCountChars", w.DWORD),
        ("dwYCountChars", w.DWORD), ("dwFillAttribute", w.DWORD),
        ("dwFlags", w.DWORD), ("wShowWindow", w.WORD), ("cbReserved2", w.WORD),
        ("lpReserved2", ctypes.POINTER(w.BYTE)), ("hStdInput", w.HANDLE),
        ("hStdOutput", w.HANDLE), ("hStdError", w.HANDLE),
    ]


class _ProcessInfo(ctypes.Structure):
    _fields_ = [("hProcess", w.HANDLE), ("hThread", w.HANDLE),
                ("dwProcessId", w.DWORD), ("dwThreadId", w.DWORD)]


class _BasicLimit(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_int64),
        ("PerJobUserTimeLimit", ctypes.c_int64), ("LimitFlags", w.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", w.DWORD),
        ("Affinity", ctypes.c_size_t), ("PriorityClass", w.DWORD),
        ("SchedulingClass", w.DWORD),
    ]


class _IoCounters(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint64) for name in (
        "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
        "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]


class _ExtendedLimit(ctypes.Structure):
    _fields_ = [("BasicLimitInformation", _BasicLimit), ("IoInfo", _IoCounters),
               ("ProcessMemoryLimit", ctypes.c_size_t),
               ("JobMemoryLimit", ctypes.c_size_t),
               ("PeakProcessMemoryUsed", ctypes.c_size_t),
               ("PeakJobMemoryUsed", ctypes.c_size_t)]


def _api():
    if (os.name != "nt" or ctypes.sizeof(ctypes.c_void_p) != 8
            or platform.machine().lower() not in {"amd64", "x86_64"}):
        raise UnsupportedPlatform("W1 Jobs require Windows x64")
    if (ctypes.sizeof(_StartupInfo), ctypes.sizeof(_ProcessInfo),
            ctypes.sizeof(_ExtendedLimit)) != (104, 24, 144):
        raise UnsupportedPlatform("unexpected Windows x64 ABI")
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    signatures = {
        "CreateJobObjectW": ([w.LPVOID, w.LPCWSTR], w.HANDLE),
        "SetInformationJobObject": ([w.HANDLE, ctypes.c_int, w.LPVOID, w.DWORD], w.BOOL),
        "CreateProcessW": ([w.LPCWSTR, w.LPWSTR, w.LPVOID, w.LPVOID, w.BOOL,
                            w.DWORD, w.LPVOID, w.LPCWSTR,
                            ctypes.POINTER(_StartupInfo), ctypes.POINTER(_ProcessInfo)], w.BOOL),
        "AssignProcessToJobObject": ([w.HANDLE, w.HANDLE], w.BOOL),
        "ResumeThread": ([w.HANDLE], w.DWORD),
        "TerminateProcess": ([w.HANDLE, w.UINT], w.BOOL),
        "WaitForSingleObject": ([w.HANDLE, w.DWORD], w.DWORD),
        "CloseHandle": ([w.HANDLE], w.BOOL),
        "GetHandleInformation": ([w.HANDLE, ctypes.POINTER(w.DWORD)], w.BOOL),
        "GetExitCodeProcess": ([w.HANDLE, ctypes.POINTER(w.DWORD)], w.BOOL),
        "GetCurrentProcess": ([], w.HANDLE),
        "DuplicateHandle": ([w.HANDLE, w.HANDLE, w.HANDLE, ctypes.POINTER(w.HANDLE),
                             w.DWORD, w.BOOL, w.DWORD], w.BOOL),
        "OpenProcess": ([w.DWORD, w.BOOL, w.DWORD], w.HANDLE),
        "IsProcessInJob": ([w.HANDLE, w.HANDLE, ctypes.POINTER(w.BOOL)], w.BOOL),
    }
    for name, (args, result) in signatures.items():
        getattr(api, name).argtypes = args
        getattr(api, name).restype = result
    return api


def _check(result):
    if not result:
        raise ctypes.WinError(ctypes.get_last_error())
    return result


class Process:
    """An owned kernel process handle, not a reusable PID cleanup claim."""

    def __init__(self, handle, pid):
        self.api = _api()
        self.handle = handle
        self.pid = pid

    @classmethod
    def observe(cls, pid):
        api = _api()
        # SYNCHRONIZE | PROCESS_QUERY_LIMITED_INFORMATION. No terminate right:
        # observed descendants are cleaned by their Job owner, not PID killing.
        return cls(_check(api.OpenProcess(0x100000 | 0x1000, False, pid)), pid)

    def wait(self, timeout_ms=10000):
        result = self.api.WaitForSingleObject(self.handle, timeout_ms)
        if result == 0x102:
            return False
        if result != 0:
            raise ctypes.WinError(ctypes.get_last_error())
        return True

    def exit_code(self):
        code = w.DWORD()
        _check(self.api.GetExitCodeProcess(self.handle, ctypes.byref(code)))
        return code.value

    def in_job(self, job):
        result = w.BOOL()
        _check(self.api.IsProcessInJob(self.handle, job.handle, ctypes.byref(result)))
        return bool(result.value)

    def close(self):
        if self.handle:
            _check(self.api.CloseHandle(self.handle))
            self.handle = None


class Job:
    def __init__(self):
        self.api = _api()
        self.handle = _check(self.api.CreateJobObjectW(None, None))
        try:
            limits = _ExtendedLimit()
            # KILL_ON_JOB_CLOSE only: neither BREAKAWAY nor SILENT_BREAKAWAY.
            limits.BasicLimitInformation.LimitFlags = 0x2000
            _check(self.api.SetInformationJobObject(
                self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)))
            if self.inheritable():
                raise RuntimeError("Job handle unexpectedly inheritable")
        except BaseException:
            self.close()
            raise

    def inheritable(self):
        flags = w.DWORD()
        _check(self.api.GetHandleInformation(self.handle, ctypes.byref(flags)))
        return bool(flags.value & 1)

    def duplicate_for_lifetime_probe(self):
        """Test-only extra handle demonstrating the last-handle requirement."""
        duplicate = w.HANDLE()
        current = self.api.GetCurrentProcess()
        _check(self.api.DuplicateHandle(current, self.handle, current,
                                       ctypes.byref(duplicate), 0, False, 2))
        other = object.__new__(Job)
        other.api, other.handle = self.api, duplicate.value
        return other

    def _assign(self, process):
        _check(self.api.AssignProcessToJobObject(self.handle, process.handle))

    def spawn(self, argv, *, cwd=None):
        """Create suspended, assign, then resume; never inherit any handles."""
        info, startup = _ProcessInfo(), _StartupInfo()
        startup.cb = ctypes.sizeof(startup)
        command = ctypes.create_unicode_buffer(subprocess.list2cmdline(argv))
        _check(self.api.CreateProcessW(
            argv[0], command, None, None, False, 4, None,
            os.fspath(cwd) if cwd is not None else None,
            ctypes.byref(startup), ctypes.byref(info)))
        process = Process(info.hProcess, info.dwProcessId)
        try:
            self._assign(process)
            if self.api.ResumeThread(info.hThread) == 0xFFFFFFFF:
                raise ctypes.WinError(ctypes.get_last_error())
        except BaseException as exc:
            confirmed = False
            try:
                _check(self.api.TerminateProcess(process.handle, 125))
                confirmed = process.wait()
            finally:
                process.close()
            raise SpawnError(info.dwProcessId, exc, confirmed) from exc
        finally:
            _check(self.api.CloseHandle(info.hThread))
        return process

    def close(self):
        if self.handle:
            _check(self.api.CloseHandle(self.handle))
            self.handle = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
