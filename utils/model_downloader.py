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

from utils.session_logger import get_logger

log = get_logger()


class ModelDownloader:
    """Класс для скачивания и установки модели Vosk"""
    
    def __init__(self, config):
        """Инициализация загрузчика модели"""
        import sys
        self.config = config
        self.model_name = "vosk-model-ru-0.42"
        self.model_url = "https://alphacephei.com/vosk/models/vosk-model-ru-0.42.zip"
        # For PyInstaller: use exe directory, otherwise use current directory
        if getattr(sys, 'frozen', False):
            base_dir = Path(os.path.dirname(sys.executable))
        else:
            base_dir = Path(".")
        self.models_dir = base_dir / "models"
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
            log.info(f"EXTRACT - Распаковка архива {self.zip_path}...")
            
            # Создаем папку models если не существует
            self.models_dir.mkdir(exist_ok=True)
            
            # Распаковываем архив
            with zipfile.ZipFile(self.zip_path, 'r') as zip_ref:
                zip_ref.extractall(self.models_dir)
            
            log.info("OK - Архив распакован успешно")
            
            # Проверяем, что модель распаковалась правильно
            if self.is_model_present():
                log.info(f"OK - Модель {self.model_name} готова к использованию")
                return True
            else:
                log.error(f"ERROR - Модель не найдена после распаковки")
                return False
                
        except zipfile.BadZipFile as e:
            log.error(f"ERROR - Ошибка архива: {e}")
            log.info("INFO - Возможно, файл поврежден")
            return False
        except Exception as e:
            log.error(f"ERROR - Неожиданная ошибка при распаковке: {e}")
            return False
    
    def download_model(self, progress_callback=None, max_retries=5, connect_timeout=5):
        """Скачивание модели Vosk с использованием httpx.
        
        Args:
            progress_callback: Optional callback(percent)
            max_retries: Number of retry attempts on connection failure
            connect_timeout: Seconds to wait for connection/first byte
        """
        import httpx
        
        for attempt in range(1, max_retries + 1):
            try:
                if attempt == 1:
                    log.info(f"DOWNLOAD - Начинаем скачивание модели {self.model_name}...")
                    log.info(f"URL: {self.model_url}")
                    log.info(f"PATH: {self.model_path}")
                else:
                    log.info(f"DOWNLOAD - Попытка {attempt}/{max_retries}...")
                
                # Удаляем пустой файл если существует
                if self.zip_path.exists():
                    self.zip_path.unlink()
                
                # Создаем папку models если не существует
                self.models_dir.mkdir(exist_ok=True)
                
                log.info(f"DOWNLOAD - Скачивание архива через httpx (timeout={connect_timeout}s)...")
                
                got_data = False
                with httpx.Client(follow_redirects=True, timeout=httpx.Timeout(connect_timeout, read=300, write=300, pool=connect_timeout)) as client:
                    with client.stream("GET", self.model_url) as response:
                        response.raise_for_status()
                        total_size = int(response.headers.get('content-length', 0))
                        downloaded = 0
                        last_log_time = 0
                        
                        with open(self.zip_path, 'wb') as f:
                            for chunk in response.iter_bytes(chunk_size=8192):
                                f.write(chunk)
                                downloaded += len(chunk)
                                got_data = True
                                
                                if total_size > 0:
                                    percent = (downloaded / total_size) * 100
                                    if progress_callback:
                                        progress_callback(percent)
                                    
                                    current_time = time.time()
                                    if current_time - last_log_time >= 5:
                                        mb_downloaded = downloaded // (1024 * 1024)
                                        mb_total = total_size // (1024 * 1024)
                                        log.info(f"DOWNLOAD: {percent:.1f}% ({mb_downloaded}MB/{mb_total}MB)")
                                        last_log_time = current_time
                
                if not got_data:
                    log.warning(f"DOWNLOAD - Нет данных, попытка {attempt}/{max_retries}")
                    if self.zip_path.exists():
                        self.zip_path.unlink()
                    if attempt < max_retries:
                        time.sleep(2)
                        continue
                    break
                
                log.info("OK - Архив скачан успешно")
                
                # Проверяем размер скачанного файла
                zip_size = self.zip_path.stat().st_size
                if zip_size < 1000:
                    log.error(f"Downloaded file too small: {zip_size} bytes")
                    self.zip_path.unlink()
                    if attempt < max_retries:
                        time.sleep(2)
                        continue
                    break
                
                log.info(f"Downloaded size: {zip_size // (1024*1024)} MB")
                
                # Распаковываем архив
                log.info("EXTRACT - Распаковка архива...")
                with zipfile.ZipFile(self.zip_path, 'r') as zip_ref:
                    zip_ref.extractall(self.models_dir)
                
                self.zip_path.unlink()
                log.info("CLEANUP - Архив удален")
                
                if self.is_model_present():
                    log.info(f"OK - Модель {self.model_name} установлена успешно")
                    return True
                else:
                    log.error(f"ERROR - Модель не найдена после распаковки")
                    return False
                    
            except (httpx.ConnectTimeout, httpx.ReadTimeout) as e:
                log.warning(f"DOWNLOAD - Таймаут соединения (попытка {attempt}/{max_retries}): {e}")
                if self.zip_path.exists():
                    self.zip_path.unlink()
                if attempt < max_retries:
                    time.sleep(2)
                    continue
            except httpx.HTTPError as e:
                log.warning(f"DOWNLOAD - Ошибка HTTP (попытка {attempt}/{max_retries}): {e}")
                if self.zip_path.exists():
                    self.zip_path.unlink()
                if attempt < max_retries:
                    time.sleep(2)
                    continue
            except zipfile.BadZipFile as e:
                log.error(f"ERROR - Ошибка архива: {e}")
                return False
            except Exception as e:
                log.warning(f"DOWNLOAD - Ошибка (попытка {attempt}/{max_retries}): {e}")
                if self.zip_path.exists():
                    self.zip_path.unlink()
                if attempt < max_retries:
                    time.sleep(2)
                    continue
        
        log.error(f"ERROR - Не удалось скачать модель после {max_retries} попыток")
        log.error(f"Скачайте вручную: {self.model_url}")
        log.error(f"Распакуйте в: {self.model_path}")
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
            log.warning(f"WARNING - Ошибка получения информации о модели: {e}")
            return None
    
    def validate_model(self):
        """Валидация модели"""
        info = self.get_model_info()
        if not info:
            return False
            
        if not info["complete"]:
            log.error(f"ERROR - Модель неполная. Отсутствуют файлы: {info['missing_files']}")
            return False
            
        log.info(f"OK - Модель валидна: {info['name']} ({info['size_mb']}MB)")
        return True
    
    def cleanup(self):
        """Очистка временных файлов"""
        try:
            if self.zip_path.exists():
                self.zip_path.unlink()
                log.info("CLEANUP - Временный архив удален")
        except Exception as e:
            log.warning(f"WARNING - Ошибка очистки: {e}")


