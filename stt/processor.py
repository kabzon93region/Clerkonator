# -*- coding: utf-8 -*-
"""
Vosk STT processor — CPU-only offline speech recognition.

Uses the Vosk library (KaldiRecognizer) to convert audio files to text.
No GPU support — Vosk runs entirely on CPU, making it suitable for
machines without NVIDIA GPUs.

Interface
---------
This class implements the common STT processor interface:
- ``initialize()``              — load the Vosk model
- ``is_model_loaded()``        — check readiness
- ``is_ready()``               — alias for is_model_loaded
- ``process_audio_file_sync()`` — synchronous transcription (returns dict)
- ``get_engine_label()``       — "vosk-cpu"
- ``get_device_label()``       — "cpu"
- ``get_mode_label()``        — human-readable mode description
- ``cleanup()``                — release resources
"""

import json
import wave
import threading
import time
import os
import sys
from vosk import Model, KaldiRecognizer

# Add project root to path for importing utils
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from utils.session_logger import get_logger

log = get_logger()

# Audio chunk size (frames) for streaming recognition.
# Smaller = lower latency, larger = better throughput.
_CHUNK_FRAMES = 4000

# Small sleep between chunks to keep the UI responsive (async mode only).
_CHUNK_SLEEP = 0.01


class STTProcessor:
    """Vosk-based speech-to-text processor (CPU only)."""

    def __init__(self, config):
        """Initialize the processor with config.

        Args:
            config: Config object — reads ``audio.sample_rate``,
                ``stt.model_path``, and client-specific model resolution.
        """
        self.config = config
        self.model = None          # Vosk Model instance (loaded in initialize())
        self.recognizer = None     # KaldiRecognizer instance
        self.is_processing = False  # True while async processing is active
        self.progress_callback = None   # Optional callback(progress: float)
        self.result_callback = None     # Optional callback(text: str)

        # Audio parameters from config
        self.sample_rate = config.get("audio.sample_rate", 16000)
        self.model_path = config.get("stt.model_path") or ""

        # For client profile, try to resolve the local Vosk model path
        if not self.model_path and getattr(config, "profile", "") == "client":
            from utils.client_stt_config import get_local_model_path, resolve_local_engine

            if resolve_local_engine(config) == "vosk":
                self.model_path = get_local_model_path(config)
        if not self.model_path:
            self.model_path = config.get("stt.model_path", "models/vosk-model-ru-0.42")

    def initialize(self, is_cancelled=None):
        """Load the Vosk model from disk.

        Args:
            is_cancelled: Optional callable returning True if loading should
                be aborted. Checked after the native Model() call (which
                cannot be interrupted) to release memory early if superseded.

        Returns:
            True if the model was loaded successfully, False otherwise.
        """
        # Helper: check cancellation (cleanup is done by caller via proc.cleanup())
        def _cancelled():
            if is_cancelled and is_cancelled():
                log.info("Vosk initialize cancelled (is_cancelled=True)")
                # Don't set self.model = None here — let cleanup() handle it
                return True
            return False

        try:
            if not os.path.exists(self.model_path):
                log.error(f"Vosk model not found: {self.model_path}")
                return False

            log.info("Using CPU for STT processing (Vosk doesn't support GPU)")
            log.info("Loading Vosk model...")

            # Track model loading time for diagnostics
            import time
            vosk_start_time = time.time()
            log.info(f"Vosk model loading started at {time.strftime('%H:%M:%S')}")

            # Check cancellation BEFORE the long blocking Model() call
            # (cannot be interrupted once started)
            if _cancelled():
                log.info("Skipping Model() load — already cancelled")
                return False

            # Load Vosk model and create recognizer (CPU only)
            # Note: Model() is a blocking native call that cannot be interrupted
            log.info("Calling Vosk Model() — this may take 1-2 minutes...")
            self.model = Model(self.model_path)
            log.info("Vosk Model() returned")

            # Check cancellation AFTER native Model() call (cannot interrupt it)
            if _cancelled():
                log.info("Skipping recognizer creation — load cancelled")
                return False

            self.recognizer = KaldiRecognizer(self.model, self.sample_rate)

            vosk_loading_time = time.time() - vosk_start_time
            log.info(f"Vosk model loaded in {vosk_loading_time:.2f} seconds")

            return True

        except Exception as e:
            log.error(f"Error loading Vosk model: {e}")
            return False

    def is_model_loaded(self):
        """Check if the Vosk model is loaded and ready."""
        return self.model is not None and self.recognizer is not None

    def is_ready(self):
        """Alias for is_model_loaded (common STT backend interface)."""
        return self.is_model_loaded()

    def get_mode_label(self):
        """Return a human-readable mode label for UI display."""
        return "локально"

    def get_engine_label(self):
        """Return the engine identifier for health/API responses."""
        return "vosk-cpu"

    def get_device_label(self):
        """Return the device identifier (always 'cpu' for Vosk)."""
        return "cpu"

    def cleanup(self):
        """Release the Vosk model and recognizer (free RAM).

        Vosk uses native C++ objects via ctypes. Setting to None allows
        Python's GC to eventually free the underlying memory.
        """
        if self.model is not None or self.recognizer is not None:
            log.info("Cleaning up Vosk model and recognizer...")
        self.recognizer = None
        self.model = None
        import gc
        gc.collect()
        log.info("Vosk processor cleaned up (model released)")

    def _validate_wav(self, wf):
        """Validate WAV file format (mono, 16-bit, correct sample rate).

        Returns:
            True if format is valid, False otherwise (with a warning logged).
        """
        if wf.getnchannels() != 1:
            log.warning("File must be mono")
            return False
        if wf.getsampwidth() != 2:
            log.warning("File must be 16-bit")
            return False
        if wf.getframerate() != self.sample_rate:
            log.warning(f"Sample rate must be {self.sample_rate} Hz")
            return False
        return True

    def _recognize_wav(self, wf):
        """Run Vosk recognition on an open WAV file handle.

        Shared by both sync and async processing methods.
        Streams audio in chunks, accumulates intermediate results,
        and returns the final recognized text.

        Args:
            wf: An open ``wave.Wave_read`` object positioned at the start.

        Returns:
            str: The full recognized text (may be empty if no speech detected).
        """
        total_frames = wf.getnframes()
        processed_frames = 0
        full_text = ""

        # Stream audio chunks through the recognizer
        while True:
            data = wf.readframes(_CHUNK_FRAMES)
            if len(data) == 0:
                break

            # AcceptWaveform returns True when a complete utterance is detected
            if self.recognizer.AcceptWaveform(data):
                result = json.loads(self.recognizer.Result())
                if result.get("text"):
                    intermediate_text = result['text'].strip()
                    if intermediate_text:
                        full_text += " " + intermediate_text
                        log.info(f"Intermediate result: '{intermediate_text}'")
                        log.info(f"Accumulated text: '{full_text.strip()}'")

            processed_frames += len(data)

            # Report progress for async mode (sync mode ignores callbacks)
            if self.progress_callback:
                progress = (processed_frames / max(1, total_frames)) * 100
                self.progress_callback(progress)

            # Small sleep for UI responsiveness (async mode only)
            if self.progress_callback:
                time.sleep(_CHUNK_SLEEP)

        # Get the final partial result (last utterance)
        final_result = json.loads(self.recognizer.FinalResult())
        final_text = final_result.get("text", "").strip()
        if final_text:
            full_text += " " + final_text

        return full_text.strip()

    def process_audio_file(self, audio_filepath, progress_callback=None, result_callback=None):
        """Start asynchronous audio processing (non-blocking).

        Launches a background thread that calls :meth:`_process_audio_thread`.
        Returns immediately — results are delivered via ``result_callback``.

        Args:
            audio_filepath: Path to the WAV file to process.
            progress_callback: Optional callback(float) for progress updates (0-100).
            result_callback: Optional callback(str) for the recognized text.

        Returns:
            True if processing was started, False if already busy or model not loaded.
        """
        if self.is_processing:
            log.warning("Processing already in progress")
            return False

        if not self.is_model_loaded():
            log.warning("Model not loaded")
            return False

        self.progress_callback = progress_callback
        self.result_callback = result_callback

        processing_thread = threading.Thread(
            target=self._process_audio_thread,
            args=(audio_filepath,),
            daemon=True
        )
        processing_thread.start()

        return True

    def process_audio_file_sync(self, audio_filepath, recognition_options=None):
        """Process audio file synchronously and return result with timing.

        This is the main transcription method called by the server queue worker
        and the client's local processing path.

        Args:
            audio_filepath: Path to the WAV file (mono, 16-bit, correct sample rate).
            recognition_options: Unused for Vosk (kept for interface compatibility).

        Returns:
            dict with keys: ``text``, ``processing_time``, ``text_length``,
            ``file_path`` — or None on error / empty result.
        """
        if not self.is_model_loaded():
            log.warning("Model not loaded")
            return None

        try:
            log.info(f"Starting synchronous file processing: {audio_filepath}")
            start_time = time.time()

            with wave.open(audio_filepath, 'rb') as wf:
                if not self._validate_wav(wf):
                    return None

                text = self._recognize_wav(wf)

                if text:
                    processing_time = time.time() - start_time
                    log.info(f"Synchronous processing finished in {processing_time:.2f}s")
                    log.info(f"Final text: '{text}'")
                    log.info(f"Text length: {len(text)} characters")

                    return {
                        "text": text,
                        "processing_time": processing_time,
                        "text_length": len(text),
                        "file_path": audio_filepath
                    }

        except Exception as e:
            log.error(f"Error processing audio file: {e}")
            return None

    def _process_audio_thread(self, audio_filepath):
        """Async processing thread — runs Vosk recognition and calls callbacks.

        Reports progress via ``self.progress_callback`` and delivers the
        final text via ``self.result_callback``.
        """
        try:
            self.is_processing = True
            log.info(f"Starting file processing: {audio_filepath}")

            with wave.open(audio_filepath, 'rb') as wf:
                if not self._validate_wav(wf):
                    return

                text = self._recognize_wav(wf)

                log.info(f"File processing finished")
                log.info(f"Final accumulated text: '{text}'")
                log.info(f"Text length: {len(text)} characters")

                if self.result_callback:
                    self.result_callback(text)

        except Exception as e:
            log.error(f"Error processing audio file: {e}")
            if self.result_callback:
                self.result_callback("")
        finally:
            self.is_processing = False

    def get_status(self):
        """Return the current processing state as a string."""
        if self.is_processing:
            return "processing"
        else:
            return "idle"

    def cleanup(self):
        """Release Vosk model resources and reset state."""
        self.is_processing = False
        self.model = None
        self.recognizer = None
        log.info("STT resources cleaned up")
