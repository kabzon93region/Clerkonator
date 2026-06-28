# -*- coding: utf-8 -*-
"""
Clerkonator STT HTTP Server — LAN speech-to-text server.

Architecture overview
--------------------
1. **HTTP layer** (`STTHTTPHandler`) — accepts REST API requests from clients.
2. **Queue layer** (`TranscriptionQueue`) — FIFO queue with a single worker thread.
   Each audio file is wrapped in a `TranscriptionJob` and processed sequentially.
3. **Processor layer** — pluggable STT backend (Whisper GPU or Vosk CPU) selected
   by `stt.server.device` in ``config.server.json``.
4. **State layer** (`ServerState`) — thread-safe shared state for health checks
   and metrics, protected by a lock.

Key design decisions
--------------------
* The server starts listening **before** the model finishes loading, so clients
  can connect immediately and queue requests.
* Audio files are saved to ``data/server_temp/`` before processing. If the server
  crashes, unprocessed files are recovered on next startup (see ``_recover_temp_files``).
* The tray icon runs in its own thread and updates periodically (every 3 seconds).

Run::

    python stt/server_app.py [--host 0.0.0.0] [--port 8765] [--silent]

REST API endpoints
------------------
* ``GET  /api/health``        — server health + model status
* ``GET  /api/ping``          — liveness check
* ``GET  /api/stats``         — uptime and processing metrics
* ``GET  /api/models``        — list available local STT models
* ``GET  /api/job/<job_id>``  — poll async job status
* ``POST /api/transcribe``    — upload WAV audio, get transcription (blocking)
* ``POST /api/switch-model``  — switch STT model at runtime
* ``POST /api/reload``         — reload config and restart model
* ``POST /api/shutdown``      — graceful shutdown
"""

import argparse
import json
import os
import queue
import signal
import socket
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.cuda_runtime import configure_cuda_dll_paths

configure_cuda_dll_paths()

from utils.config import Config
from utils.model_downloader import download_model_if_needed
from utils.session_logger import get_logger
from utils.stt_recognition import parse_recognition_headers
from stt.server_factory import create_server_processor, get_engine_name

log = get_logger()

# ── Security limits (hardcoded guard rails) ─────────────────────────
# Maximum accepted audio payload size (100 MB).
# Prevents clients from exhausting server memory with huge uploads.
MAX_AUDIO_SIZE = 100 * 1024 * 1024

# Default max number of jobs waiting in the queue.
# Can be overridden via config: ``server.max_queue_size``.
DEFAULT_MAX_QUEUE_SIZE = 20

# How long (seconds) a synchronous /api/transcribe request waits
# for the queue worker to finish before returning a 504 timeout.
TRANSCRIBE_TIMEOUT = 300  # 5 minutes


def get_max_queue_size():
    """Return the configured queue size limit.

    Reads ``server.max_queue_size`` from ``config.server.json``.
    Falls back to :data:`DEFAULT_MAX_QUEUE_SIZE` (20) when unset.
    """
    if _state and _state.config:
        return int(_state.config.get("server.max_queue_size", DEFAULT_MAX_QUEUE_SIZE))
    return DEFAULT_MAX_QUEUE_SIZE

# ── Module-level singletons (initialised in main()) ────────────────
# The active STT processor (Whisper or Vosk). Guarded by _processor_lock.
_processor = None
_processor_lock = threading.Lock()

# Generation counter for load_model_async. Prevents race conditions when
# switch_model() is called while a previous model is still loading:
# the old loading thread checks this counter and aborts if it's stale.
_load_generation = 0

# Shared server state — created once in main(), accessible via get_state().
_state = None

# The transcription queue — created once in main(), accessible via get_job_queue().
_job_queue = None

# The HTTP server instance (used for graceful shutdown).
_server = None

# Tray icon manager (optional — only on Windows with GUI available).
_tray_manager = None

# Server start timestamp for uptime calculation.
_start_time = time.time()


