"""Model manager for MLX-based vision and language models."""
import os
import base64
from typing import Dict, Any, Optional, Tuple
from io import BytesIO
import logging
from pathlib import Path

# Initialize logger first
from utils.logger import get_logger
logger = get_logger(__name__)

# Configuration
from config import settings

# Initialize MLX imports as None
mx = None
nn = None
mlx_lm = None
MLX_AVAILABLE = False

def check_mlx_availability():
    """Check if MLX and mlx_lm are available."""
    global MLX_AVAILABLE, mx, nn, mlx_lm
    
    try:
        import mlx.core as mx_core
        import mlx.nn as nn_core
        import mlx_lm as lm_core # For Gemma model loading and generation
        mx = mx_core
        nn = nn_core
        mlx_lm = lm_core
        MLX_AVAILABLE = True
        logger.info("MLX and mlx-lm loaded successfully")
        return True
    except ImportError as e:
        logger.warning(f"MLX or mlx-lm not available. Please install MLX and mlx-lm for Apple Silicon support. Error: {e}")
        return False

# Try to initialize MLX and mlx-lm
MLX_READY = check_mlx_availability()

import numpy as np
from PIL import Image

class ModelManager:
    """Manages MLX models for vision and language processing."""
    
    def __init__(self):
        """Initialize model manager."""
        if not MLX_READY:
            raise RuntimeError("MLX or mlx-lm is required but not available. Please install them.")
            
        self.vlm_model: Optional[Any] = None # Actual type depends on how .mlpackage loads
        self.gemma_model: Optional[Any] = None # mlx_lm.model.Model
        self.gemma_tokenizer: Optional[Any] = None # mlx_lm.tokenizer.Tokenizer
        
        self.models_loaded = {
            "vlm": False,
            "gemma": False
        }
        
        # Get model paths from config settings
        self.vlm_path_str = settings.VISION_MODEL_PATH
        self.gemma_path_str = settings.LLM_MODEL_PATH
        
    async def initialize(self) -> None:
        """Initialize and load models."""
        if not MLX_READY: # nn might not be needed directly if mlx_lm handles Gemma fully
            raise RuntimeError("MLX or mlx-lm not properly initialized")
            
        try:
            # Load VLM model
            logger.info(f"Loading VLM model from {self.vlm_path_str}")
            self.vlm_model = await self._load_vlm_model()
            self.models_loaded["vlm"] = True
            
            # Load Gemma model
            logger.info(f"Loading Gemma model from {self.gemma_path_str}")
            # mlx_lm.load returns (model, tokenizer)
            gemma_model_tuple = await self._load_gemma_model()
            if gemma_model_tuple:
                self.gemma_model, self.gemma_tokenizer = gemma_model_tuple
                self.models_loaded["gemma"] = True
            else:
                raise RuntimeError(f"Failed to load Gemma model from {self.gemma_path_str}")

            logger.info("All models loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize models: {e}")
            raise
            
    async def _load_vlm_model(self) -> Any:
        """Load vision-language model (.mlpackage)."""
        if not MLX_READY or not mx:
            raise RuntimeError("MLX not properly initialized for VLM loading")
            
        vlm_model_path = Path(self.vlm_path_str)
        if not vlm_model_path.exists():
            raise FileNotFoundError(f"VLM model package not found at {self.vlm_path_str}")
        # Updated check for .mlpackage structure: Data/com.apple.CoreML/model.mlmodel
        mlmodel_path = vlm_model_path / "Data" / "com.apple.CoreML" / "model.mlmodel"
        if not vlm_model_path.is_dir() or not mlmodel_path.exists():
            logger.warning(f"{self.vlm_path_str} does not appear to be a valid .mlpackage directory containing Data/com.apple.CoreML/model.mlmodel. Attempting to load anyway.")

        try:
            # Loading .mlpackage might be more complex and depend on its internal structure
            # For now, assuming mx.core.load can handle it or it's a directory MLX can interpret.
            # This part may need adjustment based on how FastVLM's .mlpackage is structured for MLX.
            # A common pattern for MLX models is to load weights and instantiate a model class.
            # If fastvithd.mlpackage is a CoreML package, direct MLX loading might not be straightforward.
            # For now, this is a placeholder for actual .mlpackage loading logic with MLX.
            # If it's a directory of MLX artifacts (e.g. weights + config), it would be different.
            logger.info(f"Attempting to load VLM from: {self.vlm_path_str}")
            # This is a placeholder. Actual loading of an .mlpackage might require specific MLX utilities
            # or conversion if it's a CoreML package not directly compatible with generic MLX loading.
            # For demonstration, we'll assume it's a path MLX can load, or this needs specific implementation.
            # model = mx.load(str(vlm_model_path)) # This is a guess, mx.load is usually for .npz or .safetensors
            
            # Placeholder: If direct loading isn't simple, this needs the actual FastVLM MLX loading code.
            # For now, returning a dummy callable to avoid crashing, but this MUST be implemented.
            def dummy_vlm_model(image_tensor):
                logger.warning("Using dummy VLM model. Implement actual FastVLM .mlpackage loading and inference.")
                if mx is None: # Should not happen if MLX_READY is True and mx is assigned
                    raise RuntimeError("MLX core (mx) is None in dummy_vlm_model.")
                return mx.random.normal(shape=(1, 512)) # Dummy features
            model = dummy_vlm_model
            logger.info("VLM model loaded (or placeholder activated).")
            return model
        except Exception as e:
            logger.error(f"Failed to load VLM model from {self.vlm_path_str}: {e}")
            raise

    async def _load_gemma_model(self) -> Optional[Tuple[Any, Any]]:
        """Load Gemma language model using mlx_lm."""
        if not MLX_READY or not mlx_lm:
            raise RuntimeError("mlx_lm not available for Gemma loading")
            
        gemma_model_dir = Path(self.gemma_path_str)
        if not gemma_model_dir.is_dir():
            raise FileNotFoundError(f"Gemma model directory not found at {self.gemma_path_str}")
        
        try:
            # mlx_lm.load expects a path to the directory containing model weights, tokenizer, config
            model, tokenizer = mlx_lm.load(str(gemma_model_dir))
            logger.info("Gemma model and tokenizer loaded successfully.")
            return model, tokenizer
        except Exception as e:
            logger.error(f"Failed to load Gemma model from {self.gemma_path_str}: {e}")
            raise
        
    def _preprocess_image(self, image_data: str, target_size: int = 224) -> Any:
        """
        Preprocess base64 image data for model input.
        
        Args:
            image_data: Base64 encoded image
            target_size: The target size (height and width) for the image.
            
        Returns:
            Processed image tensor (batch_size, height, width, channels)
        """
        if not MLX_READY or not mx:
            raise RuntimeError("MLX not properly initialized for image preprocessing")
            
        # Decode base64
        image_bytes = base64.b64decode(image_data)
        image = Image.open(BytesIO(image_bytes))
        
        # Resize and convert to RGB
        image = image.convert('RGB')
        image = image.resize((target_size, target_size))
        
        # Convert to numpy array and normalize
        image_array = np.array(image)
        image_array = image_array.astype(np.float32) / 255.0
        
        # Convert to MLX array and add batch dimension
        # Expected shape for many vision models: (batch_size, height, width, channels)
        image_tensor = mx.array(image_array)
        image_tensor = mx.expand_dims(image_tensor, axis=0)
        
        return image_tensor
            
    async def process_vision(self, image_data: str) -> Dict[str, Any]:
        """
        Process image with vision model.
        
        Args:
            image_data: Base64 encoded image
            
        Returns:
            Vision analysis results
        """
        if not MLX_READY or not mx or not self.vlm_model:
            raise RuntimeError("Vision model (VLM) not available or MLX not ready")
            
        try:
            # Preprocess image
            # FastVLM might have specific image size requirements, adjust settings.IMAGE_SIZE if needed
            image_tensor = self._preprocess_image(image_data, target_size=settings.IMAGE_SIZE)
            
            # Get vision features
            # The actual call to self.vlm_model depends on how it's loaded and its API
            # This is a placeholder and needs to be adapted to the actual FastVLM model object
            logger.debug(f"Processing vision with image tensor shape: {image_tensor.shape}")
            features = self.vlm_model(image_tensor) # This call needs to be correct for the loaded VLM
            
            # Placeholder for actual results from FastVLM
            # FastVLM might return embeddings, text descriptions, or other structured data.
            # This needs to be updated based on FastVLM's output.
            description_placeholder = "VLM analysis placeholder (implement actual FastVLM output processing)"
            confidence_placeholder = 0.75 # Placeholder
            
            # Assuming features is an MLX array
            if not isinstance(features, mx.array):
                 logger.warning(f"VLM output 'features' is not an MLX array, type: {type(features)}. Conversion to list might fail.")
                 features_list = []
            else:
                 features_list = features.tolist()


            return {
                "description": description_placeholder,
                "confidence": confidence_placeholder,
                "features": features_list
            }
            
        except Exception as e:
            logger.error(f"Vision processing failed: {e}")
            # Log traceback for more details
            import traceback
            logger.error(traceback.format_exc())
            raise
            
    async def process_text(
        self,
        prompt: str,
        vision_context: Optional[Dict] = None # vision_context is not explicitly used here yet
    ) -> Dict[str, Any]:
        """
        Process text with language model.
        
        Args:
            prompt: Text prompt to process
            vision_context: Optional vision features and context (currently unused in generation)
            
        Returns:
            Generated text response
        """
        if not MLX_READY or not mlx_lm or not self.gemma_model or not self.gemma_tokenizer:
            raise RuntimeError("Language model (Gemma) or tokenizer not available or mlx_lm not ready")
            
        try:
            generated_text = mlx_lm.generate(
                self.gemma_model,
                self.gemma_tokenizer,
                prompt=prompt,
                max_tokens=settings.MAX_TEXT_LENGTH,
                verbose=False # Set to True for debugging generation steps
            )
            
            # mlx_lm.generate returns the generated string directly.
            # Confidence score is not directly provided by mlx_lm.generate.
            # We can set a placeholder or derive it if needed through other means (e.g. logprobs if accessible).
            confidence_placeholder = 0.8 # Placeholder

            return {
                "response": generated_text,
                "confidence": confidence_placeholder
            }
            
        except Exception as e:
            logger.error(f"Text processing failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise
            
    def is_healthy(self) -> bool:
        """Check if models are loaded and healthy."""
        return MLX_READY and self.models_loaded.get("vlm", False) and self.models_loaded.get("gemma", False)
        
    async def cleanup(self) -> None:
        """Cleanup model resources."""
        self.vlm_model = None
        self.gemma_model = None
        self.gemma_tokenizer = None
        self.models_loaded = {
            "vlm": False,
            "gemma": False
        }
        logger.info("Models cleaned up")