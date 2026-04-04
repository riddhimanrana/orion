"""
Temporal Consistency Filter for Orion v2

Filters detections based on temporal persistence across frames.
Rejects 1-frame "ghost" detections that are likely false positives.

Author: Orion Research Team  
Date: January 2026
"""

from __future__ import annotations

import logging
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple, Optional

import numpy as np

logger = logging.getLogger(__name__)


def compute_iou(box1: List[float], box2: List[float]) -> float:
    """Compute IoU between two bounding boxes [x1, y1, x2, y2]."""
    x1_min, y1_min, x1_max, y1_max = box1
    x2_min, y2_min, x2_max, y2_max = box2
    
    # Intersection
    inter_x_min = max(x1_min, x2_min)
    inter_y_min = max(y1_min, y2_min)
    inter_x_max = min(x1_max, x2_max)
    inter_y_max = min(y1_max, y2_max)
    
    if inter_x_max < inter_x_min or inter_y_max < inter_y_min:
        return 0.0
    
    inter_area = (inter_x_max - inter_x_min) * (inter_y_max - inter_y_min)
    
    # Union
    box1_area = (x1_max - x1_min) * (y1_max - y1_min)
    box2_area = (x2_max - x2_min) * (y2_max - y2_min)
    union_area = box1_area + box2_area - inter_area
    
    return inter_area / max(union_area, 1e-6)


@dataclass
class DetectionCandidate:
    """A detection candidate being tracked across frames."""
    
    bbox: List[float]
    class_name: str
    confidence: float
    first_frame: int
    last_frame: int
    frame_count: int
    avg_confidence: float
    detection_history: List[Dict[str, Any]]
    
    def update(self, frame_idx: int, detection: Dict[str, Any]) -> None:
        """Update candidate with new detection from current frame."""
        self.last_frame = frame_idx
        self.frame_count += 1
        self.detection_history.append(detection)
        
        # Update bbox to latest detection (could also do weighted average)
        self.bbox = detection["bbox"]
        
        # Update rolling average confidence
        self.avg_confidence = (
            (self.avg_confidence * (self.frame_count - 1) + detection["confidence"]) 
            / self.frame_count
        )
    
    def is_stale(self, current_frame: int, max_gap: int = 2) -> bool:
        """Check if candidate has gone missing for too many frames."""
        return (current_frame - self.last_frame) > max_gap
    
    def is_valid(self, min_frames: int = 2) -> bool:
        """Check if candidate has been seen in enough frames."""
        return self.frame_count >= min_frames


