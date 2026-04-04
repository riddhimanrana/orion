"""
FastVLM Verification Filter

Replaces threshold-based semantic filtering with VLM-backed verification.
Uses MLX-FastVLM for local inference on Apple Silicon.

Key improvements over threshold filtering:
- Active verification instead of passive thresholding
- Contextual reasoning about object presence
- Explanations for filtering decisions
- Scene-aware verification prompts

Author: Orion Research Team
Date: January 2026
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple
from pathlib import Path

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


@dataclass
class FilterDecision:
    """Decision from the VLM filter."""
    keep: bool
    reason: str
    vlm_response: Optional[str] = None
    confidence: float = 0.0
    verification_method: str = "threshold"  # "threshold", "vlm", "whitelist"


@dataclass 
class FilterStats:
    """Statistics from filtering pass."""
    total_input: int = 0
    kept: int = 0
    removed_threshold: int = 0
    removed_vlm: int = 0
    removed_blacklist: int = 0
    vlm_queries: int = 0
    avg_vlm_time: float = 0.0


# Labels that require VLM verification when confidence is low
SUSPICIOUS_LABELS = {
    "refrigerator": {
        "verification_threshold": 0.55,  # Below this, ask VLM
        "common_confusions": ["wardrobe", "cabinet", "closet", "door"],
        "verification_prompt": "Is there a refrigerator/fridge in this image? Look for a tall appliance typically found in kitchens.",
    },
    "toilet": {
        "verification_threshold": 0.50,
        "common_confusions": ["chair", "vase", "bowl"],
        "verification_prompt": "Is there a toilet in this image? Look for bathroom fixtures.",
    },
    "sink": {
        "verification_threshold": 0.45,
        "common_confusions": ["bathtub", "counter", "desk"],
        "verification_prompt": "Is there a sink in this image? Look for a basin with faucet.",
    },
    "microwave": {
        "verification_threshold": 0.45,
        "common_confusions": ["tv", "monitor", "oven", "doorway"],
        "verification_prompt": "Is there a microwave oven in this image? Look for a small box-shaped kitchen appliance.",
    },
    "hair drier": {
        "verification_threshold": 0.55,
        "common_confusions": ["remote", "phone", "brush", "door handle"],
        "verification_prompt": "Is there a hair dryer in this image? Look for a handheld electrical grooming device.",
    },
    "bird": {
        "verification_threshold": 0.60,
        "common_confusions": ["plant", "decoration", "sculpture", "curtain pattern"],
        "verification_prompt": "Is there a bird (live or pet) in this image? Not decorations or artwork.",
    },
    "airplane": {
        "verification_threshold": 0.65,
        "common_confusions": ["ceiling fan", "light fixture", "drone toy"],
        "verification_prompt": "Is there an airplane or toy plane in this image?",
    },
    "toaster": {
        "verification_threshold": 0.50,
        "common_confusions": ["box", "container", "small appliance"],
        "verification_prompt": "Is there a toaster in this image? Look for a small kitchen appliance for toasting bread.",
    },
    "bed": {
        "verification_threshold": 0.45,
        "common_confusions": ["couch", "floor mat", "rug", "carpet"],
        "verification_prompt": "Is there a bed in this image? Look for a mattress with bedding.",
    },
    "teddy bear": {
        "verification_threshold": 0.50,
        "common_confusions": ["pillow", "cushion", "blanket", "clothing"],
        "verification_prompt": "Is there a teddy bear or stuffed animal in this image?",
    },
    "kite": {
        "verification_threshold": 0.60,
        "common_confusions": ["poster", "art", "flag", "fabric"],
        "verification_prompt": "Is there a kite in this image?",
    },
    "boat": {
        "verification_threshold": 0.65,
        "common_confusions": ["bowl", "container", "bathtub"],
        "verification_prompt": "Is there a boat or model boat in this image?",
    },
}

# Scene-based blacklists (objects that should never appear in certain scenes)
SCENE_BLACKLISTS = {
    "hallway": {"refrigerator", "toilet", "bathtub", "oven", "bed", "couch", "dining table"},
    "staircase": {"refrigerator", "toilet", "bathtub", "oven", "bed", "dining table", "sink"},
    "bathroom": {"refrigerator", "oven", "laptop", "keyboard", "dining table", "couch"},
    "bedroom": {"toilet", "oven", "refrigerator"},
    "office": {"toilet", "bathtub", "oven", "bed"},
    "living_room": {"toilet", "bathtub", "shower", "oven", "stove", "microwave"},
}

# Always-keep whitelist (high-confidence classes that rarely need verification)
WHITELIST_CLASSES = {
    "person", "chair", "table", "laptop", "keyboard", "mouse", "bottle", "cup",
    "cell phone", "book", "clock", "vase", "potted plant", "backpack", "handbag"
}


class FastVLMFilter:
    """
    VLM-backed semantic filter using FastVLM for verification.
    
    Strategy:
    1. Whitelist: Always keep common reliable classes
    2. Blacklist: Remove based on scene context
    3. VLM Verification: For suspicious labels with low confidence
    4. Threshold: Fallback for non-suspicious labels
    """
    
    def __init__(
        self,
        vlm_model_path: Optional[str] = None,
        enable_vlm: bool = True,
        confidence_floor: float = 0.20,
        scene_blacklist_enabled: bool = True,
        cache_vlm_responses: bool = True,
    ):
        """
        Initialize FastVLM filter.
        
        Args:
            vlm_model_path: Path to FastVLM model
            enable_vlm: Whether to use VLM verification
            confidence_floor: Absolute minimum confidence
            scene_blacklist_enabled: Use scene-based blacklists
            cache_vlm_responses: Cache VLM responses for same crop
        """
        self.vlm_model_path = vlm_model_path
        self.enable_vlm = enable_vlm
        self.confidence_floor = confidence_floor
        self.scene_blacklist_enabled = scene_blacklist_enabled
        self.cache_vlm_responses = cache_vlm_responses
        
        self._vlm = None
        self._response_cache: Dict[str, Tuple[bool, str]] = {}
        
        logger.info(f"FastVLMFilter initialized (vlm={enable_vlm}, floor={confidence_floor})")
    
    def _ensure_vlm_loaded(self):
        """Lazy-load VLM model."""
        if self._vlm is None and self.enable_vlm:
            try:
                from orion.backends.mlx_fastvlm import FastVLMMLXWrapper
                
                logger.info("Loading FastVLM for verification...")
                self._vlm = FastVLMMLXWrapper(model_source=self.vlm_model_path)
                logger.info("✓ FastVLM loaded")
                
            except Exception as e:
                logger.warning(f"Failed to load FastVLM: {e}")
                self._vlm = None
                self.enable_vlm = False
    
    def _crop_hash(self, crop: Image.Image) -> str:
        """Generate hash for crop caching."""
        import hashlib
        # Simple hash based on resized thumbnail
        thumb = crop.resize((32, 32))
        data = np.array(thumb).tobytes()
        return hashlib.md5(data).hexdigest()[:16]
    
    def _verify_with_vlm(
        self,
        crop: Image.Image,
        label: str,
        custom_prompt: Optional[str] = None
    ) -> Tuple[bool, str, float]:
        """
        Verify a detection using FastVLM.
        
        Args:
            crop: Cropped image of detection
            label: Label to verify
            custom_prompt: Optional custom verification prompt
            
        Returns:
            Tuple of (is_verified, vlm_response, confidence)
        """
        self._ensure_vlm_loaded()
        
        if self._vlm is None:
            return True, "VLM not available, keeping detection", 0.5
        
        # Check cache
        if self.cache_vlm_responses:
            cache_key = f"{self._crop_hash(crop)}_{label}"
            if cache_key in self._response_cache:
                cached = self._response_cache[cache_key]
                return cached[0], cached[1], 0.7 if cached[0] else 0.3
        
        # Build prompt
        if custom_prompt:
            prompt = custom_prompt
        elif label.lower() in SUSPICIOUS_LABELS:
            prompt = SUSPICIOUS_LABELS[label.lower()]["verification_prompt"]
        else:
            prompt = f"Is there a {label} in this image? Answer yes or no, then briefly explain."
        
        try:
            # Query VLM
            response = self._vlm.generate(
                crop,
                prompt,
                max_tokens=50,
                temperature=0.1  # Low temperature for consistent answers
            )
            
            response_lower = response.lower()
            
            # Parse response
            is_yes = any(word in response_lower for word in ["yes", "correct", "indeed", "there is", "i can see"])
            is_no = any(word in response_lower for word in ["no", "not", "cannot", "don't see", "isn't"])
            
            if is_yes and not is_no:
                is_verified = True
                confidence = 0.8
            elif is_no and not is_yes:
                is_verified = False
                confidence = 0.2
            else:
                # Ambiguous - default to keeping
                is_verified = True
                confidence = 0.5
            
            # Cache result
            if self.cache_vlm_responses:
                self._response_cache[cache_key] = (is_verified, response)
            
            return is_verified, response, confidence
            
        except Exception as e:
            logger.warning(f"VLM verification failed: {e}")
            return True, f"Error: {e}", 0.5
    
    def _detect_scene_type(self, detections: List[Dict[str, Any]]) -> str:
        """Detect scene type from detected objects."""
        # Simple heuristic based on detected classes
        classes = set(d.get("class_name", "").lower() for d in detections)
        
        # Check for scene indicators
        if "bed" in classes or "pillow" in classes:
            return "bedroom"
        if "toilet" in classes or "sink" in classes and "bathtub" in classes:
            return "bathroom"
        if "refrigerator" in classes or "oven" in classes or "stove" in classes:
            return "kitchen"
        if "couch" in classes or "tv" in classes:
            return "living_room"
        if "desk" in classes or "monitor" in classes or "keyboard" in classes:
            return "office"
        if "dining table" in classes:
            return "dining"
        
        return "unknown"
    
    def filter_detections(
        self,
        detections: List[Dict[str, Any]],
        scene_type: Optional[str] = None,
        frame: Optional[np.ndarray] = None
    ) -> Tuple[List[Dict[str, Any]], FilterStats]:
        """
        Filter detections using VLM verification.
        
        Args:
            detections: List of detection dicts
            scene_type: Optional scene type (auto-detected if None)
            frame: Optional frame for context
            
        Returns:
            Tuple of (filtered_detections, stats)
        """
        stats = FilterStats(total_input=len(detections))
        
        if not detections:
            return [], stats
        
        # Detect scene if not provided
        if scene_type is None:
            scene_type = self._detect_scene_type(detections)
        
        filtered = []
        vlm_times = []
        
        for det in detections:
            label = det.get("class_name", "").lower()
            confidence = det.get("confidence", 0.0)
            crop = det.get("crop")
            
            decision = self._evaluate_detection(
                label, confidence, crop, scene_type, vlm_times
            )
            
            # Add decision info to detection
            det_copy = {**det, "filter_decision": decision.reason, "filter_method": decision.verification_method}
            
            if decision.keep:
                filtered.append(det_copy)
                stats.kept += 1
            else:
                if decision.verification_method == "vlm":
                    stats.removed_vlm += 1
                elif decision.verification_method == "blacklist":
                    stats.removed_blacklist += 1
                else:
                    stats.removed_threshold += 1
        
        stats.vlm_queries = len(vlm_times)
        if vlm_times:
            stats.avg_vlm_time = np.mean(vlm_times)
        
        logger.info(
            f"Filter: {stats.total_input} → {stats.kept} "
            f"(removed: {stats.removed_threshold} thresh, {stats.removed_vlm} vlm, {stats.removed_blacklist} blacklist)"
        )
        
        return filtered, stats
    
    def _evaluate_detection(
        self,
        label: str,
        confidence: float,
        crop: Optional[Image.Image],
        scene_type: str,
        vlm_times: List[float]
    ) -> FilterDecision:
        """
        Evaluate a single detection.
        
        Returns FilterDecision with keep/reject and reasoning.
        """
        import time
        
        label_lower = label.lower()
        
        # Rule 1: Whitelist (always keep reliable classes)
        if label_lower in WHITELIST_CLASSES:
            return FilterDecision(
                keep=True,
                reason=f"Whitelisted class: {label}",
                confidence=confidence,
                verification_method="whitelist"
            )
        
        # Rule 2: Absolute confidence floor
        if confidence < self.confidence_floor:
            return FilterDecision(
                keep=False,
                reason=f"Below confidence floor ({confidence:.2f} < {self.confidence_floor})",
                confidence=confidence,
                verification_method="threshold"
            )
        
        # Rule 3: Scene blacklist
        if self.scene_blacklist_enabled and scene_type in SCENE_BLACKLISTS:
            blacklist = SCENE_BLACKLISTS[scene_type]
            if label_lower in blacklist:
                return FilterDecision(
                    keep=False,
                    reason=f"Blacklisted in {scene_type}: {label}",
                    confidence=confidence,
                    verification_method="blacklist"
                )
        
        # Rule 4: VLM verification for suspicious labels
        if self.enable_vlm and label_lower in SUSPICIOUS_LABELS:
            suspicious_config = SUSPICIOUS_LABELS[label_lower]
            threshold = suspicious_config["verification_threshold"]
            
            if confidence < threshold and crop is not None:
                # Verify with VLM
                start_time = time.time()
                is_verified, response, vlm_conf = self._verify_with_vlm(
                    crop, label, suspicious_config.get("verification_prompt")
                )
                vlm_times.append(time.time() - start_time)
                
                if is_verified:
                    return FilterDecision(
                        keep=True,
                        reason=f"VLM verified: {label}",
                        vlm_response=response,
                        confidence=vlm_conf,
                        verification_method="vlm"
                    )
                else:
                    return FilterDecision(
                        keep=False,
                        reason=f"VLM rejected: {label}",
                        vlm_response=response,
                        confidence=vlm_conf,
                        verification_method="vlm"
                    )
        
        # Default: Keep if above suspicious threshold or not suspicious
        if label_lower in SUSPICIOUS_LABELS:
            threshold = SUSPICIOUS_LABELS[label_lower]["verification_threshold"]
            if confidence >= threshold:
                return FilterDecision(
                    keep=True,
                    reason=f"Above suspicious threshold ({confidence:.2f} >= {threshold})",
                    confidence=confidence,
                    verification_method="threshold"
                )
        
        # Default keep for non-suspicious
        return FilterDecision(
            keep=True,
            reason="Default keep (non-suspicious, above floor)",
            confidence=confidence,
            verification_method="threshold"
        )
    
    def clear_cache(self):
        """Clear VLM response cache."""
        self._response_cache.clear()
        logger.debug("VLM response cache cleared")


# =====================================================================
# Integration with Perception Pipeline
# =====================================================================

def apply_vlm_filter(
    detections: List[Dict[str, Any]],
    scene_type: Optional[str] = None,
    enable_vlm: bool = True
) -> List[Dict[str, Any]]:
    """
    Apply FastVLM filtering to detections.
    
    Args:
        detections: List of detection dicts with 'class_name', 'confidence', 'crop'
        scene_type: Optional scene type for context
        enable_vlm: Whether to use VLM verification
        
    Returns:
        Filtered list of detections
    """
    filter_instance = FastVLMFilter(enable_vlm=enable_vlm)
    filtered, stats = filter_instance.filter_detections(detections, scene_type)
    
    return filtered


# =====================================================================
# Standalone Test
# =====================================================================

if __name__ == "__main__":
    import sys
    
    logging.basicConfig(level=logging.INFO)
    
    # Test data
    test_detections = [
        {"class_name": "person", "confidence": 0.85, "crop": None},
        {"class_name": "refrigerator", "confidence": 0.42, "crop": None},  # Should trigger VLM if enabled
        {"class_name": "chair", "confidence": 0.75, "crop": None},
        {"class_name": "hair drier", "confidence": 0.35, "crop": None},  # Suspicious
        {"class_name": "laptop", "confidence": 0.90, "crop": None},
    ]
    
    print("Testing FastVLM Filter (VLM disabled)...")
    
    filter_no_vlm = FastVLMFilter(enable_vlm=False)
    filtered, stats = filter_no_vlm.filter_detections(test_detections, scene_type="office")
    
    print(f"\nInput: {len(test_detections)} detections")
    print(f"Output: {len(filtered)} detections")
    print(f"Stats: {stats}")
    
    for det in filtered:
        print(f"  - {det['class_name']}: {det.get('filter_decision', 'N/A')}")
