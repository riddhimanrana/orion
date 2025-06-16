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
# Attempt to import coremltools and its ComputeUnit
_ctm = None
_ct_ComputeUnit = None
_COREMLTOOLS_AVAILABLE = False

try:
    import coremltools.models as _ctm_module
    from coremltools import ComputeUnit as _ComputeUnit_enum
    _ctm = _ctm_module
    _ct_ComputeUnit = _ComputeUnit_enum
    _COREMLTOOLS_AVAILABLE = True
    logger.info("coremltools and ComputeUnit loaded successfully.")
except ImportError:
    logger.warning(
        "coremltools or coremltools.ComputeUnit not available. "
        "VLM .mlpackage loading might be affected or use default compute units. "
        "Please install/update coremltools."
    )

class ModelManager:
    """Manages MLX models for vision and language processing."""
    
    def __init__(self):
        """Initialize model manager."""
        # MLX is still needed for Gemma
        if not MLX_READY:
            raise RuntimeError("MLX or mlx-lm is required for Gemma but not available. Please install them.")
        if not _COREMLTOOLS_AVAILABLE:
            # Depending on strictness, you might allow server to run without VLM
            # or raise an error if VLM is critical.
            logger.error("coremltools is required for VLM .mlpackage but not available. VLM functionality will be disabled.")
            # raise RuntimeError("coremltools is required for VLM .mlpackage but not available.")

        self.vlm_model: Optional[Any] = None # Will be coremltools.models.MLModel if loaded
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
        """Load vision-language model (.mlpackage) using Core ML."""
        if not _COREMLTOOLS_AVAILABLE or not _ctm: # _ct_ComputeUnit might be None if import failed, but _ctm is essential
            logger.error("Cannot load VLM model: coremltools or its models module is not available.")
            # Return a dummy model or raise an error to prevent further issues
            def dummy_vlm_model_coreml_unavailable(*args, **kwargs) -> Dict[str, Any]:
                logger.warning("CoreML VLM is unavailable because coremltools is missing or failed to import. Returning dummy output.")
                return {"description": "VLM (CoreML) unavailable", "confidence": 0.0, "features": []}
            return dummy_vlm_model_coreml_unavailable

        vlm_model_path_str = str(Path(self.vlm_path_str))
        if not Path(vlm_model_path_str).exists():
            raise FileNotFoundError(f"VLM model package not found at {vlm_model_path_str}")

        mlmodel_file = Path(vlm_model_path_str) / "Data" / "com.apple.CoreML" / "model.mlmodel"
        if not mlmodel_file.exists():
            logger.warning(
                f"{vlm_model_path_str} does not appear to be a valid .mlpackage. Missing {mlmodel_file}. "
                "Attempting to load with Core ML anyway."
            )
        
        try:
            logger.info(f"Attempting to load VLM .mlpackage from: {vlm_model_path_str} using Core ML")
            
            # Load the Core ML model package without specifying compute_units, letting it use the default.
            logger.info("Loading VLM model with default compute units.")
            model = _ctm.MLModel(vlm_model_path_str)
            
            # Log input/output descriptions for user to verify
            try:
                spec = model.get_spec()
                logger.info("Core ML VLM Input Descriptions:")
                for i_desc in spec.description.input:
                    logger.info(f"  Name: {i_desc.name}, Type: {i_desc.type.WhichOneof('Type')}")
                    if i_desc.type.WhichOneof('Type') == 'imageType':
                        logger.info(f"    Image Details - Width: {i_desc.type.imageType.width}, Height: {i_desc.type.imageType.height}, Format: {i_desc.type.imageType.colorSpace}")
                logger.info("Core ML VLM Output Descriptions:")
                for o_desc in spec.description.output:
                    logger.info(f"  Name: {o_desc.name}, Type: {o_desc.type.WhichOneof('Type')}")
            except Exception as spec_e:
                logger.warning(f"Could not retrieve or log Core ML model spec details: {spec_e}")

            logger.info("VLM .mlpackage model loaded successfully using Core ML.")
            return model
        except Exception as e:
            logger.error(f"Failed to load VLM .mlpackage model from {vlm_model_path_str} using Core ML: {e}")
            import traceback
            logger.error(traceback.format_exc())
            # Return a dummy model or raise an error
            def dummy_vlm_model_load_failed(*args, **kwargs) -> Dict[str, Any]: # Ensure return type hint is correct
                logger.error(f"CoreML VLM failed to load. Using dummy output. Error: {e}")
                return {"description": f"VLM (CoreML) load failed: {e}", "confidence": 0.0, "features": []}
            return dummy_vlm_model_load_failed

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
        
    def _preprocess_image_for_coreml(self, image_data: str) -> Image.Image:
        """
        Preprocess base64 image data for Core ML VLM model input.
        Returns a PIL Image.
        """
        try:
            image_bytes = base64.b64decode(image_data)
            image = Image.open(BytesIO(image_bytes))
            image = image.convert('RGB')

            # --- IMPORTANT: RESIZING LOGIC ---
            # Your Core ML model (FastVLM) likely expects a specific input image size.
            # You need to find this size (e.g., from model.get_spec() or documentation)
            # and resize the image here if it doesn't match.
            # Example: If your model expects 224x224
            # target_width = 224 # Replace with actual width from your model spec
            # target_height = 224 # Replace with actual height from your model spec
            # if image.width != target_width or image.height != target_height:
            #     logger.debug(f"Resizing image from {image.size} to ({target_width},{target_height}) for Core ML VLM.")
            #     image = image.resize((target_width, target_height))
            # else:
            #     logger.debug(f"Image size {image.size} matches Core ML VLM expected input size (or no specific size found in spec).")
            # For now, we are not resizing, assuming the model handles it or input is already correct.
            # You SHOULD verify this. The settings.IMAGE_SIZE might be relevant here if it matches VLM's need.
            if settings.IMAGE_SIZE > 0 : # Assuming IMAGE_SIZE is for VLM
                 current_size = settings.IMAGE_SIZE
                 if image.width != current_size or image.height != current_size:
                     logger.debug(f"Resizing image from {image.size} to ({current_size},{current_size}) for Core ML VLM based on settings.IMAGE_SIZE.")
                     image = image.resize((current_size, current_size))


            return image
        except Exception as e:
            logger.error(f"Error during Core ML image preprocessing: {e}")
            raise

    async def process_vision(self, image_data: str) -> Dict[str, Any]:
        """
        Process image with Core ML VLM model.
        """
        if not self.vlm_model or not _COREMLTOOLS_AVAILABLE or not _ctm: # Check _ctm as well
            logger.error("Core ML Vision model (VLM) not available or coremltools/models module missing.")
            return {
                "description": "VLM unavailable",
                "confidence": 0.0,
                "features": []
            }
        
        # If the loaded vlm_model is actually a dummy function due to load failure/unavailability
        if callable(self.vlm_model) and not isinstance(self.vlm_model, _ctm.MLModel): # Use _ctm.MLModel
            logger.warning("VLM model is a dummy function, likely due to load failure or coremltools unavailability.")
            # Call the dummy function. Since self.vlm_model is Optional[Any],
            # Pylance might not infer the return type of the callable.
            # We know our dummy functions return Dict[str, Any].
            # An explicit cast or check could be used if Pylance is strict,
            # but the dummy functions themselves are type-hinted.
            # Let's assume the type hint on the dummy functions is sufficient for runtime.
            # If Pylance error persists here and is problematic, we might need a more explicit cast.
            result = self.vlm_model()
            if isinstance(result, dict): # Runtime check to be safe
                return result
            else: # Should not happen if dummy functions are correct
                logger.error("Dummy VLM function did not return a dictionary as expected.")
                return {"description": "Error: Dummy VLM returned unexpected type", "confidence": 0.0, "features": []}


        try:
            pil_image = self._preprocess_image_for_coreml(image_data)
            
            # --- CRITICAL: REPLACE WITH YOUR MODEL'S ACTUAL INPUT NAME ---
            # From logs: Core ML VLM Input Name is "images"
            vlm_input_name = "images"
            
            logger.debug(f"Processing vision with Core ML VLM. Input name: '{vlm_input_name}', Image size: {pil_image.size}")
            # The input to predict should be a dictionary where the key is "images"
            # and the value is the PIL Image.
            # However, the model input type is "multiArrayType", not "imageType".
            # This means it likely expects a NumPy array, not a PIL Image directly.
            # We need to convert the PIL image to a NumPy array and potentially reshape/transpose it.

            # Convert PIL image to NumPy array
            img_np = np.array(pil_image).astype(np.float32) # Ensure float32

            # CoreML multiArray inputs often expect (Batch, Channel, Height, Width) or (Channel, Height, Width)
            # PIL Image to NumPy array is (Height, Width, Channel)
            # Let's assume (Channel, Height, Width) for now, and add batch dim.
            # This might need adjustment based on the exact model spec for "images" input.
            if img_np.ndim == 3: # H, W, C
                img_np = np.transpose(img_np, (2, 0, 1)) # C, H, W
            
            # Add batch dimension if not present (model might expect a batch of 1)
            if img_np.ndim == 3: # C, H, W
                 img_np = np.expand_dims(img_np, axis=0) # B, C, H, W
            
            logger.debug(f"NumPy array for Core ML VLM input '{vlm_input_name}' shape: {img_np.shape}")

            prediction = self.vlm_model.predict({vlm_input_name: img_np})
            
            # --- CRITICAL: EXTRACT OUTPUTS BASED ON YOUR MODEL'S ACTUAL OUTPUT NAMES ---
            # Inspect model.get_spec().description.output
            # Example: prediction might be {'text_description': "...", 'features_output': np.array(...)}
            
            description = "Description from Core ML VLM (Update extraction logic)"
            confidence = 0.75  # Placeholder
            features_np = np.array([]) # Placeholder for NumPy array features

            # Attempt to get common output names. YOU MUST VERIFY THESE.
            # For text description: (FastVLM typically outputs features, not direct text descriptions)
            # The output name is "image_features"
            description = "Features extracted by VLM, description to be generated by LLM." # Placeholder
            
            # For features (embeddings):
            # From logs: Core ML VLM Output Name is "image_features"
            output_features_name = "image_features"
            if output_features_name in prediction:
                features_np = prediction[output_features_name]
            else:
                logger.warning(f"Could not find output '{output_features_name}' in Core ML VLM prediction. Keys: {list(prediction.keys())}. Using empty features.")
                features_np = np.array([])

            if isinstance(features_np, np.ndarray):
                logger.debug(f"Core ML VLM features extracted, shape: {features_np.shape}")
                features_list = features_np.tolist()
            else:
                logger.warning(f"Extracted VLM features are not a NumPy array (type: {type(features_np)}). Using empty list.")
                features_list = []
            
            # Confidence might not be directly output by all VLMs.
            # If your model outputs probabilities or scores, you might derive confidence here.

            logger.info(f"Core ML VLM processed. Description (raw): '{str(description)[:100]}...'")

            return {
                "description": str(description), # Ensure it's a string
                "confidence": confidence,
                "features": features_list
            }
            
        except Exception as e:
            logger.error(f"Core ML Vision processing failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            # Return a structured error response
            return {
                "description": f"Error in VLM processing: {e}",
                "confidence": 0.0,
                "features": [],
                "error": str(e)
            }
            
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