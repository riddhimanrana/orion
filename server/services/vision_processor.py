import asyncio
import base64
import io
import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import numpy as np
from PIL import Image
import cv2

from models import Detection, FrameDataMessage
from services.model_manager import ModelManager
from utils.logger import get_logger
from config import settings

logger = get_logger(__name__)

# Add research/ to sys.path to enable importing the orion library
research_dir = Path(__file__).parent.parent.parent / "research"
if str(research_dir) not in sys.path:
    sys.path.append(str(research_dir))

# Attempt to import from the orion research package
try:
    from orion.perception import PerceptionEngine, PerceptionConfig, get_accurate_config
    from orion.perception.types import BoundingBox
    ORION_RESEARCH_AVAILABLE = True
    logger.info("Successfully imported orion perception modules from research.")
except ImportError as e:
    ORION_RESEARCH_AVAILABLE = False
    logger.warning(f"Could not import orion modules from research. Tracking will be mock-only. Error: {e}")


class VisionProcessor:
    """Handles vision processing, object detection, and Re-ID tracking."""
    
    def __init__(self, model_manager: ModelManager):
        self.model_manager = model_manager
        self.stats = {
            "frames_processed": 0,
            "total_detections": 0
        }
        self.engine: Optional[Any] = None
        self.is_initialized = False
        
    async def initialize(self) -> None:
        """Initialize the real Orion PerceptionEngine if available."""
        if self.is_initialized:
            return
            
        if ORION_RESEARCH_AVAILABLE:
            try:
                # Load theExtra Large YOLO26x balanced config
                config = get_accurate_config()
                # Disable 3D SLAM / depth mapping on live websocket thread to minimize latency
                config.enable_3d = False
                config.enable_hands = False
                
                # Initialize Orion PerceptionEngine (which manages weights and model loadings)
                self.engine = PerceptionEngine(config=config)
                logger.info("Orion PerceptionEngine and tracker successfully initialized.")
            except Exception as e:
                logger.error(f"Failed to instantiate Orion PerceptionEngine: {e}")
                self.engine = None
        else:
            logger.info("Orion research package not available. Using mock vision processor.")
            
        self.is_initialized = True
        logger.info("Vision processor ready")
        
    async def analyze_frame(self, frame: FrameDataMessage) -> Dict[str, Any]:
        """Analyzes a frame using YOLO detection, V-JEPA2 embedding, and Re-ID tracking."""
        try:
            detections: List[Detection] = []
            vlm_description: Optional[str] = None
            
            # Resolve frame index and timestamp
            frame_number = 0
            if frame.frame_id:
                try:
                    # Parse numeric frame index if possible
                    frame_number = int(frame.frame_id.split('_')[-1])
                except ValueError:
                    try:
                        frame_number = int(frame.frame_id)
                    except ValueError:
                        frame_number = self.stats["frames_processed"]
                        
            timestamp = frame.timestamp if frame.timestamp else 0.0

            if settings.PROCESSING_MODE == "full":
                if not frame.image_data:
                    raise ValueError("Image data is required for full processing mode.")
                
                # Decode base64 image data
                image_bytes = base64.b64decode(frame.image_data)
                pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
                frame_width, frame_height = pil_image.size
                
                # Convert PIL image to BGR numpy array for OpenCV/YOLO
                bgr_frame = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)

                if self.engine is not None:
                    # 1. Run YOLO/Hybrid detector via FrameObserver
                    loop = asyncio.get_event_loop()
                    raw_detections = await loop.run_in_executor(
                        None,
                        self.engine.observer.detect_objects,
                        bgr_frame,
                        frame_number,
                        timestamp,
                        frame_width,
                        frame_height
                    )
                    
                    # 2. Extract V-JEPA2 appearance embeddings for Re-ID
                    if raw_detections and self.engine.embedder:
                        raw_detections = await loop.run_in_executor(
                            None,
                            self.engine.embedder.embed_detections,
                            raw_detections
                        )
                        
                    # 3. Update EnhancedTracker with 2D/3D boxes and embeddings
                    active_tracks = []
                    if raw_detections and self.engine.enhanced_tracker:
                        converted, embs = self.engine._convert_for_enhanced_tracker(raw_detections)
                        active_tracks = await loop.run_in_executor(
                            None,
                            self.engine.enhanced_tracker.update,
                            converted,
                            embs,
                            None,  # Camera pose omitted
                            frame_number
                        )
                    
                    # Map tracks back to response detections
                    if active_tracks:
                        for track in active_tracks:
                            td = track.to_dict()
                            detections.append(Detection(
                                label=td.get("class_name", "object"),
                                confidence=td.get("confidence", 0.0),
                                bbox=td.get("bbox_2d", [0, 0, 0, 0]),
                                track_id=td.get("track_id")
                            ))
                    else:
                        # Fallback to raw detections if tracking hasn't confirmed hits yet (min_hits threshold)
                        for d in raw_detections:
                            detections.append(Detection(
                                label=d.get("class_name", d.get("object_class", "object")),
                                confidence=d.get("confidence", 0.0),
                                bbox=d.get("bbox", [0, 0, 0, 0]),
                                track_id=None
                            ))
                else:
                    # Fallback mockup if PerceptionEngine failed to load
                    await asyncio.sleep(0.1)
                    yolo_results = await self.model_manager.process_image_for_yolo(frame.image_data)
                    detections = [Detection(**d) for d in yolo_results]

                # 4. Generate scene description using FastVLM
                vlm_prompt = self._build_vlm_prompt(detections)
                await asyncio.sleep(0.1) # Yield thread
                vlm_results = await self.model_manager.process_image_for_vlm(frame.image_data, vlm_prompt)
                vlm_description = vlm_results.get("description")

                logger.info(f"Server-side Detections (with Re-ID tracking) Count: {len(detections)}")
                logger.info(f"Server-side VLM Description: {vlm_description}")

            else:  # Split mode (detections and VLM done on iOS client)
                detections = frame.detections or []
                vlm_description = frame.vlm_description or ""
                
                logger.info(f"Received iOS Detections Count: {len(detections)}")
                logger.info(f"Received iOS VLM Description: {vlm_description}")
            
            detection_info = [f"{d.label} (ID: {d.track_id if d.track_id is not None else 'None'})" for d in detections]
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
                
            logger.info(f"Vision analysis complete for frame {frame.frame_id}. Detections count: {len(detections)}.")
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing frame {frame.frame_id}: {e}")
            import traceback
            logger.error(traceback.format_exc())
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
        if self.engine is not None:
            return True
        return self.model_manager.is_healthy()
        
    async def cleanup(self) -> None:
        self.stats = {
            "frames_processed": 0,
            "total_detections": 0
        }
        self.engine = None
        self.is_initialized = False