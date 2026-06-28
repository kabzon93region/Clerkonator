# -*- coding: utf-8 -*-
"""
Модуль для автоматического скачивания модели Vosk
"""

import os
import zipfile
import urllib.request
import urllib.error
from pathlib import Path
import time


class ModelDownloader:
    """Класс для скачивания и установки модели Vosk"""
    
    def __init__(self, config):
        """Инициализация загрузчика модели"""
        self.config = config
        self.model_name = "vosk-model-ru-0.42"
        self.model_url = "https://alphacephei.com/vosk/models/vosk-model-ru-0.42.zip"
        self.models_dir = Path("models")
        self.model_path = self.models_dir / self.model_name
        self.zip_path = self.models_dir / f"{self.model_name}.zip"
        
    def is_model_present(self):
        """Проверка наличия модели"""
        return self.model_path.exists() and self.model_path.is_dir()
    
    def is_archive_present(self):
        """Проверка наличия архива модели"""
        return self.zip_path.exists() and self.zip_path.is_file()
    
    def extract_archive(self):
        """Распаковка существующего архива модели"""
        try:
            print(f"EXTRACT - Распаковка архива {self.zip_path}...")
            
            # Создаем папку models если не существует
            self.models_dir.mkdir(exist_ok=True)
            
            # Распаковываем архив
            with zipfile.ZipFile(self.zip_path, 'r') as zip_ref:
                zip_ref.extractall(self.models_dir)
            
            print("OK - Архив распакован успешно")
            
            # Проверяем, что модель распаковалась правильно
            if self.is_model_present():
                print(f"OK - Модель {self.model_name} готова к использованию")
                return True
            else:
                print(f"ERROR - Модель не найдена после распаковки")
                return False
                
        except zipfile.BadZipFile as e:
            print(f"ERROR - Error архива: {e}")
            print("INFO - Возможно, файл поврежден")
            return False
        except Exception as e:
            print(f"ERROR - Неожиданная ошибка при распаковке: {e}")
            return False
    
    def download_model(self, progress_callback=None):
        """Скачивание модели Vosk"""
        try:
            print(f"DOWNLOAD - Начинаем скачивание модели {self.model_name}...")
            print(f"URL: {self.model_url}")
            print(f"PATH: {self.model_path}")
            
            # Создаем папку models если не существует
            self.models_dir.mkdir(exist_ok=True)
            
            # Скачиваем файл
            def download_progress(block_num, block_size, total_size):
                if total_size > 0:
                    downloaded = block_num * block_size
                    percent = (downloaded / total_size) * 100
                    if progress_callback:
                        progress_callback(percent)
                    else:
                        print(f"\rDOWNLOAD: {percent:.1f}% ({downloaded//1024//1024}MB/{total_size//1024//1024}MB)", end="")
            
            print("DOWNLOAD - Скачивание архива модели...")
            urllib.request.urlretrieve(
                self.model_url, 
                self.zip_path,
                reporthook=download_progress
            )
            print("\nOK - Архив скачан успешно")
            
            # Распаковываем архив
            print("EXTRACT - Распаковка архива...")
            with zipfile.ZipFile(self.zip_path, 'r') as zip_ref:
                zip_ref.extractall(self.models_dir)
            
            # Удаляем архив
            self.zip_path.unlink()
            print("CLEANUP - Архив удален")
            
            # Проверяем, что модель распаковалась правильно
            if self.is_model_present():
                print(f"OK - Модель {self.model_name} установлена успешно")
                return True
            else:
                print(f"ERROR - Модель не найдена после распаковки")
                return False
                
        except urllib.error.URLError as e:
            print(f"ERROR - Error сети при скачивании: {e}")
            print("INFO - Проверьте подключение к интернету")
            return False
        except zipfile.BadZipFile as e:
            print(f"ERROR - Error архива: {e}")
            print("INFO - Возможно, файл поврежден при скачивании")
            return False
        except Exception as e:
            print(f"ERROR - Неожиданная ошибка: {e}")
            return False
    
    def get_model_info(self):
        """Получение информации о модели"""
        if not self.is_model_present():
            return None
            
        try:
            # Проверяем размер папки модели
            total_size = sum(f.stat().st_size for f in self.model_path.rglob('*') if f.is_file())
            size_mb = total_size / (1024 * 1024)
            
            # Проверяем основные файлы
            required_files = [
                "am/final.mdl",
                "graph/HCLG.fst", 
                "graph/words.txt",
                "ivector/final.ie"
            ]
            
            missing_files = []
            for file_path in required_files:
                if not (self.model_path / file_path).exists():
                    missing_files.append(file_path)
            
            return {
                "name": self.model_name,
                "path": str(self.model_path),
                "size_mb": round(size_mb, 2),
                "complete": len(missing_files) == 0,
                "missing_files": missing_files
            }
            
        except Exception as e:
            print(f"WARNING - Error получения информации о модели: {e}")
            return None
    
    def validate_model(self):
        """Валидация модели"""
        info = self.get_model_info()
        if not info:
            return False
            
        if not info["complete"]:
            print(f"ERROR - Модель неполная. Отсутствуют файлы: {info['missing_files']}")
            return False
            
        print(f"OK - Модель валидна: {info['name']} ({info['size_mb']}MB)")
        return True
    
    def cleanup(self):
        """Очистка временных файлов"""
        try:
            if self.zip_path.exists():
                self.zip_path.unlink()
                print("CLEANUP - Временный архив удален")
        except Exception as e:
            print(f"WARNING - Error очистки: {e}")


def download_model_if_needed(config, progress_callback=None):
    """Функция для скачивания модели если она отсутствует"""
    downloader = ModelDownloader(config)
    
    # Проверяем наличие модели
    if downloader.is_model_present():
        print("OK - Модель Vosk уже установлена")
        if downloader.validate_model():
            return True
        else:
            print("WARNING - Модель повреждена, переустанавливаем...")
    
    # Проверяем наличие архива
    if downloader.is_archive_present():
        print("ARCHIVE - Найден архив модели, распаковываем...")
        success = downloader.extract_archive()
        if success:
            print("SUCCESS - Модель Vosk успешно установлена из архива!")
            return True
        else:
            print("WARNING - Не удалось распаковать архив, скачиваем заново...")
    
    # Скачиваем модель
    print("DOWNLOAD - Модель Vosk не найдена, начинаем скачивание...")
    success = downloader.download_model(progress_callback)
    
    if success:
        print("SUCCESS - Модель Vosk успешно установлена!")
        return True
    else:
        print("ERROR - Failed to install Vosk model")
        print("INFO - Попробуйте:")
        print("   1. Проверить подключение к интернету")
        print("   2. Скачать модель вручную с https://alphacephei.com/vosk/models")
        print("   3. Распаковать в папку models/")
        return False


def main():
    """Тестирование модуля"""
    from utils.config import Config
    
    config = Config()
    downloader = ModelDownloader(config)
    
    print("CHECK - Checking Vosk model...")
    
    if downloader.is_model_present():
        print("OK - Модель найдена")
        info = downloader.get_model_info()
        if info:
            print(f"INFO - Information о модели:")
            print(f"   Название: {info['name']}")
            print(f"   Размер: {info['size_mb']}MB")
            print(f"   Полная: {'Да' if info['complete'] else 'Нет'}")
    else:
        print("ERROR - Модель не найдена")
        print("DOWNLOAD - Начинаем скачивание...")
        success = downloader.download_model()
        if success:
            print("OK - Модель установлена успешно")
        else:
            print("ERROR - Error установки модели")


if __name__ == "__main__":
    main()