class ServerState:
    """Thread-safe container for all server state.

    Holds model status (loading / loaded / error), queue counters,
    and cumulative metrics. Every field is protected by ``self.lock``.

    Read by:
    * ``health_payload()`` — for ``GET /api/health``
    * ``stats_payload()``  — for ``GET /api/stats``
    * ``ServerTrayManager`` — for tray icon and tooltip updates

    Written by:
    * ``load_model_async()``  — updates model_loaded / model_error
    * ``TranscriptionQueue._worker_loop()`` — updates queue counters and metrics
    """

    def __init__(self, config=None):
        """Initialise state from config (device, model name)."""
        self.lock = threading.Lock()
        self.model_loading = False      # True while model is being loaded
        self.model_loaded = False       # True after successful initialization
        self.model_error = None         # Error message string (None if OK)
        self.model_name = ""            # Display name (e.g. "large-v3-turbo")
        self.queue_waiting = 0          # Jobs queued but not yet started
        self.queue_active = 0           # Jobs currently being processed
        self.config = config            # Reference to the Config object
        self.engine = "unknown"         # "whisper" or "vosk"
        self.device = str(config.get("stt.server.device", "gpu") if config else "gpu")
        self.total_jobs = 0             # Lifetime count of completed jobs
        self.total_processing_time = 0.0  # Lifetime total processing seconds

        # Determine the display model name from config based on device mode
        if config:
            device = str(config.get("stt.server.device", "gpu")).lower()
            if device == "cpu":
                # Vosk: use the folder name as model name
                mp = config.get("stt.model_path", "")
                self.model_name = os.path.basename(mp) if mp else "vosk"
            else:
                # Whisper: use the configured model size name
                self.model_name = config.get("stt.server.whisper_model", "whisper")

    def health_payload(self):
        """Return a dict for the ``GET /api/health`` endpoint.

        Includes model status, queue state, and engine/device info.
        Called frequently by clients polling for server readiness.
        """
        proc = get_processor()
        with self.lock:
            payload = {
                "status": "ok",
                "model_loaded": self.model_loaded,
                "model_loading": self.model_loading,
                "model_error": self.model_error,
                "model_name": self.model_name,
                "queue_waiting": self.queue_waiting,
                "queue_processing": self.queue_active > 0,  # Derived: True if any job is active
                "queue_active": self.queue_active,
                "engine": self.engine,
                "device": self.device,
            }
        # Override with live info from the processor if available
        if proc:
            if hasattr(proc, "get_engine_label"):
                payload["engine"] = proc.get_engine_label()
            if hasattr(proc, "get_device_label"):
                payload["device"] = proc.get_device_label()
            elif hasattr(proc, "get_mode_label"):
                payload["device"] = "cpu"
        return payload

    def stats_payload(self):
        """Return a dict for the ``GET /api/stats`` endpoint.

        Includes uptime, total jobs, and average processing time.
        """
        uptime = time.time() - _start_time
        with self.lock:
            return {
                "uptime_seconds": int(uptime),
                "total_jobs": self.total_jobs,
                "total_processing_time": round(self.total_processing_time, 2),
                "avg_processing_time": round(
                    self.total_processing_time / max(1, self.total_jobs), 2
                ),
                "queue_waiting": self.queue_waiting,
                "queue_active": self.queue_active,
                "model_loaded": self.model_loaded,
                "model_name": self.model_name,
                "engine": self.engine,
                "device": self.device,
            }


class TranscriptionJob:
    """Represents a single audio transcription request.

    Created by :meth:`TranscriptionQueue.submit` when a client sends audio.
    Processed by :meth:`TranscriptionQueue._worker_loop` in the worker thread.

    Lifecycle::

        submit() → queued → worker picks up → model processes → done.set()
                                                        ↓
                                               result or error filled
    """

    def __init__(self, job_id, temp_path, recognition_options=None):
        """Create a new job.

        Args:
            job_id: Short UUID string (8 chars) for identification.
            temp_path: Path to the saved WAV file in ``data/server_temp/``.
            recognition_options: Dict of language/translation settings
                (task, source_language, translate, etc.).
        """
        self.job_id = job_id                # Short UUID for API polling
        self.temp_path = temp_path          # Path to WAV file
        self.recognition_options = recognition_options or {}
        self.done = threading.Event()       # Set when processing is complete
        self.result = None                  # Dict with text, processing_time, etc.
        self.error = None                   # Error message if processing failed
        self.queue_position = 0             # Position in queue (for UI feedback)


