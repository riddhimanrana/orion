import asyncio
from typing import Dict, Any, List, Optional

from models import Detection, FrameDataMessage
from services.model_manager import ModelManager
from utils.logger import get_logger
from config import settings

logger = get_logger(__name__)

class VisionProcessor:
    """Handles vision processing and scene understanding."""
    
    def __init__(self, model_manager: ModelManager):
        self.model_manager = model_manager
        self.stats = {
            "frames_processed": 0,
            "total_detections": 0
        }
        
    async def initialize(self) -> None:
        logger.info("Vision processor ready")
        
    async def analyze_frame(self, frame: FrameDataMessage) -> Dict[str, Any]:
        try:
            detections: List[Detection] = []
            vlm_description: Optional[str] = None
            vlm_confidence: Optional[float] = None

            if settings.PROCESSING_MODE == "full":
                if not frame.image_data:
                    raise ValueError("Image data is required for full processing mode.")
                
                # Simulate YOLO processing delay
                await asyncio.sleep(0.1)
                yolo_results = await self.model_manager.process_image_for_yolo(frame.image_data)
                detections = [Detection(**d) for d in yolo_results]

                # The prompt for VLM is now dynamic and based on the YOLO detections
                vlm_prompt = self._build_vlm_prompt(detections)
                
                # Simulate VLM processing delay
                await asyncio.sleep(1.0)
                vlm_results = await self.model_manager.process_image_for_vlm(frame.image_data, vlm_prompt)
                vlm_description = vlm_results.get("description")
                

                logger.info(f"Server-side YOLO Detections Count: {len(detections)}")
                logger.info(f"Server-side VLM Description: {vlm_description}")

            else: # split mode
                detections = frame.detections or []
                vlm_description = frame.vlm_description or ""
                
                logger.info(f"Received iOS YOLO Detections Count: {len(detections)}")
                logger.info(f"Received iOS VLM Description: {vlm_description}")
            
            detection_info = [f"{d.label} ({d.confidence:.2f})" for d in detections]
            logger.debug(f"Detections: {', '.join(detection_info)}")
            
            analysis = {
                "description": vlm_description,
                "detections": [self._enhance_detection(d) for d in detections],
                "scene_features": [],
                "ios_frame_summary": {
                    "image_data": frame.image_data
                },
                "error": None
            }
                
            self.stats["frames_processed"] += 1
            if detections:
                self.stats["total_detections"] += len(detections)
                
            logger.info(f"Vision analysis complete for frame {frame.frame_id}. Detections count: {len(detections)}. VLM Description: {vlm_description}")
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing frame {frame.frame_id}: {e}")
            return {
                "description": "Error processing frame",
                "detections": [],
                "scene_features": [],
                "error": str(e)
            }

    def _build_vlm_prompt(self, detections: List[Detection]) -> str:
        """Builds a concise prompt for the VLM based on YOLO detections."""
        if not detections:
            return "Describe the scene briefly."
        
        labels = [det.label for det in detections]
        return f"Describe the scene containing: {', '.join(labels)}. Be concise."
            
    def _enhance_detection(self, detection: Detection) -> Dict[str, Any]:
        return {
            "label": detection.label,
            "confidence": detection.confidence,
            "bbox": detection.bbox,
            "track_id": detection.track_id,
            "category": self._get_category(detection.label),
            "is_moving": detection.track_id is not None
        }
        
    def _get_category(self, label: str) -> str:
        categories = {
            "person": "human", "car": "vehicle", "truck": "vehicle", "bus": "vehicle",
            "chair": "furniture", "table": "furniture", "dog": "animal", "cat": "animal"
        }
        return categories.get(label.lower(), "object")
        
    def get_stats(self) -> Dict[str, Any]:
        return {
            "frames_processed": self.stats["frames_processed"],
            "total_detections": self.stats["total_detections"],
            "average_detections_per_frame": (
                self.stats["total_detections"] / self.stats["frames_processed"]
                if self.stats["frames_processed"] > 0 else 0
            )
        }
        
    def is_healthy(self) -> bool:
        return self.model_manager.is_healthy()
        
    async def cleanup(self) -> None:
        self.stats = {
            "frames_processed": 0,
            "total_detections": 0
        }