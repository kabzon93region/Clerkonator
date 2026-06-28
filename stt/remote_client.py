# -*- coding: utf-8 -*-
"""Remote STT client — sends audio to a Clerkonator STT server over HTTP.

This processor runs on the client side and communicates with a remote
STT server (``stt/server_app.py``) via the REST API.

Flow::

    Client app → RemoteSTTProcessor.process_audio_file_sync()
              → HTTP POST /api/transcribe (with WAV audio body)
              → Server processes audio with Whisper/Vosk
              → Returns JSON {text, processing_time, ...}

Also polls ``GET /api/health`` for server status updates.
"""

import json
import os
import time
import urllib.error
import urllib.request

from utils.session_logger import get_logger

from utils.client_stt_config import get_remote_host, get_remote_port, get_remote_timeout
from utils.stt_recognition import build_recognition_options, recognition_headers

log = get_logger()


class RemoteSTTProcessor:
    """STT processor that delegates to a remote HTTP server.

    Implements the same interface as :class:`stt.processor.STTProcessor`
    so the client app can switch between local and remote modes seamlessly.
    """

    def __init__(self, config, host=None, port=None):
        """Initialize the remote processor.

        Args:
            config: Config object for reading connection defaults.
            host: Server hostname/IP (defaults to config ``stt.remote.host``).
            port: Server port (defaults to config ``stt.remote.port``).
        """
        self.config = config
        self.host = host or get_remote_host(config)
        self.port = int(port or get_remote_port(config))
        self.timeout = int(get_remote_timeout(config))
        self.connected = False      # True after successful health check
        self.server_info = {}       # Last health payload from the server

    @property
    def base_url(self):
        """Return the base HTTP URL for the remote server."""
        return f"http://{self.host}:{self.port}"

    def fetch_health(self):
        """Query ``GET /api/health`` and return the server status dict.

        Includes model_loaded, model_loading, queue state, engine, device.
        Used for periodic health polling in the client.
        """
        url = f"{self.base_url}/api/health"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def initialize(self):
        """Connect to the remote server by performing a health check.

        The server may still be loading the model — this method just
        verifies that the server is reachable and responding.

        Returns:
            True if the server responded, False on connection error.
        """
        try:
            data = self.fetch_health()
            if data.get("status") != "ok":
                log.error(f"Server health bad: {data}")
                return False

            self.server_info = data
            self.connected = True
            if data.get("model_loaded"):
                log.info(f"Connected to STT server {self.host}:{self.port} (model ready)")
            elif data.get("model_loading"):
                log.info(f"Connected to STT server {self.host}:{self.port} (model loading)")
            else:
                log.info(f"Connected to STT server {self.host}:{self.port} (model not ready)")
            return True

        except urllib.error.URLError as e:
            log.error(f"Cannot reach STT server {self.host}:{self.port}: {e}")
            return False
        except Exception as e:
            log.error(f"Remote STT init error: {e}")
            return False

    def is_model_loaded(self):
        """Check if the server has its model loaded and is ready to transcribe."""
        return self.connected and self.server_info.get("model_loaded", False)

    def is_ready(self):
        """Check if we can send transcription requests (connected to server).

        Even if the model is still loading, we're 'ready' because the
        server will queue our request.
        """
        return self.connected

    def get_mode_label(self):
        """Return a human-readable label for UI display."""
        return f"сервер {self.host}:{self.port}"

    def get_status_text(self):
        """Return a human-readable status string for the tray tooltip.

        Reports server health, model loading state, and queue status.
        """
        if not self.connected:
            return "Не подключено"
        info = self.server_info
        if info.get("model_error"):
            return f"Сервер: ошибка модели"
        if info.get("model_loading"):
            return "Сервер: загрузка модели…"
        if not info.get("model_loaded"):
            return "Сервер: ожидание модели…"
        waiting = int(info.get("queue_waiting", 0))
        active = int(info.get("queue_active", 0))
        if active > 0 and waiting > 0:
            return f"Сервер: распознавание + очередь ({waiting})"
        if active > 0:
            return "Сервер: распознавание…"
        if waiting > 0:
            return f"Сервер: очередь ({waiting})"
        engine = info.get("engine", "")
        device = info.get("device", "")
        if engine and device:
            return f"Сервер: {engine}/{device}"
        return "Сервер: готов"

    def process_audio_file_sync(self, audio_filepath, recognition_options=None):
        """Send audio to the remote server for transcription.

        Reads the audio file, sends it as a POST body to ``/api/transcribe``,
        and returns the transcription result.

        Args:
            audio_filepath: Path to the WAV file to transcribe.
            recognition_options: Dict with language/translation settings.

        Returns:
            dict with text, processing_time, text_length, etc. — or None on error.
        """
        if not self.connected:
            log.warning("Remote STT not connected")
            return None

        if not os.path.isfile(audio_filepath):
            log.error(f"Audio file not found: {audio_filepath}")
            return None

        try:
            rec = recognition_options or build_recognition_options(self.config)
            log.info(
                "Remote transcribe → %s:%s task=%s source=%s translate=%s",
                self.host,
                self.port,
                rec.get("task"),
                rec.get("source_language"),
                rec.get("translate"),
            )
            start_time = time.time()
            with open(audio_filepath, "rb") as audio_file:
                audio_data = audio_file.read()

            url = f"{self.base_url}/api/transcribe"
            headers = {
                "Content-Type": "audio/wav",
                **recognition_headers(rec),
            }
            req = urllib.request.Request(
                url,
                data=audio_data,
                method="POST",
                headers=headers,
            )

            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                result = json.loads(resp.read().decode("utf-8"))

            processing_time = time.time() - start_time
            text = result.get("text", "")

            return {
                "text": text,
                "processing_time": result.get("processing_time", processing_time),
                "text_length": len(text),
                "file_path": audio_filepath,
                "job_id": result.get("job_id"),
                "source": os.path.basename(audio_filepath),
            }

        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            log.error(f"Server HTTP {e.code}: {body}")
            return None
        except Exception as e:
            log.error(f"Remote transcription error: {e}")
            return None

    def cleanup(self):
        """Disconnect from the server and reset state."""
        self.connected = False
        self.server_info = {}