class TranscriptionQueue:
    """Thread-safe FIFO queue with a single worker thread.

    Audio files are submitted via :meth:`submit`, placed into a
    :class:`queue.Queue`, and processed one-at-a-time by the worker thread.

    The worker waits for the model to finish loading before processing each job.
    If the model fails to load, all queued jobs receive an error.

    Queue limits
    ------------
    * ``queue_waiting`` — number of jobs not yet started (max = ``max_queue_size``)
    * ``queue_active``  — number of jobs being processed (always 0 or 1 since
      there is a single worker)
    """

    def __init__(self, state):
        """Create queue and start the worker thread.

        Args:
            state: The :class:`ServerState` instance for shared state access.
        """
        self.state = state
        self._queue = queue.Queue()
        self._worker = threading.Thread(target=self._worker_loop, name="STT-Queue", daemon=True)
        self._worker.start()

    def submit(self, temp_path, recognition_options=None):
        """Add a new audio file to the transcription queue.

        Args:
            temp_path: Path to the WAV file saved on the server.
            recognition_options: Optional dict with language/translation settings.

        Returns:
            TranscriptionJob instance, or None if the queue is full.
        """
        max_size = get_max_queue_size()
        with self.state.lock:
            if self.state.queue_waiting >= max_size:
                log.warning(f"Queue full ({max_size}), rejecting job")
                return None
        job = TranscriptionJob(str(uuid.uuid4())[:8], temp_path, recognition_options)
        with self.state.lock:
            job.queue_position = self.state.queue_waiting + 1
            self.state.queue_waiting += 1
        self._queue.put(job)
        _register_job(job)
        log.info(f"Job {job.job_id} queued (position {job.queue_position})")
        return job

    def _worker_loop(self):
        """Main worker loop — processes jobs one at a time.

        For each job:
        1. Wait for the model to be loaded (or fail).
        2. Call ``process_audio_file_sync`` on the processor.
        3. Set ``job.result`` or ``job.error``.
        4. Clean up the temp WAV file (only on success).
        5. Mark ``job.done`` so the HTTP handler can return.
        """
        while True:
            job = self._queue.get()
            try:
                # Move from "waiting" to "active"
                with self.state.lock:
                    self.state.queue_waiting = max(0, self.state.queue_waiting - 1)
                    self.state.queue_active += 1

                # Wait for model to be ready (loaded, error, or unavailable)
                while True:
                    with self.state.lock:
                        if self.state.model_loaded:
                            break
                        if self.state.model_error:
                            job.error = self.state.model_error
                            break
                        if not self.state.model_loading and not self.state.model_loaded:
                            job.error = "model not available"
                            break
                    time.sleep(0.25)

                # Run transcription if no error so far
                if job.error:
                    log.error(f"Job {job.job_id} failed: {job.error}")
                else:
                    proc = get_processor()
                    if not proc or not proc.is_model_loaded():
                        job.error = "processor not ready"
                    else:
                        with _processor_lock:
                            job.result = proc.process_audio_file_sync(
                                job.temp_path,
                                job.recognition_options,
                            )
                        if not job.result:
                            job.error = "transcription failed"
                        else:
                            log.info(f"Job {job.job_id} completed")
            except Exception as e:
                job.error = str(e)
                log.error(f"Job {job.job_id} error: {e}")
            finally:
                # Update metrics and clean up
                with self.state.lock:
                    self.state.queue_active = max(0, self.state.queue_active - 1)
                    if job.result and not job.error:
                        self.state.total_jobs += 1
                        pt = job.result.get("processing_time", 0)
                        self.state.total_processing_time += pt
                job.done.set()
                # Delete the temp WAV file only after successful processing.
                # On failure, the file is kept for potential debugging.
                if job.result and not job.error:
                    self._cleanup_temp(job.temp_path)
                self._queue.task_done()

    @staticmethod
    def _cleanup_temp(path):
        """Safely delete a temporary audio file."""
        try:
            if path and os.path.exists(path):
                os.remove(path)
        except OSError:
            pass


def get_processor():
    """Return the current STT processor (thread-safe)."""
    global _processor
    with _processor_lock:
        return _processor


def get_state():
    """Return the global ServerState singleton."""
    return _state


def get_job_queue():
    """Return the global TranscriptionQueue singleton."""
    return _job_queue


# ── Job registry (for async polling via GET /api/job/<id>) ─────────
_active_jobs = {}
_jobs_lock = threading.Lock()


def _register_job(job):
    """Add a job to the registry (called on submit)."""
    with _jobs_lock:
        _active_jobs[job.job_id] = job


def _unregister_job(job_id):
    """Remove a job from the registry."""
    with _jobs_lock:
        return _active_jobs.pop(job_id, None)


def _find_job(job_id):
    """Look up a job by ID (called by GET /api/job/<id>)."""
    with _jobs_lock:
        return _active_jobs.get(job_id)


