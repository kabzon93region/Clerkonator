# Модели распознавания речи (STT)

В проекте поддерживаются два движка: **Vosk** (CPU) и **Whisper** через faster-whisper (GPU или CPU). Выбор зависит от режима работы: локально на клиенте, на STT-сервере по LAN или оба варианта.

## Режимы работы

| Режим | Где настраивается | Движок |
|-------|-------------------|--------|
| **Сервер (LAN)** | `config.server.json` | Whisper GPU (по умолчанию) или Vosk CPU |
| **Локально (клиент)** | `config.client.json` + окно «Настройки» | Vosk или Whisper |
| **Подключение к серверу** | `config.client.json` → `stt.server.host` / `port` | Модель на сервере |

Клиент **не скачивает** модель сервера — только подключается по сети. Модель Whisper для сервера скачивается на машине, где запущен `run_server.cmd`.

---

## Модели Vosk (русский, только CPU)

Папка: `models/vosk-model-…` (распакованный архив с [alphacephei.com/vosk/models](https://alphacephei.com/vosk/models)).

| Папка | Качество | RAM | Когда использовать |
|-------|----------|-----|-------------------|
| `vosk-model-small-ru-0.22` | низкое | ~50 МБ | слабый ПК, тесты |
| `vosk-model-ru-0.22` | среднее | ~1.5 ГБ | баланс скорость/качество |
| **`vosk-model-ru-0.42`** | **лучший Vosk для RU** | ~1.8 ГБ | офлайн без GPU |

**Установка Vosk:** скачайте ZIP, распакуйте в `models/`. При локальном режиме Vosk клиент может доустановить модель автоматически при первой загрузке (если настроен путь в конфиге).

В настройках клиента модель выбирается в выпадающем списке «Локально (офлайн)».

---

## Модели Whisper (faster-whisper)

Папка по умолчанию: `models/whisper/<имя-модели>/` (внутри должен быть `model.bin`).

### Рекомендуемые для русского

| Имя в конфиге | Качество | VRAM (GPU) | Размер на диске | Комментарий |
|---------------|----------|------------|-----------------|-------------|
| `medium` | хорошее | ~1.8 ГБ | ~1.5 ГБ | быстрее large |
| **`large-v3-turbo`** или **`turbo`** | **высокое** | **~1.6 ГБ** | **~1.6 ГБ** | **по умолчанию в проекте** |
| `large-v3` или `large` | максимальное | ~3 ГБ | ~3 ГБ | медленнее, лучше на сложной речи |

### Все поддерживаемые имена

Их можно посмотреть командой:

```cmd
download_whisper_model.cmd --list
```

Полный список в коде (`utils/whisper_downloader.py`):  
`tiny`, `base`, `small`, `medium`, `large-v1`, `large-v2`, `large-v3`, `large`, `large-v3-turbo`, `turbo`, `distil-large-v2`, `distil-large-v3` и англоязычные варианты с суффиксом `.en`.

> Для русского языка используйте модели **без** суффикса `.en`.

---

## Скачивание Whisper: пошагово

Скачивальщик читает **имя модели из конфига**, затем загружает её в `models/whisper/`.

### Сервер (GPU, рекомендуется)

1. Откройте **`config.server.json`**.
2. Укажите нужную модель:

```json
{
  "stt": {
    "server": {
      "device": "gpu",
      "whisper_model": "large-v3-turbo",
      "whisper_cache_dir": "models/whisper"
    }
  }
}
```

3. Запустите скачивание (из корня проекта):

```cmd
download_whisper_model.cmd
```

Или явно:

```cmd
download_whisper_model.cmd --model large-v3-turbo
```

4. Дождитесь окончания (для `large-v3-turbo` ~1.6 ГБ, 10–30 минут в зависимости от сети).
5. Запустите сервер: `run_server.cmd`.
6. В клиенте: режим «Сервер (LAN)» → укажите IP и порт → «Подключиться».

Модель появится в `models/whisper/large-v3-turbo/`.

### Локальный Whisper на клиенте

1. Откройте **`config.client.json`**.
2. Укажите устройство и имя модели (как в настройках программы):

```json
{
  "stt": {
    "local": {
      "device": "gpu",
      "model": "large-v3-turbo"
    },
    "options": {
      "whisper_cache_dir": "models/whisper",
      "whisper_use_system_proxy": false,
      "whisper_compute_type": "float16",
      "fallback_cpu": true
    }
  }
}
```

- **Vosk:** `"device": "cpu"`, `"model": "vosk-model-ru-0.42"` (только CPU).
- **Whisper:** `"device": "cpu"` или `"gpu"`, `"model": "large-v3-turbo"` / `medium` / …

3. Скачайте модель с профилем **client**:

```cmd
download_whisper_model.cmd --profile client
```

4. В настройках клиента: «Локально» → выберите модель в списке → «Загрузить локальную модель».

> На CPU крупные модели Whisper работают **очень медленно**. Для качества без ожидания используйте сервер с GPU.

### Переопределение без правки конфига

```cmd
download_whisper_model.cmd --model large-v3
download_whisper_model.cmd --profile client --model medium
```

---

## Параметры в конфиге

### Клиент (`config.client.json`)

| Поле | Описание |
|------|----------|
| `stt.local.device` | `cpu` или `gpu` (для Whisper; Vosk всегда CPU) |
| `stt.local.model` | Имя модели: `vosk-model-ru-0.42`, `large-v3-turbo`, `medium`, … |
| `stt.options.*` | Общие настройки (кэш, прокси, float16, fallback) — для любой модели |
| `stt.remote.host` / `port` | Подключение к STT-серверу |

### Сервер (`config.server.json`)

| Параметр | Описание |
|----------|----------|
| `stt.server.whisper_model` | Имя модели Whisper |
| `stt.server.device` | `gpu` или `cpu` (cpu = Vosk) |
| `stt.server.whisper_cache_dir` | Папка `models/whisper` |

Язык распознавания: `stt.language` → `"ru"` (и в клиенте, и на сервере).

---

## Сервер: GPU vs CPU

В `config.server.json`:

```json
"device": "gpu"
```

— Whisper на видеокарте (NVIDIA + `requirements-server.txt`).

```json
"device": "cpu"
```

— Vosk на процессоре; нужна папка `models/vosk-model-ru-0.42` (путь в `stt.model_path`).

---

## Выбор модели под задачу

| Задача | Рекомендация |
|--------|--------------|
| Лучшее качество по русскому | Сервер GPU + `large-v3` или `large-v3-turbo` |
| Баланс качество/скорость на GPU | **`large-v3-turbo`** (по умолчанию) |
| Слабый ПК, офлайн | `vosk-model-ru-0.42` |
| Минимум места | `vosk-model-small-ru-0.22` или Whisper `small` |

---

## Устранение проблем

### Скачивание зависло или ошибка прокси

В конфиге сервера/клиента:

```json
"whisper_use_system_proxy": false
```

Перезапустите `download_whisper_model.cmd`.

### Модель скачана, но не видна в настройках

- Проверьте путь: `models/whisper/<имя>/model.bin`.
- Имя папки должно совпадать с `whisper_model` в конфиге.
- Перезапустите клиент или откройте настройки заново.

### Не хватает VRAM

Переключитесь на `medium` или `large-v3-turbo` вместо `large-v3`.

---

См. также: [Руководство пользователя](./user_manual.md), [README проекта](../../README.md).
