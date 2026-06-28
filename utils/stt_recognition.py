# -*- coding: utf-8 -*-
"""Recognition options for STT (language, translation, prompts).

Handles the conversion between config settings, HTTP headers, and
faster-whisper transcribe() keyword arguments.

Flow::

    Config → build_recognition_options() → recognition_headers()
    → HTTP POST /api/transcribe → parse_recognition_headers()
    → build_whisper_transcribe_kwargs() → model.transcribe()
"""

from __future__ import annotations

from typing import Any, Dict, Optional

DEFAULT_RECOGNITION = {
    "source_language": "ru",
    "translate": False,
    "target_language": "en",
}

SOURCE_LANGUAGE_CHOICES = (
    ("ru", "Русский"),
    ("en", "English"),
    ("uk", "Українська"),
    ("de", "Deutsch"),
    ("auto", "Авто"),
)

TARGET_LANGUAGE_CHOICES = (
    ("en", "English"),
)

# Initial prompt hints for Whisper to reduce English leakage when
# transcribing in Russian or other non-English languages.
_WHISPER_INITIAL_PROMPTS = {
    "ru": "Распознавание речи на русском языке. Текст:",
    "en": "Speech recognition in English. Text:",
    "uk": "Розпізнавання мови українською. Текст:",
    "de": "Spracherkennung auf Deutsch. Text:",
}


def normalize_recognition(raw: Optional[dict]) -> dict:
    """Normalize a recognition config dict to canonical form.

    Validates source_language, target_language, and ensures all
    required keys are present.
    """
    data = dict(DEFAULT_RECOGNITION)
    if raw:
        data.update(raw)
    source = str(data.get("source_language", "ru")).strip().lower() or "ru"
    if source not in {code for code, _ in SOURCE_LANGUAGE_CHOICES}:
        source = "ru"
    target = str(data.get("target_language", "en")).strip().lower() or "en"
    if target not in {code for code, _ in TARGET_LANGUAGE_CHOICES}:
        target = "en"
    return {
        "source_language": source,
        "translate": bool(data.get("translate", False)),
        "target_language": target,
        "initial_prompt": (data.get("initial_prompt") or "").strip() or None,
    }


def recognition_from_legacy(config_dict: dict) -> dict:
    """Migrate stt.language → recognition.source_language for old configs."""
    stt = config_dict.get("stt") or {}
    rec = dict(stt.get("recognition") or {})
    if "source_language" not in rec and stt.get("language"):
        rec["source_language"] = stt["language"]
    return normalize_recognition(rec)


def get_recognition_config(config) -> dict:
    """Extract the recognition section from a Config object."""
    if hasattr(config, "get"):
        rec = config.get("stt.recognition")
        if rec:
            return normalize_recognition(rec)
        return normalize_recognition({"source_language": config.get("stt.language", "ru")})
    if isinstance(config, dict):
        return recognition_from_legacy(config)
    return normalize_recognition(None)


def build_recognition_options(config) -> Dict[str, Any]:
    """Build recognition options dict for Whisper/Vosk and HTTP requests.

    Default: transcribe in Russian (no translation).
    Returns dict with: source_language, target_language, translate,
    task, language, initial_prompt.
    """
    rec = get_recognition_config(config)
    source = rec["source_language"]
    translate = rec["translate"]
    language = None if source == "auto" else source
    task = "translate" if translate else "transcribe"
    return {
        "source_language": source,
        "target_language": rec["target_language"] if translate else source,
        "translate": translate,
        "task": task,
        "language": language,
        "initial_prompt": rec.get("initial_prompt"),
    }


def build_whisper_transcribe_kwargs(
    recognition_options: Dict[str, Any],
    *,
    beam_size: int = 5,
    vad_filter: bool = True,
) -> Dict[str, Any]:
    """Build keyword arguments for faster-whisper's ``transcribe()``.

    Includes language, task, beam_size, VAD filter, and initial_prompt.
    For transcribe + Russian, an initial_prompt is added to prevent
    the model from outputting English text.
    """
    opts = dict(recognition_options or {})
    task = opts.get("task", "transcribe")
    source = opts.get("source_language", "ru")

    kwargs: Dict[str, Any] = {
        "language": opts.get("language"),
        "task": task,
        "beam_size": beam_size,
        "vad_filter": vad_filter,
        "condition_on_previous_text": False,
    }

    if task == "transcribe" and source and source != "auto":
        prompt = opts.get("initial_prompt") or _WHISPER_INITIAL_PROMPTS.get(source)
        if prompt:
            kwargs["initial_prompt"] = prompt

    return kwargs


def recognition_headers(options: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    """Build HTTP headers for ``POST /api/transcribe``.

    Encodes recognition options as ``X-STT-*`` headers.
    """
    opts = options or {}
    headers = {
        "X-STT-Task": str(opts.get("task", "transcribe")),
        "X-STT-Source-Language": str(opts.get("source_language", "ru")),
        "X-STT-Translate": "true" if opts.get("translate") else "false",
    }
    if opts.get("translate"):
        headers["X-STT-Target-Language"] = str(opts.get("target_language", "en"))
    return headers


def parse_recognition_headers(headers, server_defaults: Optional[dict] = None) -> Dict[str, Any]:
    """Parse ``X-STT-*`` headers from the request; fall back to server defaults."""
    base = build_recognition_options_from_dict(server_defaults or DEFAULT_RECOGNITION)

    def _header(name: str, default: str = "") -> str:
        return (headers.get(name) or default).strip()

    task = _header("X-STT-Task", base["task"]).lower()
    if task not in ("transcribe", "translate"):
        task = "transcribe"

    source = _header("X-STT-Source-Language", base["source_language"]).lower() or "ru"
    translate_raw = _header("X-STT-Translate", "false").lower()
    translate = translate_raw in ("1", "true", "yes", "on")
    if task == "translate":
        translate = True

    target = _header("X-STT-Target-Language", base.get("target_language", "en")).lower() or "en"

    rec = normalize_recognition({
        "source_language": source,
        "translate": translate,
        "target_language": target,
    })
    return build_recognition_options_from_dict(rec)


def build_recognition_options_from_dict(rec: dict) -> Dict[str, Any]:
    rec = normalize_recognition(rec)
    source = rec["source_language"]
    translate = rec["translate"]
    return {
        "source_language": source,
        "target_language": rec["target_language"] if translate else source,
        "translate": translate,
        "task": "translate" if translate else "transcribe",
        "language": None if source == "auto" else source,
        "initial_prompt": rec.get("initial_prompt"),
    }
