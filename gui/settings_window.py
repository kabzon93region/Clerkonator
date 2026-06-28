# -*- coding: utf-8 -*-
"""Backend settings window."""

import tkinter as tk
from tkinter import ttk, messagebox

from gui.dark_theme import apply_dark_theme, UI_FONT, COLORS, style_listbox
from gui.hotkey_capture import HotkeyCapture
from gui.keyboard_bindings import bind_text_shortcuts
from utils.audio_devices import list_input_devices
from utils.hotkey_codec import normalize_hotkey_spec
from utils.session_logger import get_logger
from utils.stt_recognition import (
    SOURCE_LANGUAGE_CHOICES,
    TARGET_LANGUAGE_CHOICES,
    get_recognition_config,
)
from utils.client_stt_config import (
    apply_model_to_config,
    get_local_device,
    get_local_model_name,
    get_remote_host,
    get_remote_port,
    get_remote_timeout,
    list_models_for_device,
    model_info_text,
    resolve_local_model,
    set_local_selection,
)

log = get_logger()


class BackendSettingsWindow:
    """Modal settings dialog for backend parameters."""

    def __init__(self, parent: tk.Tk, config, app_instance=None, on_save=None):
        self.config = config
        self.app_instance = app_instance
        self.on_save = on_save
        self._devices = list_input_devices()
        self._device_map = {label: idx for idx, label in self._devices}

        self.window = tk.Toplevel(parent)
        self.window.title("Настройки")
        self.window.minsize(700, 400)
        self.window.resizable(True, True)
        self.window.transient(parent)
        self.window.grab_set()

        self.colors = apply_dark_theme(self.window)
        self._build_ui()
        self._load_values()
        self._update_stt_status_label()
        self._fit_window_size(center=True)

        self.window.protocol("WM_DELETE_WINDOW", self._on_cancel)

    def _build_ui(self):
        """Build two-column settings layout."""
        pad = {"padx": 8, "pady": 3}
        
        # Main container
        main_frame = ttk.Frame(self.window, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Two-column area
        columns_frame = ttk.Frame(main_frame)
        columns_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create two-column layout
        left_column = ttk.Frame(columns_frame)
        left_column.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        right_column = ttk.Frame(columns_frame)
        right_column.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        # === LEFT COLUMN: STT Settings ===
        ttk.Label(left_column, text="Распознавание (STT)", style="Header.TLabel").pack(anchor=tk.W, pady=(0, 6))
        
        self.stt_status_var = tk.StringVar(value="Не подключено")
        ttk.Label(left_column, textvariable=self.stt_status_var, style="Muted.TLabel").pack(anchor=tk.W, **pad)
        
        # Mode selection
        mode_frame = ttk.Frame(left_column)
        mode_frame.pack(fill=tk.X, **pad)
        ttk.Label(mode_frame, text="Режим:").pack(side=tk.LEFT, padx=(0, 6))
        self.mode_var = tk.StringVar(value="remote")
        ttk.Radiobutton(mode_frame, text="Сервер (LAN)", variable=self.mode_var, value="remote", command=self._on_mode_change).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Radiobutton(mode_frame, text="Локально", variable=self.mode_var, value="local", command=self._on_mode_change).pack(side=tk.LEFT)
        
        # Recognition frame (language & translation)
        self.recognition_frame = ttk.LabelFrame(left_column, text="Язык и перевод", padding=(6, 4))
        self.recognition_frame.pack(fill=tk.X, **pad)
        
        ttk.Label(self.recognition_frame, text="Язык речи:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.source_lang_var = tk.StringVar(value="ru")
        source_codes = [code for code, _ in SOURCE_LANGUAGE_CHOICES]
        self.source_lang_combo = ttk.Combobox(self.recognition_frame, textvariable=self.source_lang_var, values=source_codes, state="readonly", width=10)
        self.source_lang_combo.grid(row=0, column=1, sticky=tk.W, padx=(6, 0))
        
        self.translate_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(self.recognition_frame, text="Переводить текст", variable=self.translate_var, command=self._on_translate_toggle).grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=(3, 2))
        
        ttk.Label(self.recognition_frame, text="Перевод на:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.target_lang_var = tk.StringVar(value="en")
        target_codes = [code for code, _ in TARGET_LANGUAGE_CHOICES]
        self.target_lang_combo = ttk.Combobox(self.recognition_frame, textvariable=self.target_lang_var, values=target_codes, state="readonly", width=10)
        self.target_lang_combo.grid(row=2, column=1, sticky=tk.W, padx=(6, 0))
        
        self.translate_hint_var = tk.StringVar()
        ttk.Label(self.recognition_frame, textvariable=self.translate_hint_var, style="Muted.TLabel", wraplength=300, justify=tk.LEFT).grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=(2, 0))
        self.recognition_frame.columnconfigure(1, weight=1)
        
        # Server frame
        self.server_frame = ttk.LabelFrame(left_column, text="Сервер (LAN)", padding=(6, 4))
        # server_frame is managed by _on_mode_change (pack/pack_forget)
        
        ttk.Label(self.server_frame, text="IP:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.host_var = tk.StringVar()
        self.host_entry = ttk.Entry(self.server_frame, textvariable=self.host_var, width=20)
        self.host_entry.grid(row=0, column=1, sticky=tk.W, padx=(6, 0))
        bind_text_shortcuts(self.host_entry)
        
        ttk.Label(self.server_frame, text="Порт:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.port_var = tk.StringVar(value="8765")
        self.port_entry = ttk.Entry(self.server_frame, textvariable=self.port_var, width=8)
        self.port_entry.grid(row=1, column=1, sticky=tk.W, padx=(6, 0))
        bind_text_shortcuts(self.port_entry)
        
        self.connect_btn = ttk.Button(self.server_frame, text="Подключиться", style="Accent.TButton", command=self._connect_server)
        self.connect_btn.grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=(4, 0))
        
        # Local frame
        self.local_frame = ttk.LabelFrame(left_column, text="Локальная модель", padding=(6, 4))
        # local_frame is managed by _on_mode_change (pack/pack_forget)
        
        ttk.Label(self.local_frame, text="Устройство:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.local_device_var = tk.StringVar(value="cpu")
        local_dev_frame = ttk.Frame(self.local_frame)
        local_dev_frame.grid(row=0, column=1, sticky=tk.W, padx=(6, 0))
        ttk.Radiobutton(local_dev_frame, text="CPU", variable=self.local_device_var, value="cpu", command=self._on_local_device_change).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Radiobutton(local_dev_frame, text="GPU", variable=self.local_device_var, value="gpu", command=self._on_local_device_change).pack(side=tk.LEFT)
        
        ttk.Label(self.local_frame, text="Модель:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.model_var = tk.StringVar()
        self.model_combo = ttk.Combobox(self.local_frame, textvariable=self.model_var, values=[], state="readonly", width=28)
        self.model_combo.grid(row=1, column=1, sticky=tk.EW, padx=(6, 0))
        self.model_combo.bind("<<ComboboxSelected>>", self._on_model_selected)
        self.model_combo.bind("<<ComboboxOpened>>", lambda _e: self._fix_combobox_list_font(self.model_combo))
        
        self.model_info_var = tk.StringVar(value="")
        ttk.Label(self.local_frame, textvariable=self.model_info_var, style="Muted.TLabel", wraplength=300, justify=tk.LEFT).grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=(2, 0))
        
        self.local_init_btn = ttk.Button(self.local_frame, text="Загрузить модель", style="Accent.TButton", command=self._init_local)
        self.local_init_btn.grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=(4, 0))
        self.local_frame.columnconfigure(1, weight=1)
        
        ttk.Button(left_column, text="Отключить STT", command=self._disconnect_stt).pack(anchor=tk.W, **pad)
        
        # === RIGHT COLUMN: Audio, Hotkeys, Behavior ===
        # Audio settings
        ttk.Label(right_column, text="Аудио", style="Header.TLabel").pack(anchor=tk.W, pady=(0, 6))
        
        ttk.Label(right_column, text="Микрофон:").pack(anchor=tk.W, **pad)
        self.device_var = tk.StringVar()
        device_labels = [label for _, label in self._devices]
        self.device_combo = ttk.Combobox(right_column, textvariable=self.device_var, values=device_labels, state="readonly", width=30)
        self.device_combo.pack(fill=tk.X, padx=8)
        self.device_combo.bind("<<ComboboxOpened>>", lambda _e: self._fix_combobox_list_font(self.device_combo))
        
        audio_params_frame = ttk.Frame(right_column)
        audio_params_frame.pack(fill=tk.X, **pad)
        ttk.Label(audio_params_frame, text="Частота:").pack(side=tk.LEFT, padx=(0, 6))
        self.sample_rate_var = tk.StringVar(value="16000")
        ttk.Label(audio_params_frame, textvariable=self.sample_rate_var, style="Muted.TLabel").pack(side=tk.LEFT, padx=(0, 12))
        ttk.Label(audio_params_frame, text="Буфер:").pack(side=tk.LEFT, padx=(0, 6))
        self.chunk_var = tk.StringVar()
        chunk_spin = ttk.Spinbox(audio_params_frame, from_=512, to=8192, increment=512, textvariable=self.chunk_var, width=8)
        chunk_spin.pack(side=tk.LEFT)
        
        ttk.Separator(right_column, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)
        
        # Hotkeys
        ttk.Label(right_column, text="Горячие клавиши", style="Header.TLabel").pack(anchor=tk.W, pady=(0, 6))
        
        hotkey_frame = ttk.Frame(right_column)
        hotkey_frame.pack(fill=tk.X, padx=8)
        
        ttk.Label(hotkey_frame, text="Показать окно:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.hotkey_show = HotkeyCapture(hotkey_frame)
        self.hotkey_show.grid(row=0, column=1, sticky=tk.EW, padx=(6, 0), pady=2)
        
        ttk.Label(hotkey_frame, text="Запись/Готово:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.hotkey_record = HotkeyCapture(hotkey_frame)
        self.hotkey_record.grid(row=1, column=1, sticky=tk.EW, padx=(6, 0), pady=2)
        hotkey_frame.columnconfigure(1, weight=1)
        
        ttk.Label(right_column, text="Нажмите «Изменить…» и зажмите клавиши", style="Muted.TLabel", wraplength=280, justify=tk.LEFT).pack(anchor=tk.W, padx=8, pady=(2, 0))
        
        ttk.Separator(right_column, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)
        
        # Behavior
        ttk.Label(right_column, text="Поведение", style="Header.TLabel").pack(anchor=tk.W, pady=(0, 6))
        
        self.autocopy_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(right_column, text="Копировать результат в буфер", variable=self.autocopy_var).pack(anchor=tk.W, **pad)
        
        self.always_on_top_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(right_column, text="Окно поверх других", variable=self.always_on_top_var).pack(anchor=tk.W, **pad)
        
        ttk.Label(right_column, text="STT при запуске не загружается.\nПодключитесь к серверу или загрузите модель.", style="Muted.TLabel", justify=tk.LEFT, wraplength=280).pack(anchor=tk.W, padx=8, pady=(4, 0))
        
        # Buttons at bottom (centered, full width)
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(10, 0))
        
        # Center buttons by using pack with side=LEFT and anchor='center'
        btn_inner = ttk.Frame(btn_frame)
        btn_inner.pack(anchor='center')
        
        ttk.Button(btn_inner, text="Сохранить", style="Accent.TButton", command=self._on_save).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(btn_inner, text="Закрыть", command=self._on_cancel).pack(side=tk.LEFT)
        
        self._update_translate_controls()
        self._on_mode_change()

    def _save_recognition_config(self):
        self.config.set("stt.recognition.source_language", self.source_lang_var.get().strip())
        self.config.set("stt.recognition.translate", self.translate_var.get())
        self.config.set("stt.recognition.target_language", self.target_lang_var.get().strip())

    def _on_translate_toggle(self):
        self._update_translate_controls()
        self._fit_window_size()

    def _update_translate_controls(self):
        enabled = self.translate_var.get()
        state = "readonly" if enabled else "disabled"
        self.target_lang_combo.configure(state=state)
        if enabled:
            self.translate_hint_var.set(
                "Whisper переводит только на английский. Речь распознаётся на выбранном языке."
            )
        else:
            self.translate_hint_var.set(
                "По умолчанию: текст на языке речи (русский — без перевода). Английские вставки сохраняются."
            )

    def _fit_window_size(self, center=False):
        """Resize dialog to fit content with auto-sizing."""
        self.window.update_idletasks()
        width = max(700, self.window.winfo_reqwidth() + 20)
        height = min(self.window.winfo_reqheight() + 20, int(self.window.winfo_screenheight() * 0.9))

        fitted = getattr(self, "_fitted_size", None)
        if fitted and fitted == (width, height) and not center:
            return
        self._fitted_size = (width, height)
        
        if center or self.window.winfo_x() < 0:
            parent = self.window.master
            parent.update_idletasks()
            px = parent.winfo_rootx()
            py = parent.winfo_rooty()
            pw = parent.winfo_width()
            ph = parent.winfo_height()
            x = px + max(0, (pw - width) // 2)
            y = py + max(0, (ph - height) // 2)
        else:
            x = self.window.winfo_x()
            y = self.window.winfo_y()
            sw = self.window.winfo_screenwidth()
            sh = self.window.winfo_screenheight()
            if x + width > sw:
                x = max(0, sw - width)
            if y + height > sh:
                y = max(0, sh - height)

        self.window.geometry(f"{width}x{height}+{x}+{y}")

    def _refresh_model_list(self):
        device = self.local_device_var.get() if hasattr(self, "local_device_var") else "cpu"
        names = list_models_for_device(device)
        self.model_combo["values"] = names if names else ["large-v3-turbo"]
        current = self.model_var.get()
        if current not in names and names:
            self.model_var.set(names[0])

    def _on_local_device_change(self):
        self._refresh_model_list()
        self._on_model_selected()
        self._fit_window_size()

    def _get_selected_model(self):
        device = self.local_device_var.get()
        model = self.model_var.get().strip()
        if not model:
            return None
        set_local_selection(self.config, device, model)
        return resolve_local_model(self.config)

    def _on_model_selected(self, _event=None):
        model = self._get_selected_model()
        if model:
            self.model_info_var.set(model.info_text)
            apply_model_to_config(self.config, self.local_device_var.get(), self.model_var.get())
        else:
            self.model_info_var.set("Укажите имя модели из документации")
        self._fit_window_size()

    def _on_mode_change(self):
        mode = self.mode_var.get()
        if mode == "remote":
            self.server_frame.pack(fill=tk.X, padx=8, pady=3)
            self.local_frame.pack_forget()
        else:
            self.server_frame.pack_forget()
            self.local_frame.pack(fill=tk.X, padx=8, pady=3)
            self._refresh_model_list()
            self._select_saved_model()
        self._fit_window_size()

    def _select_saved_model(self):
        device = get_local_device(self.config)
        self.local_device_var.set(device)
        self._refresh_model_list()
        name = get_local_model_name(self.config)
        values = list(self.model_combo["values"])
        if name in values:
            self.model_var.set(name)
        elif values:
            self.model_var.set(values[0])
        self.model_info_var.set(model_info_text(self.config) or "Скачайте модель: download_whisper_model.cmd")

    def _update_stt_status_label(self):
        if not self.app_instance:
            self.stt_status_var.set("Не подключено")
            self._fit_window_size()
            return
        if getattr(self.app_instance, "stt_connecting", False):
            self.stt_status_var.set("Подключение…")
            self._fit_window_size()
            return
        if self.app_instance._is_stt_ready():
            if self.app_instance.stt_mode == "remote" and hasattr(self.app_instance.stt_processor, "get_status_text"):
                self.stt_status_var.set(self.app_instance.stt_processor.get_status_text())
            else:
                label = self.app_instance._stt_mode_label()
                self.stt_status_var.set(f"Готово ({label})")
        else:
            self.stt_status_var.set("Не подключено")
        self._fit_window_size()

    def _queue(self, msg_type, data=None):
        if self.app_instance:
            self.app_instance.gui_queue.put((msg_type, data))
        self.window.after(500, self._update_stt_status_label)

    def _connect_server(self):
        try:
            host = self.host_var.get().strip()
            port = int(self.port_var.get().strip())
            if not host:
                messagebox.showerror("Ошибка", "Укажите IP-адрес сервера", parent=self.window)
                return
            self.config.set("stt.remote.host", host)
            self.config.set("stt.remote.port", port)
            self.config.set("stt.mode", "remote")
            self._save_recognition_config()
            self._queue("connect_remote_stt", {"host": host, "port": port})
            self.stt_status_var.set(f"Подключение к {host}:{port}…")
        except ValueError:
            messagebox.showerror("Ошибка", "Некорректный порт", parent=self.window)

    def _init_local(self):
        model = self._get_selected_model()
        if not model:
            messagebox.showerror(
                "Ошибка",
                "Нет доступных моделей.\nПапка models\\ пуста или модель не распознана.",
                parent=self.window,
            )
            return
        apply_model_to_config(self.config, self.local_device_var.get(), self.model_var.get())
        self._save_recognition_config()
        self.config.set("stt.mode", "local")
        self._queue("connect_local_stt")
        self.stt_status_var.set(f"Загрузка: {model.title}…")

    def _disconnect_stt(self):
        self._queue("disconnect_stt")
        self.stt_status_var.set("Не подключено")

    def _fix_combobox_list_font(self, combo):
        try:
            popdown = combo.tk.call("ttk::combobox::PopdownWindow", combo)
            listbox = combo.nametowidget(f"{popdown}.f.l")
            style_listbox(listbox, self.colors)
        except (tk.TclError, KeyError, AttributeError):
            pass

    def _load_values(self):
        idx = self.config.get("audio.input_device_index", -1)
        label = next((lbl for i, lbl in self._devices if i == idx), self._devices[0][1])
        self.device_var.set(label)
        self.chunk_var.set(str(self.config.get("audio.chunk_size", 4096)))
        rec = get_recognition_config(self.config)
        self.source_lang_var.set(rec["source_language"])
        self.translate_var.set(rec["translate"])
        self.target_lang_var.set(rec["target_language"])
        self._update_translate_controls()
        self.host_var.set(get_remote_host(self.config))
        self.port_var.set(str(get_remote_port(self.config)))
        self.autocopy_var.set(self.config.get("gui.auto_copy", True))
        self.always_on_top_var.set(self.config.get("gui.always_on_top", False))
        self.hotkey_show.set_value(self.config.get("hotkeys.show_window", "ctrl+shift+s"))
        self.hotkey_record.set_value(self.config.get("hotkeys.record_toggle", "ctrl+shift+r"))

        saved_mode = self.config.get("stt.mode", "none")
        if saved_mode == "local":
            self.mode_var.set("local")
        else:
            self.mode_var.set("remote")
        self._select_saved_model()

    def _on_save(self):
        try:
            device_label = self.device_var.get()
            device_index = self._device_map.get(device_label, -1)
            chunk = int(self.chunk_var.get())

            model = self._get_selected_model()
            if model:
                apply_model_to_config(self.config, self.local_device_var.get(), self.model_var.get())

            self.config.set("audio.input_device_index", device_index)
            self.config.set("audio.chunk_size", chunk)
            self._save_recognition_config()
            self.config.set("stt.remote.host", self.host_var.get().strip())
            self.config.set("stt.remote.port", int(self.port_var.get().strip()))
            self.config.set("gui.auto_copy", self.autocopy_var.get())
            self.config.set("gui.always_on_top", self.always_on_top_var.get())

            show_hk = normalize_hotkey_spec(self.hotkey_show.get_value())
            record_hk = normalize_hotkey_spec(self.hotkey_record.get_value())
            self.config.set("hotkeys.show_window", show_hk)
            self.config.set("hotkeys.record_toggle", record_hk)

            if self.on_save:
                self.on_save()

            log.info("Backend settings saved")
            messagebox.showinfo("Сохранено", "Настройки сохранены", parent=self.window)
        except ValueError as e:
            messagebox.showerror("Ошибка", str(e), parent=self.window)
        except Exception as e:
            log.error(f"Settings save error: {e}")
            messagebox.showerror("Ошибка", str(e), parent=self.window)

    def _on_cancel(self):
        self.window.destroy()

    def show(self):
        self.window.wait_window()
