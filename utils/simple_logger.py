#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple logging module for Clerkonator
Uses standard Python library for logging to file and console
"""

import os
import sys
import logging
from pathlib import Path
from datetime import datetime


class SimpleLogger:
    """Упрощенный класс для логирования"""
    
    def __init__(self, app_name="Clerkonator"):
        """Инициализация логгера"""
        self.app_name = app_name
        self.logs_dir = Path("logs")
        self.logs_dir.mkdir(exist_ok=True)
        
        # Создаем логгер
        self.logger = logging.getLogger(app_name)
        self.logger.setLevel(logging.DEBUG)
        
        # Очищаем существующие обработчики
        self.logger.handlers.clear()
        
        # Настраиваем логирование
        self._setup_logging()
    
    def _setup_logging(self):
        """Настройка логирования"""
        try:
            # Формат логов
            log_format = logging.Formatter(
                '%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            
            # Логирование в файл (все уровни)
            log_file = self.logs_dir / f"{self.app_name.lower()}.log"
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(log_format)
            self.logger.addHandler(file_handler)
            
            # Логирование в консоль (только INFO и выше)
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.INFO)
            console_formatter = logging.Formatter(
                '%(asctime)s | %(levelname)-8s | %(message)s',
                datefmt='%H:%M:%S'
            )
            console_handler.setFormatter(console_formatter)
            self.logger.addHandler(console_handler)
            
            # Логирование ошибок в отдельный файл
            error_log_file = self.logs_dir / f"{self.app_name.lower()}_errors.log"
            error_handler = logging.FileHandler(error_log_file, encoding='utf-8')
            error_handler.setLevel(logging.ERROR)
            error_handler.setFormatter(log_format)
            self.logger.addHandler(error_handler)
            
            self.logger.info(f"Логирование настроено для {self.app_name}")
            self.logger.info(f"Логи сохраняются в папку: {self.logs_dir.absolute()}")
            
        except Exception as e:
            print(f"Error настройки логирования: {e}")
    
    def debug(self, message):
        """Логирование отладочного сообщения"""
        self.logger.debug(message)
    
    def info(self, message):
        """Логирование информационного сообщения"""
        self.logger.info(message)
    
    def warning(self, message):
        """Логирование предупреждения"""
        self.logger.warning(message)
    
    def error(self, message):
        """Логирование ошибки"""
        self.logger.error(message)
    
    def critical(self, message):
        """Логирование критической ошибки"""
        self.logger.critical(message)
    
    def set_console_level(self, level="INFO"):
        """Устанавливает уровень логирования для консоли"""
        try:
            # Находим обработчик консоли и меняем его уровень
            for handler in self.logger.handlers:
                if isinstance(handler, logging.StreamHandler) and handler.stream == sys.stdout:
                    handler.setLevel(getattr(logging, level.upper()))
                    break
            
            self.logger.info(f"Уровень логирования консоли установлен: {level}")
            
        except Exception as e:
            self.logger.error(f"Error установки уровня логирования: {e}")
    
    def enable_debug_mode(self):
        """Включает режим отладки (DEBUG уровень для консоли)"""
        self.set_console_level("DEBUG")
        self.debug("Режим отладки включен")
    
    def disable_console_logging(self):
        """Отключает логирование в консоль"""
        try:
            # Удаляем обработчик консоли
            for handler in self.logger.handlers[:]:
                if isinstance(handler, logging.StreamHandler) and handler.stream == sys.stdout:
                    self.logger.removeHandler(handler)
                    break
            
            self.logger.info("Логирование в консоль отключено")
        except Exception as e:
            self.logger.error(f"Error отключения логирования в консоль: {e}")


# Глобальный экземпляр логгера
_logger_instance = None


def get_logger():
    """Возвращает глобальный экземпляр логгера"""
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = SimpleLogger()
    return _logger_instance


def setup_logging(app_name="Clerkonator", debug_mode=False):
    """Настраивает логирование для приложения"""
    global _logger_instance
    _logger_instance = SimpleLogger(app_name)
    
    if debug_mode:
        _logger_instance.enable_debug_mode()
    
    return _logger_instance


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
    log.info("Тест завершен")
    
    print("Тестирование завершено. Проверьте файлы в папке logs/")


if __name__ == "__main__":
    main()
