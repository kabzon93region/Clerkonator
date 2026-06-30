# -*- coding: utf-8 -*-
"""Упрощённая схема локального STT в config.client.json (device + model)."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from utils.stt_recognition import normalize_recognition, recognition_from_legacy
from utils.whisper_downloader import list_whisper_models

# Рекомендуемые Vosk для русского (имя папки в models/)
VOSK_MODEL_NAMES = (
    "vosk-model-ru-0.42",
    "vosk-model-ru-0.22",
    "vosk-model-small-ru-0.22",
)

DEFAULT_VOSK_MODEL = "vosk-model-ru-0.42"
DEFAULT_WHISPER_MODEL = "large-v3-turbo"

# Ключи stt.options — общие для любой модели
STT_OPTION_KEYS = (
    "whisper_cache_dir",
    "whisper_use_system_proxy",
    "whisper_compute_type",
    "fallback_cpu",
)

_STT_OPTION_DEFAULTS = {
    "whisper_cache_dir": "models/whisper",
    "whisper_use_system_proxy": False,
    "whisper_compute_type": "float16",
    "fallback_cpu": True,
}


def _project_root() -> str:
    """Return project root directory.
    
    For PyInstaller EXE: directory containing the .exe file.
    For normal Python: parent of utils/ directory.
    """
    import sys
    if getattr(sys, 'frozen', False):
        # PyInstaller: exe directory
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def is_vosk_model_name(name: str) -> bool:
    return bool(name) and name.startswith("vosk-model")


def is_whisper_model_name(name: str) -> bool:
    return bool(name) and not is_vosk_model_name(name)


def list_whisper_model_names() -> List[str]:
    """Имена Whisper из скачивальщика (для UI и документации)."""
    names = list_whisper_models()
    preferred = [
        "large-v3-turbo",
        "turbo",
        "large-v3",
        "large",
        "medium",
        "small",
        "base",
        "tiny",
    ]
    ordered = [n for n in preferred if n in names]
    for n in names:
        if n not in ordered and not n.endswith(".en"):
            ordered.append(n)
    return ordered


def list_models_for_device(device: str) -> List[str]:
    """Список имён моделей для выбора в UI / конфиге."""
    device = (device or "cpu").lower()
    whisper = list_whisper_model_names()
    if device == "gpu":
        return whisper
    return list(VOSK_MODEL_NAMES) + whisper


def get_remote_host(config) -> str:
    return config.get("stt.remote.host") or config.get("stt.server.host", "127.0.0.1")


def get_remote_port(config) -> int:
    return int(config.get("stt.remote.port") or config.get("stt.server.port", 8765))


def get_remote_timeout(config) -> int:
    return int(config.get("stt.remote.timeout") or config.get("stt.server.timeout", 1800))


def get_local_device(config) -> str:
    device = str(config.get("stt.local.device", "cpu")).lower()
    return "gpu" if device == "gpu" else "cpu"


def get_local_model_name(config) -> str:
    model = config.get("stt.local.model")
    if model:
        return str(model)
    # legacy
    if config.get("stt.local.whisper_model"):
        return str(config.get("stt.local.whisper_model"))
    model_id = config.get("stt.local_model_id", "")
    if isinstance(model_id, str) and ":" in model_id:
        _engine, name = model_id.split(":", 1)
        if _engine == "vosk" and not name.startswith("vosk-model"):
            return f"vosk-model-{name}" if name else DEFAULT_VOSK_MODEL
        return name
    path = config.get("stt.model_path", "")
    if path:
        base = os.path.basename(path.replace("\\", "/").rstrip("/"))
        if base:
            return base
    engine = config.get("stt.local.engine", "")
    if engine == "whisper":
        return DEFAULT_WHISPER_MODEL
    return DEFAULT_VOSK_MODEL


def get_stt_option(config, key: str, default: Any = None) -> Any:
    if default is None:
        default = _STT_OPTION_DEFAULTS.get(key)
    value = config.get(f"stt.options.{key}", None)
    if value is not None:
        return value
    # legacy
    return config.get(f"stt.local.{key}", config.get(f"stt.server.{key}", default))


def resolve_local_engine(config) -> str:
    name = get_local_model_name(config)
    return "vosk" if is_vosk_model_name(name) else "whisper"


def resolve_local_device(config) -> str:
    """Фактическое устройство: Vosk всегда cpu."""
    if resolve_local_engine(config) == "vosk":
        return "cpu"
    return get_local_device(config)


def model_path_for_name(model_name: str, project_root: Optional[str] = None) -> str:
    root = project_root or _project_root()
    name = model_name.strip()
    if is_vosk_model_name(name):
        return os.path.join(root, "models", name).replace("\\", "/")
    cache = os.path.join(root, "models", "whisper")
    return os.path.join(cache, name).replace("\\", "/")


def get_local_model_path(config, project_root: Optional[str] = None) -> str:
    return model_path_for_name(get_local_model_name(config), project_root)


def set_local_selection(config, device: str, model: str) -> None:
    """Записать device + model в конфиг (как в интерфейсе)."""
    device = (device or "cpu").lower()
    model = (model or DEFAULT_VOSK_MODEL).strip()
    if is_vosk_model_name(model):
        device = "cpu"
    config.set("stt.local.device", device)
    config.set("stt.local.model", model)


def apply_model_to_config(config, device: str, model: str) -> None:
    set_local_selection(config, device, model)


def normalize_client_stt_section(stt: dict) -> dict:
    """Привести секцию stt к упрощённому виду (миграция со старого формата)."""
    stt = dict(stt or {})
    remote = dict(stt.get("remote") or stt.get("server") or {})
    local_raw = dict(stt.get("local") or {})

    device = str(local_raw.get("device", "cpu")).lower()
    if device not in ("cpu", "gpu"):
        device = "cpu"

    model = local_raw.get("model")
    if not model:
        if local_raw.get("whisper_model"):
            model = local_raw["whisper_model"]
        elif stt.get("local_model_id"):
            mid = str(stt["local_model_id"])
            if ":" in mid:
                eng, name = mid.split(":", 1)
                model = name if eng == "whisper" else (
                    name if str(name).startswith("vosk-model") else f"vosk-model-{name}"
                )
        elif stt.get("model_path"):
            model = os.path.basename(str(stt["model_path"]).replace("\\", "/").rstrip("/"))
        elif local_raw.get("engine") == "whisper":
            model = DEFAULT_WHISPER_MODEL
        else:
            model = DEFAULT_VOSK_MODEL

    if is_vosk_model_name(str(model)):
        device = "cpu"

    options = dict(_STT_OPTION_DEFAULTS)
    options.update(stt.get("options") or {})
    for key in STT_OPTION_KEYS:
        if key in local_raw:
            options[key] = local_raw[key]
        legacy_server = stt.get("server") or {}
        if key in legacy_server and key not in stt.get("options", {}):
            options[key] = legacy_server[key]

    return {
        "mode": stt.get("mode", "none"),
        "recognition": recognition_from_legacy(stt),
        "remote": {
            "host": remote.get("host", "127.0.0.1"),
            "port": int(remote.get("port", 8765)),
            "timeout": int(remote.get("timeout", 1800)),
        },
        "local": {
            "device": device,
            "model": str(model),
        },
        "options": options,
    }


def normalize_client_config(config: dict) -> dict:
    """Убрать устаревшие поля, оставить простую структуру."""
    result = dict(config)
    if "stt" in result:
        result["stt"] = normalize_client_stt_section(result["stt"])
    return result


def resolve_local_model(config, project_root: Optional[str] = None):
    """
    Совместимость с UI: LocalSTTModel из device + model.
    """
    from utils.stt_model_catalog import LocalSTTModel, _WHISPER_CPU_RAM_MB, _WHISPER_GPU_VRAM_MB, _VOSK_MEMORY_MB, _WHISPER_TITLES, _vosk_title

    name = get_local_model_name(config)
    device = resolve_local_device(config)
    engine = resolve_local_engine(config)
    path = model_path_for_name(name, project_root)

    if engine == "vosk":
        memory_mb = _VOSK_MEMORY_MB.get(name, 500)
        return LocalSTTModel(
            model_id=f"vosk:{name}",
            path=path,
            engine="vosk",
            title=_vosk_title(name),
            device="cpu",
            memory_mb=memory_mb,
            memory_kind="ram",
        )

    memory_kind = "vram" if device == "gpu" else "ram"
    table = _WHISPER_GPU_VRAM_MB if device == "gpu" else _WHISPER_CPU_RAM_MB
    title = _WHISPER_TITLES.get(name, f"Whisper {name}")
    return LocalSTTModel(
        model_id=f"whisper:{name}",
        path=path,
        engine="whisper",
        title=title,
        device=device,
        memory_mb=table.get(name, 1500),
        memory_kind=memory_kind,
        whisper_size=name,
    )


def model_info_text(config) -> str:
    model = resolve_local_model(config)
    return model.info_text if model else ""
