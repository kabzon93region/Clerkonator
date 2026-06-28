#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Session Logger - Creates separate log files for each program run
"""

import os
import sys
import logging
from datetime import datetime
from pathlib import Path


class SessionLogger:
    """Logger that creates separate log files for each session"""
    
    def __init__(self, log_dir="logs"):
        """Initialize session logger"""
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        # Create session-specific log file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = self.log_dir / f"speechtotext_{timestamp}.log"
        
        # Setup logging
        self.setup_logging()
        
    def setup_logging(self):
        """Setup logging configuration"""
        # Create logger
        self.logger = logging.getLogger("Clerkonator")
        self.logger.setLevel(logging.INFO)
        
        # Clear existing handlers
        self.logger.handlers.clear()
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(message)s',
            datefmt='%H:%M:%S'
        )
        
        # File handler
        file_handler = logging.FileHandler(
            self.log_file, 
            encoding='utf-8',
            mode='w'
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

        # Capture pystray errors in the same log file
        pystray_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | [pystray] %(message)s',
            datefmt='%H:%M:%S',
        )
        for logger_name in ('pystray', 'pystray._win32'):
            pystray_logger = logging.getLogger(logger_name)
            pystray_logger.setLevel(logging.DEBUG)
            pystray_handler = logging.FileHandler(
                self.log_file,
                encoding='utf-8',
                mode='a',
            )
            pystray_handler.setFormatter(pystray_formatter)
            pystray_logger.addHandler(pystray_handler)
            pystray_logger.propagate = False
        
        # Log session start
        self.logger.info("=" * 60)
        self.logger.info(f"Clerkonator Session Started")
        self.logger.info(f"Log file: {self.log_file}")
        self.logger.info(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.logger.info("=" * 60)
    
    def get_logger(self):
        """Get the logger instance"""
        return self.logger
    
    def get_log_file(self):
        """Get the log file path"""
        return self.log_file


# Global session logger instance
_session_logger = None

def get_session_logger():
    """Get the global session logger instance"""
    global _session_logger
    if _session_logger is None:
        _session_logger = SessionLogger()
    return _session_logger

def get_logger():
    """Get the logger instance"""
    return get_session_logger().get_logger()

def get_log_file():
    """Get the current log file path"""
    return get_session_logger().get_log_file()
