"""Experimental W1 Win64/NTFS primitives; deliberately not an installer backend.

Only temporary native probes consume this module. Handles pin all bootstrap
ancestors; names passed to NT are exactly one prevalidated component. Neither
ACL isolation from same-user attackers nor crash recovery is claimed here.
"""

import ctypes as C
from ctypes import wintypes as W
from dataclasses import dataclass
import ntpath
import os


class Unsupported(RuntimeError):
    """The experimental capability cannot safely run on this input."""


class UNICODE_STRING(C.Structure):
    _fields_ = [("Length", W.USHORT), ("MaximumLength", W.USHORT), ("Buffer", W.LPWSTR)]


class OBJECT_ATTRIBUTES(C.Structure):
    _fields_ = [("Length", W.ULONG), ("RootDirectory", W.HANDLE),
                ("ObjectName", C.POINTER(UNICODE_STRING)), ("Attributes", W.ULONG),
                ("SecurityDescriptor", W.LPVOID), ("SecurityQualityOfService", W.LPVOID)]


class IO_STATUS_BLOCK(C.Structure):
    _fields_ = [("Status", C.c_void_p), ("Information", C.c_size_t)]


class FILE_ID_INFO(C.Structure):
    _fields_ = [("VolumeSerialNumber", C.c_ulonglong), ("FileId", C.c_ubyte * 16)]


class BY_HANDLE_FILE_INFORMATION(C.Structure):
    _fields_ = [("FileAttributes", W.DWORD), ("CreationTime", W.FILETIME),
                ("LastAccessTime", W.FILETIME), ("LastWriteTime", W.FILETIME),
                ("VolumeSerialNumber", W.DWORD), ("FileSizeHigh", W.DWORD),
                ("FileSizeLow", W.DWORD), ("NumberOfLinks", W.DWORD),
                ("FileIndexHigh", W.DWORD), ("FileIndexLow", W.DWORD)]


class FILE_RENAME_INFO(C.Structure):
    _fields_ = [("ReplaceIfExists", W.BOOLEAN), ("RootDirectory", W.HANDLE),
                ("FileNameLength", W.DWORD), ("FileName", W.WCHAR * 1)]


class OVERLAPPED(C.Structure):
    _fields_ = [("Internal", C.c_size_t), ("InternalHigh", C.c_size_t),
                ("Offset", W.DWORD), ("OffsetHigh", W.DWORD), ("hEvent", W.HANDLE)]


@dataclass(frozen=True)
class Identity:
    volume: int
    file_id: bytes
    links: int
    attributes: int


_api = None


def api():
    global _api
    if _api is not None:
        return _api
    if os.name != "nt" or C.sizeof(C.c_void_p) != 8:
        raise Unsupported("W1 requires native Windows x64")
    if C.sizeof(OBJECT_ATTRIBUTES) != 48 or FILE_RENAME_INFO.FileName.offset != 20:
        raise Unsupported("unproven Windows ABI")
    k = C.WinDLL("kernel32", use_last_error=True)
    n = C.WinDLL("ntdll")
    bindings = [
        (k, "CreateFileW", [W.LPCWSTR, W.DWORD, W.DWORD, W.LPVOID, W.DWORD,
                            W.DWORD, W.HANDLE], W.HANDLE),
        (k, "CloseHandle", [W.HANDLE], W.BOOL),
        (k, "GetFileInformationByHandle", [W.HANDLE, C.POINTER(BY_HANDLE_FILE_INFORMATION)], W.BOOL),
        (k, "GetFileInformationByHandleEx", [W.HANDLE, C.c_int, W.LPVOID, W.DWORD], W.BOOL),
        (k, "SetFileInformationByHandle", [W.HANDLE, C.c_int, W.LPVOID, W.DWORD], W.BOOL),
        (k, "GetVolumeInformationByHandleW", [W.HANDLE, W.LPWSTR, W.DWORD,
                                              C.POINTER(W.DWORD), C.POINTER(W.DWORD),
                                              C.POINTER(W.DWORD), W.LPWSTR, W.DWORD], W.BOOL),
        (k, "GetDriveTypeW", [W.LPCWSTR], W.UINT),
        (k, "LockFileEx", [W.HANDLE, W.DWORD, W.DWORD, W.DWORD, W.DWORD,
                            C.POINTER(OVERLAPPED)], W.BOOL),
        (k, "UnlockFileEx", [W.HANDLE, W.DWORD, W.DWORD, W.DWORD,
                              C.POINTER(OVERLAPPED)], W.BOOL),
        (n, "NtCreateFile", [C.POINTER(W.HANDLE), W.DWORD, C.POINTER(OBJECT_ATTRIBUTES),
                              C.POINTER(IO_STATUS_BLOCK), W.LPVOID, W.ULONG, W.ULONG,
                              W.ULONG, W.ULONG, W.LPVOID, W.ULONG], C.c_long),
        (n, "RtlNtStatusToDosError", [C.c_long], W.ULONG),
    ]
    for dll, name, args, result in bindings:
        function = getattr(dll, name)
        function.argtypes = args
        function.restype = result
    _api = k, n
    return _api


def checked(ok):
    if not ok:
        raise C.WinError(C.get_last_error())


def component(name):
    """Reject aliases rather than silently normalize an untrusted name."""
    if (not name or name in {".", ".."} or name[-1] in ". "
            or any(ord(c) < 32 or c in '/\\:*?"<>|' for c in name)
            or len(name.encode("utf-16-le")) > 510):
        raise ValueError("not a safe single Windows component")
    stem = name.split(".")[0].upper()
    if stem in {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"} or (
        len(stem) == 4 and stem[:3] in {"COM", "LPT"} and stem[3] in "123456789¹²³"
    ):
        raise ValueError("reserved Windows name")
    return name


