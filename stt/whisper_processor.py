# -*- coding: utf-8 -*-
"""STT processor using faster-whisper (NVIDIA CUDA or CPU).

Uses the ``faster-whisper`` library (CTranslate2 backend) for high-speed
speech recognition. Supports GPU acceleration via CUDA and automatic
CPU fallback when no GPU is available.

Model loading flow
-----------------
1. Check CUDA availability via ctranslate2.
2. If GPU mode requested and CUDA available → load on GPU (float16).
3. Run a short warmup inference to catch missing cuBLAS at runtime.
4. If GPU fails or CPU fallback enabled → load on CPU (int8).

Interface
---------
Implements the same interface as :class:`stt.processor.STTProcessor`:
- ``initialize()``, ``is_model_loaded()``, ``is_ready()``
- ``process_audio_file_sync()``
- ``get_engine_label()``, ``get_device_label()``, ``get_mode_label()``
- ``cleanup()``
"""

import os
import struct
import sys
import tempfile
import time
import wave

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from utils.cuda_runtime import configure_cuda_dll_paths, find_cublas_dll
from utils.session_logger import get_logger
from utils.stt_recognition import build_recognition_options, build_whisper_transcribe_kwargs
from utils.whisper_downloader import ensure_whisper_model

# CUDA DLL paths must be set before ctranslate2 is imported
configure_cuda_dll_paths()

log = get_logger()


def cuda_available() -> bool:
    """Check if at least one NVIDIA CUDA device is available."""
    try:
        import ctranslate2
        return ctranslate2.get_cuda_device_count() > 0
    except Exception:
        return False


def log_cuda_status():
    """Log CUDA device count and cuBLAS DLL status for diagnostics."""
    try:
        import ctranslate2

        count = ctranslate2.get_cuda_device_count()
        log.info(f"CUDA: GPU count = {count}")
        cublas = find_cublas_dll()
        if count > 0 and cublas:
            log.info(f"cuBLAS: {cublas}")
        elif count > 0:
            log.warning(
                "cublas64_12.dll not found. Run: pip install -r requirements-server.txt"
            )
        if count == 0:
            log.warning("CUDA: no NVIDIA GPU detected by ctranslate2")
    except Exception as exc:
        log.warning(f"CUDA: check failed — {exc}")


