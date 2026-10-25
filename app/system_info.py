from __future__ import annotations

import ctypes
import os
import sys


def total_memory_bytes() -> int:
    if sys.platform == "win32":
        class MemoryStatus(ctypes.Structure):
            _fields_ = [
                ("length", ctypes.c_ulong),
                ("memory_load", ctypes.c_ulong),
                ("total_physical", ctypes.c_ulonglong),
                ("available_physical", ctypes.c_ulonglong),
                ("total_page_file", ctypes.c_ulonglong),
                ("available_page_file", ctypes.c_ulonglong),
                ("total_virtual", ctypes.c_ulonglong),
                ("available_virtual", ctypes.c_ulonglong),
                ("available_extended_virtual", ctypes.c_ulonglong),
            ]

        status = MemoryStatus()
        status.length = ctypes.sizeof(MemoryStatus)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return int(status.total_physical)

    if hasattr(os, "sysconf"):
        page_size = os.sysconf("SC_PAGE_SIZE")
        page_count = os.sysconf("SC_PHYS_PAGES")
        return int(page_size * page_count)

    return 8 * 1024**3


# Windows and Linux report less than the installed memory (firmware and
# integrated graphics reserve part of it), e.g. 7.7 GiB on an 8 GB PC or
# 31.6 GiB on a 32 GB PC. Exact 8/16/32 GiB boundaries therefore picked one
# model too small on most 8/16/32 GB PCs, and "check for a better model" could
# never offer Turbo there. The boundaries leave room for that reservation;
# Macs report their unified memory exactly (8/16/24/32 GiB).
_BASE_MIN_GIB = 7
_SMALL_MIN_GIB = 14
_TURBO_MIN_GIB = 28


def select_model_for_memory(memory_bytes: int) -> str:
    memory_gib = memory_bytes / 1024**3
    if memory_gib < _BASE_MIN_GIB:
        return "tiny"
    if memory_gib < _SMALL_MIN_GIB:
        return "base"
    if memory_gib < _TURBO_MIN_GIB:
        return "small"
    return "turbo"
