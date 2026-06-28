# -*- coding: utf-8 -*-
"""
Main application window
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import os
from datetime import datetime, timedelta

from audio.recorder import AudioRecorder
from stt.processor import STTProcessor
from utils.clipboard import ClipboardManager
from utils.session_logger import get_logger

# Get logger
log = get_logger()


class MainWindow:
    """Main application window"""
    
    def __init__(self, config):
        """Initialize main window"""
        self.config = config
        self.app_instance = None  # Will be set by main app
        self.clipboard_manager = ClipboardManager()
        
        # Application state
        self.current_audio_file = None
        self.is_recording = False
        self.is_paused = False
        self.is_processing = False
        
        # Create GUI
        self._create_window()
        self._create_widgets()
        self._setup_bindings()
        
        # Initialize components
        self._initialize_components()
    
    def set_app_instance(self, app_instance):
        """Set reference to main application instance"""
        self.app_instance = app_instance
        
    def _create_window(self):
        """Create main window"""
        self.window = tk.Tk()
        self.window.title("Clerkonator")
        
        # Window settings
        if self.config.get("gui.always_on_top", True):
            self.window.attributes("-topmost", True)
        
        # Hide window by default
        self.window.withdraw()
        
        # Window close handler - hide window instead of closing
        self.window.protocol("WM_DELETE_WINDOW", self.hide_window)
        
    def _create_widgets(self):
        """Create interface widgets"""
        # Main frame
        main_frame = ttk.Frame(self.window, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Title
        title_label = ttk.Label(
            main_frame,
            text="Clerkonator",
            font=("Arial", 16, "bold")
        )
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 10))
        
        # Hotkeys info
        hotkeys_label = ttk.Label(
            main_frame,
            text="Hotkeys: Ctrl+R (Record), Ctrl+P (Pause), Ctrl+F (Finish), Ctrl+C (Copy), Ctrl+H/Esc (Hide)",
            font=("Arial", 8),
            foreground="gray"
        )
        hotkeys_label.grid(row=1, column=0, columnspan=3, pady=(0, 10))
        
        # Status
        self.status_label = ttk.Label(
            main_frame,
            text="Initializing...",
            font=("Arial", 12)
        )
        self.status_label.grid(row=2, column=0, columnspan=3, pady=(0, 10))
        
        # Timer
        self.timer_label = ttk.Label(
            main_frame,
            text="Recording Time: 00:00",
            font=("Arial", 10)
        )
        self.timer_label.grid(row=3, column=0, columnspan=3, pady=(0, 20))
        
        # Control buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, columnspan=3, pady=(0, 20))
        
        self.record_button = ttk.Button(
            button_frame,
            text="Start Recording",
            command=self._toggle_recording,
            width=15
        )
        self.record_button.grid(row=0, column=0, padx=(0, 5))
        
        self.pause_button = ttk.Button(
            button_frame,
            text="Pause",
            command=self._toggle_pause,
            state="disabled",
            width=15
        )
        self.pause_button.grid(row=0, column=1, padx=5)
        
        self.finish_button = ttk.Button(
            button_frame,
            text="Finish Recording",
            command=self._finish_recording,
            state="disabled",
            width=15
        )
        self.finish_button.grid(row=0, column=2, padx=(5, 0))
        
        # Progress
        self.progress_label = ttk.Label(
            main_frame,
            text="Progress: 0%",
            font=("Arial", 10)
        )
        self.progress_label.grid(row=5, column=0, columnspan=3, pady=(0, 5))
        
        self.progress_bar = ttk.Progressbar(
            main_frame,
            length=300,
            mode='determinate'
        )
        self.progress_bar.grid(row=6, column=0, columnspan=3, pady=(0, 20))
        
        # Result
        result_label = ttk.Label(
            main_frame,
            text="Result:",
            font=("Arial", 10, "bold")
        )
        result_label.grid(row=7, column=0, columnspan=3, pady=(0, 5))
        
        self.result_text = tk.Text(
            main_frame,
            height=6,
            width=50,
            wrap=tk.WORD,
            font=("Arial", 10)
        )
        self.result_text.grid(row=8, column=0, columnspan=3, pady=(0, 10), sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Bind text change event to auto-resize
        self.result_text.bind('<KeyRelease>', self._on_text_change)
        self.result_text.bind('<Button-1>', self._on_text_change)
        
        # Copy button
        self.copy_button = ttk.Button(
            main_frame,
            text="Copy to Clipboard",
            command=self._copy_to_clipboard,
            state="disabled",
            width=20
        )
        self.copy_button.grid(row=9, column=0, columnspan=3, pady=(10, 0))
        
        # Hide to tray button
        self.hide_button = ttk.Button(
            main_frame,
            text="Hide to Tray",
            command=self.hide_window,
            width=20
        )
        self.hide_button.grid(row=10, column=0, columnspan=3, pady=(5, 0))
        
        # Configure grid weights for proper resizing
        self.window.grid_rowconfigure(0, weight=1)
        self.window.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(8, weight=1)  # Text widget row
        main_frame.grid_columnconfigure(0, weight=1)
        
        # Auto-size window to content
        self.window.update_idletasks()
        self._auto_size_window()
        
    def _setup_bindings(self):
        """Setup key bindings"""
        self.window.bind('<Control-r>', lambda e: self._toggle_recording())
        self.window.bind('<Control-p>', lambda e: self._toggle_pause())
        self.window.bind('<Control-f>', lambda e: self._finish_recording())
        self.window.bind('<Control-c>', lambda e: self._copy_to_clipboard())
        self.window.bind('<Control-h>', lambda e: self.hide_window())
        self.window.bind('<Escape>', lambda e: self.hide_window())
        
    def _initialize_components(self):
        """Initialize components"""
        # Create necessary directories
        self.config.ensure_directories()
        
        log.info("OK - GUI components initialized")
        
    def _auto_size_window(self):
        """Auto-size window to content"""
        # Update window to get actual content size
        self.window.update_idletasks()
        
        # Get required size
        req_width = self.window.winfo_reqwidth()
        req_height = self.window.winfo_reqheight()
        
        # Add some padding
        padding = 20
        window_width = req_width + padding
        window_height = req_height + padding
        
        # Center window on screen
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        
        # Set window size and position
        self.window.geometry(f"{window_width}x{window_height}+{x}+{y}")
        
        # Make window resizable
        self.window.resizable(True, True)
    
    def show(self):
        """Show window"""
        self.window.deiconify()
        self.window.lift()
        self.window.focus_force()
    
    def hide_window(self):
        """Hide window to tray"""
        self.window.withdraw()
        log.info("Window hidden to tray")
        
        # Show notification that window is hidden
        try:
            import tkinter as tk
            from tkinter import messagebox
            
            # Create a temporary root for notification
            temp_root = tk.Tk()
            temp_root.withdraw()
            
            messagebox.showinfo(
                "Hidden to Tray",
                "Window hidden to system tray.\n\n"
                "Right-click on the tray icon to show the window again.\n"
                "Or use the 'Show Main Window' option from the tray menu."
            )
            
            temp_root.destroy()
        except Exception as e:
            log.error(f"Error showing hide notification: {e}")
    
    def run(self):
        """Run main loop"""
        self.window.mainloop()
    
    def destroy(self):
        """Destroy window"""
        if self.window:
            self.window.destroy()
    
    def _toggle_recording(self):
        """Toggle recording"""
        if not self.is_recording:
            self._start_recording()
        else:
            self._stop_recording()
    
    def _start_recording(self):
        """Start recording"""
        try:
            # Generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"recording_{timestamp}.wav"
            
            # Start recording
            if self.recorder.start_recording(filename):
                self.is_recording = True
                self.current_audio_file = filename
                
                # Update UI
                self.record_button.config(text="Stop Recording")
                self.pause_button.config(state="normal")
                self.finish_button.config(state="normal")
                self.status_label.config(text="Recording...", foreground="red")
                
                # Start timer update
                self._start_timer()
                
                log.info("Recording started")
            else:
                messagebox.showerror("Error", "Failed to start recording")
                
        except Exception as e:
            messagebox.showerror("Error", f"Recording start error: {str(e)}")
    
    def _stop_recording(self):
        """Stop recording"""
        if not self.is_recording:
            return
            
        self.recorder.stop_recording()
        self.is_recording = False
        self.is_paused = False
        
        # Update UI
        self.record_button.config(text="Start Recording")
        self.pause_button.config(text="Pause", state="disabled")
        self.finish_button.config(state="disabled")
        self.status_label.config(text="Recording stopped", foreground="orange")
        
        log.info("Recording stopped")
    
    def _toggle_pause(self):
        """Toggle pause"""
        if not self.is_paused:
            if self.recorder.pause_recording():
                self.is_paused = True
                self.pause_button.config(text="Resume")
                self.status_label.config(text="Paused", foreground="orange")
                log.info("Recording paused")
        else:
            if self.recorder.resume_recording():
                self.is_paused = False
                self.pause_button.config(text="Pause")
                self.status_label.config(text="Recording...", foreground="red")
                log.info("Recording resumed")
    
    def _finish_recording(self):
        """Finish recording"""
        if not self.is_recording:
            return
            
        # Stop recording
        self.recorder.stop_recording()
        self.is_recording = False
        self.is_paused = False
        
        # Update UI
        self.record_button.config(text="Start Recording")
        self.pause_button.config(text="Pause", state="disabled")
        self.finish_button.config(state="disabled")
        self.status_label.config(text="Processing...", foreground="blue")
        
        # Start processing
        self._process_audio()
    
    def _process_audio(self):
        """Process audio file"""
        if not self.current_audio_file:
            return
        
        # Check if STT processor is ready
        if not self.stt_processor or not self.stt_processor.is_model_loaded():
            log.error("STT processor not ready")
            self.is_processing = False
            messagebox.showerror("Error", "STT model not ready. Please wait for initialization to complete.")
            return
            
        # Get audio file path
        audio_dir = self.config.get("paths.recordings", "data/recordings")
        audio_path = os.path.join(audio_dir, self.current_audio_file)
        
        # Start processing in background thread
        self.is_processing = True
        self.stt_processor.process_audio_file(
            audio_path,
            progress_callback=self._update_progress,
            result_callback=self._on_processing_complete
        )
        
        log.info("Audio processing started")
    
    def _update_progress(self, progress):
        """Update progress"""
        self.progress_bar.config(value=progress)
        self.progress_label.config(text=f"Processing... {progress:.1f}%")
    
    def _on_processing_complete(self, text):
        """Handle processing completion"""
        self.is_processing = False
        
        if text and text.strip():
            # Show result
            self.result_text.delete(1.0, tk.END)
            self.result_text.insert(1.0, text)
            self.copy_button.config(state="normal")
            
            # Save text to file
            self._save_text(text)
            
            # Copy to clipboard
            self._copy_to_clipboard()
            
            self.status_label.config(text="Ready!", foreground="green")
            self.progress_label.config(text="Processing completed")
            self.progress_bar.config(value=100)
            
            print(f"OK - Processing completed: {text}")
        else:
            self.status_label.config(text="Processing error", foreground="red")
            self.progress_label.config(text="Failed to recognize speech")
            messagebox.showerror("Error", "Failed to recognize speech in audio file")
        
    def _save_text(self, text):
        """Save text to file"""
        try:
            # Create text directory
            text_dir = self.config.get("paths.transcriptions", "data/transcriptions")
            os.makedirs(text_dir, exist_ok=True)
            
            # Generate text filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            text_filename = f"transcription_{timestamp}.txt"
            text_path = os.path.join(text_dir, text_filename)
            
            with open(text_path, 'w', encoding='utf-8') as f:
                f.write(text)
            
            log.info(f"Text saved: {text_path}")
            
        except Exception as e:
            log.error(f"Text save error: {e}")
    
    def _copy_to_clipboard(self):
        """Copy to clipboard"""
        try:
            text = self.result_text.get(1.0, tk.END).strip()
            if text:
                # Copy to clipboard
                self.window.clipboard_clear()
                self.window.clipboard_append(text)
                self.window.update()  # Required for clipboard to work
                
                # Show success message
                self.copy_button.config(text="Copied!", state="normal")
                self.window.after(2000, lambda: self.copy_button.config(text="Copy to Clipboard"))
                
                log.info("Text copied to clipboard")
            else:
                messagebox.showwarning("Warning", "No text to copy")
                
        except Exception as e:
            messagebox.showerror("Error", f"Copy error: {str(e)}")
            log.error(f"Copy error: {e}")
    
    def _on_text_change(self, event=None):
        """Handle text change events"""
        # Auto-resize text widget based on content
        self.window.after(100, self._auto_resize_text)
    
    def _auto_resize_text(self):
        """Auto-resize text widget based on content"""
        try:
            # Get text content
            text = self.result_text.get(1.0, tk.END).strip()
            
            if text:
                # Calculate required height based on text
                lines = text.count('\n') + 1
                min_height = 3
                max_height = 10
                new_height = max(min_height, min(lines + 1, max_height))
                
                # Update text widget height
                self.result_text.config(height=new_height)
                
                # Update window size
                self.window.update_idletasks()
                self._auto_size_window()
        except Exception as e:
            log.error(f"Error auto-resizing text: {e}")
    
    def update_status(self, status, color="black"):
        """Update status label"""
        try:
            self.status_label.config(text=status, foreground=color)
            log.info(f"Status updated: {status}")
        except Exception as e:
            log.error(f"Error updating status: {e}")
    
    def _start_timer(self):
        """Start recording timer"""
        def update_timer():
            while self.is_recording:
                elapsed = self.recorder.get_recording_time()
                self.timer_label.config(text=f"Recording Time: {elapsed}")
                time.sleep(0.1)
        
        threading.Thread(target=update_timer, daemon=True).start()