def switch_model(model_id):
    """Switch the STT backend to a different model at runtime.

    Called from:
    * ``POST /api/switch-model`` (REST API)
    * Server tray menu ("Модели" submenu)

    Safety: Blocks switching while a model is currently loading to prevent
    race conditions and stuck states. The user must wait for the current
    load to complete before switching.

    Steps:
    1. Check if a model is currently loading — reject if so.
    2. Look up the model in the catalog by ``model_id``.
    3. Clean up the current processor (release VRAM).
    4. Update config with the new model settings.
    5. Call :func:`load_model_async` to load in a background thread.

    Args:
        model_id: Model identifier string (``engine:size`` format).

    Returns:
        True if switch was initiated, False if rejected (loading in progress).
    """
    global _processor
    state = get_state()
    if not state:
        log.error("Cannot switch model: server state not ready")
        return False

    # Safety: block switching during model loading
    if state.model_loading:
        log.warning(
            f"Model switch to '{model_id}' rejected — model is currently loading. "
            "Please wait for the current load to complete."
        )
        return False

    try:
        from utils.stt_model_catalog import find_model_by_id
        model = find_model_by_id(model_id)
        if not model:
            log.error(f"Model not found: {model_id}")
            return False

        log.info(f"Switching to model: {model.title} ({model.engine}/{model.device})")

        # Cleanup current processor
        proc = get_processor()
        if proc:
            try:
                if hasattr(proc, "cleanup"):
                    proc.cleanup()
            except Exception as e:
                log.warning(f"Cleanup old processor: {e}")

        with _processor_lock:
            _processor = None

        with state.lock:
            state.model_loaded = False
            state.model_loading = True
            state.model_error = None
            state.device = model.device
            state.engine = model.engine
            state.model_name = model.title

        # Update config for new model
        config = state.config
        if model.engine == "whisper":
            config.set("stt.server.device", model.device)
            config.set("stt.server.whisper_model", model.whisper_size or model.model_id.split(":")[1])
        else:
            config.set("stt.server.device", "cpu")
            config.set("stt.model_path", model.path)

        # Load new model
        load_model_async(config, state)
        log.info(f"Model switch initiated: {model.title}")
        return True
    except Exception as e:
        log.error(f"Switch model error: {e}")
        with state.lock:
            state.model_loading = False
            state.model_error = str(e)
        return False


def reload_server():
    """Reload server configuration and restart the model.

    Re-reads ``config.server.json``, cleans up the old processor,
    and triggers :func:`load_model_async` with the new settings.
    Called from ``POST /api/reload`` or the tray menu.
    """
    global _processor
    state = get_state()
    if not state:
        return

    try:
        log.info("Reloading server config...")
        config = Config(profile="server")
        state.config = config

        # Cleanup current processor
        proc = get_processor()
        if proc:
            try:
                if hasattr(proc, "cleanup"):
                    proc.cleanup()
            except Exception as e:
                log.warning(f"Cleanup old processor: {e}")

        with _processor_lock:
            _processor = None

        with state.lock:
            state.model_loaded = False
            state.model_loading = True
            state.model_error = None

        load_model_async(config, state)
        log.info("Server reload initiated")
    except Exception as e:
        log.error(f"Reload error: {e}")
        with state.lock:
            state.model_loading = False
            state.model_error = str(e)


def shutdown_server():
    """Graceful shutdown — stop HTTP server, clean up resources, exit.

    Called from:
    * ``POST /api/shutdown``
    * Tray menu "Выход"
    * Signal handler (SIGTERM)
    * KeyboardInterrupt in main()

    Note: temp files in ``data/server_temp/`` are intentionally NOT deleted
    so they can be recovered on next startup.
    """
    global _server
    log.info("Graceful shutdown initiated...")

    # Stop accepting new connections
    if _server:
        try:
            _server.shutdown()
        except Exception as e:
            log.warning(f"Server shutdown: {e}")

    # Cleanup processor
    proc = get_processor()
    if proc:
        try:
            if hasattr(proc, "cleanup"):
                proc.cleanup()
        except Exception as e:
            log.warning(f"Processor cleanup: {e}")

    # Stop tray
    if _tray_manager:
        try:
            _tray_manager.stop()
        except Exception:
            pass

    # NOTE: не удаляем temp-файлы из server_temp — необработанные
    # будут подхвачены при перезапуске сервера (recover_temp_files)

    log.info("Server shutdown complete")
    os._exit(0)


class STTHTTPHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the STT REST API.

    Routes:
    * GET  /api/health        → :meth:`do_GET`
    * GET  /api/ping
    * GET  /api/stats
    * GET  /api/models
    * GET  /api/job/<job_id>
    * POST /api/transcribe    → :meth:`do_POST` → :meth:`_handle_transcribe`
    * POST /api/switch-model  → :meth:`_handle_switch_model`
    * POST /api/reload         → :meth:`_handle_reload`
    * POST /api/shutdown
    """

    def log_message(self, format, *args):
        """Override default stderr logging to use the session logger."""
        log.info("HTTP %s - %s", self.address_string(), format % args)

    def _send_json(self, code, payload):
        """Send a JSON HTTP response with the given status code and payload."""
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self):
        """Read and parse a JSON body from the request."""
        length = int(self.headers.get("Content-Length", 0))
        if length <= 0:
            return None
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/health":
            state = get_state()
            if state:
                self._send_json(200, state.health_payload())
            else:
                self._send_json(200, {"status": "ok", "model_loading": True, "model_loaded": False})
            return

        if path == "/api/ping":
            uptime = int(time.time() - _start_time)
            self._send_json(200, {"status": "alive", "uptime": uptime})
            return

        if path == "/api/stats":
            state = get_state()
            if state:
                self._send_json(200, state.stats_payload())
            else:
                self._send_json(503, {"error": "server not ready"})
            return

        if path == "/api/models":
            try:
                from utils.stt_model_catalog import list_local_stt_models
                models = list_local_stt_models()
                result = []
                for m in models:
                    result.append({
                        "model_id": m.model_id,
                        "title": m.title,
                        "engine": m.engine,
                        "device": m.device,
                        "memory_mb": m.memory_mb,
                        "label": m.combo_label,
                    })
                self._send_json(200, {"models": result})
            except Exception as e:
                self._send_json(500, {"error": str(e)})
            return

        # GET /api/job/<job_id> — poll job status
        if path.startswith("/api/job/"):
            job_id = path[len("/api/job/"):]
            job = _find_job(job_id)
            if not job:
                self._send_json(404, {"error": "job not found"})
                return
            if job.done.is_set():
                if job.error:
                    self._send_json(200, {"status": "error", "error": job.error, "job_id": job.job_id})
                else:
                    self._send_json(200, {
                        "status": "done",
                        "text": job.result.get("text", ""),
                        "processing_time": job.result.get("processing_time", 0),
                        "text_length": job.result.get("text_length", 0),
                        "job_id": job.job_id,
                    })
            else:
                self._send_json(200, {
                    "status": "processing",
                    "queue_position": job.queue_position,
                    "job_id": job.job_id,
                })
            return

        self._send_json(404, {"error": "not found"})

    def do_POST(self):
        path = urlparse(self.path).path

        if path == "/api/transcribe":
            self._handle_transcribe()
            return

        if path == "/api/switch-model":
            self._handle_switch_model()
            return

        if path == "/api/reload":
            self._handle_reload()
            return

        if path == "/api/shutdown":
            self._send_json(200, {"status": "shutting down"})
            threading.Thread(target=shutdown_server, daemon=True).start()
            return

        self._send_json(404, {"error": "not found"})

    def _handle_transcribe(self):
        """Handle ``POST /api/transcribe`` — the main transcription endpoint.

        Flow:
        1. Read the raw audio body (binary WAV data).
        2. Validate size against :data:`MAX_AUDIO_SIZE`.
        3. Parse recognition options from HTTP headers (language, translate, etc.).
        4. Save the audio to ``data/server_temp/upload_<uuid>.wav``.
        5. Submit the file to :class:`TranscriptionQueue`.
        6. Wait (blocking) for the job to complete or timeout.
        7. Return the transcribed text as JSON.

        The temp file is deleted by the queue worker on success, or in the
        ``finally`` block here on error.
        """
        length = int(self.headers.get("Content-Length", 0))
        if length <= 0:
            self._send_json(400, {"error": "empty body"})
            return

        # Security: reject payloads larger than MAX_AUDIO_SIZE
        if length > MAX_AUDIO_SIZE:
            self._send_json(413, {"error": f"payload too large (max {MAX_AUDIO_SIZE // (1024*1024)} MB)"})
            return

        # Content-Type validation (warning only, not blocking)
        ct = self.headers.get("Content-Type", "")
        if ct and not ct.startswith("audio/") and not ct.startswith("application/octet-stream"):
            log.warning(f"Non-audio content type: {ct}")

        audio_data = self.rfile.read(length)

        # Parse recognition options from X-STT-* headers, with server config as fallback
        state = get_state()
        server_defaults = {}
        if state and state.config:
            server_defaults = state.config.get("stt.recognition") or {}
        recognition_options = parse_recognition_headers(self.headers, server_defaults)
        log.info(
            "Transcribe request: size=%d task=%s source=%s translate=%s target=%s",
            length,
            recognition_options.get("task"),
            recognition_options.get("source_language"),
            recognition_options.get("translate"),
            recognition_options.get("target_language"),
        )

        # Save the uploaded audio to a temp file for the queue worker
        temp_dir = os.path.join("data", "server_temp")
        os.makedirs(temp_dir, exist_ok=True)
        temp_path = os.path.join(temp_dir, f"upload_{uuid.uuid4().hex}.wav")

        try:
            with open(temp_path, "wb") as temp_file:
                temp_file.write(audio_data)

            job_queue = get_job_queue()
            if not job_queue:
                self._send_json(503, {"error": "server starting"})
                return

            job = job_queue.submit(temp_path, recognition_options)
            if not job:
                self._send_json(503, {"error": f"queue full (max {get_max_queue_size()})"})
                return
            temp_path = None  # Ownership transferred — queue worker will delete it

            # Block until the job finishes or TRANSCRIBE_TIMEOUT is reached
            if not job.done.wait(timeout=TRANSCRIBE_TIMEOUT):
                job.error = "timeout in queue"
                self._send_json(504, {"error": "timeout in queue", "job_id": job.job_id})
                return

            if job.error:
                self._send_json(503, {"error": job.error, "job_id": job.job_id})
                return

            self._send_json(200, {
                "text": job.result.get("text", ""),
                "processing_time": job.result.get("processing_time", 0),
                "text_length": job.result.get("text_length", 0),
                "job_id": job.job_id,
            })
        except Exception as e:
            log.error(f"Transcribe error: {e}")
            self._send_json(500, {"error": str(e)})
        finally:
            # Clean up temp file only if the queue worker did not take ownership
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

    def _handle_switch_model(self):
        """Handle ``POST /api/switch-model`` — switch STT model at runtime.

        Expects JSON body: ``{"model_id": "whisper:large-v3-turbo"}``
        Returns 200 if switch initiated, 409 if rejected (model loading).
        """
        try:
            body = self._read_json_body()
            if not body:
                self._send_json(400, {"error": "missing JSON body"})
                return
            model_id = body.get("model_id", "")
            if not model_id:
                self._send_json(400, {"error": "model_id required"})
                return
            log.info(f"Switch model requested: {model_id}")
            result = switch_model(model_id)
            if result:
                self._send_json(200, {"status": "switching", "model_id": model_id})
            else:
                state = get_state()
                error_msg = "model is currently loading, please wait"
                if state and state.model_error:
                    error_msg = state.model_error
                self._send_json(409, {"status": "rejected", "error": error_msg})
        except Exception as e:
            self._send_json(500, {"error": str(e)})

    def _handle_reload(self):
        """Handle ``POST /api/reload`` — reload config and restart model.

        Starts the reload in a background thread and returns immediately.
        """
        try:
            log.info("Reload requested from API")
            threading.Thread(target=reload_server, daemon=True).start()
            self._send_json(200, {"status": "reloading"})
        except Exception as e:
            self._send_json(500, {"error": str(e)})


def load_model_async(config, state):
    """Load the STT model in a background thread.

    Selects Whisper (GPU) or Vosk (CPU) based on ``stt.server.device``.
    Updates ``state.model_loading`` / ``model_loaded`` / ``model_error``.

    Race condition guard
    ---------------------
    Each call increments ``_load_generation``. The worker thread captures
    its own generation number and checks it before setting ``_processor``.
    If a newer generation exists (i.e. switch_model was called during
    loading), the old thread aborts and cleans up its partially-loaded model.

    Called from:
    * :func:`main` — initial load on server startup
    * :func:`switch_model` — after switching to a different model
    * :func:`reload_server` — after reloading config
    """
    global _load_generation
    _load_generation += 1
    my_generation = _load_generation

    def worker():
        state.model_loading = True
        device = str(config.get("stt.server.device", "gpu")).lower()
        state.device = device
        state.engine = get_engine_name(config)
        # Update model name from config
        if device == "cpu":
            mp = config.get("stt.model_path", "")
            state.model_name = os.path.basename(mp) if mp else "vosk"
        else:
            state.model_name = config.get("stt.server.whisper_model", "whisper")
        log.info(
            f"Server STT device mode: {device} (engine={state.engine}, "
            f"generation={my_generation})"
        )

        try:
            # Check if a newer generation has been started (switch_model during load)
            if my_generation != _load_generation:
                log.info(
                    f"Model load cancelled (generation {my_generation} superseded "
                    f"by {_load_generation})"
                )
                return

            if device == "cpu":
                log.info("Checking Vosk model...")
                if not download_model_if_needed(config):
                    state.model_error = "failed to install vosk model"
                    log.error(state.model_error)
                    return

            # Check again after potentially long download
            if my_generation != _load_generation:
                log.info(
                    f"Model load cancelled after download (generation {my_generation} "
                    f"superseded by {_load_generation})"
                )
                return

            proc = create_server_processor(config)

            # Check cancellation before starting long initialization
            if my_generation != _load_generation:
                log.info(
                    f"Model load cancelled before initialize() (generation {my_generation} "
                    f"superseded by {_load_generation})"
                )
                return

            if device == "gpu":
                log.info(
                    "Whisper GPU: сначала скачивание модели (если нет в models/whisper/), "
                    "затем загрузка в VRAM"
                )
            log.info("Loading STT model (may take several minutes)...")
            # Pass cancellation callback so initialize() can abort early
            # (e.g. skip GPU warmup if generation has been superseded)
            if not proc.initialize(is_cancelled=lambda: my_generation != _load_generation):
                # Check if cancelled during long initialization
                if my_generation != _load_generation:
                    log.info(
                        f"Model load cancelled after init (generation {my_generation} "
                        f"superseded by {_load_generation})"
                    )
                    # Clean up partially-loaded processor
                    if hasattr(proc, "cleanup"):
                        proc.cleanup()
                    return
                state.model_error = "failed to initialize model"
                log.error(state.model_error)
                return

            # Final check before committing the new processor
            if my_generation != _load_generation:
                log.info(
                    f"Model load cancelled before commit (generation {my_generation} "
                    f"superseded by {_load_generation})"
                )
                if hasattr(proc, "cleanup"):
                    proc.cleanup()
                return

            global _processor
            with _processor_lock:
                _processor = proc

            with state.lock:
                state.model_loaded = True
                if hasattr(proc, "get_engine_label"):
                    state.engine = proc.get_engine_label()
                if hasattr(proc, "get_device_label"):
                    state.device = proc.get_device_label()
            log.info(f"STT server ready: engine={state.engine}, device={state.device}")
            # Update tray tooltip and icon
            if _tray_manager:
                _tray_manager.update_tooltip()
                _tray_manager.update_model_menu()
        except Exception as e:
            if my_generation == _load_generation:
                state.model_error = str(e)
            log.error(f"Model load error (gen={my_generation}): {e}")
        finally:
            if my_generation == _load_generation:
                state.model_loading = False
                # Rebuild tray menu so model items become enabled again
                if _tray_manager:
                    _tray_manager.update_model_menu()

    threading.Thread(target=worker, name=f"STT-ModelLoad-{my_generation}", daemon=True).start()


def _recover_temp_files(job_queue):
    """Recover unprocessed audio files after a crash or restart.

    Scans ``data/server_temp/`` for leftover ``.wav`` files and re-queues them.
    This ensures no audio is lost if the server was killed unexpectedly.
    Called once during startup in :func:`main`.
    """
    temp_dir = os.path.join("data", "server_temp")
    if not os.path.isdir(temp_dir):
        return
    recovered = 0
    for fname in os.listdir(temp_dir):
        if not fname.endswith(".wav"):
            continue
        fpath = os.path.join(temp_dir, fname)
        if not os.path.isfile(fpath):
            continue
        try:
            job = job_queue.submit(fpath, recognition_options={})
            if job:
                recovered += 1
                log.info(f"Recovered unprocessed file: {fname}")
            else:
                log.warning(f"Could not re-queue recovered file: {fname}")
        except Exception as e:
            log.warning(f"Recovery error for {fname}: {e}")
    if recovered:
        log.info(f"Recovered {recovered} unprocessed audio file(s) from previous run")


def get_client_urls(port):
    """Return HTTP URLs that clients can use to reach this server.

    Detects the LAN IP via a UDP socket trick (connect to 8.8.8.8:80
    and read the local address). Also includes 127.0.0.1 as fallback.
    """
    urls = []
    seen = set()

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        sock.close()
        if ip not in seen:
            seen.add(ip)
            urls.append(f"http://{ip}:{port}")
    except OSError:
        pass

    for ip in ("127.0.0.1",):
        if ip not in seen:
            seen.add(ip)
            urls.append(f"http://{ip}:{port}")

    return urls


def log_client_urls(port):
    """Log the client-facing URLs to the console."""
    urls = get_client_urls(port)
    log.info("Клиенты подключаются по адресу:")
    for url in urls:
        log.info(f"  {url}")
    if len(urls) == 1:
        log.info("  (LAN IP не определён — проверьте сеть или выполните ipconfig)")


def main():
    """Server entry point.

    Startup sequence:
    1. Parse command-line arguments (host, port, silent).
    2. Load ``config.server.json``.
    3. Create :class:`ServerState` and :class:`TranscriptionQueue`.
    4. Start the HTTP server in a background thread.
    5. Start loading the model in the background (:func:`load_model_async`).
    6. Recover any unprocessed temp files (:func:`_recover_temp_files`).
    7. Start the tray icon manager.
    8. Enter the main loop (wait for shutdown signal).
    """
    global _state, _job_queue, _server, _tray_manager

    parser = argparse.ArgumentParser(description="Clerkonator LAN server")
    config = Config(profile="server")
    default_host = config.get("listen.host", "0.0.0.0")
    default_port = int(config.get("listen.port", config.get("stt.server.port", 8765)))
    parser.add_argument("--host", default=default_host, help="Bind address (0.0.0.0 for LAN)")
    parser.add_argument("--port", type=int, default=default_port, help="TCP port")
    parser.add_argument("--silent", action="store_true", help="Hide console window (run in tray only)")
    args = parser.parse_args()

    # Hide console if --silent
    if args.silent:
        try:
            import ctypes
            hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, 0)  # SW_HIDE
                log.info("Console window hidden (--silent mode)")
        except Exception as e:
            log.warning(f"Could not hide console: {e}")

    _state = ServerState(config)
    _state.model_loading = True
    _job_queue = TranscriptionQueue(_state)

    _server = HTTPServer((args.host, args.port), STTHTTPHandler)
    server_thread = threading.Thread(target=_server.serve_forever, name="STT-HTTP", daemon=True)
    server_thread.start()

    log.info(f"STT server listening on port {args.port} (model loads in background)")
    log_client_urls(args.port)
    log.info(
        "Endpoints: GET /api/health, /api/ping, /api/stats, /api/models, "
        "GET /api/job/<id>, POST /api/transcribe, /api/switch-model, /api/reload, /api/shutdown"
    )

    load_model_async(config, _state)

    # Recover unprocessed temp files from previous crash
    _recover_temp_files(_job_queue)

    # Start tray manager
    try:
        from utils.server_tray import ServerTrayManager
        _tray_manager = ServerTrayManager(
            state=_state,
            config=config,
            on_switch_model=switch_model,
            on_reload=reload_server,
            on_shutdown=shutdown_server,
        )
        _tray_manager.start_in_thread()
        log.info("Server tray manager started")
        # Refresh model menu shortly after tray starts (models may already be loaded)
        def _refresh_menu_later():
            time.sleep(2)
            if _tray_manager:
                _tray_manager.update_model_menu()
        threading.Thread(target=_refresh_menu_later, daemon=True).start()
    except Exception as e:
        log.warning(f"Tray manager not started: {e}")
        _tray_manager = None

    # Signal handling for graceful shutdown
    def signal_handler(sig, frame):
        log.info(f"Signal {sig} received")
        shutdown_server()

    try:
        signal.signal(signal.SIGTERM, signal_handler)
    except Exception:
        pass

    # Periodic tray tooltip update
    def tooltip_updater():
        while server_thread.is_alive():
            if _tray_manager:
                _tray_manager.update_tooltip()
            time.sleep(3)

    threading.Thread(target=tooltip_updater, daemon=True, name="TrayTooltip").start()

    try:
        while server_thread.is_alive():
            time.sleep(0.5)
    except KeyboardInterrupt:
        log.info("Server stopped (KeyboardInterrupt)")
    finally:
        shutdown_server()


if __name__ == "__main__":
    main()
