#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Утилита для обновления версии проекта
"""

import os
import sys
import json
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
            return json.load(f)
    except Exception as e:
        log(f"Ошибка чтения версии: {e}")
        return {'version': '1.0.0', 'last_updated': datetime.utcnow().isoformat()}

def write_version(data):
    """Записывает версию в version.json"""
    version_path = os.path.join(PROJECT_ROOT, 'version.json')
    try:
        with open(version_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log(f"Ошибка записи версии: {e}")
        raise

def increment_patch(version_str):
    """Увеличивает patch версию"""
    parts = version_str.split('.')
    if len(parts) != 3:
        return version_str + '.1'
    
    major, minor, patch = parts
    try:
        patch_i = int(patch) + 1
    except ValueError:
        patch_i = 1
    
    return f"{major}.{minor}.{patch_i}"

def main():
    """Основная функция"""
    try:
        log("[INFO] Обновляем версию проекта...")
        
        # Читаем текущую версию
        version_data = read_version()
        current_version = version_data.get('version', '1.0.0')
        
        log(f"Текущая версия: {current_version}")
        
        # Увеличиваем patch версию
        new_version = increment_patch(current_version)
        
        # Обновляем данные
        version_data['version'] = new_version
        version_data['last_updated'] = datetime.utcnow().isoformat()
        
        # Записываем новую версию
        write_version(version_data)
        
        log(f"[OK] Версия обновлена: {current_version} -> {new_version}")
        
    except Exception as e:
        log(f"[ERROR] Ошибка: {e}")
        return 1
    
    return 0

if __name__ == '__main__':
    os.chdir(PROJECT_ROOT)
    sys.exit(main())
