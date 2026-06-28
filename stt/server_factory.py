# -*- coding: utf-8 -*-
"""Factory for creating the server-side STT processor.

Based on ``stt.server.device`` in ``config.server.json``:
* ``"gpu"`` → :class:`stt.whisper_processor.WhisperSTTProcessor` (CUDA preferred)
* ``"cpu"`` → :class:`stt.processor.STTProcessor` (Vosk, CPU only)
"""

from utils.session_logger import get_logger

log = get_logger()


def create_server_processor(config):
    """Create and return the appropriate STT processor based on config.

    Args:
        config: Config object — reads ``stt.server.device``.

    Returns:
        STTProcessor (Vosk/CPU) or WhisperSTTProcessor (Whisper/GPU).
    """
    device = str(config.get("stt.server.device", "gpu")).lower()
    if device == "cpu":
        from stt.processor import STTProcessor

        log.info("Server STT engine: Vosk (CPU)")
        return STTProcessor(config)

    from stt.whisper_processor import WhisperSTTProcessor

    log.info("Server STT engine: Whisper (GPU preferred)")
    return WhisperSTTProcessor(config)


def get_engine_name(config) -> str:
    """Return the engine name for the configured device mode.

    Args:
        config: Config object — reads ``stt.server.device``.

    Returns:
        "vosk" for CPU mode, "whisper" for GPU mode.
    """
    device = str(config.get("stt.server.device", "gpu")).lower()
    return "vosk" if device == "cpu" else "whisper"
