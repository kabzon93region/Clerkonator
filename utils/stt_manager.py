#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
STT Manager - Shared STT processor instance
Manages a single STT processor instance that can be shared between modules
"""

import threading
from stt.processor import STTProcessor


class STTManager:
    """Singleton manager for STT processor"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(STTManager, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.stt_processor = None
        self.config = None
        self._initialized = True
    
    def initialize(self, config):
        """Initialize STT processor with config"""
        if self.stt_processor is not None:
            return self.stt_processor
        
        self.config = config
        self.stt_processor = STTProcessor(config)
        return self.stt_processor
    
    def get_processor(self):
        """Get STT processor instance"""
        return self.stt_processor
    
    def is_ready(self):
        """Check if STT processor is ready"""
        return (self.stt_processor is not None and 
                self.stt_processor.is_model_loaded())


# Global STT manager instance
_stt_manager = STTManager()

def get_stt_manager():
    """Get the global STT manager instance"""
    return _stt_manager

def get_stt_processor():
    """Get the STT processor instance"""
    return _stt_manager.get_processor()

def is_stt_ready():
    """Check if STT processor is ready"""
    return _stt_manager.is_ready()
