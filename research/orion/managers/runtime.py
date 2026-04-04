"""
Runtime Backend Management
==========================

Handles selection of compute backends (Torch vs MLX) based on
hardware availability and user configuration.

Author: Orion Research Team
"""

import logging
import platform
import importlib.util
from typing import Optional, Literal

from orion.settings import OrionSettings

logger = logging.getLogger(__name__)

BackendType = Literal["torch", "mlx"]

def is_mlx_available() -> bool:
    """Check if MLX is available and we are on Apple Silicon."""
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        return False
    return importlib.util.find_spec("mlx") is not None

_ACTIVE_BACKEND: Optional[BackendType] = None

def get_active_backend() -> Optional[BackendType]:
    """
    Get the explicitly configured backend from settings.
    Returns None if set to 'auto'.
    """
    return _ACTIVE_BACKEND

def set_active_backend(backend: BackendType) -> None:
    """Set the active backend."""
    global _ACTIVE_BACKEND
    _ACTIVE_BACKEND = backend

def select_backend() -> BackendType:
    """
    Select the best available backend.
    
    Logic:
    1. If on Apple Silicon AND MLX is installed -> 'mlx'
    2. Otherwise -> 'torch'
    """
    if is_mlx_available():
        logger.info("Apple Silicon detected with MLX installed. Using MLX backend.")
        return "mlx"
    
    logger.info("Using PyTorch backend (CUDA/CPU/MPS).")
    return "torch"
