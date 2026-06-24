"""Configuration settings for the Orion server."""
import os
from pathlib import Path
from typing import Any, Dict

from pydantic import BaseModel
from dotenv import load_dotenv

# Root directory
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

class Settings(BaseModel):
    """Server configuration settings."""
    
    # Server settings
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    
    # MLX model settings
    WEIGHTS_DIR: Path = ROOT_DIR / "weights"
    LLM_MODEL_PATH: str = "mlx-community/gemma-4-e2b-it-qat-OptiQ-4bit"
    YOLO_MODEL_PATH: str = "yolo26x"
    FASTVLM_MODEL_PATH: str = str(ROOT_DIR.parent / "mobile/FastVLM/model/")
    PROCESSING_MODE: str = "full"  # "split" (VLM on device, LLM on server) or "full" (VLM+LLM on server)
    
    # Supabase & WebRTC Signaling
    SUPABASE_URL: str = "https://svltefplctinykebecyv.supabase.co"
    SUPABASE_PUBLISHABLE_KEY: str = ""
    SUPABASE_SECRET_KEY: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    P2P_SIGNAL_JWT_SECRET: str = ""
    SERVER_DEVICE_ID: str = "macos-server-dev"
    SERVER_DEVICE_NAME: str = "macOS Orion Server"
    
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
