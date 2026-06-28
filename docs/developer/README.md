# Документация для разработчиков

## 🏗️ Архитектура проекта

### Общая структура

```
Clerkonator/
├── main.py                     # Точка входа клиента
├── stt/
│   ├── server_app.py           # HTTP STT-сервер (REST API + очередь)
│   ├── server_factory.py       # Выбор процессора (Whisper GPU / Vosk CPU)
│   ├── processor.py            # Vosk STT (CPU only)
│   ├── whisper_processor.py    # faster-whisper STT (GPU/CPU)
│   └── remote_client.py        # HTTP-клиент к удалённому серверу
├── gui/
│   ├── simple_window.py        # Главное окно GUI (Tkinter)
│   ├── settings_window.py      # Окно настроек
│   ├── dark_theme.py           # Тёмная тема
│   └── keyboard_bindings.py   # Горячие клавиши в текстовых полях
├── audio/
│   ├── recorder.py             # Запись с микрофона (PyAudio)
│   └── player.py               # Воспроизведение аудио (pygame)
├── utils/
│   ├── config.py               # Управление конфигурацией
│   ├── hotkeys.py              # Глобальные горячие клавиши (pynput)
│   ├── tray_manager.py        # Системный трей клиента
│   ├── server_tray.py          # Системный трей сервера
│   ├── app_icon.py             # Генерация иконок (PIL)
│   ├── session_logger.py       # Логирование (сессии)
│   ├── stt_recognition.py      # Параметры распознавания (язык, перевод)
│   ├── stt_model_catalog.py    # Каталог доступных моделей
│   └── whisper_downloader.py   # Скачивание моделей Whisper
├── config.client.json          # Настройки клиента
├── config.server.json          # Настройки сервера
├── requirements.txt            # Зависимости клиента
├── requirements-server.txt     # Зависимости сервера (GPU)
└── build.cmd                   # Сборка .exe (PyInstaller)
```

### Принципы архитектуры

1. **Модульность** — каждый компонент изолирован и имеет чёткую ответственность
2. **Слабая связанность** — модули взаимодействуют через интерфейсы процессоров
3. **Потокобезопасность** — общее состояние защищено блокировками

### Многопоточность

Клиент использует следующую модель потоков:

| Поток | Роль |
|-------|------|
| **Main thread** | Tkinter mainloop (GUI должен быть на главном потоке Windows) |
| **Backend thread** | Обработка сообщений из `gui_queue` |
| **Tray thread** | Иконка системного трея (pystray) |
| **Worker threads** | Загрузка модели, STT-обработка, опрос здоровья сервера |

Связь между потоками:
- **GUI → Backend**: очередь `gui_queue` (сообщения: start_recording, stop_recording, и т.д.)
- **Backend → GUI**: `window.after(0, callback)` — потокобезопасное обновление Tkinter

Сервер использует:

| Поток | Роль |
|-------|------|
| **HTTP server** | Обработка входящих запросов (http.server) |
| **Queue worker** | Последовательная обработка задач транскрипции |
| **Model load** | Фоновая загрузка модели при старте/переключении |
| **Tray tooltip** | Периодическое обновление тултипа (каждые 3 сек) |

### STT движки

| Движок | Устройство | Библиотека | Описание |
|--------|-----------|------------|----------|
| **Whisper** | GPU (CUDA) | faster-whisper | Высокая скорость, ~20 языков, нужен NVIDIA GPU |
| **Whisper** | CPU | faster-whisper | Медленнее, но работает без GPU |
| **Vosk** | CPU | vosk | Офлайн, только CPU, лёгкие модели |

Выбор движка определяется параметром `stt.server.device` в `config.server.json`:
- `"gpu"` → Whisper (GPU preferred, с fallback на CPU)
- `"cpu"` → Vosk (CPU only)

### Форматы аудио

| Операция | Формат |
|----------|--------|
| Запись с микрофона | WAV, моно, 16-bit, 16000 Hz |
| Распознавание (Vosk) | Тот же WAV (строго) |
| Распознавание (Whisper) | WAV, MP3, FLAC и др. |
| Прослушивание (pygame) | WAV, MP3, FLAC и др. |

---

## 🔧 REST API сервера

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/health` | Статус сервера, модели, очереди |
| GET | `/api/ping` | Проверка живости |
| GET | `/api/stats` | Метрики (uptime, всего задач, среднее время) |
| GET | `/api/models` | Список доступных моделей |
| GET | `/api/job/<id>` | Статус асинхронной задачи |
| POST | `/api/transcribe` | Распознать аудио (тело = WAV) |
| POST | `/api/switch-model` | Сменить модель STT |
| POST | `/api/reload` | Перезагрузить конфиг и модель |
| POST | `/api/shutdown` | Корректное завершение |

### Параметр `server.max_queue_size`

Максимальный размер очереди задач транскрипции. Настраивается в `config.server.json`:

```json
{
  "server": {
    "max_queue_size": 20
  }
}
```

По умолчанию — 20. Если очередь заполнена, новые запросы отклоняются с HTTP 503.

---

## 🧪 Тестирование

```bash
# Запуск тестов
python tests/test_app.py

# Проверка GPU-менеджера
python tests/test_gpu_manager.py

# Проверка скачивания моделей
python tests/test_model_downloader.py
```

---

## 🛠️ Разработка

### Настройка окружения

```bash
# 1. Клонирование
git clone <repository>
cd Clerkonator

# 2. Виртуальное окружение
python -m venv venv
venv\Scripts\activate

# 3. Зависимости клиента
pip install -r requirements.txt

# 4. Зависимости сервера (опционально, для GPU)
pip install -r requirements-server.txt
```

### Стандарты кодирования

1. **PEP 8** — стандарты оформления Python
2. **Docstrings** — все функции и классы документируются на английском
3. **Комментарии** — на английском, подробные, для неопытных разработчиков
4. **Логирование** — через `utils/session_logger.py` (отдельный файл на сессию)
5. **Thread safety** — общее состояние защищено `threading.Lock`

### Структура логирования

Каждый запуск приложения создаёт отдельный лог-файл в `logs/`:
```
logs/speechtotext_YYYYMMDD_HHMMSS.log
```

Формат: `HH:MM:SS | LEVEL    | message`

---

## 📦 Сборка дистрибутива

```cmd
build.cmd
```

Создаёт:
- `release/Clerkonator-Client.exe` — клиент (с иконкой микрофона)
- `release/Clerkonator-Server.exe` — сервер (с иконкой антенны)

Требования: `pip install pyinstaller`

---

## 🔄 Система версий

```bash
# Создание версии
python versions/version_manager.py create --version 1.0.5 --description "Описание" --author "Author"

# Список версий
python versions/version_manager.py list

# Восстановление версии
python versions/version_manager.py restore --version 1.0.5
```

---

## 🤝 Участие в разработке

1. Fork репозитория
2. Создайте feature branch
3. Внесите изменения
4. Обновите документацию
5. Создайте Pull Request

### Commit Message Convention

```
type(scope): description

Типы: feat, fix, docs, style, refactor, test, chore
```

Примеры:
```
feat(server): add max_queue_size to config
fix(tray): resolve blinking thread leak
docs(api): update STT processor documentation
```
