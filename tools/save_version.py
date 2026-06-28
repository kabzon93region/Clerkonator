#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Простая утилита для сохранения текущей версии проекта в историю
Исключает большие файлы и ненужные директории
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

def should_exclude_dir(dirname):
    """Проверяет, нужно ли исключить директорию"""
    exclude_dirs = {
        'venv', 'models', 'data', 'logs', '__pycache__', 
        '.git', '.cursor', '.agent-tools', '.mypy_cache', 
        '.pytest_cache', 'build', 'dist', 'node_modules',
        'versions'  # Исключаем саму папку versions!
    }
    return dirname in exclude_dirs

def should_exclude_file(filename):
    """Проверяет, нужно ли исключить файл"""
    exclude_files = {
        '.DS_Store', 'Thumbs.db', 'desktop.ini'
    }
    exclude_extensions = {
        '.pyc', '.pyo', '.log', '.tmp', '.temp'
    }
    
    if filename in exclude_files:
        return True
    
    for ext in exclude_extensions:
        if filename.endswith(ext):
            return True
    
    return False

def copy_project_to_history(version, timestamp):
    """Копирует проект в папку истории версий"""
    versions_dir = os.path.join(PROJECT_ROOT, 'versions')
    os.makedirs(versions_dir, exist_ok=True)
    
    target_dir = os.path.join(versions_dir, f"v{version}_{timestamp}")
    
    if os.path.exists(target_dir):
        log(f"Удаляем существующую папку: {target_dir}")
        shutil.rmtree(target_dir)
    
    os.makedirs(target_dir)
    log(f"Создаем снимок версии {version} в: {target_dir}")
    
    files_copied = 0
    dirs_copied = 0
    
    # Копируем файлы и папки
    for root, dirs, files in os.walk(PROJECT_ROOT):
        # Исключаем ненужные директории
        dirs[:] = [d for d in dirs if not should_exclude_dir(d)]
        
        # Вычисляем относительный путь
        rel_path = os.path.relpath(root, PROJECT_ROOT)
        if rel_path == '.':
            rel_path = ''
        
        # Создаем целевую директорию
        if rel_path:
            target_subdir = os.path.join(target_dir, rel_path)
            os.makedirs(target_subdir, exist_ok=True)
            dirs_copied += 1
        
        # Копируем файлы
        for filename in files:
            if should_exclude_file(filename):
                continue
            
            src_file = os.path.join(root, filename)
            if rel_path:
                dst_file = os.path.join(target_dir, rel_path, filename)
            else:
                dst_file = os.path.join(target_dir, filename)
            
            try:
                shutil.copy2(src_file, dst_file)
                files_copied += 1
            except Exception as e:
                log(f"Ошибка копирования {src_file}: {e}")
    
    log(f"Скопировано: {files_copied} файлов, {dirs_copied} папок")
    return target_dir

def main():
    """Основная функция"""
    try:
        log("[INFO] Начинаем сохранение версии в историю...")
        
        # Получаем текущую версию
        current_version = read_version()
        timestamp = time.strftime('%Y%m%d_%H%M%S')
        
        log(f"Текущая версия: {current_version}")
        log(f"Временная метка: {timestamp}")
        
        # Создаем снимок
        snapshot_path = copy_project_to_history(current_version, timestamp)
        
        log(f"[OK] Версия {current_version} успешно сохранена в историю!")
        log(f"Путь: {snapshot_path}")
        
    except Exception as e:
        log(f"[ERROR] Ошибка: {e}")
        return 1
    
    return 0

if __name__ == '__main__':
    os.chdir(PROJECT_ROOT)
    sys.exit(main())
