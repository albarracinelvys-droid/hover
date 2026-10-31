"""Prevent two concurrent Windows HOVER voice engines from fighting over UI/audio.

Uses a Windows named mutex held by a kernel handle for the whole voice
session. No network or saved passwords involved. No need to kill Python
processes or edit Windows Registry.
"""
from __future__ import annotations

from contextlib import contextmanager
import sys


class AlreadyRunning(RuntimeError):
    pass


@contextmanager
def voice_instance():
    if sys.platform != "win32":
        yield
        return
    import ctypes
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    create = kernel.CreateMutexW
    create.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
    create.restype = wintypes.HANDLE
    close = kernel.CloseHandle
    close.argtypes = [wintypes.HANDLE]
    close.restype = wintypes.BOOL

    handle = create(None, False, "Local\\HOVER_NEXT_VOICE_SINGLE_INSTANCE")
    if not handle:
        raise OSError(ctypes.get_last_error(), "No pude crear la protección de HOVER.")
    if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
        close(handle)
        raise AlreadyRunning(
            "HOVER ya está ejecutándose. Cierra la instancia anterior "
            "antes de iniciar otra.")
    try:
        yield
    finally:
        close(handle)
