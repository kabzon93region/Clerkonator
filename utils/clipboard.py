# -*- coding: utf-8 -*-
"""
Работа с буфером обмена
"""

import pyperclip
import tkinter as tk
from tkinter import messagebox


class ClipboardManager:
    """Менеджер для работы с буфером обмена"""
    
    def __init__(self):
        """Инициализация менеджера буфера обмена"""
        self.last_copied_text = ""
        
    def copy_to_clipboard(self, text):
        """Копирование текста в буфер обмена"""
        try:
            if not text or not text.strip():
                print("⚠️ Пустой текст для копирования")
                return False
                
            # Очищаем и форматируем текст
            cleaned_text = self._clean_text(text)
            
            # Копируем в буфер обмена
            pyperclip.copy(cleaned_text)
            self.last_copied_text = cleaned_text
            
            print(f"📋 Text copied to clipboard ({len(cleaned_text)} символов)")
            return True
            
        except Exception as e:
            print(f"❌ Error копирования в буфер обмена: {e}")
            return False
    
    def get_from_clipboard(self):
        """Получение текста из буфера обмена"""
        try:
            text = pyperclip.paste()
            return text
        except Exception as e:
            print(f"❌ Error получения из буфера обмена: {e}")
            return ""
    
    def _clean_text(self, text):
        """Очистка и форматирование текста"""
        if not text:
            return ""
            
        # Убираем лишние пробелы и переносы строк
        lines = [line.strip() for line in text.split('\n')]
        lines = [line for line in lines if line]  # Убираем пустые строки
        
        # Объединяем в один текст с пробелами
        cleaned = ' '.join(lines)
        
        # Убираем множественные пробелы
        while '  ' in cleaned:
            cleaned = cleaned.replace('  ', ' ')
            
        return cleaned.strip()
    
    def show_copy_notification(self, parent_window=None):
        """Показ уведомления об успешном копировании"""
        try:
            if parent_window:
                # Создаем всплывающее окно
                notification = tk.Toplevel(parent_window)
                notification.title("Успешно!")
                notification.geometry("200x100")
                notification.resizable(False, False)
                
                # Center window
                notification.transient(parent_window)
                notification.grab_set()
                
                # Добавляем текст
                label = tk.Label(
                    notification, 
                    text="✅ Текст скопирован\nв буфер обмена!",
                    font=("Arial", 10),
                    justify=tk.CENTER
                )
                label.pack(expand=True)
                
                # Автоматически закрываем через 2 секунды
                notification.after(2000, notification.destroy)
            else:
                print("✅ Текст успешно скопирован в буфер обмена!")
                
        except Exception as e:
            print(f"⚠️ Error показа уведомления: {e}")
    
    def get_last_copied_text(self):
        """Получение последнего скопированного текста"""
        return self.last_copied_text
