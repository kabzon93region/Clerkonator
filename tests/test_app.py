#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тестовый скрипт для проверки компонентов приложения
"""

import sys
import os

# Добавляем пути к модулям
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

def test_imports():
    """Тест импортов модулей"""
    print("Тестирование импортов...")
    
    try:
        from utils.config import Config
        print("OK - utils.config")
    except Exception as e:
        print(f"ОШИБКА - utils.config: {e}")
        return False
    
    try:
        from utils.clipboard import ClipboardManager
        print("OK - utils.clipboard")
    except Exception as e:
        print(f"ОШИБКА - utils.clipboard: {e}")
        return False
    
    try:
        from audio.recorder import AudioRecorder
        print("OK - audio.recorder")
    except Exception as e:
        print(f"ОШИБКА - audio.recorder: {e}")
        return False
    
    try:
        from stt.processor import STTProcessor
        print("OK - stt.processor")
    except Exception as e:
        print(f"ОШИБКА - stt.processor: {e}")
        return False
    
    try:
        from gui.main_window import MainWindow
        print("OK - gui.main_window")
    except Exception as e:
        print(f"ОШИБКА - gui.main_window: {e}")
        return False
    
    try:
        from utils.model_downloader import ModelDownloader
        print("OK - utils.model_downloader")
    except Exception as e:
        print(f"ОШИБКА - utils.model_downloader: {e}")
        return False
    
    return True

def test_config():
    """Тест конфигурации"""
    print("\nТестирование конфигурации...")
    
    try:
        from utils.config import Config
        config = Config()
        
        # Проверяем основные настройки
        sample_rate = config.get("audio.sample_rate")
        print(f"Частота дискретизации: {sample_rate}")
        
        model_path = config.get("stt.model_path")
        print(f"Путь к модели: {model_path}")
        
        # Проверяем наличие модели
        if os.path.exists(model_path):
            print("Модель Vosk найдена")
        else:
            print("Модель Vosk не найдена")
            return False
        
        return True
        
    except Exception as e:
        print(f"Ошибка конфигурации: {e}")
        return False

def test_audio_system():
    """Тест аудио системы"""
    print("\nТестирование аудио системы...")
    
    try:
        import pyaudio
        audio = pyaudio.PyAudio()
        
        # Получаем информацию о микрофоне
        device_count = audio.get_device_count()
        print(f"Найдено аудио устройств: {device_count}")
        
        # Ищем устройство ввода по умолчанию
        default_input = audio.get_default_input_device_info()
        print(f"Микрофон по умолчанию: {default_input['name']}")
        
        audio.terminate()
        return True
        
    except Exception as e:
        print(f"Ошибка аудио системы: {e}")
        return False

def test_stt_model():
    """Тест модели STT"""
    print("\nТестирование модели STT...")
    
    try:
        from vosk import Model
        from utils.config import Config
        
        config = Config()
        model_path = config.get("stt.model_path")
        
        if not os.path.exists(model_path):
            print("Модель не найдена")
            return False
        
        print("Загрузка модели...")
        model = Model(model_path)
        print("Модель Vosk загружена успешно")
        
        return True
        
    except Exception as e:
        print(f"Ошибка модели STT: {e}")
        return False

def test_model_downloader():
    """Тест модуля скачивания модели"""
    print("\nТестирование модуля скачивания модели...")
    
    try:
        from utils.model_downloader import ModelDownloader
        from utils.config import Config
        
        config = Config()
        downloader = ModelDownloader(config)
        
        # Проверяем инициализацию
        print(f"Модель: {downloader.model_name}")
        print(f"URL: {downloader.model_url}")
        print(f"Путь: {downloader.model_path}")
        
        # Проверяем наличие модели
        is_present = downloader.is_model_present()
        print(f"Модель присутствует: {'Да' if is_present else 'Нет'}")
        
        # Получаем информацию о модели
        if is_present:
            info = downloader.get_model_info()
            if info:
                print(f"Размер модели: {info['size_mb']}MB")
                print(f"Модель полная: {'Да' if info['complete'] else 'Нет'}")
        
        print("Модуль скачивания модели работает корректно")
        return True
        
    except Exception as e:
        print(f"Ошибка модуля скачивания: {e}")
        return False

def test_gpu_manager():
    """Тест модуля управления GPU"""
    print("Тестирование GPU Manager...")
    
    try:
        from utils.gpu_manager import GPUManager
        
        gpu_manager = GPUManager()
        
        # Тестируем получение информации о GPU
        gpu_info = gpu_manager.get_gpu_info()
        print(f"Информация о GPU: {gpu_info}")
        
        # Тестируем проверку Intel Iris Xe
        test_names = [
            "Intel Iris Xe Graphics",
            "NVIDIA GeForce RTX 3060",
            "Intel HD Graphics 620"
        ]
        
        for name in test_names:
            is_iris_xe = gpu_manager.is_intel_iris_xe(name)
            print(f"{name}: Intel Iris Xe = {is_iris_xe}")
        
        # Тестируем получение VRAM
        vram_info = gpu_manager.get_vram_usage()
        print(f"Информация о VRAM: {vram_info}")
        
        # Тестируем проверку возможности использования GPU
        can_use, message = gpu_manager.can_use_gpu()
        print(f"Можно использовать GPU: {can_use}")
        print(f"Сообщение: {message}")
        
        # Тестируем рекомендацию устройства
        recommendation = gpu_manager.get_recommended_device()
        print(f"Рекомендация: {recommendation}")
        
        # Тестируем полную информацию о системе
        system_info = gpu_manager.get_system_info()
        print(f"Информация о системе: {system_info}")
        
        print("GPU Manager работает корректно")
        return True
        
    except Exception as e:
        print(f"Ошибка GPU Manager: {e}")
        return False

def main():
    """Главная функция тестирования"""
    print("Запуск тестирования Clerkonator\n")
    
    tests = [
        ("Импорты модулей", test_imports),
        ("Конфигурация", test_config),
        ("Аудио система", test_audio_system),
        ("Модель STT", test_stt_model),
        ("Модуль скачивания модели", test_model_downloader),
        ("GPU Manager", test_gpu_manager)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{'='*50}")
        print(f"Тест: {test_name}")
        print('='*50)
        
        if test_func():
            passed += 1
            print(f"ПРОЙДЕН - {test_name}")
        else:
            print(f"ПРОВАЛЕН - {test_name}")
    
    print(f"\n{'='*50}")
    print(f"РЕЗУЛЬТАТ: {passed}/{total} тестов пройдено")
    print('='*50)
    
    if passed == total:
        print("Все тесты пройдены! Приложение готово к работе.")
        return True
    else:
        print("Некоторые тесты провалены. Проверьте настройки.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
