#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Утилита для создания релизного архива для пользователей
Исключает модели, данные, логи и другие ненужные файлы
"""

import os
import sys
import json
import shutil
import time
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def log(message):
    """Вывод сообщения с временной меткой"""
    timestamp = time.strftime('%H:%M:%S')
    print(f"{timestamp} | {message}")
    sys.stdout.flush()

def read_version():
    """Читает текущую версию из version.json"""
    version_path = os.path.join(PROJECT_ROOT, 'version.json')
    try:
        with open(version_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('version', '1.0.0')
    except Exception as e:
        log(f"Ошибка чтения версии: {e}")
        return '1.0.0'

def create_release_archive(version, timestamp):
    """Создает релизный архив"""
    archive_name = f"Clerkonator_v{version}_{timestamp}"
    staging_dir = os.path.join(PROJECT_ROOT, f".release_staging_{timestamp}")
    
    # Очищаем staging директорию
    if os.path.exists(staging_dir):
        shutil.rmtree(staging_dir)
    os.makedirs(staging_dir)
    log(f"Создана временная папка: {staging_dir}")
    
    # Файлы и папки для включения в релиз
    include_dirs = ['audio', 'gui', 'stt', 'utils', 'docs']
    include_files = [
        '.cursorrules',
        '.editorconfig', 
        '.gitignore',
        'config.client.json',
        'config.server.json',
        'main.py',
        'PROJECT_STRUCTURE.md',
        'README.md',
        'requirements.txt',
        'run.cmd',
        'setup.cmd',
        'ЗАПУСК.md',
        'version.json'
    ]
    
    # Копируем папки
    for dirname in include_dirs:
        src_dir = os.path.join(PROJECT_ROOT, dirname)
        if os.path.isdir(src_dir):
            dst_dir = os.path.join(staging_dir, dirname)
            shutil.copytree(src_dir, dst_dir)
            log(f"Скопирована папка: {dirname}")
    
    # Копируем файлы
    for filename in include_files:
        src_file = os.path.join(PROJECT_ROOT, filename)
        if os.path.isfile(src_file):
            dst_file = os.path.join(staging_dir, filename)
            shutil.copy2(src_file, dst_file)
            log(f"Скопирован файл: {filename}")
    
    # Создаем ZIP архив
    zip_path = os.path.join(PROJECT_ROOT, f"{archive_name}.zip")
    log("Создаем ZIP архив...")
    shutil.make_archive(archive_name, 'zip', staging_dir)
    
    # Перемещаем архив в корень проекта
    if not os.path.exists(zip_path):
        shutil.move(f"{archive_name}.zip", zip_path)
    
    # Очищаем временную папку
    shutil.rmtree(staging_dir)
    log("Временная папка удалена")
    
    return zip_path

def main():
    """Основная функция"""
    try:
        log("[INFO] Начинаем создание релизного архива...")
        
        # Получаем текущую версию
        current_version = read_version()
        timestamp = time.strftime('%Y%m%d_%H%M%S')
        
        log(f"Версия: {current_version}")
        log(f"Временная метка: {timestamp}")
        
        # Создаем архив
        archive_path = create_release_archive(current_version, timestamp)
        
        # Получаем размер архива
        archive_size = os.path.getsize(archive_path) / (1024 * 1024)  # MB
        
        log(f"[OK] Релизный архив создан!")
        log(f"Путь: {archive_path}")
        log(f"Размер: {archive_size:.1f} MB")
        
    except Exception as e:
        log(f"[ERROR] Ошибка: {e}")
        return 1
    
    return 0

if __name__ == '__main__':
    os.chdir(PROJECT_ROOT)
    sys.exit(main())
