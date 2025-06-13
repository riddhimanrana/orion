"""
Utils package for shared utilities.

This package contains shared utilities used across the application,
including logging, file handling, and other common functionality.
"""

from .logger import setup_logger, get_logger

__all__ = ['setup_logger', 'get_logger']