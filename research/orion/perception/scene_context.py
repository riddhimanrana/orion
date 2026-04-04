"""
Scene Context Manager for Orion v2

Manages scene-level semantic understanding using FastVLM:
1. Generates scene captions for video frames
2. Caches semantic embeddings for efficient similarity checks
3. Provides scene context for track validation and filtering

FastVLM 0.5B is extremely fast, so we can run it frequently on full frames.

Author: Orion Research Team
Date: January 2026
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import time

import numpy as np
from PIL import Image
import cv2

logger = logging.getLogger(__name__)

# Lazy imports
_sentence_transformer = None
_fastvlm = None


def get_sentence_transformer():
    """Lazy-load sentence transformer model."""
    global _sentence_transformer
    if _sentence_transformer is None:
        try:
            from sentence_transformers import SentenceTransformer
            logger.info("Loading all-mpnet-base-v2 for scene embeddings...")
            _sentence_transformer = SentenceTransformer('sentence-transformers/all-mpnet-base-v2')
            logger.info("✓ Sentence transformer loaded")
        except ImportError:
            raise ImportError("sentence-transformers required: pip install sentence-transformers")
    return _sentence_transformer


def get_fastvlm(device: str = "cuda"):
    """Lazy-load FastVLM model."""
    global _fastvlm
    if _fastvlm is None:
        from orion.backends.torch_fastvlm import FastVLMTorchWrapper
        logger.info(f"Loading FastVLM 0.5B on {device}...")
        _fastvlm = FastVLMTorchWrapper(device=device)
        logger.info("✓ FastVLM loaded")
    return _fastvlm


@dataclass
class SceneSnapshot:
    """A single scene caption at a specific frame."""
    frame_idx: int
    timestamp: float
    caption: str
    embedding: Optional[np.ndarray] = None
    objects_mentioned: List[str] = field(default_factory=list)


@dataclass
class SceneContextConfig:
    """Configuration for scene context management."""
    
    # Caption generation
    caption_prompt: str = "Describe this scene briefly. What objects and activities are visible?"
    """Prompt for scene captioning."""
    
    max_tokens: int = 100
    """Maximum tokens for scene caption."""
    
    temperature: float = 0.2
    """VLM temperature for captions."""
    
    # Update frequency
    update_interval_frames: int = 30
    """Generate new scene caption every N frames."""
    
    update_interval_seconds: float = 2.0
    """Alternative: generate new caption every N seconds (at 15fps = 30 frames)."""
    
    # Caching
    max_cached_scenes: int = 50
    """Maximum number of scene snapshots to keep in memory."""
    
    # Embedding
    cache_embeddings: bool = True
    """Whether to cache scene embeddings for similarity checks."""
    
    # Device
    device: str = "cuda"
    """Device for FastVLM inference."""


class SceneContextManager:
    """
    Manages scene-level semantic context throughout a video.
    
    Key Features:
    - Fast scene captioning with FastVLM 0.5B
    - Semantic embeddings for scene-to-object matching
    - Temporal coherence (scenes don't change every frame)
    - Object extraction from captions for validation
    
    Usage:
        manager = SceneContextManager()
        
        # Process video frames
        for frame_idx, frame in enumerate(frames):
            scene = manager.update(frame, frame_idx)
            
            # Use scene context for filtering
            if manager.is_object_contextual("boat", scene):
                # Object fits the scene
                pass
    """
    
    def __init__(self, config: Optional[SceneContextConfig] = None):
        """Initialize scene context manager.
        
        Args:
            config: Configuration. Uses defaults if None.
        """
        self.config = config or SceneContextConfig()
        self._vlm = None
        self._sentence_model = None
        self._scenes: List[SceneSnapshot] = []
        self._current_scene: Optional[SceneSnapshot] = None
        self._last_update_frame: int = -999
        self._object_embedding_cache: Dict[str, np.ndarray] = {}
        
    @property
    def vlm(self):
        """Lazy-load VLM."""
        if self._vlm is None:
            self._vlm = get_fastvlm(self.config.device)
        return self._vlm
    
    @property
    def sentence_model(self):
        """Lazy-load sentence transformer."""
        if self._sentence_model is None:
            self._sentence_model = get_sentence_transformer()
        return self._sentence_model
    
    @property
    def current_scene(self) -> Optional[SceneSnapshot]:
        """Get the current scene context."""
        return self._current_scene
    
    @property
    def current_caption(self) -> str:
        """Get the current scene caption (empty string if none)."""
        return self._current_scene.caption if self._current_scene else ""
    
    @property
    def current_embedding(self) -> Optional[np.ndarray]:
        """Get the current scene embedding (None if none)."""
        return self._current_scene.embedding if self._current_scene else None
    
    def should_update(self, frame_idx: int) -> bool:
        """Check if we should generate a new scene caption.
        
        Args:
            frame_idx: Current frame index.
            
        Returns:
            True if we should update the scene context.
        """
        if self._current_scene is None:
            return True
        frames_since_update = frame_idx - self._last_update_frame
        return frames_since_update >= self.config.update_interval_frames
    
    def generate_caption(self, frame: np.ndarray) -> str:
        """Generate a scene caption for a frame.
        
        Args:
            frame: BGR numpy array (OpenCV format).
            
        Returns:
            Scene caption string.
        """
        try:
            # Convert BGR to RGB PIL Image
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(rgb_frame)
            
            caption = self.vlm.generate_description(
                pil_image,
                self.config.caption_prompt,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
            )
            return caption.strip()
        except Exception as e:
            logger.warning(f"Scene captioning failed: {e}")
            return ""
    
    def embed_text(self, text: str) -> np.ndarray:
        """Embed text using sentence transformer."""
        return self.sentence_model.encode(text, convert_to_numpy=True)
    
    def extract_objects_from_caption(self, caption: str) -> List[str]:
        """Extract mentioned objects from a caption.
        
        This is a simple heuristic extraction. More sophisticated
        NLP could be used, but this is fast and effective.
        
        Args:
            caption: Scene caption.
            
        Returns:
            List of object nouns mentioned.
        """
        # Common object words to look for
        common_objects = {
            "person", "people", "man", "woman", "child", "dog", "cat", "bird",
            "car", "truck", "bicycle", "motorcycle", "bus", "train",
            "chair", "table", "desk", "couch", "sofa", "bed", "lamp",
            "tv", "television", "computer", "laptop", "phone", "monitor",
            "refrigerator", "fridge", "oven", "microwave", "sink",
            "toilet", "bathtub", "shower", "mirror",
            "book", "bottle", "cup", "glass", "bowl", "plate",
            "door", "window", "wall", "floor", "ceiling",
            "tree", "plant", "flower", "grass",
            "clock", "picture", "painting", "poster",
        }
        
        words = caption.lower().split()
        found = []
        for word in words:
            # Remove punctuation
            clean = ''.join(c for c in word if c.isalnum())
            if clean in common_objects:
                found.append(clean)
        
        return list(set(found))  # Remove duplicates
    
    def update(
        self, 
        frame: np.ndarray, 
        frame_idx: int,
        timestamp: float = 0.0,
        force: bool = False,
    ) -> SceneSnapshot:
        """Update scene context if needed.
        
        Args:
            frame: Current video frame (BGR).
            frame_idx: Current frame index.
            timestamp: Frame timestamp in seconds.
            force: Force update even if interval not reached.
            
        Returns:
            Current SceneSnapshot (may be cached or newly generated).
        """
        if not force and not self.should_update(frame_idx):
            return self._current_scene
        
        # Generate new caption
        start_time = time.time()
        caption = self.generate_caption(frame)
        gen_time = time.time() - start_time
        
        if not caption:
            # Keep previous scene if generation failed
            if self._current_scene:
                return self._current_scene
            caption = "Unknown scene"
        
        # Create embedding
        embedding = None
        if self.config.cache_embeddings and caption:
            embedding = self.embed_text(caption)
        
        # Extract objects
        objects = self.extract_objects_from_caption(caption)
        
        # Create snapshot
        snapshot = SceneSnapshot(
            frame_idx=frame_idx,
            timestamp=timestamp,
            caption=caption,
            embedding=embedding,
            objects_mentioned=objects,
        )
        
        # Update state
        self._current_scene = snapshot
        self._last_update_frame = frame_idx
        self._scenes.append(snapshot)
        
        # Limit cache size
        if len(self._scenes) > self.config.max_cached_scenes:
            self._scenes = self._scenes[-self.config.max_cached_scenes:]
        
        logger.debug(f"Scene updated at frame {frame_idx} ({gen_time:.2f}s): {caption[:80]}...")
        
        return snapshot
    
    def get_object_embedding(self, label: str) -> np.ndarray:
        """Get embedding for an object label (cached).
        
        Args:
            label: Object label (e.g., "chair").
            
        Returns:
            768-dim embedding vector.
        """
        if label not in self._object_embedding_cache:
            # Expand label for better matching
            expanded = f"A {label} in a room or scene"
            self._object_embedding_cache[label] = self.embed_text(expanded)
        return self._object_embedding_cache[label]
    
    def compute_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Compute cosine similarity between two embeddings."""
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))
    
    def is_object_contextual(
        self,
        label: str,
        scene: Optional[SceneSnapshot] = None,
        threshold: float = 0.20,
    ) -> Tuple[bool, float]:
        """Check if an object label is contextually valid for the scene.
        
        This helps filter out detections that don't make sense in context.
        E.g., detecting a "boat" in a kitchen scene would have low similarity.
        
        Args:
            label: Object label to check.
            scene: Scene to check against (defaults to current scene).
            threshold: Minimum similarity to consider valid.
            
        Returns:
            Tuple of (is_valid, similarity_score).
        """
        scene = scene or self._current_scene
        
        if scene is None or scene.embedding is None:
            # No scene context, assume valid
            return True, 0.5
        
        # Check if object is directly mentioned in caption
        if label.lower() in [obj.lower() for obj in scene.objects_mentioned]:
            return True, 1.0
        
        # Compute semantic similarity
        obj_embedding = self.get_object_embedding(label)
        similarity = self.compute_similarity(obj_embedding, scene.embedding)
        
        is_valid = similarity >= threshold
        return is_valid, similarity
    
    def get_scene_history(self) -> List[SceneSnapshot]:
        """Get all cached scene snapshots."""
        return self._scenes.copy()
    
    def reset(self):
        """Reset the scene context manager."""
        self._scenes = []
        self._current_scene = None
        self._last_update_frame = -999
        self._object_embedding_cache = {}
        logger.debug("SceneContextManager reset")