def download_model_if_needed(config, progress_callback=None):
    """Функция для скачивания модели если она отсутствует.
    
    Returns:
        True if model is ready, False otherwise.
    """
    downloader = ModelDownloader(config)
    
    # Проверяем наличие модели
    if downloader.is_model_present():
        log.info("OK - Модель Vosk уже установлена")
        if downloader.validate_model():
            return True
        else:
            log.warning("WARNING - Модель повреждена, переустанавливаем...")
    
    # Проверяем наличие архива
    if downloader.is_archive_present():
        log.info("ARCHIVE - Найден архив модели, распаковываем...")
        success = downloader.extract_archive()
        if success:
            log.info("SUCCESS - Модель Vosk успешно установлена из архива!")
            return True
        else:
            log.warning("WARNING - Не удалось распаковать архив, скачиваем заново...")
    
    # Скачиваем модель
    log.info("DOWNLOAD - Модель Vosk не найдена, начинаем скачивание...")
    success = downloader.download_model(progress_callback)
    
    if success:
        log.info("SUCCESS - Модель Vosk успешно установлена!")
        return True
    else:
        log.error("ERROR - Не удалось установить модель Vosk")
        log.error(f"Скачайте вручную: {downloader.model_url}")
        log.error(f"Распакуйте в: {downloader.model_path}")
        return False


def get_manual_download_info(config):
    """Get manual download URL and path for user instructions."""
    downloader = ModelDownloader(config)
    return {
        "url": downloader.model_url,
        "path": str(downloader.model_path),
    }


def main():
    """Тестирование модуля"""
    from utils.config import Config
    
    config = Config()
    downloader = ModelDownloader(config)
    
    log.info("CHECK - Checking Vosk model...")
    
    if downloader.is_model_present():
        log.info("OK - Модель найдена")
        info = downloader.get_model_info()
        if info:
            log.info(f"INFO - Информация о модели:")
            log.info(f"   Название: {info['name']}")
            log.info(f"   Размер: {info['size_mb']}MB")
            log.info(f"   Полная: {'Да' if info['complete'] else 'Нет'}")
    else:
        log.error("ERROR - Модель не найдена")
        log.info("DOWNLOAD - Начинаем скачивание...")
        success = downloader.download_model()
        if success:
            log.info("OK - Модель установлена успешно")
        else:
            log.error("ERROR - Ошибка установки модели")


if __name__ == "__main__":
    main()
