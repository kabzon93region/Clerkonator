# 🎤 Clerkonator

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Release](https://img.shields.io/badge/release-v1.0.4-blue)](https://github.com/kabzon93region/Clerkonator/releases)
[![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Windows](https://img.shields.io/badge/Windows-10%2F11-0078D6?logo=windows&logoColor=white)](https://www.microsoft.com/windows)
[![Whisper](https://img.shields.io/badge/faster--whisper-GPU%20%2F%20CPU-orange)](https://github.com/SYSTRAN/faster-whisper)
[![Vosk](https://img.shields.io/badge/Vosk-offline%20CPU-green)](https://alphacephei.com/vosk/)

**Десктопное приложение для преобразования речи в текст** — клиент с GUI и системным треем + STT-сервер по LAN с GPU-ускорением.

| | |
|---|---|
| **Разработчик** | [kabzon93region](https://github.com/kabzon93region) |
| **Версия** | 1.0.4 |
| **Платформа** | Windows 10/11 |
| **GitHub** | [Clerkonator](https://github.com/kabzon93region/Clerkonator) |

---

## ✨ Возможности

| Компонент | Описание |
|-----------|----------|
| **Клиент** | Запись с микрофона, пауза, горячие клавиши (глобальные), системный трей, тёмная тема |
| **Сервер** | HTTP STT-сервер по LAN, системный трей с переключением моделей, динамическая иконка статуса |
| **Распознавание** | **Vosk** (CPU, офлайн) или **faster-whisper** (GPU/CPU, ~20 языков) |
| **Управление** | REST API сервера, горячие клавиши, GUI-настройки с авторазмером |
| **Удобства** | Автокопирование в буфер, звуковые уведомления, история распознаваний |

### Горячие клавиши (по умолчанию)

| Сочетание | Действие |
|-----------|----------|
| `Ctrl+Alt+R` | Начать/остановить запись |
| `Ctrl+Alt+P` | Пауза/продолжить запись |
| `Ctrl+Alt+X` | Отменить запись |
| `Ctrl+Alt+E` | Показать/скрыть окно |

---

## 🚀 Быстрый старт

### Клиент (Windows)

```cmd
setup.cmd
run.cmd
```

### STT-сервер (GPU-машина в LAN)

```cmd
pip install -r requirements-server.txt
download_whisper_model.cmd
run_server.cmd
```

Сервер запускается в трее с иконкой. Модель по умолчанию: **large-v3-turbo** (~1.6 ГБ VRAM).

---

## ⚙️ Конфигурация

| Файл | Назначение |
|------|------------|
| `config.client.json` | Клиент: горячие клавиши, микрофон, GUI, подключение к серверу |
| `config.server.json` | Сервер: порт, GPU/CPU, модель Whisper, язык, размер очереди |

> При первом запуске — скопируйте из `.example.json` шаблонов.

---

## 📁 Структура проекта

```
Clerkonator/
├── main.py                     # Точка входа клиента
├── stt/server_app.py           # HTTP STT-сервер
├── gui/                        # Tkinter GUI (тёмная тема)
├── audio/                      # Запись/воспроизведение аудио
├── utils/                      # Hotkeys, tray, config, model catalog
├── models/                     # Vosk-модели и models/whisper/
├── scripts/                    # CMD-скрипты запуска
├── assets/                     # Иконки
├── docs/                       # Документация
├── config.client.example.json  # Шаблон конфига клиента
├── config.server.example.json  # Шаблон конфига сервера
├── requirements.txt            # Зависимости клиента
├── requirements-server.txt     # Зависимости сервера (GPU)
└── build.cmd                   # Сборка .exe для релиза
```

---

## 🛠️ Сборка .exe

Для создания автономных `.exe` файлов (без консоли, с иконкой):

```cmd
build.cmd
```

Результат: папка `release/` с `Clerkonator-Client.exe` и `Clerkonator-Server.exe`.

---

## 🔧 Технологии

| Слой | Технологии |
|------|-----------|
| GUI | Python 3.8+, Tkinter, pystray, Pillow |
| Аудио | PyAudio, pygame, winsound |
| STT | faster-whisper (GPU/CPU), Vosk (CPU офлайн) |
| Hotkeys | pynput (глобальные, layout-independent) |
| Сервер | http.server, threading, REST API |
| Сборка | PyInstaller |

---

## 🐛 Устранение неполадок

| Проблема | Решение |
|----------|---------|
| Нет распознавания | Подключите STT в настройках (сервер или локальная модель) |
| Сервер не отвечает | Проверьте IP/порт, файрвол, `run_server.cmd` на хосте |
| Whisper не скачивается | Проверьте `whisper_use_system_proxy: false` в конфиге |
| Vosk не работает | Нужна папка `models/vosk-model-ru-0.42` |
| Горячие клавиши не работают | Проверьте раскладку (EN), переустановите в настройках |

---

## 📚 Документация

- [Модели STT и скачивание](docs/user/models.md)
- [Руководство пользователя](docs/user/user_manual.md)
- [Документация (индекс)](docs/README.md)

---

## 🤖 AI-Assisted Development

Проект разработан с участием AI-агентов в качестве ассистентов программирования:

[![Qoder IDE](https://img.shields.io/badge/AI%20Agent-Qoder%20IDE-6C63FF?logo=data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTYiIGhlaWdodD0iMTYiIHZpZXdCb3g9IjAgMCAxNiAxNiIgZmlsbD0id2hpdGUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHJlY3Qgd2lkdGg9IjE2IiBoZWlnaHQ9IjE2IiByeD0iMyIvPjwvc3ZnPg==&logoColor=white)](https://qoder.ai)
[![Cursor IDE](https://img.shields.io/badge/AI%20Agent-Cursor%20IDE-000000?logo=data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTYiIGhlaWdodD0iMTYiIHZpZXdCb3g9IjAgMCAxNiAxNiIgZmlsbD0id2hpdGUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHJlY3Qgd2lkdGg9IjE2IiBoZWlnaHQ9IjE2IiByeD0iMyIvPjwvc3ZnPg==&logoColor=white)](https://cursor.com)

| IDE | Роль |
|-----|------|
| **[Qoder IDE](https://qoder.ai)** | Архитектура серверной части, системный трей, API управления, оптимизация GUI |
| **[Cursor IDE](https://cursor.com)** | Начальная архитектура, клиент-серверная модель, темная тема, базовый STT pipeline |

> Человек-разработчик отвечает за постановку задач, архитектурные решения, тестирование и финальную интеграцию. AI-агенты использовались как инструмент ускорения написания кода.

---

## 📝 Лицензия

[MIT](LICENSE) © [kabzon93region](https://github.com/kabzon93region)

---

## 💖 Поддержать проект

Разовый донат (карта РФ, СБП, ЮMoney, VK Pay):

**[DonationAlerts → kabzon93region](https://www.donationalerts.com/r/kabzon93region)**

---

## Связанные проекты

| Проект | Описание |
|--------|----------|
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | CTranslate2-based Whisper inference |
| [Vosk](https://github.com/alphacep/vosk-api) | Офлайн распознавание речи |
| [pystray](https://github.com/moses-palmer/pystray) | Системный трей для Python |

---

## Disclaimer

Не аффилирован с OpenAI, SYSTRAN, Alpha Cephei или Microsoft. Whisper™ является товарным знаком OpenAI. Используйте на свой риск.
