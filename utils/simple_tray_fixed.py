#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple system tray manager for Clerkonator
Uses tkinter to create tray icon
"""

import os
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageDraw, ImageFont
import io

# Add paths to utils for importing GPUManager
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from utils.gpu_manager import GPUManager


class SimpleTrayFixed:
    """Simple system tray manager"""

    def __init__(self, show_main_window_callback):
        self.show_main_window_callback = show_main_window_callback
        self.is_running = False
        self.gpu_manager = GPUManager()
        
        # Create hidden Tkinter window for event handling
        self.root = tk.Tk()
        self.root.withdraw()  # Hide main Tkinter window
        self.root.protocol("WM_DELETE_WINDOW", self.stop)  # Handle window close
        
        self.log_message("INFO", "Tray Manager initialized")

    def create_image(self, width, height, color1, color2, text="STT"):
        """Create image for tray icon."""
        image = Image.new('RGB', (width, height), color1)
        dc = ImageDraw.Draw(image)
        dc.rectangle((width // 4, height // 4, width * 3 // 4, height * 3 // 4), fill=color2)
        
        try:
            # Try to load font
            font_size = int(height * 0.6)
            font = ImageFont.truetype("arial.ttf", font_size)
        except IOError:
            # If font not found, use default font
            font = ImageFont.load_default()
        
        text_width, text_height = dc.textsize(text, font=font)
        x = (width - text_width) / 2
        y = (height - text_height) / 2 - 2  # Small adjustment
        dc.text((x, y), text, fill="black", font=font)
        return image

    def show_gpu_status(self):
        """Show GPU status."""
        device_info = self.gpu_manager.get_recommended_device()
        system_info = self.gpu_manager.get_system_info()
        
        message = (
            f"System: {system_info['system']['platform']}\n"
            f"CPU: {system_info['system']['cpu_cores']} cores\n"
            f"RAM: {system_info['system']['ram_total_gb']}GB (Available: {system_info['system']['ram_available_gb']}GB)\n\n"
            f"Recommended device: {device_info['device_name']} ({device_info['device']})\n"
            f"Reason: {device_info['reason']}\n"
            f"Performance: {device_info['performance']}"
        )
        messagebox.showinfo("GPU Status", message)
        self.log_message("INFO", "GPU status shown")

    def show_settings(self):
        """Show settings window (placeholder)."""
        messagebox.showinfo("Settings", "Settings functionality will be added later.")
        self.log_message("INFO", "Settings shown (placeholder)")

    def show_about(self):
        """Show program information."""
        messagebox.showinfo(
            "About",
            "Clerkonator\n"
            "Version: 1.0.8\n"
            "Developer: AI Assistant\n"
            "Designed for speech-to-text conversion."
        )
        self.log_message("INFO", "About information shown")

    def log_message(self, level, message):
        """Simple console logging."""
        timestamp = time.strftime('%H:%M:%S')
        print(f"{timestamp} | {level} | {message}")

    def run(self):
        """Start tray icon."""
        self.is_running = True
        self.log_message("OK", "Tray Manager started")
        self.log_message("INFO", "Application running in system tray")
        self.log_message("INFO", "Right-click on tray icon to access menu")
        
        # Start main Tkinter loop for event handling
        self.root.mainloop()

    def stop(self):
        """Stop tray icon and terminate application."""
        self.log_message("INFO", "Terminating application...")
        self.is_running = False
        
        # Terminate main Tkinter loop
        if self.root:
            self.root.quit()
            self.log_message("OK", "Tkinter mainloop stopped")
        
        # Force terminate all pythonw.exe processes
        try:
            import subprocess
            subprocess.run(['taskkill', '/F', '/IM', 'pythonw.exe', '/T'], capture_output=True, timeout=5)
            self.log_message("OK", "All pythonw.exe processes terminated")
        except Exception as e:
            self.log_message("ERROR", f"Error terminating pythonw.exe processes: {e}")
        
        # Force terminate current process
        os._exit(0)


if __name__ == "__main__":
    # Example usage
    def dummy_show_main_window():
        print("Dummy: Show main window")
        messagebox.showinfo("Window", "Main window shown!")

    tray = SimpleTrayFixed(dummy_show_main_window)
    tray.run()