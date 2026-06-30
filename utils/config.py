# -*- coding: utf-8 -*-
"""
Configuration management for Clerkonator client and server.

Each profile (client / server) uses its own JSON config file:
* ``config.client.json`` — client settings (hotkeys, audio, GUI, STT connection)
* ``config.server.json`` — server settings (listen port, STT device, model)

A legacy ``config.json`` is automatically split into the two files on
first run via :meth:`Config._migrate_legacy_if_needed`.
"""

import json
import os
from copy import deepcopy
from datetime import datetime
from typing import Any, Optional

CLIENT_CONFIG_FILE = "config.client.json"
SERVER_CONFIG_FILE = "config.server.json"
LEGACY_CONFIG_FILE = "config.json"

_STT_ENGINE_KEYS = (
    "device",
    "whisper_model",
    "whisper_cache_dir",
    "whisper_use_system_proxy",
    "whisper_compute_type",
    "fallback_cpu",
)


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


def _config_path(filename: str) -> str:
    return os.path.join(_project_root(), filename)


DEFAULT_CLIENT_CONFIG = {
    "hotkeys": {
        "show_window": "ctrl+shift+s",
        "record_toggle": "ctrl+shift+r",
    },
    "audio": {
        "sample_rate": 16000,
        "channels": 1,
        "chunk_size": 4096,
        "format": "int16",
        "input_device_index": -1,
    },
    "stt": {
        "mode": "none",
        "recognition": {
            "source_language": "ru",
            "translate": False,
            "target_language": "en",
        },
        "remote": {
            "host": "127.0.0.1",
            "port": 8765,
            "timeout": 1800,
        },
        "local": {
            "device": "cpu",
            "model": "vosk-model-ru-0.42",
        },
        "options": {
            "whisper_cache_dir": "models/whisper",
            "whisper_use_system_proxy": False,
            "whisper_compute_type": "float16",
            "fallback_cpu": True,
        },
    },
    "files": {
        "audio_dir": "data/recordings",
        "text_dir": "data/transcriptions",
        "audio_format": "wav",
    },
    "gui": {
        "window_size": "480x340",
        "always_on_top": False,
        "theme": "dark",
        "auto_copy": True,
    },
}

DEFAULT_SERVER_CONFIG = {
    "listen": {
        "host": "0.0.0.0",
        "port": 8765,
    },
    "audio": {
        "sample_rate": 16000,
    },
    "stt": {
        "recognition": {
            "source_language": "ru",
            "translate": False,
            "target_language": "en",
        },
        "language": "ru",
        "model_path": "models/vosk-model-ru-0.42",
        "server": {
            "device": "gpu",
            "whisper_model": "large-v3-turbo",
            "whisper_cache_dir": "models/whisper",
            "whisper_use_system_proxy": False,
            "whisper_compute_type": "float16",
            "fallback_cpu": True,
        },
    },
}


def _merge_configs(default: dict, user: dict) -> dict:
    result = deepcopy(default)
    for key, value in user.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _merge_configs(result[key], value)
        else:
            result[key] = value
    return result


def _extract_client_config(legacy: dict) -> dict:
    from utils.client_stt_config import normalize_client_config

    stt = legacy.get("stt", {})
    server_remote = stt.get("server", {})
    local = stt.get("local", {})

    raw = {
        "hotkeys": legacy.get("hotkeys", {}),
        "audio": legacy.get("audio", {}),
        "files": legacy.get("files", {}),
        "gui": legacy.get("gui", {}),
        "stt": {
            "mode": stt.get("mode", "none"),
            "language": stt.get("language", "ru"),
            "remote": {
                "host": server_remote.get("host", "127.0.0.1"),
                "port": server_remote.get("port", 8765),
                "timeout": server_remote.get("timeout", 1800),
            },
            "local": {
                "device": local.get("device", "cpu"),
                "model": local.get("model") or local.get("whisper_model"),
            },
            "options": {},
            "model_path": stt.get("model_path"),
            "local_model_id": stt.get("local_model_id"),
            "server": server_remote,
        },
    }
    if raw["stt"]["local"]["model"] is None:
        del raw["stt"]["local"]["model"]
    return normalize_client_config(raw)


def _extract_server_config(legacy: dict) -> dict:
    stt = legacy.get("stt", {})
    server_block = stt.get("server", {})
    return {
        "listen": {
            "host": "0.0.0.0",
            "port": server_block.get("port", 8765),
        },
        "audio": {
            "sample_rate": legacy.get("audio", {}).get("sample_rate", 16000),
        },
        "stt": {
            "language": stt.get("language", "ru"),
            "model_path": stt.get("model_path", DEFAULT_SERVER_CONFIG["stt"]["model_path"]),
            "server": {
                key: server_block.get(key, DEFAULT_SERVER_CONFIG["stt"]["server"][key])
                for key in DEFAULT_SERVER_CONFIG["stt"]["server"]
            },
        },
    }