class WhisperSTTProcessor:
    """Speech-to-text processor using faster-whisper (GPU preferred).

    Tries GPU (CUDA, float16) first; falls back to CPU (int8) if GPU
    is unavailable or the warmup inference fails.
    """

    def __init__(self, config):
        """Initialize from config.

        Args:
            config: Config object — reads device mode, model size,
                compute type, recognition options, and fallback setting.
        """
        self.config = config
        self.model = None          # faster_whisper.WhisperModel instance
        self.device_mode = str(config.get_stt_engine("device", "gpu")).lower()  # "gpu" or "cpu"
        self.model_size = config.get_stt_engine("whisper_model", "medium")       # e.g. "large-v3-turbo"
        self.compute_type_gpu = config.get_stt_engine("whisper_compute_type", "float16")
        self._default_recognition = build_recognition_options(config)
        self.fallback_cpu = config.get_stt_engine("fallback_cpu", True)  # Auto-fallback to CPU?
        self.actual_device = "cpu"      # Updated after initialize() ("cpu" or "cuda")
        self.engine_label = "whisper-cpu"  # Updated after initialize()
        self.model_path = None          # Path to the downloaded model folder

    def initialize(self, is_cancelled=None):
        """Load the Whisper model (GPU first, CPU fallback).

        Args:
            is_cancelled: Optional callable returning True if loading should
                be aborted (e.g. generation counter mismatch on model switch).
                Checked at key points to avoid wasting time on GPU warmup
                for a model that will be immediately discarded.

        Returns:
            True if the model loaded successfully, False otherwise.
        """
        # Helper: check cancellation without raising
        def _cancelled():
            if is_cancelled and is_cancelled():
                log.info("Whisper initialize cancelled (is_cancelled=True)")
                self.model = None
                return True
            return False

        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            log.error(
                "faster-whisper not installed. Run: pip install -r requirements-server.txt"
            )
            raise exc

        log_cuda_status()

        try:
            self.model_path = ensure_whisper_model(self.config, self.model_size)
        except Exception as exc:
            log.error(f"Whisper model download failed: {exc}")
            return False

        if _cancelled():
            return False

        want_gpu = self.device_mode == "gpu"
        if want_gpu and cuda_available():
            if not find_cublas_dll():
                log.warning("cuBLAS not available — skipping GPU load")
            else:
                log.info("Loading model into VRAM (CUDA)...")
                if self._load_model(WhisperModel, "cuda", self.compute_type_gpu):
                    # Check cancellation BEFORE GPU warmup (saves ~15s if superseded)
                    if _cancelled():
                        log.info("Skipping GPU warmup — load cancelled")
                        return False
                    if self._verify_gpu_inference():
                        self.actual_device = "cuda"
                        self.engine_label = "whisper-gpu"
                        log.info(f"Whisper on GPU (CUDA), model={self.model_size}")
                        self._warn_distil_russian()
                        return True
                    log.warning("GPU inference test failed (cublas/cudnn)")
                    self.model = None

        # GPU failed or not requested — try CPU fallback
        if want_gpu and not self.fallback_cpu:
            log.error("GPU unavailable and fallback_cpu=false")
            return False

        if _cancelled():
            return False

        log.info("Loading model into RAM (CPU)...")
        if self._load_model(WhisperModel, "cpu", "int8"):
            self.actual_device = "cpu"
            self.engine_label = "whisper-cpu"
            log.info(f"Whisper on CPU, model={self.model_size}")
            self._warn_distil_russian()
            return True

        return False

    def _load_model(self, whisper_model_cls, device, compute_type):
        """Attempt to load the Whisper model on the given device.

        Args:
            whisper_model_cls: The ``faster_whisper.WhisperModel`` class.
            device: "cuda" for GPU or "cpu" for CPU.
            compute_type: Quantization type ("float16" for GPU, "int8" for CPU).

        Returns:
            True if loaded successfully, False on error.
        """
        try:
            log.info(
                f"Initializing Whisper '{self.model_size}' on {device} "
                f"(compute_type={compute_type})..."
            )
            start = time.time()
            self.model = whisper_model_cls(
                self.model_path,
                device=device,
                compute_type=compute_type,
                local_files_only=True,  # Don't download at runtime
            )
            elapsed = time.time() - start
            log.info(f"Whisper loaded on {device} in {elapsed:.1f}s")
            multilingual = getattr(getattr(self.model, "model", None), "is_multilingual", None)
            if multilingual is not None:
                log.info(f"Whisper model multilingual={multilingual}")
            if device == "cuda":
                log.info("Model in VRAM — check nvidia-smi")
            return True
        except Exception as exc:
            log.error(f"Whisper load error ({device}): {exc}")
            self.model = None
            return False

    def _verify_gpu_inference(self):
        """Run a short test transcription to catch missing cuBLAS at runtime.

        Creates a tiny silent WAV file and transcribes it. If cuBLAS
        is missing, the inference will fail here rather than on a real request.

        Returns:
            True if GPU inference works, False if it fails.
        """
        if not self.model:
            return False
        temp_path = None
        try:
            fd, temp_path = tempfile.mkstemp(suffix=".wav")
            os.close(fd)
            with wave.open(temp_path, "w") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(b"\x00\x00" * 8000)
            log.info("GPU warmup: test inference...")
            segments, _ = self.model.transcribe(
                temp_path,
                language=self._default_recognition.get("language"),
                task="transcribe",
                beam_size=1,
                vad_filter=False,
            )
            list(segments)
            log.info("GPU warmup: OK")
            return True
        except Exception as exc:
            log.error(f"GPU warmup failed: {exc}")
            return False
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

    def is_model_loaded(self):
        """Check if the Whisper model is loaded."""
        return self.model is not None

    def is_ready(self):
        """Alias for is_model_loaded (common STT backend interface)."""
        return self.is_model_loaded()

    def get_engine_label(self):
        """Return engine identifier (e.g. 'whisper-gpu' or 'whisper-cpu')."""
        return self.engine_label

    def get_device_label(self):
        """Return device identifier ('cuda' or 'cpu')."""
        return self.actual_device

    def get_mode_label(self):
        """Return human-readable mode label for UI display."""
        dev = "GPU" if self.actual_device == "cuda" else "CPU"
        return f"локально Whisper {self.model_size} ({dev})"

    def _warn_distil_russian(self):
        """Warn if a distil model is used with Russian (known issue).

        distil-* models often output English instead of Russian even
        when ``language=ru`` is specified. This is a known limitation.
        """
        if "distil" not in str(self.model_size).lower():
            return
        src = self._default_recognition.get("source_language", "ru")
        if src in ("ru", "uk"):
            log.warning(
                "Model %s poorly recognizes Russian (often outputs English). "
                "Use large-v3-turbo or large-v3 in config.server.json",
                self.model_size,
            )

    def _resolve_recognition(self, recognition_options=None):
        """Merge default recognition options with per-request overrides.

        Args:
            recognition_options: Optional dict from client/request headers.

        Returns:
            Dict with task, language, translate, etc.
        """
        opts = dict(self._default_recognition)
        if recognition_options:
            opts.update(recognition_options)
        if not opts.get("translate"):
            opts["task"] = "transcribe"
        return opts

    def process_audio_file_sync(self, audio_filepath, recognition_options=None):
        """Transcribe an audio file synchronously.

        Args:
            audio_filepath: Path to the audio file (WAV, MP3, etc.).
            recognition_options: Optional dict with language/translation settings.

        Returns:
            dict with text, processing_time, text_length, engine, device, etc.
            Returns None on error or if model is not loaded.
        """
        if not self.is_model_loaded():
            return None

        rec = self._resolve_recognition(recognition_options)
        transcribe_kwargs = build_whisper_transcribe_kwargs(rec)

        try:
            log.info(
                f"Whisper transcribe kwargs: task={transcribe_kwargs.get('task')} "
                f"lang={transcribe_kwargs.get('language')} "
                f"prompt={bool(transcribe_kwargs.get('initial_prompt'))}"
            )
            start = time.time()
            segments, info = self.model.transcribe(audio_filepath, **transcribe_kwargs)
            parts = []
            for segment in segments:
                text = segment.text.strip()
                if text:
                    parts.append(text)
            result_text = " ".join(parts).strip()
            processing_time = time.time() - start
            log.info(
                f"Whisper ({self.actual_device}) {transcribe_kwargs.get('task')} "
                f"src={rec.get('source_language')} whisper_lang={getattr(info, 'language', '?')} "
                f"prob={getattr(info, 'language_probability', 0):.2f} "
                f"done in {processing_time:.2f}s, {len(result_text)} chars"
            )
            if result_text:
                preview = result_text[:120] + ("…" if len(result_text) > 120 else "")
                log.info(f"Whisper result: {preview!r}")
            return {
                "text": result_text,
                "processing_time": processing_time,
                "text_length": len(result_text),
                "file_path": audio_filepath,
                "engine": self.engine_label,
                "device": self.actual_device,
                "task": transcribe_kwargs.get("task"),
                "source_language": rec.get("source_language"),
                "target_language": rec.get("target_language"),
                "detected_language": getattr(info, "language", None),
            }
        except Exception as exc:
            log.error(f"Whisper transcribe error: {exc}")
            return None

    def cleanup(self):
        """Release the Whisper model (free VRAM/RAM).

        Explicitly calls gc.collect() to ensure CTranslate2 releases
        GPU/CPU memory immediately rather than waiting for GC cycles.
        Calls torch.cuda.empty_cache() if available to free CUDA allocator.
        """
        if self.model is not None:
            log.info(f"Cleaning up Whisper model (device={self.actual_device})...")
        self.model = None
        import gc
        # Two-pass GC to ensure all circular references are collected
        gc.collect()
        gc.collect()
        # Try to free CUDA cache if torch is available (faster-whisper uses CTranslate2,
        # but some setups may have torch loaded which holds VRAM references)
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                log.info("CUDA cache cleared")
        except ImportError:
            pass
        log.info("Whisper processor cleaned up (model released)")
