# -*- coding: utf-8 -*-
"""Pre-download faster-whisper model (server or local client)."""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.config import Config
from utils.session_logger import get_logger
from utils.whisper_downloader import ensure_whisper_model, list_whisper_models

log = get_logger()


def main():
    parser = argparse.ArgumentParser(
        description="Скачать модель Whisper в models/whisper/ (имя из конфига или --model)"
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Имя модели (например large-v3-turbo). По умолчанию — из конфига",
    )
    parser.add_argument(
        "--profile",
        choices=("server", "client"),
        default="server",
        help="Какой конфиг читать: config.server.json (по умолчанию) или config.client.json",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Показать поддерживаемые имена моделей и выйти",
    )
    args = parser.parse_args()

    if args.list:
        print("Поддерживаемые модели Whisper:")
        for name in list_whisper_models():
            print(f"  - {name}")
        return

    config = Config(profile=args.profile)
    if args.model:
        model = args.model
    elif args.profile == "client":
        from utils.client_stt_config import get_local_model_name, is_vosk_model_name

        name = get_local_model_name(config)
        model = name if not is_vosk_model_name(name) else config.get_stt_engine("whisper_model", "large-v3-turbo")
    else:
        model = config.get_stt_engine("whisper_model", "large-v3-turbo")
    cache_dir = config.get_stt_engine("whisper_cache_dir", "models/whisper")
    log.info(f"Профиль: {args.profile}, модель: {model}, папка: {cache_dir}")
    path = ensure_whisper_model(config, model)
    log.info(f"Готово: {path}")


if __name__ == "__main__":
    main()
