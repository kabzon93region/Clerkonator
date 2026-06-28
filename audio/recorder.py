# -*- coding: utf-8 -*-
"""
Audio recording module — microphone capture via PyAudio.

Records audio from the system microphone in chunks, supports pause/resume,
and saves the result as a WAV file (mono, 16-bit, configurable sample rate).

Threading
---------
Recording runs in a background thread (``_recording_loop``) to avoid
blocking the main application thread.
"""

import os
import threading
import time
import wave

import pyaudio

from utils.audio_devices import resolve_device_index
from utils.session_logger import get_logger

log = get_logger()


class AudioRecorder:
    """Microphone audio recorder with device selection and pause support.

    Uses PyAudio for audio capture. Recording runs in a background thread.
    Audio is accumulated as a list of byte chunks and saved as WAV on stop.
    """

    def __init__(self, config):
        self.config = config
        self.audio = None
        self.stream = None
        self.frames = []
        self.is_recording = False
        self.is_paused = False
        self.recording_thread = None
        self.start_time = None
        self.pause_time = 0
        self.total_pause_time = 0

        self.sample_rate = config.get("audio.sample_rate", 16000)
        self.channels = config.get("audio.channels", 1)
        self.chunk_size = config.get("audio.chunk_size", 4096)
        self.input_device_index = config.get("audio.input_device_index", -1)
        self.format = pyaudio.paInt16

    def reload_settings(self):
        """Reload parameters from config (call after settings change)."""
        self.sample_rate = self.config.get("audio.sample_rate", 16000)
        self.channels = self.config.get("audio.channels", 1)
        self.chunk_size = self.config.get("audio.chunk_size", 4096)
        self.input_device_index = self.config.get("audio.input_device_index", -1)

    def initialize(self):
        """Initialize the PyAudio system. Must be called before recording."""
        try:
            self.audio = pyaudio.PyAudio()
            log.info("Audio system initialized")
            return True
        except Exception as e:
            log.error(f"Audio init error: {e}")
            return False

    def _open_stream(self):
        """Open a PyAudio input stream with configured parameters."""
        kwargs = {
            "format": self.format,
            "channels": self.channels,
            "rate": self.sample_rate,
            "input": True,
            "frames_per_buffer": self.chunk_size,
        }
        device = resolve_device_index(self.input_device_index)
        if device is not None:
            kwargs["input_device_index"] = device
        return self.audio.open(**kwargs)

    def start_recording(self, filename):
        """Start recording audio in a background thread.

        Args:
            filename: Output filename (e.g. ``recording_20260626_120000.wav``).

        Returns:
            True if recording started, False on error or already recording.
        """
        if self.is_recording:
            log.warning("Recording already in progress")
            return False

        try:
            if not self.audio and not self.initialize():
                return False

            self.reload_settings()
            self.stream = self._open_stream()
            self.frames = []
            self.is_recording = True
            self.is_paused = False
            self.start_time = time.time()
            self.pause_time = 0
            self.total_pause_time = 0

            self.recording_thread = threading.Thread(target=self._recording_loop, daemon=True)
            self.recording_thread.start()

            log.info(f"Recording started: {filename}")
            return True
        except Exception as e:
            log.error(f"Start recording error: {e}")
            self._cleanup_stream()
            return False

    def pause_recording(self):
        """Pause the active recording (can be resumed)."""
        if not self.is_recording or self.is_paused:
            return False
        self.is_paused = True
        self.pause_time = time.time()
        return True

    def resume_recording(self):
        """Resume a paused recording."""
        if not self.is_recording or not self.is_paused:
            return False
        self.is_paused = False
        if self.pause_time:
            self.total_pause_time += time.time() - self.pause_time
            self.pause_time = 0
        return True

    def stop_recording(self, filename=None):
        """Stop recording, optionally save the WAV file.

        Args:
            filename: If provided, save the recorded audio to ``data/recordings/<filename>``.

        Returns:
            True if stopped successfully, False on error.
        """
        if not self.is_recording:
            return False
        try:
            self.is_recording = False
            self.is_paused = False

            if self.recording_thread and self.recording_thread.is_alive():
                self.recording_thread.join(timeout=2.0)

            self._cleanup_stream()

            if filename and self.frames:
                self._save_recording(filename)

            log.info("Recording stopped")
            return True
        except Exception as e:
            log.error(f"Stop recording error: {e}")
            return False

    def cancel_recording(self):
        """Stop recording and discard captured audio."""
        if not self.is_recording:
            return False
        try:
            self.is_recording = False
            self.is_paused = False
            self.frames = []

            if self.recording_thread and self.recording_thread.is_alive():
                self.recording_thread.join(timeout=2.0)

            self._cleanup_stream()
            log.info("Recording cancelled")
            return True
        except Exception as e:
            log.error(f"Cancel recording error: {e}")
            return False

    def _cleanup_stream(self):
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except Exception:
                pass
            self.stream = None

    def _recording_loop(self):
        """Background thread loop — reads audio chunks from the microphone."""
        try:
            while self.is_recording:
                if not self.is_paused and self.stream:
                    data = self.stream.read(self.chunk_size, exception_on_overflow=False)
                    self.frames.append(data)
                else:
                    time.sleep(0.05)
        except Exception as e:
            log.error(f"Recording loop error: {e}")

    def _save_recording(self, filename):
        """Save accumulated audio frames as a WAV file in the recordings directory."""
        try:
            audio_dir = self.config.get("files.audio_dir", "data/recordings")
            os.makedirs(audio_dir, exist_ok=True)
            filepath = os.path.join(audio_dir, filename)

            with wave.open(filepath, "wb") as wf:
                wf.setnchannels(self.channels)
                wf.setsampwidth(self.audio.get_sample_size(self.format))
                wf.setframerate(self.sample_rate)
                wf.writeframes(b"".join(self.frames))

            log.info(f"Recording saved: {filepath}")
            return filepath
        except Exception as e:
            log.error(f"Save recording error: {e}")
            return None

    def get_recording_time(self):
        """Return elapsed recording time (excluding pauses) in seconds."""
        if not self.is_recording:
            return 0
        current_time = time.time()
        if self.is_paused:
            return self.pause_time - self.start_time - self.total_pause_time
        return current_time - self.start_time - self.total_pause_time

    def get_status(self):
        if not self.is_recording:
            return "stopped"
        if self.is_paused:
            return "paused"
        return "recording"

    def cleanup(self):
        """Cancel any active recording and terminate PyAudio."""
        self.cancel_recording()
        if self.audio:
            self.audio.terminate()
            self.audio = None
