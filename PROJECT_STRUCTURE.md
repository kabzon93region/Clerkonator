# 📁 Структура проекта Clerkonator

```
Clerkonator/
│
├── main.py                     # Точка входа клиента (GUI + STT)
├── build.cmd                   # Сборка .exe (PyInstaller)
├── run.cmd                     # Быстрый запуск клиента
├── run_server.cmd              # Быстрый запуск сервера
├── run_silent.cmd              # Запуск без консоли
├── download_whisper_model.cmd  # Скачивание модели Whisper
├── setup.cmd                   # Первичная настройка venv
│
├── config.client.json          # Конфиг клиента
├── config.server.json          # Конфиг сервера
├── config.client.example.json # Шаблон конфига клиента
├── config.server.example.json # Шаблон конфига сервера
├── requirements.txt            # Зависимости клиента
├── requirements-server.txt     # Зависимости сервера (GPU)
├── version.json                # Текущая версия
├── LICENSE                     # MIT License
│
├── gui/                        # GUI-модули
│   ├── simple_window.py        # Основное окно (тёмная тема)
│   ├── settings_window.py      # Окно настроек
│   ├── dark_theme.py           # Стили Tkinter
│   ├── hotkey_capture.py       # Захват сочетания клавиш
│   └── keyboard_bindings.py   # Горячие клавиши в окне
│
├── audio/                      # Аудио-модули
│   ├── recorder.py             # Запись с микрофона (PyAudio)
│   └── player.py               # Воспроизведение (pygame)
│
├── stt/                        # STT-модули
│   ├── server_app.py           # HTTP-сервер + REST API + очередь + tray
│   ├── server_factory.py       # Фабрика процессоров (Vosk/Whisper)
│   ├── processor.py            # Vosk STT (CPU only)
│   ├── whisper_processor.py    # faster-whisper STT (GPU/CPU)
│   └── remote_client.py        # HTTP-клиент к удалённому серверу
│
├── utils/                      # Утилиты
│   ├── config.py               # Менеджер конфигурации
│   ├── hotkeys.py              # Глобальные hotkeys (pynput)
│   ├── hotkey_codec.py         # Парсинг сочетаний клавиш
│   ├── tray_manager.py         # Системный трей клиента
│   ├── server_tray.py          # Системный трей сервера
│   ├── app_icon.py             # Генерация иконок (клиент/сервер)
│   ├── stt_recognition.py      # Параметры распознавания (язык, перевод)
│   ├── stt_model_catalog.py    # Каталог локальных моделей
│   ├── whisper_downloader.py   # Скачивание моделей Whisper
│   ├── model_downloader.py     # Скачивание моделей Vosk
│   ├── session_logger.py       # Логирование
│   ├── audio_devices.py        # Список микрофонов (кодировка)
│   └── cuda_runtime.py         # CUDA DLL paths
│
├── assets/                     # Ресурсы
│   ├── app_icon.ico            # Иконка (ICO)
│   └── app_icon.png            # Иконка (PNG)
│
├── models/                     # Модели STT (не в git)
│   ├── vosk-model-ru-0.42/     # Vosk модель
│   └── whisper/                # Whisper модели
│       └── large-v3-turbo/
│
├── scripts/                    # Вспомогательные скрипты
│   ├── run.cmd
│   ├── run_server.cmd
│   ├── run_silent.cmd
│   ├── setup.cmd
│   └── _stt_venv.cmd
│
├── docs/                       # Документация
│   ├── README.md               # Индекс документации
│   ├── developer/
│   │   └── README.md           # Архитектура, API, стандарты
│   ├── user/
│   │   ├── user_manual.md      # Руководство пользователя
│   │   └── models.md           # Модели STT (таблицы, скачивание)
│   └── legal/
│       ├── LICENSE.md
│       ├── COPYRIGHT.md
│       └── COMMERCIAL_USE.md
│
├── data/                       # Данные (не в git)
│   ├── recordings/             # Аудио-записи
│   ├── transcriptions/         # Результаты распознавания
│   └── server_temp/            # Временные файлы сервера
│
├── tests/                      # Тесты
│   ├── test_app.py
│   ├── test_gpu_manager.py
│   └── test_model_downloader.py
│
├── tools/                      # Утилиты разработки
│   ├── bump_version.py
│   ├── create_release.py
│   └── save_version.py
│
├── versions/                   # Система версий
│   ├── version_manager.py
│   ├── versions.json
│   └── v1.0.x/                 # Снимки версий
│
└── logs/                       # Логи (не в git)
    └── speechtotext_YYYYMMDD_HHMMSS.log
```

## Ключевые точки входа

| Файл | Описание |
|------|----------|
| `main.py` | Клиент: GUI + запись + STT через сервер или локально |
| `stt/server_app.py` | Сервер: HTTP API + очередь + tray + управление моделями |
| `build.cmd` | Сборка .exe файлов для релиза |

## Конфигурация

| Файл | Назначение |
|------|------------|
| `config.client.json` | Клиент: горячие клавиши, микрофон, GUI, подключение к серверу, локальные модели |
| `config.server.json` | Сервер: порт, GPU/CPU, модель Whisper, язык, `server.max_queue_size` |
