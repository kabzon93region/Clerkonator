#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль логирования для Clerkonator
Использует Loguru для логирования в файл и консоль
"""

import os
import sys
from loguru import logger
from pathlib import Path


class ClerkonatorLogger:
    """Класс для настройки логирования"""
    
    def __init__(self, app_name="Clerkonator"):
        """Инициализация логгера"""
        self.app_name = app_name
        self.logs_dir = Path("logs")
        self.logs_dir.mkdir(exist_ok=True)
        
        # Удаляем стандартный обработчик loguru
        logger.remove()
        
        # Настраиваем логирование
        self._setup_logging()
    
    def _setup_logging(self):
        """Настройка логирования"""
        try:
            # Формат логов
            log_format = (
                "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
                "<level>{message}</level>"
            )
            
            # Логирование в файл (все уровни)
            log_file = self.logs_dir / f"{self.app_name.lower()}.log"
            logger.add(
                log_file,
                format=log_format,
                level="DEBUG",
                rotation="10 MB",
                retention="7 days",
                compression="zip",
                encoding="utf-8"
            )
            
            # Логирование в консоль (только INFO и выше)
            logger.add(
                sys.stdout,
                format=log_format,
                level="INFO",
                colorize=True,
                encoding="utf-8"
            )
            
            # Логирование ошибок в отдельный файл
            error_log_file = self.logs_dir / f"{self.app_name.lower()}_errors.log"
            logger.add(
                error_log_file,
                format=log_format,
                level="ERROR",
                rotation="5 MB",
                retention="30 days",
                compression="zip",
                encoding="utf-8"
            )
            
            logger.info(f"Логирование настроено для {self.app_name}")
            logger.info(f"Логи сохраняются в папку: {self.logs_dir.absolute()}")
            
        except Exception as e:
            print(f"Ошибка настройки логирования: {e}")
    
    def get_logger(self):
        """Возвращает настроенный логгер"""
        return logger
    
    def set_console_level(self, level="INFO"):
        """Устанавливает уровень логирования для консоли"""
        try:
            # Удаляем старый обработчик консоли
            logger.remove(handler_id=1)
            
            # Добавляем новый с нужным уровнем
            logger.add(
                sys.stdout,
                format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
                level=level,
                colorize=True,
                encoding="utf-8"
            )
            
            logger.info(f"Уровень логирования консоли установлен: {level}")
            
        except Exception as e:
            logger.error(f"Ошибка установки уровня логирования: {e}")
    
    def enable_debug_mode(self):
        """Включает режим отладки (DEBUG уровень для консоли)"""
        self.set_console_level("DEBUG")
        logger.debug("Режим отладки включен")
    
    def disable_console_logging(self):
        """Отключает логирование в консоль"""
        try:
            logger.remove(handler_id=1)
            logger.info("Логирование в консоль отключено")
        except Exception as e:
            logger.error(f"Ошибка отключения логирования в консоль: {e}")
    
    def get_log_files(self):
        """Возвращает список файлов логов"""
        try:
            log_files = list(self.logs_dir.glob("*.log"))
            return [str(f) for f in log_files]
        except Exception as e:
            logger.error(f"Ошибка получения списка файлов логов: {e}")
            return []
    
    def clear_old_logs(self, days=7):
        """Очищает старые логи"""
        try:
            import time
            current_time = time.time()
            cutoff_time = current_time - (days * 24 * 60 * 60)
            
            cleared_count = 0
            for log_file in self.logs_dir.glob("*.log*"):
                if log_file.stat().st_mtime < cutoff_time:
                    log_file.unlink()
                    cleared_count += 1
            
            logger.info(f"Очищено {cleared_count} старых файлов логов")
            
        except Exception as e:
            logger.error(f"Ошибка очистки старых логов: {e}")


# Глобальный экземпляр логгера
_logger_instance = None


def get_logger():
    """Возвращает глобальный экземпляр логгера"""
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = ClerkonatorLogger()
    return _logger_instance.get_logger()


def setup_logging(app_name="Clerkonator", debug_mode=False):
    """Настраивает логирование для приложения"""
    global _logger_instance
    _logger_instance = ClerkonatorLogger(app_name)
    
    if debug_mode:
        _logger_instance.enable_debug_mode()
    
    return _logger_instance.get_logger()


def main():
    """Тестирование логгера"""
    print("Тестирование системы логирования...")
    
    # Настраиваем логирование
    log = setup_logging("TestApp", debug_mode=True)
    
    # Тестируем разные уровни логирования
    log.debug("Это сообщение отладки")
    log.info("Это информационное сообщение")
    log.warning("Это предупреждение")
    log.error("Это ошибка")
    log.critical("Это критическая ошибка")
    
    # Тестируем с контекстом
    log.info("Тест завершен", extra={"test": True, "result": "success"})
    
    print("Тестирование завершено. Проверьте файлы в папке logs/")


if __name__ == "__main__":
    main()
