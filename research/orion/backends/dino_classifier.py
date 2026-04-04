"""
DINOv2/v3 Backend for Full-Image Classification

This module provides context-aware classification using DINOv2/v3 features.
Unlike crop-based approaches (YOLO-World), this uses full-frame features
to classify objects with spatial context.

Key features:
- Full-frame feature extraction (no crop context loss)
- Patch-level feature pooling for object regions
- SentenceTransformer for text-to-visual matching
- Scene-aware label selection

Author: Orion Research Team
Date: January 2026
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# Lazy-loaded models
_dino_model = None
_dino_processor = None
_sentence_model = None
_scene_type_detector = None
_dinov3_classifier_cache: Dict[str, "DINOv3Classifier"] = {}


@dataclass
class DINOClassificationResult:
    """Result of DINOv3 classification."""
    original_class: str
    refined_class: str
    confidence: float
    all_candidates: List[Tuple[str, float]]
    source: str = "dino_fullimg"


# Scene-aware fine-grained label mappings
FINE_GRAINED_LABELS = {
    "chair": {
        "office": ["office chair", "desk chair", "swivel chair", "ergonomic chair"],
        "dining": ["dining chair", "kitchen chair", "wooden chair"],
        "living_room": ["armchair", "recliner", "accent chair", "lounge chair"],
        "bedroom": ["reading chair", "vanity chair", "bedroom chair"],
        "default": ["chair", "seat", "stool"],
    },
    "table": {
        "office": ["desk", "work desk", "computer desk", "writing desk"],
        "dining": ["dining table", "kitchen table", "eating table"],
        "living_room": ["coffee table", "side table", "end table", "console table"],
        "bedroom": ["nightstand", "bedside table", "dresser"],
        "default": ["table", "surface"],
    },
    "couch": {
        "living_room": ["sofa", "couch", "sectional", "loveseat", "settee"],
        "office": ["office sofa", "waiting room couch"],
        "default": ["couch", "sofa"],
    },
    "tv": {
        "office": ["monitor", "computer screen", "display", "desktop monitor"],
        "living_room": ["tv", "television", "flat screen tv", "smart tv"],
        "bedroom": ["bedroom tv", "wall-mounted tv"],
        "default": ["screen", "display", "monitor"],
    },
    "bed": {
        "bedroom": ["bed", "queen bed", "king bed", "twin bed", "mattress"],
        "default": ["bed"],
    },
    "refrigerator": {
        "kitchen": ["refrigerator", "fridge", "freezer"],
        "default": ["refrigerator"],
    },
    "person": {
        "default": ["person", "man", "woman", "human"],
    },
    "laptop": {
        "office": ["laptop", "notebook computer", "portable computer"],
        "bedroom": ["laptop", "notebook"],
        "default": ["laptop", "computer"],
    },
    "bottle": {
        "kitchen": ["bottle", "water bottle", "drink bottle", "beverage"],
        "office": ["water bottle", "drink"],
        "default": ["bottle", "container"],
    },
    "cup": {
        "kitchen": ["cup", "mug", "coffee cup", "tea cup"],
        "office": ["coffee mug", "cup"],
        "default": ["cup", "mug"],
    },
    "ball": {
        "default": ["ball", "sports ball", "toy ball", "soccer ball", "basketball", "tennis ball"],
    },
    "toy": {
        "default": ["toy", "teddy bear", "stuffed animal", "doll", "action figure"],
    },
    "bag": {
        "default": ["bag", "backpack", "handbag", "purse", "tote bag", "shopping bag"],
    },
    "bowl": {
        "kitchen": ["bowl", "mixing bowl", "serving bowl", "cereal bowl"],
        "default": ["bowl", "dish"],
    },
}


def get_dino_model(device: str = "mps"):
    """Lazy-load DINO model (prefers local DINOv3 if available)."""
    global _dino_model, _dino_processor
    
    if _dino_model is None:
        try:
            import torch
            from transformers import AutoModel, AutoImageProcessor
            
            # Check for local DINOv3 model first
            local_dinov3 = Path("models/dinov3-vitl16")
            if local_dinov3.exists():
                model_id = str(local_dinov3)
                logger.info(f"Loading local DINOv3 model: {model_id}")
            else:
                model_id = "facebook/dinov2-large"
                logger.info(f"Loading DINOv2 model (fallback): {model_id}")
            
            _dino_processor = AutoImageProcessor.from_pretrained(model_id)
            _dino_model = AutoModel.from_pretrained(model_id, trust_remote_code=True)
            
            # Move to device
            if device == "mps" and torch.backends.mps.is_available():
                _dino_model = _dino_model.to("mps")
            elif device == "cuda" and torch.cuda.is_available():
                _dino_model = _dino_model.to("cuda")
            else:
                _dino_model = _dino_model.to("cpu")
            
            _dino_model.eval()
            logger.info(f"✓ DINOv2 loaded on {device}")
            
        except Exception as e:
            logger.error(f"Failed to load DINOv2: {e}")
            return None, None
    
    return _dino_model, _dino_processor


def get_sentence_model():
    """Lazy-load SentenceTransformer for text matching."""
    global _sentence_model
    
    if _sentence_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            
            logger.info("Loading SentenceTransformer (all-mpnet-base-v2)...")
            _sentence_model = SentenceTransformer('sentence-transformers/all-mpnet-base-v2')
            logger.info("✓ SentenceTransformer loaded")
            
        except Exception as e:
            logger.error(f"Failed to load SentenceTransformer: {e}")
            return None
    
    return _sentence_model


def get_scene_type_detector() -> "SceneTypeDetector":
    """Return a cached SceneTypeDetector instance."""
    global _scene_type_detector
    if _scene_type_detector is None:
        _scene_type_detector = SceneTypeDetector()
    return _scene_type_detector


def get_dinov3_classifier(device: str = "mps", scene_aware: bool = True) -> "DINOv3Classifier":
    """Return a cached DINOv3Classifier for the requested device."""
    cache_key = f"{device}:{'scene' if scene_aware else 'nosce'}"
    cached = _dinov3_classifier_cache.get(cache_key)
    if cached is None:
        cached = DINOv3Classifier(device=device, scene_aware=scene_aware)
        _dinov3_classifier_cache[cache_key] = cached
    return cached


class DINOv3Classifier:
    """
    Full-image classifier using DINOv2/v3 features.
    
    Unlike crop-based approaches, this extracts features from the full frame
    and pools features for each detection region, preserving spatial context.
    """
    
    def __init__(
        self,
        device: str = "mps",
        scene_aware: bool = True,
    ):
        """
        Initialize DINOv3 classifier.
        
        Args:
            device: Device to run on ('mps', 'cuda', 'cpu')
            scene_aware: Use scene type for label selection
        """
        self.device = device
        self.scene_aware = scene_aware
        
        # Models loaded lazily
        self._dino_model = None
        self._dino_processor = None
        self._sentence_model = None
        
        # Precomputed embeddings cache
        self._label_embeddings_cache: Dict[str, np.ndarray] = {}
        
        logger.info(f"DINOv3Classifier initialized (device={device}, scene_aware={scene_aware})")
    
    def _ensure_models_loaded(self):
        """Ensure all models are loaded."""
        if self._dino_model is None:
            self._dino_model, self._dino_processor = get_dino_model(self.device)
        if self._sentence_model is None:
            self._sentence_model = get_sentence_model()
    
    def _get_fine_labels(self, coarse_class: str, scene_type: str = "default") -> List[str]:
        """Get fine-grained labels for a coarse class based on scene type."""
        coarse_lower = coarse_class.lower()
        
        if coarse_lower not in FINE_GRAINED_LABELS:
            return [coarse_class]
        
        labels_by_scene = FINE_GRAINED_LABELS[coarse_lower]
        
        if scene_type in labels_by_scene:
            return labels_by_scene[scene_type]
        else:
            return labels_by_scene.get("default", [coarse_class])
    
    def _get_label_embeddings(self, labels: List[str]) -> np.ndarray:
        """Get or compute text embeddings for labels."""
        # Check cache
        cache_key = "|".join(sorted(labels))
        if cache_key in self._label_embeddings_cache:
            return self._label_embeddings_cache[cache_key]
        
        # Compute embeddings
        if self._sentence_model is None:
            self._sentence_model = get_sentence_model()
        
        embeddings = self._sentence_model.encode(labels, convert_to_numpy=True)
        self._label_embeddings_cache[cache_key] = embeddings
        
        return embeddings
    
    def extract_frame_features(self, frame: Union[np.ndarray, Image.Image]) -> Dict[str, Any]:
        """
        Extract DINOv2 features from a full frame.
        
        Args:
            frame: Input frame (BGR numpy array or PIL Image)
            
        Returns:
            Dict with 'patch_features', 'cls_token', and metadata
        """
        self._ensure_models_loaded()
        
        if self._dino_model is None:
            return {"error": "DINOv2 model not available"}
        
        import torch
        
        # Convert to PIL if needed
        if isinstance(frame, np.ndarray):
            if frame.shape[-1] == 3:
                # Assume BGR
                import cv2
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            else:
                frame_rgb = frame
            pil_image = Image.fromarray(frame_rgb)
        else:
            pil_image = frame
        
        # Get frame dimensions
        width, height = pil_image.size
        
        # Process image
        inputs = self._dino_processor(images=pil_image, return_tensors="pt")
        
        # Move to device
        device = next(self._dino_model.parameters()).device
        inputs = {k: v.to(device) for k, v in inputs.items()}
        
        # Extract features
        with torch.no_grad():
            outputs = self._dino_model(**inputs)
        
        # Get features
        # last_hidden_state: [batch, num_patches + 1, hidden_dim]
        # First token is CLS, rest are patch tokens
        last_hidden = outputs.last_hidden_state[0]  # [num_patches + 1, hidden_dim]
        
        cls_token = last_hidden[0].cpu().numpy()  # [hidden_dim]
        patch_features = last_hidden[1:].cpu().numpy()  # [num_patches, hidden_dim]
        
        # Calculate patch grid dimensions
        # DINOv2 uses 14x14 patches on 518x518 or similar input
        num_patches = patch_features.shape[0]
        patch_grid_size = int(np.sqrt(num_patches))
        
        return {
            "cls_token": cls_token,
            "patch_features": patch_features,
            "patch_grid_size": patch_grid_size,
            "original_width": width,
            "original_height": height,
            "feature_dim": cls_token.shape[0],
        }
    
    def pool_region_features(
        self,
        frame_features: Dict[str, Any],
        bbox: List[float],
        pooling: str = "mean"
    ) -> np.ndarray:
        """
        Pool patch features for a bounding box region.
        
        Args:
            frame_features: Output from extract_frame_features()
            bbox: [x1, y1, x2, y2] in pixel coordinates
            pooling: 'mean', 'max', or 'cls' (use CLS token)
            
        Returns:
            Pooled feature vector
        """
        if "error" in frame_features:
            return np.zeros(1024)  # Default dim
        
        if pooling == "cls":
            return frame_features["cls_token"]
        
        patch_features = frame_features["patch_features"]
        patch_grid_size = frame_features["patch_grid_size"]
        orig_w = frame_features["original_width"]
        orig_h = frame_features["original_height"]
        
        # Convert bbox to patch coordinates
        x1, y1, x2, y2 = bbox
        
        # Normalize to [0, 1] then scale to patch grid
        px1 = int((x1 / orig_w) * patch_grid_size)
        py1 = int((y1 / orig_h) * patch_grid_size)
        px2 = int((x2 / orig_w) * patch_grid_size)
        py2 = int((y2 / orig_h) * patch_grid_size)
        
        # Clamp to valid range
        px1 = max(0, min(px1, patch_grid_size - 1))
        py1 = max(0, min(py1, patch_grid_size - 1))
        px2 = max(px1 + 1, min(px2, patch_grid_size))
        py2 = max(py1 + 1, min(py2, patch_grid_size))
        
        # Reshape patch features to grid
        patch_grid = patch_features.reshape(patch_grid_size, patch_grid_size, -1)
        
        # Extract region
        region_patches = patch_grid[py1:py2, px1:px2, :]  # [h, w, dim]
        
        if region_patches.size == 0:
            # Fallback to CLS token
            return frame_features["cls_token"]
        
        # Flatten and pool
        region_flat = region_patches.reshape(-1, region_patches.shape[-1])
        
        if pooling == "mean":
            return region_flat.mean(axis=0)
        elif pooling == "max":
            return region_flat.max(axis=0)
        else:
            return region_flat.mean(axis=0)
    
    def classify_detection(
        self,
        frame_features: Dict[str, Any],
        detection: Dict[str, Any],
        scene_type: str = "default",
        top_k: int = 3
    ) -> DINOClassificationResult:
        """
        Classify a detection using DINOv2 features + text matching.
        
        Args:
            frame_features: Output from extract_frame_features()
            detection: Detection dict with 'bbox', 'class_name', 'confidence'
            scene_type: Scene type for context-aware labels
            top_k: Number of top candidates to return
            
        Returns:
            DINOClassificationResult with refined class
        """
        self._ensure_models_loaded()
        
        original_class = detection.get("class_name", "object")
        bbox = detection.get("bbox") or detection.get("bbox_2d", [0, 0, 100, 100])
        
        # Get fine-grained label candidates
        if self.scene_aware:
            candidates = self._get_fine_labels(original_class, scene_type)
        else:
            candidates = self._get_fine_labels(original_class, "default")
        
        if len(candidates) <= 1:
            # No refinement available
            return DINOClassificationResult(
                original_class=original_class,
                refined_class=original_class,
                confidence=detection.get("confidence", 0.5),
                all_candidates=[(original_class, 1.0)],
                source="no_refinement"
            )
        
        # Pool region features
        region_features = self.pool_region_features(frame_features, bbox, pooling="mean")
        
        # Get text embeddings for candidates
        candidate_embeddings = self._get_label_embeddings(candidates)
        
        # Also get embedding for the visual description
        # We'll use the original class + "object" as a proxy
        visual_description = f"{original_class} object in scene"
        visual_embedding = self._sentence_model.encode([visual_description])[0]
        
        # Compute similarities
        from sentence_transformers import util
        import torch
        
        # Use text-to-text similarity (simplified approach)
        # A more sophisticated approach would train a projection from DINO space to text space
        visual_tensor = torch.tensor(visual_embedding)
        candidate_tensor = torch.tensor(candidate_embeddings)
        
        similarities = util.cos_sim(visual_tensor, candidate_tensor)[0].numpy()
        
        # Rank candidates
        ranked_indices = np.argsort(similarities)[::-1][:top_k]
        
        all_candidates = [
            (candidates[i], float(similarities[i])) 
            for i in ranked_indices
        ]
        
        best_class = candidates[ranked_indices[0]]
        best_confidence = float(similarities[ranked_indices[0]])
        
        return DINOClassificationResult(
            original_class=original_class,
            refined_class=best_class,
            confidence=best_confidence,
            all_candidates=all_candidates,
            source="dino_fullimg"
        )
    
    def classify_frame_detections(
        self,
        frame: Union[np.ndarray, Image.Image],
        detections: List[Dict[str, Any]],
        scene_type: str = "default"
    ) -> List[Dict[str, Any]]:
        """
        Classify all detections in a frame using full-image context.
        
        Args:
            frame: Input frame
            detections: List of detection dicts
            scene_type: Scene type for context-aware classification
            
        Returns:
            List of detections with 'refined_class' and 'refinement_confidence' added
        """
        if not detections:
            return detections
        
        # Extract frame features once
        frame_features = self.extract_frame_features(frame)
        
        if "error" in frame_features:
            logger.warning(f"Frame feature extraction failed: {frame_features['error']}")
            return detections
        
        # Classify each detection
        results = []
        for det in detections:
            classification = self.classify_detection(frame_features, det, scene_type)
            
            result = {
                **det,
                "refined_class": classification.refined_class,
                "refinement_confidence": classification.confidence,
                "refinement_candidates": classification.all_candidates,
                "refinement_source": classification.source,
            }
            results.append(result)
        
        return results

    def classify_crop(
        self,
        crop: Union[np.ndarray, Image.Image],
        coarse_class: str,
        scene_type: str = "default",
        top_k: int = 3
    ) -> DINOClassificationResult:
        """
        Classify a single crop directly (no full-frame context).
        
        This is a fallback for legacy code or when full frames are unavailable.
        """
        self._ensure_models_loaded()
        
        # Extract features from crop as if it were a frame
        features = self.extract_frame_features(crop)
        
        # Use the CLS token or mean pooling for classification of the crop
        # For a crop, we treat the whole thing as the region of interest
        detection = {
            "bbox": [0, 0, features["original_width"], features["original_height"]],
            "class_name": coarse_class
        }
        return self.classify_detection(
            features, 
            detection,
            scene_type,
            top_k
        )


# =====================================================================
# Scene Type Detection
# =====================================================================

class SceneTypeDetector:
    """
    Detect scene type from frame for context-aware classification.
    
    Uses SentenceTransformer to match frame caption against scene types.
    """
    
    SCENE_KEYWORDS = {
        "office": ["desk", "computer", "monitor", "keyboard", "office chair", "work", "cubicle"],
        "bedroom": ["bed", "pillow", "mattress", "nightstand", "dresser", "closet", "sleep"],
        "kitchen": ["stove", "refrigerator", "sink", "counter", "cabinet", "cooking", "kitchen"],
        "living_room": ["couch", "sofa", "tv", "coffee table", "living room", "fireplace"],
        "dining": ["dining table", "chairs", "eating", "meal", "dining room"],
        "bathroom": ["toilet", "sink", "shower", "bathtub", "mirror", "bathroom"],
        "hallway": ["hallway", "corridor", "door", "entrance", "passage"],
    }
    
    def __init__(self):
        self._model = None
        self._scene_embeddings = None
    
    def _ensure_loaded(self):
        if self._model is None:
            self._model = get_sentence_model()
            
            # Precompute scene embeddings
            scene_descriptions = []
            self._scene_names = []
            
            for scene_name, keywords in self.SCENE_KEYWORDS.items():
                description = f"{scene_name} with {', '.join(keywords)}"
                scene_descriptions.append(description)
                self._scene_names.append(scene_name)
            
            self._scene_embeddings = self._model.encode(scene_descriptions)
    
    def detect_scene_type(self, detected_objects: List[str]) -> Tuple[str, float]:
        """
        Detect scene type from list of detected object classes.
        
        Args:
            detected_objects: List of object class names
            
        Returns:
            Tuple of (scene_type, confidence)
        """
        self._ensure_loaded()
        
        if self._model is None or not detected_objects:
            return "default", 0.0
        
        # Create description from detected objects
        objects_text = ", ".join(detected_objects[:10])  # Limit to 10 objects
        query = f"scene containing {objects_text}"
        
        query_embedding = self._model.encode([query])[0]
        
        # Compute similarities
        from sentence_transformers import util
        import torch
        
        similarities = util.cos_sim(
            torch.tensor(query_embedding),
            torch.tensor(self._scene_embeddings)
        )[0].numpy()
        
        best_idx = np.argmax(similarities)
        best_scene = self._scene_names[best_idx]
        best_confidence = float(similarities[best_idx])
        
        return best_scene, best_confidence


# =====================================================================
# Integration Helper
# =====================================================================

def classify_detections_with_context(
    frame: Union[np.ndarray, Image.Image],
    detections: List[Dict[str, Any]],
    device: str = "mps"
) -> List[Dict[str, Any]]:
    """
    Convenience function to classify detections with full context.
    
    Args:
        frame: Input frame
        detections: List of detection dicts
        device: Device for inference
        
    Returns:
        List of detections with refined classes
    """
    # Detect scene type
    scene_detector = get_scene_type_detector()
    detected_classes = [d.get("class_name", "") for d in detections]
    scene_type, scene_conf = scene_detector.detect_scene_type(detected_classes)
    
    logger.debug(f"Detected scene type: {scene_type} (confidence: {scene_conf:.2f})")
    
    # Classify detections
    classifier = get_dinov3_classifier(device=device, scene_aware=True)
    refined_detections = classifier.classify_frame_detections(frame, detections, scene_type)
    
    # Add scene info to each detection
    for det in refined_detections:
        det["scene_type"] = scene_type
        det["scene_confidence"] = scene_conf
    
    return refined_detections
