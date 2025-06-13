"""Vision processing service using MLX."""
from typing import Dict, Any, List

from models import DetectionFrame, Detection
from services.model_manager import ModelManager
from utils.logger import get_logger

logger = get_logger(__name__)

class VisionProcessor:
    """Handles vision processing and scene understanding."""
    
    def __init__(self, model_manager: ModelManager):
        """
        Initialize vision processor.
        
        Args:
            model_manager: MLX model manager instance
        """
        self.model_manager = model_manager
        self.stats = {
            "frames_processed": 0,
            "total_detections": 0,
            "average_confidence": 0.0
        }
        logger.info("VisionProcessor initialized")
        
    async def initialize(self) -> None:
        """Initialize vision processing."""
        logger.info("Vision processor ready")
        
    async def analyze_frame(self, frame: DetectionFrame) -> Dict[str, Any]:
        """
        Analyze a frame with iOS detections.
        
        Args:
            frame: Frame data with iOS YOLOv11n detections
            
        Returns:
            Enhanced analysis results
        """
        try:
            # Log received detections from iOS
            detection_info = [f"{d.label} ({d.confidence:.2f})" for d in frame.detections]
            logger.debug(f"iOS detections: {', '.join(detection_info)}")
            
            # Get enhanced understanding from MLX models
            if frame.image_data:
                # Get VLM analysis
                vision_result = await self.model_manager.process_vision(frame.image_data)
                
                # Combine iOS detections with MLX understanding
                analysis = {
                    "description": vision_result["description"],
                    "confidence": vision_result["confidence"],
                    "detections": [self._enhance_detection(d) for d in frame.detections],
                    "scene_features": vision_result.get("features", []),
                    "error": None
                }
                
            else:
                # No image data, just use iOS detections
                analysis = {
                    "description": self._generate_description(frame.detections),
                    "confidence": sum(d.confidence for d in frame.detections) / len(frame.detections) if frame.detections else 0.0,
                    "detections": [self._enhance_detection(d) for d in frame.detections],
                    "scene_features": [],
                    "error": "No image data available"
                }
                
            # Update stats
            self.stats["frames_processed"] += 1
            if frame.detections:
                self.stats["total_detections"] += len(frame.detections)
                self.stats["average_confidence"] = (
                    (self.stats["average_confidence"] * (self.stats["frames_processed"] - 1) + 
                    analysis["confidence"]) / self.stats["frames_processed"]
                )
                
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing frame {frame.frame_id}: {e}")
            return {
                "description": "Error processing frame",
                "confidence": 0.0,
                "detections": [],
                "scene_features": [],
                "error": str(e)
            }
            
    def _enhance_detection(self, detection: Detection) -> Dict[str, Any]:
        """Enhance a single detection with additional info."""
        return {
            "label": detection.label,
            "confidence": detection.confidence,
            "bbox": detection.bbox,
            "track_id": detection.track_id,
            # Add any additional enhancements
            "category": self._get_category(detection.label),
            "is_moving": detection.track_id is not None
        }
        
    def _get_category(self, label: str) -> str:
        """Map detection label to category."""
        categories = {
            "person": "human",
            "car": "vehicle",
            "truck": "vehicle",
            "bus": "vehicle",
            "chair": "furniture",
            "table": "furniture",
            "dog": "animal",
            "cat": "animal"
        }
        return categories.get(label.lower(), "object")
        
    def _generate_description(self, detections: List[Detection]) -> str:
        """Generate basic description from detections."""
        if not detections:
            return "No objects detected"
            
        # Count objects by category
        categories: Dict[str, int] = {}
        for det in detections:
            cat = self._get_category(det.label)
            categories[cat] = categories.get(cat, 0) + 1
            
        # Generate description
        parts = []
        for cat, count in categories.items():
            parts.append(f"{count} {cat}{'s' if count > 1 else ''}")
            
        return "Scene contains " + ", ".join(parts)
        
    def get_stats(self) -> Dict[str, Any]:
        """Get processing statistics."""
        return {
            "frames_processed": self.stats["frames_processed"],
            "total_detections": self.stats["total_detections"],
            "average_confidence": self.stats["average_confidence"],
            "average_detections_per_frame": (
                self.stats["total_detections"] / self.stats["frames_processed"]
                if self.stats["frames_processed"] > 0 else 0
            )
        }
        
    def is_healthy(self) -> bool:
        """Check if processor is healthy."""
        return self.model_manager.is_healthy()
        
    async def cleanup(self) -> None:
        """Cleanup processor resources."""
        self.stats = {
            "frames_processed": 0,
            "total_detections": 0,
            "average_confidence": 0.0
        }
        logger.info("Vision processor cleaned up")