# -*- coding: utf-8 -*-
"""Download faster-whisper models into project folder with visible progress."""

import os
import threading
from contextlib import contextmanager
from urllib.request import getproxies

from utils.session_logger import get_logger

log = get_logger()

_PROXY_ENV_KEYS = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
)

_MODEL_REPOS = {
    "tiny.en": "Systran/faster-whisper-tiny.en",
    "tiny": "Systran/faster-whisper-tiny",
    "base.en": "Systran/faster-whisper-base.en",
    "base": "Systran/faster-whisper-base",
    "small.en": "Systran/faster-whisper-small.en",
    "small": "Systran/faster-whisper-small",
    "medium.en": "Systran/faster-whisper-medium.en",
    "medium": "Systran/faster-whisper-medium",
    "large-v1": "Systran/faster-whisper-large-v1",
    "large-v2": "Systran/faster-whisper-large-v2",
    "large-v3": "Systran/faster-whisper-large-v3",
    "large": "Systran/faster-whisper-large-v3",
    "distil-large-v2": "Systran/faster-distil-whisper-large-v2",
    "distil-medium.en": "Systran/faster-distil-whisper-medium.en",
    "distil-small.en": "Systran/faster-distil-whisper-small.en",
    "distil-large-v3": "Systran/faster-distil-whisper-large-v3",
    "large-v3-turbo": "mobiuslabsgmbh/faster-whisper-large-v3-turbo",
    "turbo": "mobiuslabsgmbh/faster-whisper-large-v3-turbo",
}

_MODEL_SIZE_HINT = {
    "tiny": "~75 МБ",
    "base": "~150 МБ",
    "small": "~500 МБ",
    "medium": "~1.5 ГБ",
    "large": "~3 ГБ",
    "large-v3": "~3 ГБ",
    "large-v3-turbo": "~1.6 ГБ",
    "turbo": "~1.6 ГБ",
}

_ALLOW_PATTERNS = [
    "config.json",
    "preprocessor_config.json",
    "model.bin",
    "tokenizer.json",
    "vocabulary.*",
]


def list_whisper_models():
    """Sorted supported Whisper model ids for CLI/docs."""
    return sorted(_MODEL_REPOS.keys())


def whisper_model_dir(config, model_size=None):
    """Local directory for a Whisper model size."""
    cache_root = config.get_stt_engine("whisper_cache_dir", "models/whisper")
    size = model_size or config.get_stt_engine("whisper_model", "medium")
    return os.path.join(cache_root, size)


def is_whisper_model_ready(model_dir):
    """True if converted CTranslate2 model files are present."""
    return os.path.isfile(os.path.join(model_dir, "model.bin"))


def get_model_size_hint(model_size):
    return _MODEL_SIZE_HINT.get(model_size, "несколько ГБ")


def _describe_system_proxies():
    """Env vars + Windows registry proxies (urllib)."""
    parts = []
    for key in _PROXY_ENV_KEYS:
        value = os.environ.get(key)
        if value:
            parts.append(f"{key}={value}")
    for key, value in getproxies().items():
        if value and key not in ("no",):
            parts.append(f"win:{key}={value}")
    return parts


@contextmanager
def _without_proxy_env():
    saved = {k: os.environ.pop(k, None) for k in _PROXY_ENV_KEYS}
    try:
        yield
    finally:
        for key, value in saved.items():
            if value is not None:
                os.environ[key] = value


@contextmanager
def _hf_http_direct():
    """
    HuggingFace httpx client without system/registry proxy.

    On Windows socks4 from VPN is often only in the registry — clearing env is not enough.
    """
    import httpx
    from huggingface_hub.utils._http import (
        default_client_factory,
        hf_request_event_hook,
        set_client_factory,
    )

    def direct_client_factory():
        return httpx.Client(
            event_hooks={"request": [hf_request_event_hook]},
            follow_redirects=True,
            timeout=None,
            trust_env=False,
        )

    set_client_factory(direct_client_factory)
    try:
        yield
    finally:
        set_client_factory(default_client_factory)


def _snapshot_download(repo_id, model_dir):
    from huggingface_hub import snapshot_download

    return snapshot_download(
        repo_id,
        local_dir=model_dir,
        allow_patterns=_ALLOW_PATTERNS,
    )


def download_whisper_snapshot(config, repo_id, model_dir):
    """
    Download model from HuggingFace Hub.

    httpx does not support socks4. Windows VPN proxy is often in the registry,
    not in environment variables — use trust_env=False for direct downloads.
    """
    use_proxy = config.get_stt_engine("whisper_use_system_proxy", False)
    proxy_info = _describe_system_proxies()

    if proxy_info:
        log.info("Обнаружен прокси: " + "; ".join(proxy_info))

    if use_proxy:
        log.info("Используется системный прокси (whisper_use_system_proxy=true)")
        return _snapshot_download(repo_id, model_dir)

    log.info(
        "Прямое подключение к HuggingFace (прокси отключён, trust_env=false). "
        "socks4 из VPN не поддерживается."
    )
    with _without_proxy_env(), _hf_http_direct():
        return _snapshot_download(repo_id, model_dir)


def ensure_whisper_model(config, model_size=None):
    """
    Ensure Whisper model exists locally. Downloads from HuggingFace if needed.

    Returns:
        Absolute path to model directory.
    """
    size = model_size or config.get_stt_engine("whisper_model", "medium")
    model_dir = os.path.abspath(whisper_model_dir(config, size))

    if is_whisper_model_ready(model_dir):
        log.info(f"Whisper model ready locally: {model_dir}")
        return model_dir

    repo_id = _MODEL_REPOS.get(size)
    if not repo_id:
        raise ValueError(
            f"Unknown whisper model '{size}'. "
            f"Supported: {', '.join(sorted(_MODEL_REPOS.keys()))}"
        )

    os.makedirs(model_dir, exist_ok=True)
    size_hint = get_model_size_hint(size)
    log.info("=" * 60)
    log.info(f"Скачивание Whisper '{size}' ({size_hint}) с HuggingFace")
    log.info(f"Репозиторий: {repo_id}")
    log.info(f"Папка: {model_dir}")
    log.info("VRAM появится только ПОСЛЕ скачивания и загрузки в CUDA.")
    log.info("Прогресс скачивания — полоска ниже в консоли.")
    log.info("=" * 60)

    stop_watch = threading.Event()

    def size_watcher():
        while not stop_watch.wait(30):
            total = _dir_size_mb(model_dir)
            if total > 0:
                log.info(f"Скачивание… уже на диске: {total:.0f} МБ ({model_dir})")

    watcher = threading.Thread(target=size_watcher, name="WhisperDownloadWatch", daemon=True)
    watcher.start()

    try:
        download_whisper_snapshot(config, repo_id, model_dir)
    finally:
        stop_watch.set()

    if not is_whisper_model_ready(model_dir):
        raise RuntimeError(
            f"Скачивание завершилось, но model.bin не найден в {model_dir}. "
            f"Скачайте вручную: https://huggingface.co/{repo_id}"
        )

    log.info(f"Whisper model downloaded: {model_dir} ({_dir_size_mb(model_dir):.0f} МБ)")
    return model_dir


def _dir_size_mb(path):
    total = 0
    if not os.path.isdir(path):
        return 0.0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                pass
    return total / (1024 * 1024)
