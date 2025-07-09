"""
Orion Computer Vision Server

A real-time computer vision server that processes video streams from iOS devices,
performs object detection and scene analysis using git-base and Gemma models,
and provides enhanced contextual understanding through a combination of
computer vision and language models.

Components:
- FastAPI web server with WebSocket support
- Real-time vision processing using git-base
- Contextual analysis using Gemma 3B
- Context memory system for temporal awareness
- Dashboard WebSocket interface for monitoring
"""

__version__ = "1.0.0"
__author__ = "Riddhiman Rana"

from .models import (
    DetectionFrame,
    ServerResponse,
    AnalysisResult,
    SystemStatus,
    HealthCheck,
    ContextEntry,
    PacketEvent
)

from .services import (
    WebSocketManager,
    LLMProcessor,
    ContextMemory,
    ModelManager
)

from .utils import setup_logger, get_logger

# Version info tuple
VERSION_INFO = tuple(map(int, __version__.split('.')))

__all__ = [
    # Version info
    '__version__',
    'VERSION_INFO',
    
    # Models
    'DetectionFrame',
    'ServerResponse',
    'AnalysisResult',
    'SystemStatus',
    'HealthCheck',
    'ContextEntry',
    
    # Services
    'WebSocketManager',
    'LLMProcessor',
    'ContextMemory',
    'ModelManager',
    
    # Utils
    'setup_logger',
    'get_logger'
]