import os
import base64
import io
from typing import Dict, Any, Optional, Tuple, List
import logging
from pathlib import Path

import numpy as np
from PIL import Image
import coremltools as ct

from utils.logger import get_logger
from config import settings

logger = get_logger(__name__)

# MLX imports (still needed for Gemma)
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
        import mlx_lm as lm_core
        mx = mx_core
        nn = nn_core
        mlx_lm = lm_core
        MLX_AVAILABLE = True
        logger.info("MLX and mlx-lm loaded successfully")
        return True
    except ImportError as e:
        logger.warning(f"MLX or mlx-lm not available. Please install MLX and mlx-lm for Apple Silicon support. Error: {e}")
        return False

MLX_READY = check_mlx_availability()

class ModelManager:
    """Manages MLX models for language and CoreML models for vision processing."""
    
    def __init__(self):
        if not MLX_READY:
            raise RuntimeError("MLX or mlx-lm is required but not available. Please install them.")
        
        self.gemma_model: Optional[Any] = None
        self.gemma_tokenizer: Optional[Any] = None
        self.yolo_model: Optional[ct.models.MLModel] = None
        self.vlm_model: Optional[ct.models.MLModel] = None
        
        self.models_loaded = {"gemma": False, "yolo": False, "vlm": False}
        
        self.gemma_path_str = settings.LLM_MODEL_PATH
        self.yolo_path_str = settings.YOLO_MODEL_PATH
        self.vlm_path_str = settings.FASTVLM_MODEL_PATH
        
    async def initialize(self) -> None:
        if not MLX_READY:
            raise RuntimeError("MLX or mlx-lm not properly initialized")
            
        try:
            logger.info(f"Loading Gemma model from {self.gemma_path_str}")
            gemma_model_tuple = await self._load_gemma_model()
            if gemma_model_tuple:
                self.gemma_model, self.gemma_tokenizer = gemma_model_tuple
                self.models_loaded["gemma"] = True
            else:
                raise RuntimeError(f"Failed to load Gemma model from {self.gemma_path_str}")

            if settings.PROCESSING_MODE == "full":
                logger.info("Full processing mode: Loading YOLO and VLM models.")
                self.yolo_model = await self._load_yolo_model()
                self.models_loaded["yolo"] = self.yolo_model is not None
                
                self.vlm_model = await self._load_vlm_model()
                self.models_loaded["vlm"] = self.vlm_model is not None
            
            logger.info("All required models loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize models: {e}")
            raise
            
    async def _load_gemma_model(self) -> Optional[Tuple[Any, Any]]:
        if not MLX_READY or not mlx_lm:
            raise RuntimeError("mlx_lm not available for Gemma loading")
            
        gemma_model_dir = Path(self.gemma_path_str)
        if not gemma_model_dir.is_dir():
            raise FileNotFoundError(f"Gemma model directory not found at {self.gemma_path_str}")
        
        try:
            model, tokenizer = mlx_lm.load(str(gemma_model_dir))
            logger.info("Gemma model and tokenizer loaded successfully.")
            return model, tokenizer
        except Exception as e:
            logger.error(f"Failed to load Gemma model from {self.gemma_path_str}: {e}")
            raise
        
    async def _load_yolo_model(self) -> Optional[ct.models.MLModel]:
        logger.info(f"Loading YOLOv11n model from {self.yolo_path_str}")
        try:
            # CoreML models are loaded using coremltools.models.MLModel
            model = ct.models.MLModel(self.yolo_path_str)
            logger.info("YOLOv11n model loaded successfully.")
            return model
        except Exception as e:
            logger.error(f"Error loading YOLO model from {self.yolo_path_str}: {e}")
            return None

    async def _load_vlm_model(self) -> Optional[ct.models.MLModel]:
        logger.info(f"Loading FastVLM model from {self.vlm_path_str}")
        try:
            # FastVLM is also a CoreML model
            # The .mlpackage contains the model.mlmodel file
            vlm_model_path = Path(self.vlm_path_str) / "fastvithd.mlpackage" / "Data" / "com.apple.CoreML" / "model.mlmodel"
            model = ct.models.MLModel(str(vlm_model_path))
            logger.info("FastVLM model loaded successfully.")
            return model
        except Exception as e:
            logger.error(f"Error loading FastVLM model from {self.vlm_path_str}: {e}")
            return None
            
    async def process_text(
        self,
        prompt: str,
        vision_context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        if not MLX_READY or not mlx_lm or not self.gemma_model or not self.gemma_tokenizer:
            raise RuntimeError("Language model (Gemma) or tokenizer not available or mlx_lm not ready")
            
        try:
            generated_text = mlx_lm.generate(
                self.gemma_model,
                self.gemma_tokenizer,
                prompt=prompt,
                max_tokens=settings.MAX_TEXT_LENGTH,
                verbose=False
            )
            
            confidence_placeholder = 0.8

            return {
                "response": generated_text,
                "confidence": confidence_placeholder
            }
            
        except Exception as e:
            logger.error(f"Text processing failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise
            
    async def process_image_for_yolo(self, image_data_b64: str) -> List[Dict[str, Any]]:
        if not self.yolo_model:
            logger.warning("YOLO model not loaded. Cannot perform detection.")
            return []

        try:
            image_data = base64.b64decode(image_data_b64)
            image = Image.open(io.BytesIO(image_data)).convert("RGB")
            
            # YOLOv11n expects 640x640 input
            image = image.resize((640, 640))

            # CoreML model prediction
            # The input name 'image' is derived from the CoreML model's input features
            # You might need to inspect the .mlmodel to confirm the exact input/output names
            predictions = self.yolo_model.predict({"image": image})

            # Process predictions (this part is highly model-specific)
            # Assuming output format similar to what's expected by iOS ObjectDetector
            detections = []
            # Example: if output is 'coordinates' and 'confidence'
            # You need to map these to your Detection model format
            # This is a placeholder and needs to be adapted to the actual YOLOv11n CoreML output
            
            # Example of processing output from a typical YOLO CoreML model
            # This assumes the model outputs are named 'coordinates' and 'confidence'
            # and that 'confidence' is a multiarray of shape (num_boxes, num_classes)
            # and 'coordinates' is (num_boxes, 4) for [x,y,w,h] or [x1,y1,x2,y2]
            
            # You need to inspect your specific yolov11n.mlpackage to know the exact output names and shapes.
            # For demonstration, let's assume it outputs 'var_1' (boxes) and 'var_2' (confidences)
            # and that the boxes are normalized [x,y,w,h] and confidences are per class.
            
            # This is a generic example, replace with actual output parsing for yolov11n.mlpackage
            if "var_1" in predictions and "var_2" in predictions:
                boxes = predictions["var_1"]
                confidences = predictions["var_2"]
                
                # Assuming classNames are available (e.g., from a config or hardcoded)
                class_names = ["person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat",
                               "traffic light", "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat",
                               "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe", "backpack",
                               "umbrella", "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball",
                               "kite", "baseball bat", "baseball glove", "skateboard", "surfboard", "tennis racket",
                               "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple",
                               "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake",
                               "chair", "couch", "potted plant", "bed", "dining table", "toilet", "tv", "laptop",
                               "mouse", "remote", "keyboard", "cell phone", "microwave", "oven", "toaster", "sink",
                               "refrigerator", "book", "clock", "vase", "scissors", "teddy bear", "hair drier", "toothbrush"]

                for i in range(confidences.shape[0]): # Iterate over detected boxes
                    # Find the class with the highest confidence for this box
                    max_confidence_idx = np.argmax(confidences[i])
                    max_confidence = confidences[i, max_confidence_idx]
                    
                    if max_confidence > 0.25: # Example confidence threshold
                        label = class_names[max_confidence_idx]
                        bbox_raw = boxes[i] # [x,y,w,h] or [x1,y1,x2,y2] depending on model
                        
                        # Convert [x,y,w,h] to [x1,y1,x2,y2] if necessary and normalize
                        # Assuming bbox_raw is already normalized [x_center, y_center, width, height]
                        x_center, y_center, width, height = bbox_raw
                        x1 = x_center - width / 2
                        y1 = y_center - height / 2
                        x2 = x_center + width / 2
                        y2 = y_center + height / 2
                        
                        detections.append({
                            "label": label,
                            "confidence": float(max_confidence),
                            "bbox": [float(x1), float(y1), float(x2), float(y2)]
                        })
            
            return detections
        except Exception as e:
            logger.error(f"Error during YOLO processing: {e}")
            return []

    async def process_image_for_vlm(self, image_data_b64: str, prompt: str) -> Dict[str, Any]:
        if not self.vlm_model:
            logger.warning("VLM model not loaded. Cannot perform captioning.")
            return {"description": "VLM model not loaded.", "confidence": 0.0}

        try:
            image_data = base64.b64decode(image_data_b64)
            image = Image.open(io.BytesIO(image_data)).convert("RGB")
            
            # FastVLM expects 1024x1024 input
            image = image.resize((1024, 1024))

            # CoreML model prediction
            # The input name 'images' is derived from the CoreML model's input features
            predictions = self.vlm_model.predict({"images": image})

            # Process predictions (this part is highly model-specific)
            # Assuming output is 'image_features' which needs to be processed by an LLM
            # This is a placeholder and needs to be adapted to the actual FastVLM CoreML output
            
            # The FastVLM CoreML model outputs image features, not directly a description.
            # These features would then be fed into an LLM (like Gemma) to generate the description.
            # For now, we'll return a placeholder description and confidence.
            
            # You would typically pass these image features to your LLM (Gemma) along with the text prompt.
            # This requires a more complex integration than just a single CoreML model call.
            
            logger.warning("FastVLM CoreML model outputs features, not direct description. LLM integration needed.")
            return {"description": "FastVLM features processed. LLM integration pending.", "confidence": 0.75}

        except Exception as e:
            logger.error(f"Error during VLM processing: {e}")
            return {"description": "Error during VLM processing", "confidence": 0.0}
            
    def get_model_health(self) -> Dict[str, bool]:
        """Returns the health status of loaded models."""
        return self.models_loaded

    def is_healthy(self) -> bool:
        if settings.PROCESSING_MODE == "full":
            return MLX_READY and self.models_loaded.get("gemma", False) and self.models_loaded.get("yolo", False) and self.models_loaded.get("vlm", False)
        else: # split mode
            return MLX_READY and self.models_loaded.get("gemma", False)
        
    async def cleanup(self) -> None:
        self.gemma_model = None
        self.gemma_tokenizer = None
        self.yolo_model = None
        self.vlm_model = None
        self.models_loaded = {"gemma": False, "yolo": False, "vlm": False}
        logger.info("Models cleaned up")

