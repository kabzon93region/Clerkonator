#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Compact dark GUI for Clerkonator client.

Tkinter-based window with:
- Status bar (STT connection state, timer)
- Recording controls (record, pause, cancel, finish)
- Progress bar and result text area
- History list (last 50 transcriptions)
- Audio file import and playback

The window is hidden by default (runs in system tray).
Keyboard shortcuts are handled via ``_on_keypress`` / ``_on_keyrelease``.
"""

import os
import threading
import time
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk

from gui.dark_theme import apply_dark_theme, style_text_widget, style_listbox
from gui.keyboard_bindings import bind_text_shortcuts
from gui.settings_window import BackendSettingsWindow
from utils.hotkey_codec import matches_hotkey_tk_event
from utils.app_icon import get_icon_ico_path
from utils.session_logger import get_logger

log = get_logger()


class SimpleWindow:
    """Main application window with dark compact layout.

    All GUI updates from backend threads go through ``window.after()``
    to ensure thread-safe Tkinter access.
    """

    def __init__(self, config):
        self.config = config
        self.app_instance = None
        self.colors = None

        self.is_recording = False
        self.is_paused = False
        self.is_processing = False
        self.current_audio_file = None
        self.loaded_audio_file = None
        self.is_playing_audio = False
        self.is_paused_audio = False
        self._timer_thread = None
        self.history_items = []
        self._history_seq = 0

        self._create_window()
        self._create_widgets()
        self._setup_bindings()
        log.info("GUI window initialized (dark compact)")

    def set_app_instance(self, app_instance):
        self.app_instance = app_instance

    def _create_window(self):
        self.window = tk.Tk()
        self.window.title("Clerkonator")
        self.colors = apply_dark_theme(self.window)

        # Auto-size window to content
        self.window.update_idletasks()
        req_width = self.window.winfo_reqwidth() + 20
        req_height = self.window.winfo_reqheight() + 20
        
        # Ensure minimum size (wide enough for buttons)
        req_width = max(req_width, 640)
        req_height = max(req_height, 540)
        
        # Center window on screen
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        x = (screen_width - req_width) // 2
        y = (screen_height - req_height) // 2
        
        self.window.geometry(f"{req_width}x{req_height}+{x}+{y}")
        self.window.minsize(420, 400)
        self.window.withdraw()

        try:
            self.window.iconbitmap(get_icon_ico_path())
        except Exception as e:
            log.warning(f"Window icon not set: {e}")

        if self.config.get("gui.always_on_top", False):
            self.window.attributes("-topmost", True)

        self.window.protocol("WM_DELETE_WINDOW", self.hide_window)

    def _create_widgets(self):
        root = ttk.Frame(self.window, padding=(8, 6))
        root.pack(fill=tk.BOTH, expand=True)

        # Status bar row
        status_frame = ttk.Frame(root)
        status_frame.pack(fill=tk.X, pady=(0, 6))

        self.status_label = ttk.Label(status_frame, text="STT не подключён", style="Status.TLabel")
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Button(status_frame, text="⚙ Настройки", command=self.open_settings, width=12).pack(
            side=tk.RIGHT, padx=(4, 0)
        )

        self.timer_label = ttk.Label(status_frame, text="00:00", style="Muted.TLabel", width=6)
        self.timer_label.pack(side=tk.RIGHT, padx=(4, 0))

        # Recording controls
        rec_frame = ttk.Frame(root)
        rec_frame.pack(fill=tk.X, pady=(0, 6))

        self.record_button = ttk.Button(rec_frame, text="● Запись", command=self._start_recording, width=10)
        self.record_button.pack(side=tk.LEFT, padx=(0, 4))

        self.pause_button = ttk.Button(rec_frame, text="⏸ Пауза", command=self._toggle_pause, state="disabled", width=10)
        self.pause_button.pack(side=tk.LEFT, padx=(0, 4))

        self.cancel_button = ttk.Button(rec_frame, text="✕ Отмена", command=self._cancel_recording, state="disabled", width=10)
        self.cancel_button.pack(side=tk.LEFT, padx=(0, 4))

        self.finish_button = ttk.Button(
            rec_frame, text="✓ Готово", command=self._finish_recording, state="disabled", width=10, style="Accent.TButton"
        )
        self.finish_button.pack(side=tk.LEFT)

        self.progress_bar = ttk.Progressbar(root, mode="determinate", maximum=100)
        self.progress_bar.pack(fill=tk.X, pady=(0, 2))

        self.progress_label = ttk.Label(root, text="", style="Muted.TLabel")
        self.progress_label.pack(anchor=tk.W, pady=(0, 2))

        # Result + history
        result_lf = ttk.LabelFrame(root, text="Результат", padding=(4, 4))
        result_lf.pack(fill=tk.BOTH, expand=True)

        # Text area with scrollbar and buttons
        text_frame = ttk.Frame(result_lf)
        text_frame.pack(fill=tk.BOTH, expand=True)

        # Create text widget with scrollbar
        text_with_scroll = ttk.Frame(text_frame)
        text_with_scroll.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.result_text = tk.Text(text_with_scroll, height=4, wrap=tk.WORD, font=("Segoe UI", 10))
        style_text_widget(self.result_text, self.colors)
        bind_text_shortcuts(self.result_text)
        
        # Add vertical scrollbar
        text_scroll = ttk.Scrollbar(text_with_scroll, orient=tk.VERTICAL, command=self.result_text.yview)
        self.result_text.config(yscrollcommand=text_scroll.set)
        
        self.result_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        text_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Side buttons (right side)
        side_btns = ttk.Frame(text_frame)
        side_btns.pack(side=tk.RIGHT, fill=tk.Y, padx=(6, 0))

        self.copy_button = ttk.Button(side_btns, text="Копировать", command=self._copy_to_clipboard, state="disabled", width=10)
        self.copy_button.pack(pady=(0, 4))

        ttk.Button(side_btns, text="В трей", command=self.hide_window, width=10).pack(pady=(0, 4))

        hist_header = ttk.Frame(result_lf)
        hist_header.pack(fill=tk.X, pady=(6, 2))
        ttk.Label(hist_header, text="История распознаваний", style="Muted.TLabel").pack(side=tk.LEFT)
        ttk.Button(hist_header, text="Очистить", command=self._clear_history, width=8).pack(side=tk.RIGHT)

        hist_frame = ttk.Frame(result_lf)
        hist_frame.pack(fill=tk.BOTH, expand=True)

        self.history_listbox = tk.Listbox(hist_frame, height=5)
        style_listbox(self.history_listbox, self.colors)
        hist_scroll = ttk.Scrollbar(hist_frame, orient=tk.VERTICAL, command=self.history_listbox.yview)
        self.history_listbox.config(yscrollcommand=hist_scroll.set)
        self.history_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        hist_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.history_listbox.bind("<Double-Button-1>", self._on_history_activate)
        self.history_listbox.bind("<<ListboxSelect>>", self._on_history_select)

        hist_hint = ttk.Label(
            result_lf,
            text="Двойной щелчок — открыть в поле выше и скопировать",
            style="Muted.TLabel",
        )
        hist_hint.pack(anchor=tk.W, pady=(2, 0))

        # File section
        file_lf = ttk.LabelFrame(root, text="Файл", padding=(6, 4))
        file_lf.pack(fill=tk.X, pady=(6, 0))

        file_row = ttk.Frame(file_lf)
        file_row.pack(fill=tk.X)

        ttk.Button(file_row, text="Открыть", command=self._load_audio_file, width=8).pack(side=tk.LEFT, padx=(0, 4))
        self.play_button = ttk.Button(file_row, text="▶", command=self._play_audio, state="disabled", width=3)
        self.play_button.pack(side=tk.LEFT, padx=(0, 2))
        self.pause_button_audio = ttk.Button(file_row, text="⏸", command=self._pause_audio, state="disabled", width=3)
        self.pause_button_audio.pack(side=tk.LEFT, padx=(0, 2))
        self.stop_button_audio = ttk.Button(file_row, text="⏹", command=self._stop_audio, state="disabled", width=3)
        self.stop_button_audio.pack(side=tk.LEFT, padx=(0, 4))
        self.convert_button = ttk.Button(file_row, text="В текст", command=self._convert_audio, state="disabled", width=8)
        self.convert_button.pack(side=tk.LEFT)

        self.current_file_label = ttk.Label(file_lf, text="файл не выбран", style="Muted.TLabel")
        self.current_file_label.pack(anchor=tk.W, pady=(2, 0))

    def _setup_bindings(self):
        self.window.bind_all("<KeyPress>", self._on_keypress, add=True)
        self.window.bind_all("<KeyRelease>", self._on_keyrelease, add=True)

    def _on_keyrelease(self, event):
        """Configured record toggle (start / готово)."""
        top = event.widget.winfo_toplevel()
        if top.title() == "Настройки":
            return

        record_spec = self.config.get("hotkeys.record_toggle", "ctrl+shift+r")
        if not matches_hotkey_tk_event(event, record_spec):
            return

        if self.app_instance:
            self.app_instance.toggle_recording()
        else:
            self._toggle_recording_local()
        return "break"

    def _toggle_recording_local(self):
        if self.is_recording:
            self._finish_recording()
        else:
            self._start_recording()

    def _on_keypress(self, event):
        """Window shortcuts by physical key (RU/EN layout)."""
        top = event.widget.winfo_toplevel()
        if top.title() == "Настройки":
            return

        state = int(event.state)
        kc = int(event.keycode)

        if state & 0x4:
            if kc == 80:
                self._toggle_pause()
                return "break"
            if kc == 70:
                self._finish_recording()
                return "break"
            if kc == 188:
                self.open_settings()
                return "break"
            if kc in (67, 86, 65, 88, 90) and str(event.widget) == str(self.result_text):
                return

        if event.keysym == "Escape":
            self.hide_window()
            return "break"

    def _queue(self, msg_type, data=None):
        if self.app_instance:
            self.app_instance.gui_queue.put((msg_type, data))

    def _start_recording(self):
        if self.is_recording:
            return
        if not self.app_instance:
            messagebox.showerror("Ошибка", "Приложение не подключено")
            return
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._queue("start_recording", f"recording_{timestamp}.wav")

    def _cancel_recording(self):
        if not self.is_recording:
            return
        self._queue("cancel_recording", None)

    def _toggle_pause(self):
        if not self.is_recording:
            return
        if not self.is_paused:
            self._queue("pause_recording", None)
        else:
            self._queue("resume_recording", None)

    def _finish_recording(self):
        if not self.app_instance or not self.current_audio_file:
            messagebox.showwarning("Внимание", "Нет активной записи")
            return
        self._queue("finish_recording", self.current_audio_file)

    def _copy_to_clipboard(self):
        try:
            text = self.result_text.get(1.0, tk.END).strip()
            if not text:
                messagebox.showwarning("Внимание", "Нет текста для копирования")
                return
            self.window.clipboard_clear()
            self.window.clipboard_append(text)
            self.window.update()
            self.copy_button.config(text="✓")
            self.window.after(1500, lambda: self.copy_button.config(text="Копировать"))
        except Exception as e:
            log.error(f"Copy error: {e}")

    def open_settings(self):
        def on_save():
            if self.config.get("gui.always_on_top", False):
                self.window.attributes("-topmost", True)
            else:
                self.window.attributes("-topmost", False)
            if self.app_instance and hasattr(self.app_instance, "apply_backend_settings"):
                self.app_instance.apply_backend_settings()

        BackendSettingsWindow(self.window, self.config, app_instance=self.app_instance, on_save=on_save)

    def show(self):
        self.window.deiconify()
        self.window.lift()
        self.window.focus_force()

    def hide_window(self):
        self.window.withdraw()

    def run(self):
        self.window.mainloop()

    def destroy(self):
        try:
            self.window.unbind_all("<KeyPress>")
            self.window.unbind_all("<KeyRelease>")
        except tk.TclError:
            pass
        self.window.destroy()

    def _set_status(self, text, tone="fg"):
        color_key = {"fg": "fg", "success": "success", "warning": "warning", "error": "error", "accent": "accent"}.get(tone, "fg")
        self.status_label.config(text=text, foreground=self.colors[color_key])

    def _set_recording_ui(self, active):
        if active:
            self.record_button.config(state="disabled")
            self.pause_button.config(state="normal", text="⏸ Пауза")
            self.cancel_button.config(state="normal")
            self.finish_button.config(state="normal")
        else:
            self.record_button.config(state="normal")
            self.pause_button.config(state="disabled", text="⏸ Пауза")
            self.cancel_button.config(state="disabled")
            self.finish_button.config(state="disabled")
            self.timer_label.config(text="00:00")

    # --- handlers from main thread ---

    def handle_recording_started(self, filename):
        self.is_recording = True
        self.is_paused = False
        self.current_audio_file = filename
        self._set_recording_ui(True)
        self._set_status("Запись…", "error")
        self._start_timer()
        log.info(f"Recording started: {filename}")

    def handle_recording_stopped(self):
        self.is_recording = False
        self.is_paused = False
        self._set_recording_ui(False)
        self._set_status("Готово", "success")

    def handle_recording_cancelled(self):
        self.is_recording = False
        self.is_paused = False
        self.current_audio_file = None
        self._set_recording_ui(False)
        self._set_status("Запись отменена", "warning")

    def handle_recording_paused(self):
        self.is_paused = True
        self.pause_button.config(text="▶ Продолжить")
        self._set_status("Пауза", "warning")

    def handle_recording_resumed(self):
        self.is_paused = False
        self.pause_button.config(text="⏸ Пауза")
        self._set_status("Запись…", "error")

    def handle_recording_failed(self, error=None):
        self._set_status("Запись недоступна", "error")
        if error:
            messagebox.showwarning("Запись", str(error))

    def handle_processing_started(self, data=None):
        self.is_processing = True
        job_no = ""
        if isinstance(data, dict) and data.get("job_no"):
            job_no = f" #{data['job_no']}"
        self._set_status(f"Распознавание{job_no}…", "accent")
        self.progress_bar["value"] = 0
        self.progress_label.config(text="Ожидание сервера / обработка…")

    def handle_processing_progress(self, progress):
        self.progress_bar["value"] = progress
        self.progress_label.config(text=f"{progress:.0f}%")

    def handle_processing_complete(self, result):
        text = ""
        processing_time = 0
        job_no = None
        source = ""

        if isinstance(result, dict):
            text = result.get("text", "")
            processing_time = result.get("processing_time", 0)
            job_no = result.get("job_no")
            source = result.get("source", "")
        else:
            text = result or ""

        self._add_history_entry(text, processing_time, job_no, source)

        self.result_text.delete(1.0, tk.END)
        self.result_text.insert(tk.END, text)
        time_suffix = f" ({processing_time:.1f} с)" if processing_time else ""
        job_suffix = f" #{job_no}" if job_no else ""
        self._set_status(f"Готово{job_suffix}{time_suffix}", "success")
        self.copy_button.config(state="normal")
        self.progress_bar["value"] = 100
        self.progress_label.config(text="")
        self.is_processing = False

        # Play success sound
        self._play_system_sound("success")

        if self.config.get("gui.auto_copy", True) and text.strip():
            self._copy_to_clipboard()

    def handle_processing_failed(self, error=None):
        self.is_processing = False
        self.progress_bar["value"] = 0
        self.progress_label.config(text="")
        msg = str(error) if error else "Ошибка распознавания"
        self._set_status(msg, "error")
        
        # Play error sound
        self._play_system_sound("error")
        
        messagebox.showwarning("Распознавание", msg)

    def handle_conversion_started(self):
        self.handle_processing_started()

    def handle_conversion_complete(self, result):
        if isinstance(result, dict):
            self.handle_processing_complete(result)
        else:
            self.handle_processing_complete({"text": result or "", "processing_time": 0})

    def handle_conversion_failed(self, error):
        self.is_processing = False
        self._set_status("Ошибка распознавания", "error")
        
        # Play error sound
        self._play_system_sound("error")
        
        messagebox.showerror("Ошибка", str(error))

    def handle_stt_idle(self):
        self._set_status("STT не подключён — «Настройки»", "warning")

    def handle_stt_connecting(self, target):
        label = target or "…"
        self._set_status(f"Подключение: {label}", "accent")

    def handle_stt_ready(self, mode_label=None):
        suffix = f" ({mode_label})" if mode_label else ""
        self._set_status(f"Готово{suffix}", "success")

    def handle_stt_failed(self, error=None):
        self._set_status("STT недоступен", "error")
        if error:
            messagebox.showwarning("STT", str(error))

    def handle_stt_server_status(self, health):
        """Update status bar from remote server health."""
        if not isinstance(health, dict):
            return
        if health.get("status") == "error":
            self._set_status("Сервер: нет связи", "warning")
            return
        if health.get("model_error"):
            self._set_status("Сервер: ошибка модели", "error")
            return
        if health.get("model_loading"):
            self._set_status("Сервер: загрузка модели…", "accent")
            return
        if not health.get("model_loaded"):
            self._set_status("Сервер: ожидание модели…", "warning")
            return
        engine = health.get("engine", "")
        device = health.get("device", "")
        backend = f"{engine}/{device}" if engine and device else (engine or device or "готов")
        waiting = int(health.get("queue_waiting", 0))
        active = int(health.get("queue_active", 0))
        if self.is_processing or active > 0:
            extra = f", очередь {waiting}" if waiting else ""
            self._set_status(f"Сервер: {backend}{extra}", "accent")
        elif waiting > 0:
            self._set_status(f"Сервер: очередь ({waiting})", "accent")
        else:
            self._set_status(f"Сервер: {backend}", "success")

    def _add_history_entry(self, text, processing_time=0, job_no=None, source=""):
        self._history_seq += 1
        preview = text.replace("\n", " ").strip()
        if len(preview) > 60:
            preview = preview[:57] + "…"
        if not preview:
            preview = "(пусто)"
        
        # Get recording duration from WAV file instead of timestamp
        duration_str = ""
        if source and str(source).lower().endswith('.wav'):
            try:
                import wave
                audio_dir = self.config.get("files.audio_dir", "data/recordings")
                audio_path = os.path.join(audio_dir, os.path.basename(str(source)))
                if os.path.exists(audio_path):
                    with wave.open(audio_path, 'rb') as wf:
                        frames = wf.getnframes()
                        rate = wf.getframerate()
                        duration_sec = frames / float(rate)
                        m, s = divmod(int(duration_sec), 60)
                        duration_str = f"[{m:02d}:{s:02d}]"
            except Exception as e:
                log.warning(f"Could not read WAV duration: {e}")
        
        if not duration_str:
            # Fallback to timestamp if WAV not available
            duration_str = datetime.now().strftime("%H:%M:%S")
        
        line = duration_str
        if job_no:
            line += f" #{job_no}"
        if source:
            line += f" · {os.path.basename(str(source))}"
        line += f" — {preview}"

        item = {
            "id": self._history_seq,
            "time": duration_str,
            "text": text,
            "processing_time": processing_time,
            "job_no": job_no,
            "source": source,
            "line": line,
        }
        self.history_items.insert(0, item)
        if len(self.history_items) > 50:
            self.history_items = self.history_items[:50]
        self._refresh_history_list()
        self.history_listbox.selection_clear(0, tk.END)
        self.history_listbox.selection_set(0)
        self.history_listbox.see(0)

    def _refresh_history_list(self):
        self.history_listbox.delete(0, tk.END)
        for item in self.history_items:
            self.history_listbox.insert(tk.END, item["line"])

    def _on_history_select(self, _event=None):
        sel = self.history_listbox.curselection()
        if not sel:
            return
        item = self.history_items[sel[0]]
        self.result_text.delete(1.0, tk.END)
        self.result_text.insert(tk.END, item["text"])
        self.copy_button.config(state="normal" if item["text"].strip() else "disabled")

    def _on_history_activate(self, _event=None):
        self._on_history_select()
        text = self.result_text.get(1.0, tk.END).strip()
        if text:
            self._copy_to_clipboard()

    def _clear_history(self):
        self.history_items.clear()
        self._refresh_history_list()

    def _start_timer(self):
        def update_timer():
            start = time.time()
            while self.is_recording:
                elapsed = int(time.time() - start)
                m, s = divmod(elapsed, 60)
                try:
                    self.timer_label.config(text=f"{m:02d}:{s:02d}")
                except tk.TclError:
                    break
                time.sleep(0.2)

        threading.Thread(target=update_timer, daemon=True).start()

    def _load_audio_file(self):
        path = filedialog.askopenfilename(
            title="Аудиофайл",
            filetypes=[
                ("Аудио", "*.wav *.mp3 *.flac *.ogg *.m4a"),
                ("WAV", "*.wav"),
                ("Все файлы", "*.*"),
            ],
        )
        if not path:
            return
        self.loaded_audio_file = path
        self.current_file_label.config(text=os.path.basename(path))
        for btn in (self.play_button, self.pause_button_audio, self.stop_button_audio, self.convert_button):
            btn.config(state="normal")

    def _play_audio(self):
        if not self.loaded_audio_file:
            return
        if self.is_paused_audio:
            self._queue("resume_audio", None)
            self.is_paused_audio = False
            self.play_button.config(text="⏸")
        else:
            self._queue("play_audio", self.loaded_audio_file)
            self.is_playing_audio = True
            self.play_button.config(text="⏸")

    def _pause_audio(self):
        if not self.is_playing_audio:
            return
        self._queue("pause_audio", None)
        self.is_paused_audio = True
        self.play_button.config(text="▶")

    def _stop_audio(self):
        if not self.is_playing_audio and not self.is_paused_audio:
            return
        self._queue("stop_audio", None)
        self.is_playing_audio = False
        self.is_paused_audio = False
        self.play_button.config(text="▶")

    def _convert_audio(self):
        if self.loaded_audio_file:
            self._queue("convert_audio_file", self.loaded_audio_file)

    def _play_system_sound(self, sound_type="success"):
        """Play system sound notification.
        
        Args:
            sound_type: "success" or "error"
        """
        try:
            import winsound
            
            if sound_type == "success":
                # System asterisk sound (information)
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
            elif sound_type == "error":
                # System hand sound (error)
                winsound.MessageBeep(winsound.MB_ICONHAND)
            elif sound_type == "warning":
                # System exclamation sound
                winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            else:
                # Default beep
                winsound.MessageBeep(winsound.MB_OK)
        except Exception as e:
            # Fallback to simple beep if winsound fails
            try:
                import winsound
                winsound.Beep(1000, 200)  # 1000 Hz for 200 ms
            except Exception:
                log.warning(f"Could not play system sound: {e}")