class TemporalFilter:
    """
    Temporal consistency filter for detections.
    
    Tracks detections across frames and only accepts those that persist
    for a minimum number of consecutive frames.
    
    Strategy:
    1. Maintain a buffer of recent frames
    2. For each new detection, try to match it to existing candidates
    3. Only emit detections that have persisted for min_consecutive_frames
    4. Expire stale candidates
    """
    
    def __init__(
        self,
        min_consecutive_frames: int = 2,
        temporal_iou_threshold: float = 0.5,
        temporal_memory_frames: int = 5,
        max_gap_frames: int = 2,
    ):
        """
        Initialize temporal filter.
        
        Args:
            min_consecutive_frames: Minimum frames a detection must appear in
            temporal_iou_threshold: IoU threshold for matching detections
            temporal_memory_frames: Number of frames to keep in history
            max_gap_frames: Maximum gap before expiring a candidate
        """
        self.min_consecutive_frames = min_consecutive_frames
        self.temporal_iou_threshold = temporal_iou_threshold
        self.temporal_memory_frames = temporal_memory_frames
        self.max_gap_frames = max_gap_frames
        
        # Tracking state
        self.candidates: Dict[int, DetectionCandidate] = {}
        self.next_candidate_id = 0
        self.current_frame_idx = 0
        
        # Frame buffer for adaptive processing
        self.frame_buffer: deque = deque(maxlen=temporal_memory_frames)
        
        # Statistics
        self.stats = {
            "total_raw_detections": 0,
            "accepted_detections": 0,
            "rejected_detections": 0,
            "active_candidates": 0,
        }
        
        logger.debug(
            f"TemporalFilter initialized: min_frames={min_consecutive_frames}, "
            f"iou_thresh={temporal_iou_threshold}"
        )
    
    def process_frame(
        self,
        detections: List[Dict[str, Any]],
        frame_idx: int
    ) -> List[Dict[str, Any]]:
        """
        Process detections for a single frame.
        
        Args:
            detections: Raw detections from detector
            frame_idx: Current frame index
            
        Returns:
            Filtered detections that pass temporal consistency check
        """
        self.current_frame_idx = frame_idx
        self.stats["total_raw_detections"] += len(detections)
        
        # Match detections to existing candidates
        matched_detections = set()
        for detection in detections:
            bbox = detection["bbox"]
            class_name = detection["class_name"]
            
            # Try to match with existing candidates
            best_match_id = None
            best_iou = 0.0
            
            for cand_id, candidate in self.candidates.items():
                # Only match same class
                if candidate.class_name != class_name:
                    continue
                
                # Check if still active
                if candidate.is_stale(frame_idx, self.max_gap_frames):
                    continue
                
                iou = compute_iou(bbox, candidate.bbox)
                if iou > best_iou and iou >= self.temporal_iou_threshold:
                    best_iou = iou
                    best_match_id = cand_id
            
            if best_match_id is not None:
                # Update existing candidate
                self.candidates[best_match_id].update(frame_idx, detection)
                matched_detections.add(best_match_id)
            else:
                # Create new candidate
                candidate = DetectionCandidate(
                    bbox=bbox,
                    class_name=class_name,
                    confidence=detection["confidence"],
                    first_frame=frame_idx,
                    last_frame=frame_idx,
                    frame_count=1,
                    avg_confidence=detection["confidence"],
                    detection_history=[detection],
                )
                self.candidates[self.next_candidate_id] = candidate
                matched_detections.add(self.next_candidate_id)
                self.next_candidate_id += 1
        
        # Expire stale candidates
        stale_ids = [
            cand_id for cand_id, cand in self.candidates.items()
            if cand.is_stale(frame_idx, self.max_gap_frames)
        ]
        for cand_id in stale_ids:
            del self.candidates[cand_id]
        
        # Collect valid detections (candidates that have persisted long enough)
        valid_detections = []
        for cand_id, candidate in self.candidates.items():
            if candidate.is_valid(self.min_consecutive_frames):
                # Return the latest detection from this candidate
                if candidate.detection_history:
                    det = candidate.detection_history[-1].copy()
                    # Add temporal metadata
                    det["temporal_frame_count"] = candidate.frame_count
                    det["temporal_avg_confidence"] = candidate.avg_confidence
                    det["temporal_first_frame"] = candidate.first_frame
                    valid_detections.append(det)
        
        # Update statistics
        self.stats["accepted_detections"] += len(valid_detections)
        self.stats["rejected_detections"] += len(detections) - len(valid_detections)
        self.stats["active_candidates"] = len(self.candidates)
        
        return valid_detections
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get filter statistics."""
        total = self.stats["total_raw_detections"]
        if total == 0:
            return self.stats
        
        return {
            **self.stats,
            "acceptance_rate": self.stats["accepted_detections"] / total,
            "rejection_rate": self.stats["rejected_detections"] / total,
        }
    
    def reset(self) -> None:
        """Reset filter state."""
        self.candidates.clear()
        self.next_candidate_id = 0
        self.current_frame_idx = 0
        self.frame_buffer.clear()
        self.stats = {
            "total_raw_detections": 0,
            "accepted_detections": 0,
            "rejected_detections": 0,
            "active_candidates": 0,
        }
