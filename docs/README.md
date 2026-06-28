# 📚 Документация Clerkonator

## 📁 Содержание

### 👤 Для пользователей
- **[Руководство пользователя](./user/user_manual.md)** — установка, настройка, использование
- **[Модели STT](./user/models.md)** — таблицы Vosk/Whisper, VRAM, скачивание

### 👨‍💻 Для разработчиков
- **[Документация разработчика](./developer/README.md)** — архитектура, API, стандарты

### ⚖️ Правовая информация
- [Лицензия MIT](./legal/LICENSE.md)
- [Авторские права](./legal/COPYRIGHT.md)
- [Коммерческое использование](./legal/COMMERCIAL_USE.md)

---

## 🚀 Быстрый старт

### Клиент (Windows)

```cmd
setup.cmd
run.cmd
```

STT при старте **не загружается** — подключите сервер или локальную модель в **⚙ Настройки**.

### STT-сервер (GPU-машина в LAN)

```cmd
pip install -r requirements-server.txt
download_whisper_model.cmd
run_server.cmd
```

Модель по умолчанию: **large-v3-turbo** (~1.6 ГБ VRAM).

---

## ⚙️ Конфигурация

| Файл | Назначение |
|------|------------|
| `config.client.json` | Клиент: горячие клавиши, микрофон, GUI, подключение к серверу |
| `config.server.json` | Сервер: порт, GPU/CPU, модель Whisper, язык, размер очереди |

> Шаблоны: `config.client.example.json`, `config.server.example.json`

### Параметр `server.max_queue_size`

Максимальное количество задач в очереди сервера (по умолчанию 20).
Если очередь заполнена, новые запросы отклоняются с ошибкой 503.

---

## 🔧 Архитектура

```
┌─────────────────┐         HTTP/LAN         ┌─────────────────────┐
│   Клиент (GUI)  │ ◄─────────────────────► │  STT-Сервер (GPU)   │
│  main.py        │    /api/transcribe        │  stt/server_app.py  │
│  Системный трей │    /api/health            │  Системный трей     │
│  Горячие клавиши│    /api/models            │  REST API управления│
└─────────────────┘                           └─────────────────────┘
```

### Модули

| Модуль | Файлы | Описание |
|--------|-------|----------|
| GUI | `gui/` | Tkinter (тёмная тема), настройки, главное окно |
| Audio | `audio/` | Запись (PyAudio), воспроизведение (pygame) |
| STT | `stt/` | Сервер, процессоры Vosk (CPU) и Whisper (GPU/CPU) |
| Utils | `utils/` | Config, hotkeys, tray, model catalog, icon |

---

## 🏗️ Сборка .exe

```cmd
build.cmd
```

Результат: `release/Clerkonator-Client.exe` и `release/Clerkonator-Server.exe`

---

## 📝 Лицензия

[MIT](./legal/LICENSE.md) © kabzon93region
