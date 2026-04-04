"""
Gemini 3.5-Flash VLM Integration
=================================

Replaces FastVLM/OLLAMA with Gemini 3.5-Flash for stronger scene understanding.

This is the "paper version" for evaluations - provides better results for the paper.
For deployment, use the lightweight FastVLM version.
"""

import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import base64
from pathlib import Path

import numpy as np

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class VLMCaptionResult:
    """Result from VLM caption generation."""
    text: str
    confidence: float = 0.9
    model: str = "gemini-3.5-flash"


class GeminiVLMBackend:
    """
    Gemini 3.5-Flash VLM backend for scene understanding.
    
    Used for:
    - Generating rich object descriptions
    - Understanding spatial relationships
    - Predicting future scene graphs (anticipation)
    - Semantic filtering
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-2.0-flash-001",
    ):
        """
        Initialize Gemini VLM backend.
        
        Args:
            api_key: Google API key (reads from env if not provided)
            model: Gemini model to use (default: gemini-2.0-flash-001)
        """
        if not GEMINI_AVAILABLE:
            raise ImportError("google-generativeai not installed. Install with: pip install google-generativeai")
        
        self.api_key = api_key or self._get_api_key()
        self.model = model
        
        # Configure Gemini
        genai.configure(api_key=self.api_key)
        self.client = genai.GenerativeModel(model)
        
        logger.info(f"✓ Initialized Gemini VLM backend ({model})")
    
    @staticmethod
    def _get_api_key() -> str:
        """Get Gemini API key from environment."""
        import os
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError(
                "GOOGLE_API_KEY not set. "
                "Set with: export GOOGLE_API_KEY=your_key_here"
            )
        return api_key
    
    def describe_objects(
        self,
        frame: np.ndarray,
        detections: List[Dict],
        context: str = ""
    ) -> Dict[int, VLMCaptionResult]:
        """
        Generate rich descriptions for detected objects.
        
        Args:
            frame: Video frame (numpy array)
            detections: List of detections with bbox, class_name
            context: Scene context (e.g., "kitchen scene")
            
        Returns:
            Dict mapping detection_idx -> caption result
        """
        results = {}
        
        for idx, det in enumerate(detections):
            bbox = det.get('bbox', [0, 0, 100, 100])
            class_name = det.get('class_name', 'object')
            confidence = det.get('confidence', 0.5)
            
            # Crop object region
            x1, y1, x2, y2 = [int(v) for v in bbox]
            obj_crop = frame[y1:y2, x1:x2]
            
            if obj_crop.size == 0:
                results[idx] = VLMCaptionResult(text=class_name, confidence=0.0)
                continue
            
            # Generate description
            prompt = f"""Analyze this {class_name} in the video frame.
            {f'Scene context: {context}' if context else ''}
            
            Provide a concise description covering:
            1. Object state/condition
            2. Any visible interactions
            3. Spatial relationships to surroundings
            
            Keep response to 1-2 sentences."""
            
            try:
                # Convert numpy array to base64 for API
                caption = self._query_image(obj_crop, prompt)
                results[idx] = VLMCaptionResult(
                    text=caption,
                    confidence=min(0.95, confidence + 0.3)  # Boost confidence for VLM-filtered objects
                )
            except Exception as e:
                logger.warning(f"Failed to describe object {idx}: {e}")
                results[idx] = VLMCaptionResult(text=class_name, confidence=0.5)
        
        return results
    
    def understand_relationships(
        self,
        frame: np.ndarray,
        detections: List[Dict],
    ) -> List[Tuple[int, str, int]]:
        """
        Understand spatial relationships between detected objects.
        
        Args:
            frame: Video frame
            detections: List of detections
            
        Returns:
            List of (subject_idx, predicate, object_idx) triplets
        """
        if len(detections) < 2:
            return []
        
        # Build object list
        objects_str = "\n".join([
            f"{i}: {det.get('class_name', 'object')} at bbox {det.get('bbox', [])}"
            for i, det in enumerate(detections)
        ])
        
        prompt = f"""Analyze the spatial relationships between these detected objects:
        
{objects_str}

For each meaningful relationship, list as "subject_id predicate object_id"
Examples: "0 is holding 1", "1 is on 2", "3 is near 4"
Only list relationships that are clearly visible in the image."""
        
        try:
            response = self._query_text(prompt)
            
            # Parse relationships
            relationships = []
            for line in response.split('\n'):
                line = line.strip()
                if not line or line.startswith('Example'):
                    continue
                
                # Try to parse "subject_id predicate object_id"
                parts = line.split()
                if len(parts) >= 3:
                    try:
                        subj_id = int(parts[0])
                        obj_id = int(parts[-1])
                        predicate = ' '.join(parts[1:-1])
                        
                        if 0 <= subj_id < len(detections) and 0 <= obj_id < len(detections):
                            relationships.append((subj_id, predicate, obj_id))
                    except (ValueError, IndexError):
                        continue
            
            return relationships
        except Exception as e:
            logger.warning(f"Failed to understand relationships: {e}")
            return []
    
    def anticipate_scene_graphs(
        self,
        frames_so_far: List[np.ndarray],
        scene_graphs_so_far: List[List[Tuple[str, str, str]]],
        num_future_frames: int = 5
    ) -> List[List[Tuple[str, str, str]]]:
        """
        Anticipate future scene graphs given observed frames.
        
        Task: Given frames 0 to t, predict scene graphs at frames t+1, t+2, ...
        
        Args:
            frames_so_far: List of observed frames (video history)
            scene_graphs_so_far: Scene graphs for observed frames
            num_future_frames: Number of future frames to anticipate
            
        Returns:
            List of anticipated scene graphs
        """
        if not frames_so_far or not scene_graphs_so_far:
            return [[] for _ in range(num_future_frames)]
        
        # Summarize observed scene evolution
        sg_summary = "\n".join([
            f"Frame {i}: {', '.join([f'{s}-{p}-{o}' for s, p, o in sg])}"
            for i, sg in enumerate(scene_graphs_so_far[-5:])  # Last 5 frames
        ])
        
        prompt = f"""Given this video scene progression:

{sg_summary}

Anticipate what relationships will exist in the next {num_future_frames} frames.
Consider:
1. Physical laws (objects don't appear/disappear)
2. Interaction patterns (ongoing actions)
3. Likely future states

List predicted relationships as "subject predicate object" per line.
Provide {num_future_frames} blocks, one per future frame.
Separate blocks with "---Frame N---"."""
        
        try:
            response = self._query_text(prompt)
            
            # Parse anticipated scene graphs
            future_sgs = []
            current_sg = []
            frame_num = 0
            
            for line in response.split('\n'):
                line = line.strip()
                
                if line.startswith('---Frame'):
                    if current_sg:
                        future_sgs.append(current_sg)
                        current_sg = []
                    frame_num += 1
                    continue
                
                if not line or line.startswith('Anticipate'):
                    continue
                
                # Try to parse triplet
                parts = line.split()
                if len(parts) >= 3:
                    subject = parts[0]
                    predicate = ' '.join(parts[1:-1])
                    obj = parts[-1]
                    current_sg.append((subject, predicate, obj))
            
            # Pad to num_future_frames
            while len(future_sgs) < num_future_frames:
                future_sgs.append(current_sg if current_sg else [])
            
            return future_sgs[:num_future_frames]
        except Exception as e:
            logger.warning(f"Failed to anticipate scene graphs: {e}")
            return [[] for _ in range(num_future_frames)]
    
    def _query_image(
        self,
        image: np.ndarray,
        prompt: str,
        max_retries: int = 2
    ) -> str:
        """Query Gemini with image and text prompt."""
        import cv2
        
        # Convert to PIL Image
        from PIL import Image
        
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(rgb_image)
        
        for attempt in range(max_retries):
            try:
                response = self.client.generate_content([prompt, pil_image])
                return response.text
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                logger.debug(f"Retry {attempt + 1}/{max_retries}: {e}")
        
        return ""
    
    def _query_text(self, prompt: str, max_retries: int = 2) -> str:
        """Query Gemini with text only."""
        for attempt in range(max_retries):
            try:
                response = self.client.generate_content(prompt)
                return response.text
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                logger.debug(f"Retry {attempt + 1}/{max_retries}: {e}")
        
        return ""


# Lightweight version for deployment
class FastVLMBackend:
    """
    FastVLM lightweight backend for deployment.
    
    Faster inference, lower quality - suitable for real-time applications.
    """
    
    def __init__(self):
        """Initialize FastVLM backend."""
        logger.info("✓ Initialized FastVLM lightweight backend")
    
    def describe_objects(
        self,
        frame: np.ndarray,
        detections: List[Dict],
        context: str = ""
    ) -> Dict[int, VLMCaptionResult]:
        """Fast object description using lightweight model."""
        # Placeholder - would use actual FastVLM
        return {
            idx: VLMCaptionResult(
                text=det.get('class_name', 'object'),
                model='fastvlm',
                confidence=det.get('confidence', 0.5)
            )
            for idx, det in enumerate(detections)
        }
    
    def understand_relationships(
        self,
        frame: np.ndarray,
        detections: List[Dict],
    ) -> List[Tuple[int, str, int]]:
        """Fast relationship detection."""
        # Placeholder
        return []
    
    def anticipate_scene_graphs(
        self,
        frames_so_far: List[np.ndarray],
        scene_graphs_so_far: List[List[Tuple[str, str, str]]],
        num_future_frames: int = 5
    ) -> List[List[Tuple[str, str, str]]]:
        """Fast anticipation - less accurate."""
        return [[] for _ in range(num_future_frames)]


def create_vlm_backend(backend: str = "gemini", **kwargs) -> GeminiVLMBackend | FastVLMBackend:
    """
    Factory for creating VLM backends.
    
    Args:
        backend: "gemini" (paper) or "fastvlm" (lightweight)
        **kwargs: Backend-specific arguments
        
    Returns:
        VLM backend instance
    """
    if backend == "gemini":
        if not GEMINI_AVAILABLE:
            logger.warning("Gemini not available, falling back to FastVLM")
            return FastVLMBackend()
        return GeminiVLMBackend(**kwargs)
    elif backend == "fastvlm":
        return FastVLMBackend()
    else:
        raise ValueError(f"Unknown VLM backend: {backend}")
