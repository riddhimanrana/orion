"""Configuration settings for the Orion server."""
import os
from pathlib import Path
from typing import Any, Dict

from pydantic import BaseModel

# Root directory
ROOT_DIR = Path(__file__).parent

class Settings(BaseModel):
    """Server configuration settings."""
    
    # Server settings
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    
    # MLX model settings
    WEIGHTS_DIR: Path = ROOT_DIR / "weights"
    LLM_MODEL_PATH: str = str(ROOT_DIR / "weights/gemma-3-1b-it-4bit/")
    YOLO_MODEL_PATH: str = str(ROOT_DIR / "weights/yolov11n/yolo11n.mlpackage")
    FASTVLM_MODEL_PATH: str = str(ROOT_DIR / "weights/fastvlm-0.5b/")
    PROCESSING_MODE: str = "split"  # "split" (VLM on device, LLM on server) or "full" (VLM+LLM on server)
    
    # Memory settings
    MAX_MEMORY_FRAMES: int = 1000
    MEMORY_CLEANUP_INTERVAL: int = 300  # 5 minutes
    
    # Processing settings
    IMAGE_SIZE: int = 1024 # Changed from 224 to match FastVLM CoreML requirement
    MAX_TEXT_LENGTH: int = 100
    
    def __init__(self, **data: Dict[str, Any]):
        super().__init__(**data)
        # Load from environment variables
        for key, value in os.environ.items():
            if hasattr(self, key):
                setattr(self, key, value)
        
        # Ensure required directories exist
        self.WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)

    class Config:
        validate_assignment = True
        arbitrary_types_allowed = True

# Create settings instance
settings = Settings()