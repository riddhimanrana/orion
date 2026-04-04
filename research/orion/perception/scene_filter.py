"""
Scene-Based Semantic Filter for Orion v2

Uses CLIP text embeddings to filter detections based on scene context.
This replaces the expensive per-crop VLM approach with a more efficient
scene-to-label similarity check.

The key insight: We run VLM once on the whole scene to get a caption,
then use CLIP to compare detection labels against the scene embedding.
Objects that don't semantically fit the scene (e.g., "refrigerator" in
an office scene) get filtered out.

Author: Orion Research Team
Date: January 2026
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any

import numpy as np

logger = logging.getLogger(__name__)

# Lazy-loaded models
_clip_model = None
_clip_processor = None


def get_clip_text_encoder(device: str = "cuda"):
    """Lazy-load CLIP model for text embedding.
    
    Uses openai/clip-vit-base-patch32 which gives 512-dim embeddings.
    Only loads the text encoder to minimize memory usage.
    """
    global _clip_model, _clip_processor
    
    if _clip_model is None:
        try:
            import torch
            from transformers import CLIPProcessor, CLIPModel
            
            logger.info("Loading CLIP for scene-based filtering...")
            _clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
            _clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
            
            # Move to device
            if device != "cpu" and torch.cuda.is_available():
                _clip_model = _clip_model.to(device)
            
            logger.info(f"✓ CLIP loaded on {device}")
        except ImportError as e:
            logger.warning(f"CLIP not available: {e}")
            return None, None
    
    return _clip_model, _clip_processor


@dataclass
class SceneFilterConfig:
    """Configuration for scene-based semantic filtering."""
    
    # Similarity thresholds
    min_similarity: float = 0.56
    """Minimum scene-to-label similarity to keep detection.
    Based on empirical testing (validated with Gemini):
    - 0.56+ = likely fits the scene (monitor=0.698, keyboard=0.638)
    - 0.50-0.56 = ambiguous (refrigerator=0.549 was false positive)
    - <0.50 = likely doesn't fit (toothbrush=0.477)
    """
    
    soft_threshold: float = 0.50
    """Soft threshold for borderline cases (requires higher confidence)."""
    
    soft_min_confidence: float = 0.5
    """Minimum detection confidence for soft-threshold cases."""
    
    # Label expansion
    expand_labels: bool = True
    """Expand labels for better matching (e.g., 'chair' -> 'a chair')."""
    
    # Semantic aliases for COCO labels that often mismatch scene descriptions
    use_semantic_aliases: bool = True
    """Use semantic aliases for better matching (e.g., 'tv' -> 'monitor')."""
    
    # Caching
    cache_embeddings: bool = True
    """Cache label embeddings to avoid recomputing."""
    
    # Device
    device: str = "cuda"
    """Device for CLIP inference."""


# Semantic aliases: COCO label -> scene-relevant alternatives
# These are common COCO labels that may semantically match other scene terms
SEMANTIC_ALIASES = {
    # Displays
    "tv": ["monitor", "screen", "display"],
    "laptop": ["computer", "notebook"],
    
    # Furniture
    "dining table": ["desk", "table", "work surface"],
    "couch": ["sofa", "settee"],
    "bed": ["mattress"],
    
    # Office items
    "keyboard": ["computer keyboard"],
    "mouse": ["computer mouse"],
    "cell phone": ["phone", "smartphone", "mobile"],
    
    # Storage
    "refrigerator": ["fridge", "cabinet"],  # Note: cabinet is a common false positive
    "oven": ["stove", "range"],
    "microwave": ["microwave oven"],
    
    # Containers
    "bottle": ["water bottle", "drink"],
    "cup": ["mug", "glass"],
    "bowl": ["dish"],
    
    # Seating
    "chair": ["office chair", "seat"],
}


class SceneFilter:
    """
    Filters detections based on semantic similarity to scene context.
    
    This is more efficient than per-crop VLM because:
    1. Scene caption generated once per scene change
    2. Label embeddings are cached and reused
    3. Similarity computation is fast (dot product)
    
    Usage:
        filter = SceneFilter()
        filter.set_scene("A desk with a computer monitor and keyboard")
        
        # Filter detections
        for det in detections:
            is_valid, score = filter.check_detection(det["object_class"])
            if not is_valid:
                det["scene_filtered"] = True
    """
    
    def __init__(self, config: Optional[SceneFilterConfig] = None):
        self.config = config or SceneFilterConfig()
        self._clip_model = None
        self._clip_processor = None
        self._scene_embedding: Optional[np.ndarray] = None
        self._scene_caption: str = ""
        self._label_cache: Dict[str, np.ndarray] = {}
        
    def _ensure_clip(self) -> bool:
        """Ensure CLIP is loaded."""
        if self._clip_model is None:
            self._clip_model, self._clip_processor = get_clip_text_encoder(self.config.device)
        return self._clip_model is not None
    
    def _embed_text(self, text: str) -> Optional[np.ndarray]:
        """Embed text using CLIP.
        
        Args:
            text: Text to embed.
            
        Returns:
            512-dim normalized embedding, or None if failed.
        """
        if not self._ensure_clip():
            return None
        
        try:
            import torch
            
            with torch.no_grad():
                inputs = self._clip_processor(
                    text=[text], 
                    return_tensors="pt", 
                    padding=True, 
                    truncation=True
                )
                
                # Move to device
                device = next(self._clip_model.parameters()).device
                inputs = {k: v.to(device) for k, v in inputs.items()}
                
                emb = self._clip_model.get_text_features(**inputs)
                emb = emb / emb.norm(dim=-1, keepdim=True)
                
                return emb.cpu().numpy().flatten()
        except Exception as e:
            logger.warning(f"CLIP embedding failed: {e}")
            return None
    
    def set_scene(self, caption: str) -> bool:
        """Set the current scene context from a caption.
        
        Args:
            caption: Scene description (e.g., from VLM).
            
        Returns:
            True if scene was set successfully.
        """
        if not caption or not caption.strip():
            logger.warning("Empty scene caption")
            return False
        
        self._scene_caption = caption.strip()
        self._scene_embedding = self._embed_text(self._scene_caption)
        
        if self._scene_embedding is not None:
            logger.info(f"Scene filter set: '{self._scene_caption[:60]}...'")
            return True
        return False
    
    def get_label_embedding(self, label: str) -> Optional[np.ndarray]:
        """Get embedding for a label (cached).
        
        Args:
            label: Object label (e.g., "chair").
            
        Returns:
            512-dim embedding, or None if failed.
        """
        if self.config.cache_embeddings and label in self._label_cache:
            return self._label_cache[label]
        
        # Expand label for better matching
        if self.config.expand_labels:
            text = f"a {label}"
        else:
            text = label
        
        emb = self._embed_text(text)
        
        if self.config.cache_embeddings and emb is not None:
            self._label_cache[label] = emb
        
        return emb
    
    def compute_similarity(self, label: str) -> float:
        """Compute similarity between a label and the current scene.
        
        Uses semantic aliases to find the best matching term.
        For example, "tv" might match better as "monitor" in an office scene.
        
        Args:
            label: Object label to check.
            
        Returns:
            Cosine similarity score (0-1), or 0.5 if no scene set.
        """
        if self._scene_embedding is None:
            return 0.5  # No scene context, neutral score
        
        # Get base similarity for the raw label
        label_emb = self.get_label_embedding(label)
        if label_emb is None:
            return 0.5
        
        best_sim = float(np.dot(self._scene_embedding, label_emb))
        
        # Try semantic aliases if enabled
        if self.config.use_semantic_aliases and label in SEMANTIC_ALIASES:
            for alias in SEMANTIC_ALIASES[label]:
                alias_emb = self.get_label_embedding(alias)
                if alias_emb is not None:
                    alias_sim = float(np.dot(self._scene_embedding, alias_emb))
                    if alias_sim > best_sim:
                        best_sim = alias_sim
        
        return best_sim
    
    def check_detection(
        self,
        label: str,
        confidence: float = 0.5,
    ) -> Tuple[bool, float, str]:
        """Check if a detection should be kept based on scene context.
        
        Args:
            label: Detection label.
            confidence: Detection confidence.
            
        Returns:
            Tuple of (is_valid, similarity, reason).
        """
        if self._scene_embedding is None:
            return True, 0.5, "no_scene_context"
        
        similarity = self.compute_similarity(label)
        
        # High similarity = definitely keep
        if similarity >= self.config.min_similarity:
            return True, similarity, "fits_scene"
        
        # Soft threshold: keep if confidence is high enough
        if similarity >= self.config.soft_threshold and confidence >= self.config.soft_min_confidence:
            return True, similarity, "borderline_high_conf"
        
        # Low similarity = filter out
        return False, similarity, "does_not_fit_scene"
    
    def filter_detections(
        self,
        detections: List[Dict[str, Any]],
        label_key: str = "object_class",
        confidence_key: str = "confidence",
        in_place: bool = True,
    ) -> List[Dict[str, Any]]:
        """Filter a list of detections based on scene context.
        
        Args:
            detections: List of detection dicts.
            label_key: Key for object label in detection dict.
            confidence_key: Key for confidence in detection dict.
            in_place: If True, modify detections in place. Otherwise, return filtered copy.
            
        Returns:
            Filtered list of detections.
        """
        if self._scene_embedding is None:
            return detections
        
        filtered = []
        removed = 0
        
        for det in detections:
            label = det.get(label_key, "unknown")
            confidence = float(det.get(confidence_key, 0.5) or 0.5)
            
            is_valid, similarity, reason = self.check_detection(label, confidence)
            
            if in_place:
                det["scene_similarity"] = similarity
                det["scene_filter_reason"] = reason
            
            if is_valid:
                filtered.append(det)
            else:
                removed += 1
                if in_place:
                    det["scene_filtered"] = True
        
        if removed > 0:
            logger.info(f"Scene filter: Removed {removed}/{len(detections)} detections")
        
        return filtered
    
    def get_similarity_scores(
        self,
        labels: List[str],
    ) -> Dict[str, float]:
        """Get similarity scores for multiple labels.
        
        Useful for debugging/analysis.
        
        Args:
            labels: List of labels to check.
            
        Returns:
            Dict mapping label -> similarity score.
        """
        return {label: self.compute_similarity(label) for label in labels}
    
    def reset(self):
        """Reset scene context and caches."""
        self._scene_embedding = None
        self._scene_caption = ""
        self._label_cache = {}
        logger.debug("SceneFilter reset")
