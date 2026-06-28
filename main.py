#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Clerkonator — Desktop speech-to-text application.

Client-side application with GUI (Tkinter), system tray (pystray),
global hotkeys (pynput), and audio recording (PyAudio).

Threading model
----------------
* **Main thread** — Tkinter mainloop (GUI must run on main thread on Windows).
* **Backend thread** — processes GUI messages from ``gui_queue``.
* **Tray thread** — pystray icon runs in a dedicated background thread.
* **Worker threads** — STT processing, model loading, health polling.

STT modes
---------
* ``"none"``   — no STT backend (user must connect in settings)
* ``"local"``  — local Vosk or Whisper model loaded on this machine
* ``"remote"`` — connected to a remote Clerkonator STT server via HTTP
"""

import sys
import os
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import queue
from datetime import datetime

# Add module paths
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Setup session logging
from utils.session_logger import get_logger, get_log_file

# Get session logger
log = get_logger()
log_file = get_log_file()

from gui.simple_window import SimpleWindow
from utils.tray_manager import TrayManager
from utils.hotkeys import GlobalHotkeyService
from audio.player import AudioPlayer
from utils.config import Config
from utils.model_downloader import download_model_if_needed
from stt.processor import STTProcessor
from stt.remote_client import RemoteSTTProcessor
from audio.recorder import AudioRecorder


class ClerkonatorApp:
    """Main application controller — coordinates GUI, audio, STT, and tray.

    The app uses a message-queue pattern: GUI actions are put into
    ``gui_queue``, and the backend thread processes them in order.
    Results are sent back to the GUI via ``_notify_gui()`` which uses
    ``window.after()`` for thread-safe Tkinter updates.
    """
    
    def __init__(self):
        """Initialize application state (no I/O until start() is called)."""
        self.config = Config(profile="client")
        self.stt_processor = None
        self.audio_recorder = None
        self.gui_window = None
        self.tray_manager = None
        self.running = False
        
        # Threading
        self.gui_thread = None
        self.gui_queue = queue.Queue()
        
        # Application state
        self.is_recording = False
        self.is_paused = False
        self.is_processing = False
        self.current_audio_file = None
        self.stt_mode = "none"  # none | local | remote
        self.stt_connecting = False
        self.processing_count = 0
        self._remote_poll_stop = threading.Event()
        self._last_server_health = None
        self.hotkey_service = None
        self._last_record_toggle_at = 0.0
        
    def start(self):
        """Start the application — initialize all subsystems and enter main loop.

        Startup sequence:
        1. Initialize audio recorder and player.
        2. Create the GUI window (hidden initially).
        3. Start the backend message-processing thread.
        4. Start the tray icon manager.
        5. Start the global hotkey service.
        6. Enter the Tkinter mainloop (blocking on main thread).
        """
        try:
            self.running = True
            log.info("Clerkonator started!")
            log.info("STT: подключение через настройки (сервер или локальная модель)")
            
            # Log loaded hotkey config
            log.info(f"Loaded hotkeys - show_window: {self.config.get('hotkeys.show_window', 'NOT SET')}")
            log.info(f"Loaded hotkeys - record_toggle: {self.config.get('hotkeys.record_toggle', 'NOT SET')}")
            log.info(f"Loaded hotkeys - pause_recording: {self.config.get('hotkeys.pause_recording', 'NOT SET')}")
            log.info(f"Loaded hotkeys - cancel_recording: {self.config.get('hotkeys.cancel_recording', 'NOT SET')}")
            
            # Initialize audio recorder
            self.audio_recorder = AudioRecorder(self.config)
            if not self.audio_recorder.initialize():
                log.error("Failed to initialize audio system")
                messagebox.showerror("Error", "Failed to initialize audio system. Please check your microphone.")
                return False
            
            # Initialize audio player
            self.audio_player = AudioPlayer()
            log.info("Audio player initialized")
            
            # GUI must run on the main thread (Windows + pystray + Tkinter)
            self.gui_window = SimpleWindow(self.config)
            self.gui_window.set_app_instance(self)
            log.info("GUI ready (hidden)")
            
            # Backend queue processing in a worker thread
            self._backend_thread = threading.Thread(target=self._main_loop, daemon=True)
            self._backend_thread.start()
            log.info("Backend thread started")
            
            # Tray icon (non-blocking, detached from Tk mainloop)
            self.tray_manager = TrayManager(self)
            self.tray_manager.start_in_thread()

            # Initialize and start global hotkeys
            self.hotkey_service = GlobalHotkeyService(self)
            self.hotkey_service.start()
            log.info("Global hotkey service started")

            # STT is not loaded on startup — user connects via settings
            self._notify_gui("stt_idle")
            
            # Tk mainloop on main thread
            self.gui_window.run()
            return True
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start application: {str(e)}")
            log.error(f"Startup error: {e}")
            return False
    
    def _start_gui_thread(self):
        """Deprecated: GUI now runs on main thread."""
        pass
    
    # ── STT connection management ────────────────────────────────────

    def _is_stt_ready(self):
        """Check if the current STT backend is ready to transcribe.

        For remote mode: checks ``connected`` flag.
        For local mode: checks ``is_ready()`` method on the processor.
        """
        if self.stt_mode == "remote":
            return (
                self.stt_processor is not None
                and getattr(self.stt_processor, "connected", False)
            )
        return (
            self.stt_processor is not None
            and hasattr(self.stt_processor, "is_ready")
            and self.stt_processor.is_ready()
        )

    def _can_use_stt(self):
        """Whether recording / transcription is allowed."""
        return self._is_stt_ready()

    def _stt_mode_label(self):
        """Return a human-readable label for the current STT backend."""
        if self.stt_processor and hasattr(self.stt_processor, "get_mode_label"):
            return self.stt_processor.get_mode_label()
        return ""

    def _disconnect_stt(self):
        """Release the current STT backend and reset to idle state."""
        self._remote_poll_stop.set()
        if self.stt_processor and hasattr(self.stt_processor, "cleanup"):
            try:
                self.stt_processor.cleanup()
            except Exception as e:
                log.error(f"STT cleanup error: {e}")
        self.stt_processor = None
        self.stt_mode = "none"
        self.stt_connecting = False
        self._last_server_health = None
        self.config.set("stt.mode", "none")
        self._notify_gui("stt_idle")
        self._update_tray_status("Не подключено")

    def connect_local_stt(self):
        """Start loading a local STT model (Vosk or Whisper).

        Called from the settings window when the user selects local mode.
        Loading happens in a background thread; GUI is notified of progress.
        """
        if self.stt_connecting:
            log.warning("STT connection already in progress")
            return
        if self._is_stt_ready() and self.stt_mode == "local":
            log.info("Local STT already ready")
            self._notify_gui("stt_ready", self._stt_mode_label())
            return

        self._disconnect_stt()
        self.stt_connecting = True
        self.stt_mode = "local"
        self.config.set("stt.mode", "local")
        self._notify_gui("stt_connecting", "локальная модель")
        self._update_tray_status("Загрузка модели")
        self._load_local_stt_async()

    def connect_remote_stt(self, host=None, port=None):
        """Connect to a remote Clerkonator STT server.

        Called from the settings window when the user enters server host/port.
        Connection happens in a background thread.
        """
        if self.stt_connecting:
            log.warning("STT connection already in progress")
            return

        from utils.client_stt_config import get_remote_host, get_remote_port

        host = (host or get_remote_host(self.config)).strip()
        port = int(port or get_remote_port(self.config))
        self.config.set("stt.remote.host", host)
        self.config.set("stt.remote.port", port)
        self.config.set("stt.mode", "remote")

        self._disconnect_stt()
        self.stt_connecting = True
        self.stt_mode = "remote"
        self._notify_gui("stt_connecting", f"сервер {host}:{port}")
        self._update_tray_status("Подключение")

        def connect_worker():
            try:
                processor = RemoteSTTProcessor(self.config, host, port)
                if processor.initialize():
                    self.stt_processor = processor
                    self.stt_connecting = False
                    log.info(f"Remote STT connected: {host}:{port}")
                    self._start_remote_status_poll()
                    self._apply_remote_health(processor.server_info)
                    self._update_tray_status("Подключено")
                else:
                    self.stt_connecting = False
                    self.stt_mode = "none"
                    self.config.set("stt.mode", "none")
                    self._notify_gui("stt_failed", "Не удалось подключиться к серверу")
                    self._update_tray_status("Не подключено")
            except Exception as e:
                self.stt_connecting = False
                self.stt_mode = "none"
                log.error(f"Remote STT error: {e}")
                self._notify_gui("stt_failed", str(e))
                self._update_tray_status("Не подключено")

        threading.Thread(target=connect_worker, daemon=True).start()

    # ── Remote server health polling ─────────────────────────────────

    def _server_health_changed(self, health):
        """Detect if server health changed since last poll.

        Compares key fields to avoid spamming the GUI with unchanged updates.
        """
        key = (
            health.get("status"),
            health.get("model_loaded"),
            health.get("model_loading"),
            health.get("model_error"),
            health.get("queue_waiting"),
            health.get("queue_active"),
            health.get("engine"),
            health.get("device"),
        )
        if key == self._last_server_health:
            return False
        self._last_server_health = key
        return True

    def _apply_remote_health(self, health):
        """Update GUI status bar from a server health payload."""
        if health.get("model_loaded"):
            self._notify_gui("stt_ready", self._stt_mode_label())
        if self._server_health_changed(health):
            self._notify_gui("stt_server_status", health)

    def _start_remote_status_poll(self):
        """Start polling the remote server health every 2 seconds."""
        self._remote_poll_stop.clear()

        def poll_worker():
            while self.running and not self._remote_poll_stop.is_set():
                if self.stt_mode != "remote" or not self.stt_processor:
                    break
                try:
                    health = self.stt_processor.fetch_health()
                    self.stt_processor.server_info = health
                    if self._server_health_changed(health):
                        self._notify_gui("stt_server_status", health)
                except Exception as e:
                    log.warning(f"Server health poll failed: {e}")
                    self._notify_gui("stt_server_status", {"status": "error", "error": str(e)})
                if self._remote_poll_stop.wait(2.0):
                    break

        threading.Thread(target=poll_worker, name="STT-HealthPoll", daemon=True).start()

    def _load_local_stt_async(self):
        """Load the local STT model in a background thread.

        Resolves the model type (Vosk vs Whisper) from config and loads it.
        Includes a 15-minute timeout to prevent indefinite hangs.
        """
        def load_worker():
            try:
                from utils.client_stt_config import resolve_local_model

                model = resolve_local_model(self.config)
                if model and model.engine == "whisper":
                    log.info(f"Loading Whisper model locally: {model.title}")
                    try:
                        from stt.whisper_processor import WhisperSTTProcessor

                        processor = WhisperSTTProcessor(self.config)
                    except ImportError:
                        self.stt_connecting = False
                        self.stt_mode = "none"
                        self.config.set("stt.mode", "none")
                        self._notify_gui(
                            "stt_failed",
                            "Для Whisper локально нужен pip install -r requirements-server.txt",
                        )
                        self._update_tray_status("Не подключено")
                        return
                else:
                    log.info("Loading Vosk model (local mode)...")
                    if not model:
                        if not download_model_if_needed(self.config):
                            log.error("Failed to install Vosk model")
                            self.stt_connecting = False
                            self.stt_mode = "none"
                            self.config.set("stt.mode", "none")
                            self._notify_gui("stt_failed", "Модель Vosk не найдена")
                            self._update_tray_status("Не подключено")
                            return
                    processor = STTProcessor(self.config)
                start_time = time.time()
                init_result = [None]
                init_exception = [None]

                def init_worker():
                    try:
                        init_result[0] = processor.initialize()
                    except Exception as e:
                        init_exception[0] = e

                init_thread = threading.Thread(target=init_worker, daemon=True)
                init_thread.start()
                init_thread.join(timeout=900)
                loading_time = time.time() - start_time

                if init_thread.is_alive():
                    log.error(f"Local STT init timeout after {loading_time:.0f}s")
                    self.stt_connecting = False
                    self.stt_mode = "none"
                    self.config.set("stt.mode", "none")
                    self._notify_gui(
                        "stt_failed",
                        f"Таймаут загрузки модели ({loading_time:.0f} с). Попробуйте сетевой режим.",
                    )
                    self._update_tray_status("Не подключено")
                elif init_exception[0]:
                    log.error(f"Local STT init error: {init_exception[0]}")
                    self.stt_connecting = False
                    self.stt_mode = "none"
                    self.config.set("stt.mode", "none")
                    self._notify_gui("stt_failed", str(init_exception[0]))
                    self._update_tray_status("Не подключено")
                elif init_result[0]:
                    self.stt_processor = processor
                    self.stt_connecting = False
                    log.info(f"Local STT ready in {loading_time:.2f}s")
                    self._notify_gui("stt_ready", processor.get_mode_label())
                    self._update_tray_status("Готово")
                else:
                    self.stt_connecting = False
                    self.stt_mode = "none"
                    self.config.set("stt.mode", "none")
                    self._notify_gui("stt_failed", "Не удалось инициализировать модель")
                    self._update_tray_status("Не подключено")

            except Exception as e:
                self.stt_connecting = False
                self.stt_mode = "none"
                log.error(f"Error loading local STT: {e}")
                self._notify_gui("stt_failed", str(e))
                self._update_tray_status("Не подключено")

        threading.Thread(target=load_worker, daemon=True).start()

    def _load_model_and_stt_async(self):
        """Deprecated: use connect_local_stt()."""
        self.connect_local_stt()
    
    def _start_tray_manager(self):
        """Deprecated: tray starts via TrayManager.start_detached()."""
        pass
    
    # ── Backend message processing ────────────────────────────────────

    def _main_loop(self):
        """Backend thread loop — processes messages from the GUI queue."""
        try:
            while self.running:
                # Process GUI messages
                try:
                    while True:
                        message = self.gui_queue.get_nowait()
                        self._process_gui_message(message)
                except queue.Empty:
                    pass
                
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            log.info("Received stop signal...")
        except Exception as e:
            log.error(f"Main loop error: {e}")
        finally:
            self.stop()
    
    def _process_gui_message(self, message):
        """Dispatch a message from the GUI to the appropriate handler method.

        Message format: ``(message_type: str, data: any)``
        """
        try:
            message_type, data = message
            log.info(f"Processing GUI message: {message_type}, data: {data}")
            
            if message_type == "start_recording":
                self._start_recording(data)
            elif message_type == "stop_recording":
                self._stop_recording()
            elif message_type == "cancel_recording":
                self._cancel_recording()
            elif message_type == "finish_recording":
                self._finish_and_process(data)
            elif message_type == "pause_recording":
                self._pause_recording()
            elif message_type == "resume_recording":
                self._resume_recording()
            elif message_type == "process_audio":
                self._process_audio(data)
            elif message_type == "process_audio_file":
                self._process_audio_file(data)
            elif message_type == "play_audio":
                self._play_audio(data)
            elif message_type == "pause_audio":
                self._pause_audio()
            elif message_type == "resume_audio":
                self._resume_audio()
            elif message_type == "stop_audio":
                self._stop_audio()
            elif message_type == "convert_audio_file":
                self._convert_audio_file(data)
            elif message_type == "connect_local_stt":
                self.connect_local_stt()
            elif message_type == "connect_remote_stt":
                host = None
                port = None
                if isinstance(data, dict):
                    host = data.get("host")
                    port = data.get("port")
                self.connect_remote_stt(host, port)
            elif message_type == "disconnect_stt":
                self._disconnect_stt()
            else:
                log.warning(f"Unknown GUI message type: {message_type}")
                
        except Exception as e:
            log.error(f"Error processing GUI message: {e}")
    
    def _notify_gui(self, message_type, data=None):
        """Send a message to the GUI thread (thread-safe via window.after).

        Called from backend/worker threads to update the UI.
        """
        try:
            verbose = message_type != "stt_server_status"
            if verbose:
                log.info(f"Notifying GUI: {message_type}, data: {data}")
            if self.gui_window:
                self.gui_window.window.after(0, lambda: self._handle_gui_message(message_type, data))
                if verbose:
                    log.info(f"GUI notification sent: {message_type}, data: {data}")
            else:
                log.warning(f"GUI window not available for notification: {message_type}")
        except Exception as e:
            log.error(f"Error notifying GUI: {e}")
    
    def _handle_gui_message(self, message_type, data):
        """Handle a message in the GUI thread — dispatches to SimpleWindow handlers."""
        try:
            if message_type != "stt_server_status":
                log.info(f"Handling GUI message: {message_type}, data: {data}")
            if message_type == "start_recording":
                # This is a message from GUI to main thread, not a notification to GUI
                log.warning(f"Received start_recording in GUI thread - this should go to main thread")
            elif message_type == "recording_started":
                self.gui_window.handle_recording_started(data)
            elif message_type == "recording_stopped":
                self.gui_window.handle_recording_stopped()
            elif message_type == "recording_cancelled":
                self.gui_window.handle_recording_cancelled()
            elif message_type == "recording_paused":
                self.gui_window.handle_recording_paused()
            elif message_type == "recording_resumed":
                self.gui_window.handle_recording_resumed()
            elif message_type == "recording_failed":
                self.gui_window.handle_recording_failed(data)
            elif message_type == "processing_started":
                self.gui_window.handle_processing_started(data)
            elif message_type == "processing_progress":
                self.gui_window.handle_processing_progress(data)
            elif message_type == "processing_complete":
                self.gui_window.handle_processing_complete(data)
            elif message_type == "processing_failed":
                self.gui_window.handle_processing_failed(data)
            elif message_type == "stt_ready":
                self.gui_window.handle_stt_ready(data)
            elif message_type == "stt_failed":
                self.gui_window.handle_stt_failed(data)
            elif message_type == "stt_idle":
                self.gui_window.handle_stt_idle()
            elif message_type == "stt_connecting":
                self.gui_window.handle_stt_connecting(data)
            elif message_type == "stt_server_status":
                self.gui_window.handle_stt_server_status(data)
            elif message_type == "conversion_started":
                self.gui_window.handle_conversion_started()
            elif message_type == "conversion_complete":
                self.gui_window.handle_conversion_complete(data)
            elif message_type == "conversion_failed":
                self.gui_window.handle_conversion_failed(data)
            else:
                log.warning(f"Unknown GUI message type: {message_type}")
                
        except Exception as e:
            log.error(f"Error handling GUI message: {e}")
    
    # ── Recording controls ──────────────────────────────────────────

    def _start_recording(self, filename):
        """Start audio recording with the given filename."""
        try:
            if self.is_recording:
                log.warning("Already recording")
                return
            
            if not self._can_use_stt():
                log.warning("STT processor not ready")
                self._notify_gui("recording_failed", "STT не подключён. Откройте настройки и подключитесь к серверу или загрузите локальную модель.")
                return
            
            # Start recording
            if self.audio_recorder.start_recording(filename):
                self.is_recording = True
                self.is_paused = False
                self.current_audio_file = filename
                log.info(f"Recording started: {filename}")
                self._notify_gui("recording_started", filename)
                self._update_tray_status("Запись")
            else:
                log.error("Failed to start recording")
                self._notify_gui("recording_failed", "Failed to start recording")
                
        except Exception as e:
            log.error(f"Error starting recording: {e}")
            self._notify_gui("recording_failed", str(e))
    
    def _stop_recording(self):
        """Stop audio recording (saves the file but does not transcribe)."""
        try:
            if not self.is_recording:
                log.warning("Not recording")
                return
            
            self.audio_recorder.stop_recording(self.current_audio_file)
            self.is_recording = False
            self.is_paused = False
            log.info("Recording stopped")
            self._notify_gui("recording_stopped")
            self._update_tray_status("Готово")
            
        except Exception as e:
            log.error(f"Error stopping recording: {e}")
    
    def _cancel_recording(self):
        """Cancel recording without saving the audio."""
        try:
            if not self.is_recording:
                return
            self.audio_recorder.cancel_recording()
            self.is_recording = False
            self.is_paused = False
            self.current_audio_file = None
            log.info("Recording cancelled")
            self._notify_gui("recording_cancelled")
            self._update_tray_status("Готово")
        except Exception as e:
            log.error(f"Error cancelling recording: {e}")
    
    def _finish_and_process(self, audio_file):
        """Stop recording, save the file, and immediately run STT on it."""
        try:
            if not self.is_recording:
                if audio_file:
                    self._process_audio(audio_file)
                return
            file_to_process = audio_file or self.current_audio_file
            self.audio_recorder.stop_recording(file_to_process)
            self.is_recording = False
            self.is_paused = False
            self._notify_gui("recording_stopped")
            if file_to_process:
                self._process_audio(file_to_process)
            self._update_tray_status("Распознавание")
        except Exception as e:
            log.error(f"Error finish recording: {e}")
    
    def _pause_recording(self):
        """Pause audio recording (can be resumed)."""
        try:
            if not self.is_recording:
                log.warning("Not recording")
                return
            
            self.audio_recorder.pause_recording()
            self.is_paused = True
            log.info("Recording paused")
            self._notify_gui("recording_paused")
            self._update_tray_status("Пауза")
            
        except Exception as e:
            log.error(f"Error pausing recording: {e}")
    
    def _resume_recording(self):
        """Resume a paused audio recording."""
        try:
            if not self.is_recording:
                log.warning("Not recording")
                return
            
            self.audio_recorder.resume_recording()
            self.is_paused = False
            log.info("Recording resumed")
            self._notify_gui("recording_resumed")
            self._update_tray_status("Запись")
            
        except Exception as e:
            log.error(f"Error resuming recording: {e}")
    
    # ── STT processing ──────────────────────────────────────────────

    def _process_audio(self, audio_file):
        """Process a recording from the audio directory."""
        audio_dir = self.config.get("files.audio_dir", "data/recordings")
        audio_path = os.path.join(audio_dir, audio_file)
        self._run_stt_job(audio_path, audio_file)

    def _on_progress(self, progress):
        """Handle STT progress updates from the processor."""
        self._notify_gui("processing_progress", progress)

    def _on_result(self, result):
        """Handle STT result from the processor."""
        self._notify_gui("processing_complete", result)
    
    # ── UI actions ──────────────────────────────────────────────────

    def show_gui(self):
        """Show the GUI window (from tray or hotkey)."""
        try:
            if self.gui_window:
                self.gui_window.window.after(0, self.gui_window.show)
                log.info("GUI window shown")
        except Exception as e:
            log.error(f"Error showing GUI: {e}")
    
    def show_settings(self):
        """Open the settings window (on the GUI thread)."""
        try:
            if self.gui_window:
                self.gui_window.window.after(0, self.gui_window.open_settings)
        except Exception as e:
            log.error(f"Error opening settings: {e}")
    
    def apply_backend_settings(self):
        """Apply config changes to running backend (audio recorder, hotkeys)."""
        if self.audio_recorder:
            self.audio_recorder.reload_settings()
        if self.hotkey_service:
            self.hotkey_service.reload()
    
    def _update_tray_status(self, status):
        """Update the tray icon status and tooltip text."""
        if self.tray_manager:
            try:
                self.tray_manager.update_status(status)
            except Exception as e:
                log.error(f"Tray status update error: {e}")
    
    # ── Tray-initiated actions ──────────────────────────────────────

    def _generate_recording_name(self):
        """Generate a timestamped recording filename."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"recording_{timestamp}.wav"

    def tray_start_recording(self):
        """Start recording (called from tray menu)."""
        if self.is_recording:
            return
        self.gui_queue.put(("start_recording", self._generate_recording_name()))

    def tray_pause_recording(self):
        """Pause recording (called from tray menu)."""
        if self.is_recording and not self.is_paused:
            self.gui_queue.put(("pause_recording", None))

    def tray_resume_recording(self):
        """Resume recording (called from tray menu)."""
        if self.is_recording and self.is_paused:
            self.gui_queue.put(("resume_recording", None))

    def tray_cancel_recording(self):
        """Cancel recording (called from tray menu)."""
        if self.is_recording:
            self.gui_queue.put(("cancel_recording", None))

    def tray_finish_recording(self):
        """Finish recording and start transcription (called from tray menu)."""
        audio_file = self.current_audio_file
        recording = self.is_recording
        if self.gui_window:
            if not audio_file:
                audio_file = self.gui_window.current_audio_file
            if not recording:
                recording = self.gui_window.is_recording
        if recording and audio_file:
            self.gui_queue.put(("finish_recording", audio_file))

    def toggle_recording(self):
        """Toggle between recording and finish-and-transcribe (hotkey / tray).

        If not recording → start recording.
        If recording → finish and transcribe.
        Includes a 350ms debounce to prevent double-toggles.
        """
        now = time.monotonic()
        if now - self._last_record_toggle_at < 0.35:
            return
        self._last_record_toggle_at = now

        recording = self.is_recording
        if self.gui_window and self.gui_window.is_recording:
            recording = True

        if recording:
            self.tray_finish_recording()
        else:
            self.tray_start_recording()

    def tray_toggle_recording(self):
        """One hotkey: start recording or finish and transcribe."""
        self.toggle_recording()
    
    # ── Shutdown ─────────────────────────────────────────────────────

    def stop(self):
        """Stop the application — clean up all resources and exit."""
        log.info("Stopping Clerkonator...")
        self.running = False
        
        # Stop audio recording
        if self.audio_recorder:
            try:
                self.audio_recorder.stop_recording()
            except Exception as e:
                log.error(f"Error stopping audio recorder: {e}")
        
        # Destroy GUI window
        if self.gui_window:
            try:
                self.gui_window.destroy()
            except Exception as e:
                log.error(f"Error destroying GUI window: {e}")
        
        # Stop tray manager
        if self.tray_manager:
            try:
                self.tray_manager.stop()
            except Exception as e:
                log.error(f"Error stopping tray manager: {e}")

        if self.hotkey_service:
            try:
                self.hotkey_service.stop()
            except Exception as e:
                log.error(f"Error stopping hotkeys: {e}")
        
        log.info("Clerkonator stopped")
        
        # Force exit
        import os
        os._exit(0)
    
    def _process_audio_file(self, file_path):
        """Process external audio file"""
        self._run_stt_job(file_path, os.path.basename(file_path))

    def _run_stt_job(self, audio_path, source_label):
        """Run a single STT transcription job in a background thread.

        Supports parallel jobs (multiple files can be transcribed simultaneously).
        Updates the processing counter and tray status accordingly.
        """
        try:
            if not self._can_use_stt():
                self._notify_gui("processing_failed", "STT не подключён")
                return

            self.processing_count += 1
            job_no = self.processing_count
            log.info(f"STT job #{job_no}: {source_label}")
            self._notify_gui("processing_started", {"job_no": job_no, "source": source_label})
            if self.processing_count == 1:
                self._update_tray_status("Распознавание")

            def process_worker():
                try:
                    from utils.stt_recognition import build_recognition_options

                    rec_opts = build_recognition_options(self.config)
                    result = self.stt_processor.process_audio_file_sync(audio_path, rec_opts)
                    if result:
                        if isinstance(result, dict):
                            result.setdefault("job_no", job_no)
                            result.setdefault("source", source_label)
                            self._notify_gui("processing_complete", result)
                        else:
                            self._notify_gui("processing_complete", {
                                "text": result,
                                "job_no": job_no,
                                "source": source_label,
                            })
                    else:
                        self._notify_gui("processing_failed", f"Ошибка распознавания (#{job_no})")
                except Exception as e:
                    self._notify_gui("processing_failed", str(e))
                finally:
                    self.processing_count = max(0, self.processing_count - 1)
                    if self.processing_count == 0:
                        if self.stt_mode == "remote" and self.stt_processor:
                            self._update_tray_status(self.stt_processor.get_status_text())
                        else:
                            self._update_tray_status("Готово")

            threading.Thread(target=process_worker, daemon=True).start()
        except Exception as e:
            self._notify_gui("processing_failed", str(e))
    
    # ── Audio playback controls ─────────────────────────────────────

    def _play_audio(self, file_path):
        """Play an audio file in a separate thread."""
        try:
            log.info(f"Playing audio file: {file_path}")
            
            # Play audio in separate thread
            def play_worker():
                try:
                    success = self.audio_player.play_file(file_path)
                    if success:
                        log.info("Audio playback started")
                    else:
                        log.error("Failed to start audio playback")
                        
                except Exception as e:
                    log.error(f"Error playing audio: {e}")
            
            # Start playback thread
            play_thread = threading.Thread(target=play_worker, daemon=True)
            play_thread.start()
            
        except Exception as e:
            log.error(f"Error playing audio: {e}")
    
    def _pause_audio(self):
        """Pause audio playback."""
        try:
            log.info("Pausing audio playback")
            self.audio_player.pause()
        except Exception as e:
            log.error(f"Error pausing audio: {e}")
    
    def _resume_audio(self):
        """Resume audio playback."""
        try:
            log.info("Resuming audio playback")
            self.audio_player.unpause()
        except Exception as e:
            log.error(f"Error resuming audio: {e}")
    
    def _stop_audio(self):
        """Stop audio playback."""
        try:
            log.info("Stopping audio playback")
            self.audio_player.stop()
        except Exception as e:
            log.error(f"Error stopping audio: {e}")
    
    def _convert_audio_file(self, file_path):
        """Transcribe an external audio file (not from recording)."""
        try:
            if not self._can_use_stt():
                self._notify_gui("conversion_failed", "STT не подключён")
                return
            self._notify_gui("conversion_started")
            self._run_stt_job(file_path, os.path.basename(file_path))
        except Exception as e:
            log.error(f"Error converting audio file: {e}")
            self._notify_gui("conversion_failed", str(e))


def main():
    """Application entry point."""
    log.info("Starting Clerkonator...")
    
    app = ClerkonatorApp()
    
    try:
        app.start()
    except KeyboardInterrupt:
        log.info("Received stop signal...")
    except Exception as e:
        log.critical(f"Critical error: {e}")
    finally:
        if app.running:
            app.running = False
            log.info("Application main loop ended")


if __name__ == "__main__":
    main()