class Handle:
    def __init__(self, value):
        self.value = value

    def close(self):
        if self.value is not None:
            value, self.value = self.value, None
            checked(api()[0].CloseHandle(value))

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def identity(self):
        k, _ = api()
        info, fid = BY_HANDLE_FILE_INFORMATION(), FILE_ID_INFO()
        checked(k.GetFileInformationByHandle(self.value, C.byref(info)))
        checked(k.GetFileInformationByHandleEx(self.value, 18, C.byref(fid), C.sizeof(fid)))
        return Identity(fid.VolumeSerialNumber, bytes(fid.FileId), info.NumberOfLinks,
                        info.FileAttributes)

    def child(self, name, *, directory=False, create=False, mutable=False, pinned=False,
              delete_only=False):
        name = component(name)
        if delete_only and (mutable or pinned or create):
            raise ValueError("delete-only proof requires an existing unpinned entry")
        _, n = api()
        buffer = C.create_unicode_buffer(name)
        size = len(name.encode("utf-16-le"))
        string = UNICODE_STRING(size, size + 2, C.cast(buffer, W.LPWSTR))
        # OBJ_CASE_INSENSITIVE; FILE_OPEN_REPARSE_POINT opens the entry itself.
        attributes = OBJECT_ATTRIBUTES(C.sizeof(OBJECT_ATTRIBUTES), self.value,
                                       C.pointer(string), 0x40, None, None)
        handle, status = W.HANDLE(), IO_STATUS_BLOCK()
        access = 0x100080  # SYNCHRONIZE | FILE_READ_ATTRIBUTES
        if directory:
            access |= 1  # FILE_LIST_DIRECTORY
        if mutable:
            # Pinned guards deliberately omit DELETE; otherwise two guard
            # openers would conflict before they reach the byte-range lock.
            access |= (0 if pinned else 0x10000) | 0x12019F
        if delete_only:
            access |= 0x10000  # DELETE without FILE_WRITE_DATA for disposition probes
        options = 0x200000 | 0x20 | (1 if directory else 0x40)
        result = n.NtCreateFile(C.byref(handle), access, C.byref(attributes),
                                C.byref(status), None, 0, 3 if pinned else 7,
                                2 if create else 1, options, None, 0)
        if result < 0:
            raise C.WinError(n.RtlNtStatusToDosError(result))
        opened = Handle(handle.value)
        try:
            if opened.identity().attributes & 0x400:
                raise Unsupported("reparse entry rejected without following it")
            return opened
        except BaseException:
            opened.close()
            raise

    def rename(self, parent, name):
        name = component(name)
        encoded = name.encode("utf-16-le")
        size = max(C.sizeof(FILE_RENAME_INFO), FILE_RENAME_INFO.FileName.offset + len(encoded))
        buffer = C.create_string_buffer(size)
        info = FILE_RENAME_INFO.from_buffer(buffer)
        info.ReplaceIfExists = 0
        info.RootDirectory = parent.value
        info.FileNameLength = len(encoded)
        C.memmove(C.addressof(buffer) + FILE_RENAME_INFO.FileName.offset, encoded, len(encoded))
        checked(api()[0].SetFileInformationByHandle(self.value, 3, buffer, size))

    def delete(self):
        # FILE_DISPOSITION_INFO is BOOLEAN, not Win32 BOOL.
        disposition = W.BOOLEAN(1)
        checked(api()[0].SetFileInformationByHandle(self.value, 4, C.byref(disposition), 1))

    def lock(self):
        if self.identity().links != 1 or self.identity().attributes & (0x400 | 0x10):
            raise Unsupported("guard must be a single-link regular file")
        overlap = OVERLAPPED()
        # All participants lock precisely byte [0, 1), fail immediately.
        checked(api()[0].LockFileEx(self.value, 3, 0, 1, 0, C.byref(overlap)))

    def unlock(self):
        overlap = OVERLAPPED()
        checked(api()[0].UnlockFileEx(self.value, 0, 1, 0, C.byref(overlap)))


class PinnedDirectory:
    """Hold every ancestor from a local drive root until the probe finishes."""

    def __init__(self, path):
        k, _ = api()
        path = os.fspath(path)
        drive, tail = ntpath.splitdrive(path)
        if len(drive) != 2 or drive[1] != ":" or not tail.startswith("\\"):
            raise Unsupported("only absolute local drive paths are supported")
        root = drive + "\\"
        if k.GetDriveTypeW(root) != 3:
            raise Unsupported("only local fixed drives are supported")
        value = k.CreateFileW(root, 0x100081, 3, None, 3, 0x02200000, None)
        if value == C.c_void_p(-1).value:
            raise C.WinError(C.get_last_error())
        self.handles = [Handle(value)]
        try:
            fs = C.create_unicode_buffer(32)
            checked(k.GetVolumeInformationByHandleW(value, None, 0, None, None, None, fs, len(fs)))
            if fs.value != "NTFS":
                raise Unsupported("only local NTFS is proven by W1")
            if self.handles[0].identity().attributes & 0x400:
                raise Unsupported("reparse root")
            for part in tail[1:].split("\\"):
                if part:
                    self.handles.append(self.handles[-1].child(part, directory=True, pinned=True))
            self.handle = self.handles[-1]
        except BaseException:
            self.close()
            raise

    def close(self):
        while self.handles:
            self.handles.pop().close()

    def __enter__(self):
        return self.handle

    def __exit__(self, *_):
        self.close()
