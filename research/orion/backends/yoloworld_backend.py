"""
YOLO-World Backend for Orion v2

Open-vocabulary object detection using YOLO-World v2.
Enables detection of any object class via text prompts without retraining.

Key features:
- "Prompt-then-detect" strategy
- Custom class vocabulary per domain
- Offline vocabulary caching for efficiency
"""

import logging
from pathlib import Path
from typing import Optional, Union
from dataclasses import dataclass, field
import numpy as np

logger = logging.getLogger(__name__)


# Default class vocabulary: COARSE prompts only to avoid prompt collapse.
# For fine-grained labeling, use the candidate-label pipeline (CLIP-based).
# The legacy large vocabulary is kept in LEGACY_INDOOR_CLASSES for research.
DEFAULT_CLASSES = [
    # Coarse, stable super-categories
    "person", "face", "hand",
    "container", "bottle", "cup",
    "bag", "box",
    "furniture", "table", "chair",
    "electronic device", "phone", "laptop",
    "door", "window",
    "text",
    "",  # Background class per Ultralytics guidance
]

# Legacy vocabulary (~100 classes) retained for ablation/research only.
# Do NOT use as default; causes prompt collapse + noisy semantics.
LEGACY_INDOOR_CLASSES = [
    "person", "face", "hand", "feet",
    "chair", "armchair", "office chair", "stool", "ottoman", "couch", "sofa", "bench",
    "table", "coffee table", "dining table", "side table", "desk", "kitchen island", "counter", "nightstand", "dresser",
    "cabinet", "shelf", "drawer", "bed",
    "pillow", "cushion", "blanket", "rug", "carpet", "mat", "curtain", "blinds",
    "laptop", "closed laptop", "computer", "desktop computer", "monitor", "computer screen", "television", "tv screen",
    "keyboard", "mouse", "mousepad", "camera", "speaker", "bluetooth speaker", "headphones", "earbuds",
    "phone", "smartphone", "remote", "cable", "wire", "power cord",
    "microwave", "refrigerator", "sink", "oven", "stove", "toaster", "coffee maker",
    "cup", "mug", "glass", "bottle", "water bottle", "plate", "bowl", "fork", "spoon", "knife", "pan", "pot", "kettle",
    "food", "fruit", "bread",
    "piano", "piano book", "sheet music",
    "book", "textbook", "notebook", "notepad", "paper", "document", "pen", "pencil",
    "backpack", "bag", "purse", "box", "key",
    "lamp", "table lamp", "floor lamp", "ceiling light", "ceiling fan", "chandelier", "light fixture",
    "plant", "potted plant", "vase", "picture", "picture frame", "painting", "artwork", "clock", "mirror", "decoration",
    "doorway", "hallway", "window", "door", "wall", "floor", "ceiling", "staircase", "stairs", "railing", "fireplace", "baseboard",
    "",
]


@dataclass
class YOLOWorldConfig:
    """Configuration for YOLO-World detector."""
    
    model: str = "yolov8x-worldv2"  # Largest model for best quality
    classes: list[str] = field(default_factory=lambda: DEFAULT_CLASSES.copy())
    confidence: float = 0.25
    iou_threshold: float = 0.45
    max_detections: int = 100
    image_size: int = 640
    device: str = "cuda"
    
    # Offline vocabulary (for speed)
    save_custom_model: bool = False
    custom_model_path: Optional[str] = None