class Config:
    """Configuration manager for client or server profile.

    Loads, merges, and saves JSON config files. Uses a dotted-path API:
    ``config.get("listen.port", 8765)``.
    """

    def __init__(self, profile: str = "client", config_file: Optional[str] = None):
        profile = (profile or "client").lower()
        if profile not in ("client", "server"):
            raise ValueError(f"Unknown config profile: {profile}")

        self.profile = profile
        if config_file:
            self.config_file = config_file
        elif profile == "server":
            self.config_file = _config_path(SERVER_CONFIG_FILE)
        else:
            self.config_file = _config_path(CLIENT_CONFIG_FILE)

        self.default_config = (
            deepcopy(DEFAULT_SERVER_CONFIG)
            if profile == "server"
            else deepcopy(DEFAULT_CLIENT_CONFIG)
        )
        self._migrate_legacy_if_needed()
        self.config = self.load_config()

    def _migrate_legacy_if_needed(self):
        """Split legacy config.json into client/server configs on first run."""
        if os.path.exists(self.config_file):
            return

        legacy_path = _config_path(LEGACY_CONFIG_FILE)
        if not os.path.exists(legacy_path):
            return

        try:
            with open(legacy_path, "r", encoding="utf-8") as handle:
                legacy = json.load(handle)
        except (OSError, json.JSONDecodeError):
            return

        client_path = _config_path(CLIENT_CONFIG_FILE)
        server_path = _config_path(SERVER_CONFIG_FILE)

        if not os.path.exists(client_path):
            self._write_json(client_path, _extract_client_config(legacy))
        if not os.path.exists(server_path):
            self._write_json(server_path, _extract_server_config(legacy))

    def load_config(self) -> dict:
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as handle:
                    user_config = json.load(handle)
                merged = _merge_configs(self.default_config, user_config)
                if self.profile == "client":
                    from utils.client_stt_config import normalize_client_config

                    return normalize_client_config(merged)
                return merged
            except (OSError, json.JSONDecodeError) as exc:
                print(f"⚠️ Error загрузки конфигурации: {exc}")
                return deepcopy(self.default_config)

        self.save_config(self.default_config)
        return deepcopy(self.default_config)

    def save_config(self, config: Optional[dict] = None) -> None:
        payload = config if config is not None else self.config
        if self.profile == "client":
            from utils.client_stt_config import normalize_client_config

            payload = normalize_client_config(payload)
            self.config = payload
        self._write_json(self.config_file, payload)

    @staticmethod
    def _write_json(path: str, payload: dict) -> None:
        try:
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
        except OSError as exc:
            print(f"⚠️ Error сохранения конфигурации: {exc}")

    def get(self, key_path: str, default: Any = None) -> Any:
        keys = key_path.split(".")
        value: Any = self.config
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default

    def set(self, key_path: str, value: Any) -> None:
        keys = key_path.split(".")
        node = self.config
        for key in keys[:-1]:
            if key not in node or not isinstance(node[key], dict):
                node[key] = {}
            node = node[key]
        node[keys[-1]] = value
        self.save_config()

    def get_stt_engine(self, key: str, default: Any = None) -> Any:
        """Get STT engine parameters (Whisper/Vosk device settings).

        For server profile: reads from ``stt.server.<key>``.
        For client profile: delegates to client_stt_config helpers.
        """
        if self.profile == "server":
            return self.get(f"stt.server.{key}", default)
        from utils.client_stt_config import (
            get_local_device,
            get_local_model_name,
            get_stt_option,
            is_vosk_model_name,
        )

        if key == "device":
            return get_local_device(self)
        if key == "whisper_model":
            name = get_local_model_name(self)
            return name if not is_vosk_model_name(name) else default
        return get_stt_option(self, key, default)

    def ensure_directories(self) -> None:
        if self.profile != "client":
            return
        for directory in (
            self.get("files.audio_dir"),
            self.get("files.text_dir"),
        ):
            if directory and not os.path.exists(directory):
                os.makedirs(directory)
                print(f"📁 Создана директория: {directory}")

    def get_audio_filename(self) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        audio_format = self.get("files.audio_format", "wav")
        return f"recording_{timestamp}.{audio_format}"

    def get_text_filename(self, audio_filename: str) -> str:
        base_name = os.path.splitext(audio_filename)[0]
        return f"{base_name}.txt"
