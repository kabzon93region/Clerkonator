# -*- coding: utf-8 -*-
"""
Pygame silent initialization to suppress warnings and messages
"""

import os
import warnings

# Suppress pygame warnings
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'

# Suppress pkg_resources deprecation warning
warnings.filterwarnings('ignore', category=UserWarning, module='pygame')

# Suppress setuptools deprecation warning
warnings.filterwarnings('ignore', message='.*pkg_resources.*')

def init_pygame_silent():
    """Initialize pygame with suppressed messages"""
    try:
        import pygame
        pygame.init()
        return True
    except Exception as e:
        print(f"Failed to initialize pygame: {e}")
        return False
