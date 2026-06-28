# -*- coding: utf-8 -*-
"""Discover local STT models and build UI labels (device + memory)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Optional

_VOSK_MEMORY_MB = {
    "vosk-model-ru-0.42": 1800,
    "vosk-model-small-ru-0.22": 50,
    "vosk-model-ru-0.22": 1500,
}

_WHISPER_GPU_VRAM_MB = {
    "tiny": 400,
    "base": 500,
    "small": 1000,
    "medium": 1800,
    "large": 3200,
    "large-v3": 3200,
    "large-v2": 3000,
    "turbo": 1600,
    "large-v3-turbo": 1600,
}

_WHISPER_CPU_RAM_MB = {
    "tiny": 200,
    "base": 300,
    "small": 800,
    "medium": 2000,
    "large": 5000,
    "large-v3": 5000,
    "large-v2": 4500,
    "turbo": 2200,
    "large-v3-turbo": 2200,
}

_WHISPER_TITLES = {
    "tiny": "Whisper Tiny",
    "base": "Whisper Base",
    "small": "Whisper Small",
    "medium": "Whisper Medium",
    "large": "Whisper Large",
    "large-v3": "Whisper Large v3",
    "large-v2": "Whisper Large v2",
    "turbo": "Whisper Turbo",
    "large-v3-turbo": "Whisper Large v3 Turbo",
}


@dataclass(frozen=True)
class LocalSTTModel:
    """One installable local STT model."""

    model_id: str
    path: str
    engine: str
    title: str
    device: str
    memory_mb: int
    memory_kind: str
    whisper_size: Optional[str] = None

    @property
    def combo_label(self) -> str:
        mem = format_memory(self.memory_mb, self.memory_kind)
        device = "CPU" if self.device == "cpu" else "GPU"
        return f"{self.title} · {device} · {mem}"

    @property
    def info_text(self) -> str:
        mem = format_memory(self.memory_mb, self.memory_kind)
        device = "процессор (CPU)" if self.device == "cpu" else "видеокарта (GPU)"
        kind = "оперативная память" if self.memory_kind == "ram" else "видеопамять"
        return f"Устройство: {device} · {kind.capitalize()}: {mem}"


def format_memory(mb: float, kind: str = "ram") -> str:
    suffix = "VRAM" if kind == "vram" else "RAM"
    if mb >= 1024:
        return f"~{mb / 1024:.1f} ГБ {suffix}"
    return f"~{int(mb)} МБ {suffix}"


def _project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _dir_size_mb(path: str) -> float:
    total = 0
    if not os.path.isdir(path):
        return 0.0
    for root, _dirs, files in os.walk(path):
        if ".cache" in root.replace("\\", "/").split("/"):
            continue
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                pass
    return total / (1024 * 1024)


def _is_vosk_model(path: str) -> bool:
    markers = (
        os.path.join(path, "am", "final.mdl"),
        os.path.join(path, "graph", "HCLG.fst"),
        os.path.join(path, "graph", "HCLr.fst"),
    )
    return any(os.path.isfile(p) for p in markers)


def _is_whisper_model(path: str) -> bool:
    return os.path.isfile(os.path.join(path, "model.bin"))


def _gpu_available() -> bool:
    try:
        from utils.cuda_runtime import configure_cuda_dll_paths

        configure_cuda_dll_paths()
        import ctranslate2

        return ctranslate2.get_cuda_device_count() > 0
    except Exception:
        return False


def _vosk_title(folder_name: str) -> str:
    if folder_name.startswith("vosk-model-"):
        part = folder_name.replace("vosk-model-", "", 1)
        return f"Vosk {part.replace('-', ' ')}"
    return folder_name


def _scan_vosk_models(models_dir: str) -> List[LocalSTTModel]:
    found: List[LocalSTTModel] = []
    if not os.path.isdir(models_dir):
        return found

    for name in sorted(os.listdir(models_dir)):
        if not name.startswith("vosk-model"):
            continue
        path = os.path.join(models_dir, name)
        if not os.path.isdir(path) or not _is_vosk_model(path):
            continue
        disk_mb = _dir_size_mb(path)
        memory_mb = disk_mb if disk_mb > 10 else _VOSK_MEMORY_MB.get(name, 500)
        found.append(
            LocalSTTModel(
                model_id=f"vosk:{name}",
                path=path.replace("\\", "/"),
                engine="vosk",
                title=_vosk_title(name),
                device="cpu",
                memory_mb=int(memory_mb),
                memory_kind="ram",
            )
        )
    return found


def _scan_whisper_models(whisper_dir: str) -> List[LocalSTTModel]:
    found: List[LocalSTTModel] = []
    if not os.path.isdir(whisper_dir):
        return found

    use_gpu = _gpu_available()
    for name in sorted(os.listdir(whisper_dir)):
        if name.startswith("_") or name.startswith("."):
            continue
        path = os.path.join(whisper_dir, name)
        if not os.path.isdir(path) or not _is_whisper_model(path):
            continue

        if use_gpu:
            device = "gpu"
            memory_kind = "vram"
            memory_mb = _WHISPER_GPU_VRAM_MB.get(name, 1500)
        else:
            device = "cpu"
            memory_kind = "ram"
            memory_mb = _WHISPER_CPU_RAM_MB.get(name, 2000)

        title = _WHISPER_TITLES.get(name, f"Whisper {name}")
        found.append(
            LocalSTTModel(
                model_id=f"whisper:{name}",
                path=path.replace("\\", "/"),
                engine="whisper",
                title=title,
                device=device,
                memory_mb=memory_mb,
                memory_kind=memory_kind,
                whisper_size=name,
            )
        )
    return found


def list_local_stt_models(project_root: Optional[str] = None) -> List[LocalSTTModel]:
    root = project_root or _project_root()
    models_dir = os.path.join(root, "models")
    whisper_dir = os.path.join(models_dir, "whisper")
    items = _scan_vosk_models(models_dir) + _scan_whisper_models(whisper_dir)
    items.sort(key=lambda m: (m.engine, m.title))
    return items


def find_model_by_id(model_id: str, project_root: Optional[str] = None) -> Optional[LocalSTTModel]:
    for model in list_local_stt_models(project_root):
        if model.model_id == model_id:
            return model
    return None


def find_model_by_path(path: str, project_root: Optional[str] = None) -> Optional[LocalSTTModel]:
    if not path:
        return None
    norm = os.path.normpath(path).replace("\\", "/")
    for model in list_local_stt_models(project_root):
        if os.path.normpath(model.path).replace("\\", "/") == norm:
            return model
    return None


def resolve_local_model(config, project_root: Optional[str] = None) -> Optional[LocalSTTModel]:
    from utils.client_stt_config import resolve_local_model as _resolve

    return _resolve(config, project_root)


def apply_model_to_config(config, model: LocalSTTModel) -> None:
    from utils.client_stt_config import set_local_selection

    set_local_selection(config, model.device, model.whisper_size or os.path.basename(model.path))
