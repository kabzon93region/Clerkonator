# -*- coding: utf-8 -*-
"""Locate NVIDIA CUDA DLLs from pip packages (Windows + ctranslate2)."""

import os
import sys
import site

from utils.session_logger import get_logger

log = get_logger()

_CONFIGURED = False


def configure_cuda_dll_paths():
    """
    Add nvidia-* pip package bin dirs to PATH / DLL search path.

    ctranslate2 needs cublas64_12.dll etc.; driver alone is not enough.
    Safe to call multiple times.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return []

    added = []
    if sys.platform != "win32":
        _CONFIGURED = True
        return added

    search_roots = []

    # PyInstaller: nvidia packages are in _MEIPASS/nvidia/
    if getattr(sys, '_MEIPASS', None):
        meipass_nvidia = os.path.join(sys._MEIPASS, "nvidia")
        if os.path.isdir(meipass_nvidia):
            search_roots.append(sys._MEIPASS)

    # Normal Python: search in site-packages
    for sp in site.getsitepackages():
        search_roots.append(sp)
    user_sp = site.getusersitepackages()
    if user_sp:
        search_roots.append(user_sp)

    for sp in search_roots:
        nvidia_root = os.path.join(sp, "nvidia")
        if not os.path.isdir(nvidia_root):
            continue
        for name in sorted(os.listdir(nvidia_root)):
            bin_dir = os.path.join(nvidia_root, name, "bin")
            if not os.path.isdir(bin_dir):
                continue
            if bin_dir in added:
                continue
            os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")
            if hasattr(os, "add_dll_directory"):
                try:
                    os.add_dll_directory(bin_dir)
                except OSError as exc:
                    log.warning(f"add_dll_directory failed for {bin_dir}: {exc}")
            added.append(bin_dir)

    if added:
        log.info("CUDA runtime DLL paths: " + "; ".join(added))
    else:
        log.warning(
            "CUDA runtime DLL не найдены в venv. "
            "Установите: pip install -r requirements-server.txt"
        )

    _CONFIGURED = True
    return added


def find_cublas_dll():
    """Return path to cublas64_12.dll if present after configure."""
    configure_cuda_dll_paths()
    for folder in os.environ.get("PATH", "").split(os.pathsep):
        if not folder:
            continue
        candidate = os.path.join(folder, "cublas64_12.dll")
        if os.path.isfile(candidate):
            return candidate
    return None