class YOLOWorldDetector:
    """
    YOLO-World open-vocabulary object detector.
    
    .. deprecated::
        Use `orion.managers.model_manager.ModelManager.yoloworld` instead.
        This standalone class is kept for backward compatibility and research
        scripts, but the canonical path uses coarse defaults to prevent prompt
        collapse. If you need the legacy ~100 class vocabulary, pass
        `YOLOWorldConfig(classes=LEGACY_INDOOR_CLASSES.copy())`.
    """
    
    def __init__(self, config: Optional[YOLOWorldConfig] = None):
        import warnings
        warnings.warn(
            "YOLOWorldDetector is deprecated; prefer ModelManager.yoloworld for pipeline runs. "
            "Default class list is now coarse (~17 classes) to prevent prompt collapse.",
            DeprecationWarning,
            stacklevel=2,
        )
        self.config = config or YOLOWorldConfig()
        self._model = None
        self._loaded = False
    
    def _ensure_loaded(self):
        """Lazy load model on first use."""
        if self._loaded:
            return
        
        logger.info(f"Loading YOLO-World: {self.config.model}")
        
        try:
            from ultralytics import YOLOWorld
            
            # Check for custom cached model
            if self.config.custom_model_path and Path(self.config.custom_model_path).exists():
                logger.info(f"Loading cached custom model: {self.config.custom_model_path}")
                self._model = YOLOWorld(self.config.custom_model_path)
            else:
                # Load base model - handle .pt extension
                model_name = self.config.model
                if not model_name.endswith('.pt'):
                    model_name = f"{model_name}.pt"
                self._model = YOLOWorld(model_name)
                
                # Move model to device BEFORE setting classes
                # This ensures CLIP text encoding runs on GPU
                logger.info(f"Moving model to {self.config.device}")
                self._model.to(self.config.device)
                
                # Set custom classes (now on GPU for fast CLIP encoding)
                logger.info(f"Setting {len(self.config.classes)} custom classes")
                self._model.set_classes(self.config.classes)
                
                # Optionally save for faster future loading
                if self.config.save_custom_model and self.config.custom_model_path:
                    logger.info(f"Saving custom model to: {self.config.custom_model_path}")
                    self._model.save(self.config.custom_model_path)
            
            self._loaded = True
            logger.info(f"✓ YOLO-World loaded ({len(self.config.classes)} classes)")
            
        except Exception as e:
            logger.error(f"Failed to load YOLO-World: {e}")
            raise
    
    @property
    def class_names(self) -> list[str]:
        """Get the current class vocabulary."""
        return self.config.classes
    
    def set_classes(self, classes: list[str]):
        """
        Update the detection vocabulary.
        
        This is a key feature of YOLO-World: you can change what
        objects to detect without retraining.
        """
        self.config.classes = classes
        if self._loaded:
            self._model.set_classes(classes)
            logger.info(f"Updated vocabulary: {len(classes)} classes")
    
    def detect(
        self, 
        image: Union[np.ndarray, str, Path],
        confidence: Optional[float] = None,
        classes: Optional[list[str]] = None
    ) -> list[dict]:
        """
        Detect objects in an image.
        
        Args:
            image: Image as numpy array, file path, or URL
            confidence: Override confidence threshold
            classes: Override class vocabulary for this detection
            
        Returns:
            List of detection dicts with keys:
            - bbox: [x1, y1, x2, y2] in pixel coordinates
            - confidence: float 0-1
            - class_id: int
            - label: str class name
        """
        self._ensure_loaded()
        
        # Temporarily set classes if provided
        if classes is not None:
            self._model.set_classes(classes)
        
        # Run inference
        results = self._model.predict(
            source=image,
            conf=confidence or self.config.confidence,
            iou=self.config.iou_threshold,
            max_det=self.config.max_detections,
            imgsz=self.config.image_size,
            device=self.config.device,
            verbose=False
        )
        
        # Restore original classes if we changed them
        if classes is not None:
            self._model.set_classes(self.config.classes)
        
        # Parse results
        detections = []
        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue
            
            for i in range(len(boxes)):
                bbox = boxes.xyxy[i].cpu().numpy().tolist()
                conf = float(boxes.conf[i].cpu())
                cls_id = int(boxes.cls[i].cpu())
                
                # Get class name from vocabulary
                # Note: YOLO-World uses the custom classes we set
                try:
                    label = self.config.classes[cls_id] if classes is None else classes[cls_id]
                except IndexError:
                    label = f"class_{cls_id}"
                
                detections.append({
                    "bbox": bbox,
                    "confidence": conf,
                    "class_id": cls_id,
                    "label": label
                })
        
        return detections
    
    def detect_video(
        self,
        video_path: Union[str, Path],
        fps: float = 5.0,
        confidence: Optional[float] = None
    ):
        """
        Generator that yields detections for each sampled frame.
        
        Args:
            video_path: Path to video file
            fps: Target FPS for sampling
            confidence: Override confidence threshold
            
        Yields:
            Tuple of (frame_id, frame_image, detections)
        """
        import cv2
        
        self._ensure_loaded()
        
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")
        
        video_fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        sample_interval = int(video_fps / fps)
        
        logger.info(f"Video: {video_fps:.1f} FPS, {total_frames} frames, sampling every {sample_interval}")
        
        frame_id = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            if frame_id % sample_interval == 0:
                # Convert BGR to RGB
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # Detect
                detections = self.detect(frame_rgb, confidence=confidence)
                
                yield frame_id, frame_rgb, detections
            
            frame_id += 1
        
        cap.release()
    
    def track(
        self,
        video_path: Union[str, Path],
        tracker: str = "bytetrack.yaml"
    ):
        """
        Run tracking on video using YOLO-World with built-in tracker.
        
        Note: This uses YOLO's built-in tracking, which may differ from
        our custom tracker. Consider using this for comparison.
        """
        self._ensure_loaded()
        
        results = self._model.track(
            source=str(video_path),
            conf=self.config.confidence,
            iou=self.config.iou_threshold,
            tracker=tracker,
            device=self.config.device,
            stream=True,
            verbose=False
        )
        
        for frame_id, result in enumerate(results):
            if result.boxes is None:
                yield frame_id, []
                continue
            
            tracks = []
            boxes = result.boxes
            
            for i in range(len(boxes)):
                track_id = int(boxes.id[i].cpu()) if boxes.id is not None else -1
                bbox = boxes.xyxy[i].cpu().numpy().tolist()
                conf = float(boxes.conf[i].cpu())
                cls_id = int(boxes.cls[i].cpu())
                
                try:
                    label = self.config.classes[cls_id]
                except IndexError:
                    label = f"class_{cls_id}"
                
                tracks.append({
                    "track_id": track_id,
                    "bbox": bbox,
                    "confidence": conf,
                    "class_id": cls_id,
                    "label": label
                })
            
            yield frame_id, tracks


