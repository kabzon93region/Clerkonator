# -*- coding: utf-8 -*-
"""
Упаковка интерпретатора Python в venv/_base_python.

Стандартный venv на Windows ссылается на системный Python (C:\\Program Files\\...).
Скрипт копирует runtime в venv/_base_python и переписывает pyvenv.cfg,
чтобы activate + python работали после копирования папки проекта на другой ПК.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

MARKER = ".stt_bundled"
BASE_DIR_NAME = "_base_python"


def _win_path(p: Path) -> str:
    return str(p.resolve()).replace("/", "\\")


def read_pyvenv_home(cfg_path: Path) -> Path:
    text = cfg_path.read_text(encoding="utf-8")
    match = re.search(r"^home\s*=\s*(.+)$", text, re.MULTILINE)
    if not match:
        raise RuntimeError(f"home не найден в {cfg_path}")
    return Path(match.group(1).strip())


def write_pyvenv_cfg(
    cfg_path: Path,
    *,
    home: Path,
    executable: Path,
    version: str,
    command: str,
) -> None:
    cfg_path.write_text(
        f"home = {_win_path(home)}\n"
        f"include-system-site-packages = false\n"
        f"version = {version}\n"
        f"executable = {_win_path(executable)}\n"
        f"command = {command}\n",
        encoding="utf-8",
        newline="\r\n",
    )


def copy_file(src: Path, dst: Path) -> None:
    if src.is_file():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def copy_tree(src: Path, dst: Path) -> None:
    if not src.is_dir():
        return
    if dst.exists():
        shutil.rmtree(dst, ignore_errors=True)
    shutil.copytree(src, dst, ignore_dangling_symlinks=True)


def read_bundled_from(marker: Path) -> Path | None:
    if not marker.is_file():
        return None
    for line in marker.read_text(encoding="utf-8").splitlines():
        if line.startswith("bundled_from="):
            path = Path(line.split("=", 1)[1].strip())
            if path.is_dir():
                return path
    return None


def resolve_copy_source(src_home: Path, base_dst: Path, marker: Path) -> Path:
    """Источник файлов Python: системный prefix или bundled_from при пересборке."""
    if src_home.resolve() != base_dst.resolve():
        return src_home
    original = read_bundled_from(marker)
    if original and original.is_dir():
        return original
    return src_home


def test_tkinter(python_exe: Path) -> subprocess.CompletedProcess:
    code = "import tkinter as tk; r=tk.Tk(); r.destroy()"
    return subprocess.run(
        [str(python_exe), "-c", code],
        capture_output=True,
        text=True,
        timeout=60,
    )


def find_tcl_prefix(copy_src: Path, marker: Path) -> Path:
    """Найти установку Python с каталогом tcl."""
    candidates = [copy_src]
    original = read_bundled_from(marker)
    if original:
        candidates.append(original)

    for prefix in candidates:
        if (prefix / "tcl" / "tcl8.6" / "init.tcl").is_file():
            return prefix

    for cmd in (
        ["py", "-3", "-c", "import sys; print(sys.base_prefix)"],
        ["python", "-c", "import sys; print(sys.base_prefix)"],
    ):
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if result.returncode != 0:
            continue
        prefix = Path(result.stdout.strip())
        if (prefix / "tcl" / "tcl8.6" / "init.tcl").is_file():
            return prefix

    raise RuntimeError(
        "Не найден Python с Tcl/Tk (каталог tcl/tcl8.6).\n"
        "Переустановите Python с галочкой tcl/tk и выполните: scripts\\setup.cmd --recreate"
    )


def copy_tcl_runtime(copy_src: Path, base_dst: Path, marker: Path) -> None:
    """Tcl/Tk для tkinter (Windows)."""
    prefix = find_tcl_prefix(copy_src, marker)
    tcl_src = prefix / "tcl"
    copy_tree(tcl_src, base_dst / "tcl")
    init_tcl = base_dst / "tcl" / "tcl8.6" / "init.tcl"
    if not init_tcl.is_file():
        raise RuntimeError(f"init.tcl не найден после копирования: {init_tcl}")


def bundle(root: Path, *, force: bool = False) -> None:
    root = root.resolve()
    venv = root / "venv"
    cfg = venv / "pyvenv.cfg"
    base_dst = venv / BASE_DIR_NAME
    marker = base_dst / MARKER
    venv_py = venv / "Scripts" / "python.exe"

    if not cfg.is_file():
        raise RuntimeError("venv/pyvenv.cfg не найден")
    if not venv_py.is_file():
        raise RuntimeError("venv/Scripts/python.exe не найден")

    if marker.is_file() and not force:
        test = subprocess.run(
            [str(venv_py), "--version"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        tk_test = test_tkinter(venv_py)
        if test.returncode == 0 and tk_test.returncode == 0:
            print(f"[OK] venv уже упакован ({base_dst})")
            return
        if test.returncode == 0 and tk_test.returncode != 0:
            print("[WARN] venv без Tcl/Tk — доупаковка tcl...")
            copy_src = resolve_copy_source(read_pyvenv_home(cfg), base_dst, marker)
            copy_tcl_runtime(copy_src, base_dst, marker)
            if test_tkinter(venv_py).returncode != 0:
                raise RuntimeError("tkinter не работает после копирования tcl")
            print("[OK] Tcl/Tk добавлен в _base_python")
            return

    src_home = read_pyvenv_home(cfg)
    copy_src = resolve_copy_source(src_home, base_dst, marker)

    if not copy_src.is_dir():
        raise RuntimeError(
            f"Исходный Python не найден: {copy_src}\n"
            "Запустите scripts\\setup.cmd на ПК с установленным Python."
        )

    print(f"[INFO] Упаковка Python в venv (копия runtime в {BASE_DIR_NAME})...")
    print(f"[INFO] Источник: {copy_src}")

    if base_dst.exists():
        shutil.rmtree(base_dst, ignore_errors=True)
    base_dst.mkdir(parents=True, exist_ok=True)

    for name in ("python.exe", "pythonw.exe"):
        copy_file(copy_src / name, base_dst / name)

    for item in copy_src.iterdir():
        if item.is_file() and (
            item.name.lower().startswith("python")
            or item.name.lower().startswith("vcruntime")
            or item.suffix.lower() in (".dll", ".zip", ".pth")
        ):
            copy_file(item, base_dst / item.name)

    copy_tree(copy_src / "Lib", base_dst / "Lib")
    copy_tree(copy_src / "DLLs", base_dst / "DLLs")
    if (copy_src / "libs").is_dir():
        copy_tree(copy_src / "libs", base_dst / "libs")

    copy_tcl_runtime(copy_src, base_dst, marker)

    bundled_sp = base_dst / "Lib" / "site-packages"
    if bundled_sp.is_dir():
        shutil.rmtree(bundled_sp, ignore_errors=True)

    version = "3.11.0"
    for line in cfg.read_text(encoding="utf-8").splitlines():
        if line.startswith("version ="):
            version = line.split("=", 1)[1].strip()
            break

    write_pyvenv_cfg(
        cfg,
        home=base_dst,
        executable=base_dst / "python.exe",
        version=version,
        command=f"{_win_path(base_dst / 'python.exe')} -m venv {_win_path(venv)}",
    )
    marker.write_text(f"bundled_from={copy_src}\nroot={root}\n", encoding="utf-8")

    test = subprocess.run([str(venv_py), "--version"], capture_output=True, text=True, timeout=60)
    out = (test.stdout or test.stderr or "").strip()
    if test.returncode != 0:
        raise RuntimeError(f"venv не запустился после упаковки: {out}")

    tk_test = test_tkinter(venv_py)
    if tk_test.returncode != 0:
        err = (tk_test.stderr or tk_test.stdout or "").strip()
        raise RuntimeError(f"tkinter не работает после упаковки: {err}")

    print(f"[OK] {out}")
    print(f"[OK] Python + Tcl/Tk упакованы в {_win_path(base_dst)}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Упаковать Python в venv/_base_python")
    parser.add_argument("root", nargs="?", default=str(Path(__file__).resolve().parent.parent))
    parser.add_argument("--force", action="store_true", help="Пересобрать _base_python")
    args = parser.parse_args()
    root = Path(args.root)
    if not (root / "venv").is_dir():
        print("[ERROR] Папка venv не найдена")
        return 1
    try:
        bundle(root, force=args.force)
    except Exception as exc:
        print(f"[ERROR] {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
