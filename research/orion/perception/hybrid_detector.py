"""
Hybrid Detection Engine for Orion v2

Combines YOLO11x (fast, precise on COCO) with GroundingDINO (zero-shot, high recall)
to get the best of both worlds.

Strategy:
1. Run YOLO11x on every frame (fast baseline)
2. Trigger GroundingDINO when:
   - Scene context suggests rare/unusual objects
   - Low detection count for a frame (possibly missing objects)
   - User query asks for specific non-COCO objects
3. Merge detections with smart NMS to avoid duplicates

Author: Orion Research Team
Date: January 2026
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch
from PIL import Image

logger = logging.getLogger(__name__)


@dataclass
class HybridDetectorConfig:
    """Configuration for hybrid detection."""
    
    # Primary detector (always runs)
    primary_backend: str = "yolo"
    primary_model: str = "yolo11x"
    primary_confidence: float = 0.25
    
    # Secondary detector (triggered conditionally)
    secondary_backend: str = "groundingdino"
    secondary_model: str = "IDEA-Research/grounding-dino-tiny"
    secondary_confidence: float = 0.40  # Raised from 0.30 to reduce false positives when checking COCO

    # Secondary detector vocabulary control
    include_coco_in_secondary: bool = True
    """If True, include the full COCO label set in the GroundingDINO text prompt.

    Changed to True to catch YOLO misses. Uses higher confidence (0.40) to reduce false positives.
    This allows GDINO to detect COCO objects that YOLO missed without excessive noise.
    """

    secondary_categories: Optional[List[str]] = None
    """Optional custom list of categories to use for GroundingDINO when query_objects is None.

    If provided, this overrides the built-in focused list.
    """
    
    # Triggering conditions
    min_detections_for_skip: int = 3  # If YOLO finds >= N objects, skip GDINO
    trigger_on_scene_uncertainty: bool = True  # Trigger if scene context is ambiguous
    trigger_on_specific_queries: bool = True  # Trigger if user asks for specific objects
    
    # Merging strategy
    nms_iou_threshold: float = 0.5  # IoU threshold for merging duplicates
    prefer_primary_on_overlap: bool = True  # Prefer YOLO detection on overlap
    
    # Class-specific overrides (always trigger GDINO for these)
    always_verify_classes: List[str] = field(default_factory=lambda: [
        "remote", "clock", "vase", "scissors", "toothbrush"  # Small objects YOLO often misses
    ])


class HybridDetector:
    """
    Hybrid detector combining YOLO11x speed with GroundingDINO recall.
    
    Key insight from deep research:
    - YOLO11x: 12 FPS, avg confidence 0.53, precise but misses unusual objects
    - GroundingDINO: 7 FPS, avg confidence 0.26, high recall but noisy
    
    Solution: Use YOLO as primary, GDINO as secondary verification.
    """
    
    def __init__(
        self,
        config: HybridDetectorConfig,
        yolo_model: Any,
        gdino_model: Optional[Any] = None,
        gdino_processor: Optional[Any] = None,
        device: str = "cuda",
    ):
        self.config = config
        self.device = device
        self.yolo = yolo_model
        self.gdino = gdino_model
        self.gdino_processor = gdino_processor
        
        # COCO-80 class names for YOLO
        self.coco_classes = list(self.yolo.names.values()) if hasattr(self.yolo, "names") else []
        
        # Statistics for adaptive triggering
        self._frame_count = 0
        self._gdino_trigger_count = 0
        self._total_yolo_dets = 0
        self._total_gdino_dets = 0
        
        logger.info(f"HybridDetector initialized: primary={config.primary_backend}, secondary={config.secondary_backend}")
    
    def detect(
        self,
        frame: np.ndarray,
        scene_context: Optional[str] = None,
        query_objects: Optional[List[str]] = None,
        force_secondary: bool = False,
    ) -> Tuple[List[Dict], Dict[str, Any]]:
        """
        Run hybrid detection on a frame.
        
        Args:
            frame: BGR frame from OpenCV
            scene_context: Optional scene description for context-aware triggering
            query_objects: Optional list of specific objects to search for
            force_secondary: Force running secondary detector
            
        Returns:
            Tuple of (detections, metadata)
        """
        self._frame_count += 1
        metadata = {
            "primary_ran": True,
            "secondary_ran": False,
            "trigger_reason": None,
            "primary_count": 0,
            "secondary_count": 0,
            "merged_count": 0,
        }
        
        # Step 1: Run primary detector (YOLO)
        primary_dets = self._run_yolo(frame)
        metadata["primary_count"] = len(primary_dets)
        self._total_yolo_dets += len(primary_dets)
        
        # Step 2: Decide whether to trigger secondary detector
        should_trigger, trigger_reason = self._should_trigger_secondary(
            primary_dets, scene_context, query_objects, force_secondary
        )
        
        if should_trigger and self.gdino is not None:
            metadata["secondary_ran"] = True
            metadata["trigger_reason"] = trigger_reason
            self._gdino_trigger_count += 1
            
            # Run GroundingDINO
            secondary_dets = self._run_gdino(frame, query_objects)
            metadata["secondary_count"] = len(secondary_dets)
            self._total_gdino_dets += len(secondary_dets)
            
            # Merge detections
            merged_dets = self._merge_detections(primary_dets, secondary_dets)
            metadata["merged_count"] = len(merged_dets)
            
            return merged_dets, metadata
        
        return primary_dets, metadata
    
    def _run_yolo(self, frame: np.ndarray) -> List[Dict]:
        """Run YOLO11x detection."""
        results = self.yolo(
            frame,
            conf=self.config.primary_confidence,
            verbose=False,
        )
        
        detections = []
        for result in results:
            boxes = result.boxes
            for i in range(len(boxes)):
                bbox = boxes.xyxy[i].cpu().numpy().astype(float).tolist()
                class_id = int(boxes.cls[i])
                detections.append({
                    "bbox": bbox,
                    "confidence": float(boxes.conf[i]),
                    "class_id": class_id,
                    "class_name": result.names[class_id],
                    "source": "yolo",
                })
        
        return detections
    
    def _run_gdino(self, frame: np.ndarray, query_objects: Optional[List[str]] = None) -> List[Dict]:
        """Run GroundingDINO detection."""
        if self.gdino is None or self.gdino_processor is None:
            return []
        
        import cv2
        
        # Convert to PIL
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb_frame)
        
        # Build text prompt
        if query_objects:
            categories = list(query_objects)
        elif self.config.secondary_categories:
            categories = list(self.config.secondary_categories)
        else:
            # Focus GDINO on categories YOLO is likely to miss or under-label.
            # NOTE: We intentionally do NOT include all COCO labels by default.
            categories = []
            if bool(self.config.include_coco_in_secondary):
                categories.extend(self.coco_classes)

            # Always-verify classes (small/ambiguous items)
            categories.extend(list(self.config.always_verify_classes or []))

            # Common household + structural objects (often missing from COCO-trained detectors)
            categories.extend(
                [
                    "stairs",
                    "staircase",
                    "railing",
                    "banister",
                    "window",
                    "door",
                    "doorway",
                    "picture frame",
                    "wall art",
                    "painting",
                    "ceiling light",
                    "chandelier",
                    "lamp",
                    "floor lamp",
                    "curtains",
                    "blinds",
                    "rug",
                    "kitchen island",
                    "kitchen cabinets",
                    "cabinet",
                    "refrigerator",
                    "fireplace",
                    "tv",
                    "bookshelf",
                    "bookcase",
                    "ottoman",
                    "stool",
                    "coffee table",
                    "vase",
                    "flowers",
                    # A few common small indoor items that help in office/home scenes
                    "remote control",
                    "wall clock",
                    "power strip",
                    "cable",
                    "charger",
                    "headphones",
                ]
            )

        # Deduplicate / clean prompt tokens
        cleaned: List[str] = []
        seen = set()
        for c in categories:
            s = str(c).strip()
            if not s:
                continue
            key = s.lower()
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(s)
        categories = cleaned

        if not categories:
            return []
        
        text_prompt = " . ".join(categories) + " ."
        
        device = next(self.gdino.parameters()).device
        inputs = self.gdino_processor(images=pil_img, text=text_prompt, return_tensors="pt").to(device)
        
        with torch.no_grad():
            outputs = self.gdino(**inputs)
        
        target_sizes = torch.tensor([pil_img.size[::-1]]).to(device)
        results = self.gdino_processor.post_process_grounded_object_detection(
            outputs,
            inputs.input_ids,
            threshold=self.config.secondary_confidence,
            target_sizes=target_sizes
        )[0]
        
        detections = []
        boxes = results["boxes"].cpu().numpy().tolist()
        scores = results["scores"].cpu().numpy().tolist()
        labels = results.get("text_labels", results.get("labels", []))
        
        for i in range(len(boxes)):
            label = labels[i] if isinstance(labels[i], str) else f"class_{labels[i]}"
            detections.append({
                "bbox": boxes[i],
                "confidence": float(scores[i]),
                "class_id": -1,  # GDINO doesn't use class IDs
                "class_name": label,
                "source": "gdino",
            })
        
        return detections
    
    def _should_trigger_secondary(
        self,
        primary_dets: List[Dict],
        scene_context: Optional[str],
        query_objects: Optional[List[str]],
        force: bool,
    ) -> Tuple[bool, Optional[str]]:
        """Decide whether to trigger secondary detector."""
        
        if force:
            return True, "forced"
        
        # Condition 1: Low detection count
        if len(primary_dets) < self.config.min_detections_for_skip:
            return True, "low_detection_count"
        
        # Condition 2: Scene context suggests unusual objects
        if self.config.trigger_on_scene_uncertainty and scene_context:
            unusual_keywords = ["unusual", "rare", "unique", "strange", "interesting"]
            if any(kw in scene_context.lower() for kw in unusual_keywords):
                return True, "scene_uncertainty"
        
        # Condition 3: User querying for specific non-COCO objects
        if self.config.trigger_on_specific_queries and query_objects:
            non_coco = [obj for obj in query_objects if obj.lower() not in [c.lower() for c in self.coco_classes]]
            if non_coco:
                return True, f"specific_query:{non_coco}"
        
        # Condition 4: Primary found classes that need verification
        primary_classes = {d["class_name"].lower() for d in primary_dets}
        verify_needed = primary_classes.intersection(set(c.lower() for c in self.config.always_verify_classes))
        if verify_needed:
            return True, f"verify_classes:{list(verify_needed)}"
        
        return False, None
    
    def _merge_detections(
        self,
        primary: List[Dict],
        secondary: List[Dict],
    ) -> List[Dict]:
        """
        Merge detections from both detectors using smart NMS.
        
        Strategy:
        1. Keep all primary detections
        2. Add secondary detections that don't overlap with primary
        3. For overlapping, prefer primary (higher precision)
        """
        if not secondary:
            return primary
        
        merged = list(primary)
        
        for sec_det in secondary:
            sec_bbox = sec_det["bbox"]
            
            # Check overlap with all primary detections
            is_duplicate = False
            for pri_det in primary:
                iou = self._compute_iou(sec_bbox, pri_det["bbox"])
                if iou > self.config.nms_iou_threshold:
                    is_duplicate = True
                    break
            
            # Add if not duplicate
            if not is_duplicate:
                # Boost confidence slightly if it's a class YOLO might miss
                if sec_det["class_name"].lower() in [c.lower() for c in self.config.always_verify_classes]:
                    sec_det["confidence"] = min(1.0, sec_det["confidence"] * 1.2)
                merged.append(sec_det)
        
        return merged
    
    def _compute_iou(self, box1: List[float], box2: List[float]) -> float:
        """Compute IoU between two bboxes [x1, y1, x2, y2]."""
        x1 = max(box1[0], box2[0])
        y1 = max(box1[1], box2[1])
        x2 = min(box1[2], box2[2])
        y2 = min(box1[3], box2[3])
        
        inter = max(0, x2 - x1) * max(0, y2 - y1)
        if inter == 0:
            return 0.0
        
        area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
        area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
        union = area1 + area2 - inter
        
        return inter / union if union > 0 else 0.0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get detection statistics."""
        return {
            "frames_processed": self._frame_count,
            "gdino_trigger_rate": self._gdino_trigger_count / max(1, self._frame_count),
            "avg_yolo_dets_per_frame": self._total_yolo_dets / max(1, self._frame_count),
            "avg_gdino_dets_per_trigger": self._total_gdino_dets / max(1, self._gdino_trigger_count),
        }