# Preset class vocabularies for different domains
PRESETS = {
    "indoor": DEFAULT_CLASSES,
    
    "kitchen": [
        "person", "hand",
        "cup", "mug", "glass", "bottle", "plate", "bowl", 
        "fork", "spoon", "knife", "pan", "pot",
        "microwave", "refrigerator", "oven", "toaster", "blender",
        "sink", "faucet", "counter", "cabinet", "drawer",
        "food", "fruit", "vegetable", "bread", "cheese",
        ""
    ],
    
    "office": [
        "person", "face", "hand",
        "laptop", "computer", "monitor", "keyboard", "mouse",
        "phone", "cellphone", "headphones",
        "desk", "chair", "table",
        "book", "notebook", "pen", "paper", "document",
        "coffee cup", "water bottle",
        ""
    ],
    
    "living_room": [
        "person", "face",
        "couch", "sofa", "chair", "table", "tv", "television",
        "remote", "controller", "lamp", "pillow", "blanket",
        "book", "magazine", "phone", "glass", "cup",
        ""
    ],
    
    "minimal": [
        "person", "object", "furniture", "electronic device", "container",
        ""
    ]
}


def get_preset_classes(preset: str) -> list[str]:
    """Get class vocabulary for a preset domain."""
    if preset not in PRESETS:
        raise ValueError(f"Unknown preset: {preset}. Available: {list(PRESETS.keys())}")
    return PRESETS[preset].copy()
