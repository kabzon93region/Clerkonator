# -*- coding: utf-8 -*-
"""Audio playback module using pygame mixer.

Plays audio files (WAV, MP3, etc.) in a background thread.
Supports play, pause, resume, and stop operations.
"""

import pygame
import threading
import time
import os
from utils.session_logger import get_logger
from utils.pygame_silent import init_pygame_silent

log = get_logger()


class AudioPlayer:
    """Audio player using pygame mixer.

    Playback runs in a background thread to avoid blocking the main thread.
    """
    
    def __init__(self):
        """Initialize audio player"""
        self.is_playing = False
        self.current_file = None
        self.play_thread = None
        self._init_pygame()
    
    def _init_pygame(self):
        """Initialize pygame mixer"""
        try:
            # Initialize pygame silently
            init_pygame_silent()
            pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
            log.info("Pygame mixer initialized")
        except Exception as e:
            log.error(f"Failed to initialize pygame mixer: {e}")
    
    def play_file(self, file_path):
        """Play audio file"""
        try:
            if not os.path.exists(file_path):
                log.error(f"Audio file not found: {file_path}")
                return False
            
            # Stop current playback if any
            self.stop()
            
            # Start playback in separate thread
            self.play_thread = threading.Thread(
                target=self._play_thread,
                args=(file_path,),
                daemon=True
            )
            self.play_thread.start()
            
            return True
            
        except Exception as e:
            log.error(f"Error playing audio file: {e}")
            return False
    
    def _play_thread(self, file_path):
        """Play audio in separate thread"""
        try:
            self.is_playing = True
            self.current_file = file_path
            
            log.info(f"Starting playback: {file_path}")
            
            # Load and play the file
            pygame.mixer.music.load(file_path)
            pygame.mixer.music.play()
            
            # Wait for playback to finish
            while pygame.mixer.music.get_busy() and self.is_playing:
                time.sleep(0.1)
            
            log.info("Playback finished")
            
        except Exception as e:
            log.error(f"Error in playback thread: {e}")
        finally:
            self.is_playing = False
            self.current_file = None
    
    def stop(self):
        """Stop current playback"""
        try:
            if self.is_playing:
                pygame.mixer.music.stop()
                self.is_playing = False
                self.current_file = None
                log.info("Playback stopped")
        except Exception as e:
            log.error(f"Error stopping playback: {e}")
    
    def pause(self):
        """Pause current playback"""
        try:
            if self.is_playing:
                pygame.mixer.music.pause()
                log.info("Playback paused")
        except Exception as e:
            log.error(f"Error pausing playback: {e}")
    
    def unpause(self):
        """Unpause current playback"""
        try:
            if self.is_playing:
                pygame.mixer.music.unpause()
                log.info("Playback unpaused")
        except Exception as e:
            log.error(f"Error unpausing playback: {e}")
    
    def is_paused(self):
        """Check if playback is paused"""
        try:
            return self.is_playing and not pygame.mixer.music.get_busy()
        except:
            return False
    
    def is_playing_file(self):
        """Check if currently playing"""
        return self.is_playing and pygame.mixer.music.get_busy()
    
    def get_current_file(self):
        """Get currently playing file"""
        return self.current_file if self.is_playing else None
