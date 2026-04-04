"""
Evidence Gates for Detection Verification
==========================================

Multi-level verification system to validate detection labels:
1. Confidence gate - simple threshold
2. Temporal gate - consistency across frames
3. Margin gate - confidence margin between top hypotheses
4. VLM gate - language model verification for uncertain cases

These gates prevent false positives from reaching final outputs
while allowing true detections through efficiently.

Usage:
    gates = EvidenceGates.from_config(config)
    verified = gates.apply(detections, track_history)

Author: Orion Research Team
Date: January 2026
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class VerificationStatus(str, Enum):
    """Status of detection verification."""
    VERIFIED = "verified"
    PENDING = "pending"
    UNVERIFIED = "unverified"
    REJECTED = "rejected"


class VerificationSource(str, Enum):
    """Source of verification decision."""
    CONFIDENCE = "confidence"
    TEMPORAL = "temporal"
    MARGIN = "margin"
    VLM = "vlm"
    MANUAL = "manual"
    NONE = "none"


@dataclass
class EvidenceGatesConfig:
    """Configuration for evidence gates."""
    
    # Confidence gate
    enable_confidence_gate: bool = True
    confidence_threshold_high: float = 0.35
    """Detections above this are auto-verified."""
    confidence_threshold_low: float = 0.15
    """Detections below this are rejected unless other evidence."""
    
    # Temporal consistency gate
    enable_temporal_gate: bool = True
    temporal_window_frames: int = 5
    """Number of frames for temporal voting."""
    temporal_consistency_threshold: float = 0.6
    """Fraction of frames that must agree on label."""
    temporal_iou_threshold: float = 0.5
    """IoU threshold for matching detections across frames."""
    
    # Margin gate (confidence margin between top hypotheses)
    enable_margin_gate: bool = True
    margin_threshold: float = 0.10
    """Minimum margin between top-1 and top-2 hypotheses."""
    margin_auto_verify: float = 0.20
    """If margin > this, auto-verify without other checks."""
    
    # VLM verification gate
    enable_vlm_gate: bool = False
    vlm_threshold: float = 0.20
    """Trigger VLM verification below this confidence."""
    vlm_model: str = "fastvlm-0.5b"
    """VLM model for verification."""
    vlm_similarity_threshold: float = 0.50
    """VLM description must have this similarity to label."""
    
    # Class-specific overrides
    class_confidence_overrides: Dict[str, float] = field(default_factory=dict)
    """Per-class confidence thresholds (e.g., {'clock': 0.40})."""
    
    always_verify_classes: List[str] = field(default_factory=lambda: [
        "clock", "vase", "potted plant", "remote", "scissors",
    ])
    """Classes that always require additional verification."""


class EvidenceGates:
    """
    Multi-level evidence gating system.
    
    Applies a cascade of gates to validate detection labels:
    1. High-confidence detections pass immediately
    2. Low-confidence but temporally consistent pass
    3. Uncertain cases go to margin or VLM verification
    4. Rejected cases are filtered out
    """
    
    def __init__(
        self,
        config: EvidenceGatesConfig,
        vlm_model: Optional[Any] = None,
    ):
        self.config = config
        self.vlm_model = vlm_model
        
        # Track history for temporal gating
        self._track_history: Dict[int, List[Dict]] = {}
        
        # Statistics
        self._stats = {
            "total_processed": 0,
            "verified_by_confidence": 0,
            "verified_by_temporal": 0,
            "verified_by_margin": 0,
            "verified_by_vlm": 0,
            "rejected": 0,
            "pending": 0,
        }
        
        logger.info(f"EvidenceGates initialized")
    
    @classmethod
    def from_config(
        cls,
        config: Optional[EvidenceGatesConfig] = None,
    ) -> "EvidenceGates":
        """Create gates from configuration."""
        config = config or EvidenceGatesConfig()
        
        vlm_model = None
        if config.enable_vlm_gate:
            vlm_model = cls._load_vlm(config.vlm_model)
        
        return cls(config, vlm_model)
    
    @staticmethod
    def _load_vlm(model_name: str) -> Optional[Any]:
        """Load VLM for verification."""
        try:
            # Import FastVLM or similar
            logger.info(f"Loading VLM for verification: {model_name}")
            # TODO: Implement actual VLM loading
            return None
        except Exception as e:
            logger.warning(f"Failed to load VLM: {e}")
            return None
    
    def apply(
        self,
        detections: List[Dict[str, Any]],
        frame_idx: int = 0,
        frame: Optional[np.ndarray] = None,
    ) -> List[Dict[str, Any]]:
        """
        Apply all enabled gates to detections.
        
        Args:
            detections: Raw detections with label_hypotheses_topk
            frame_idx: Current frame number
            frame: Optional frame image for VLM verification
            
        Returns:
            Verified/filtered detections with status
        """
        results = []
        
        for det in detections:
            self._stats["total_processed"] += 1
            
            # Apply gates in cascade
            status, source = self._evaluate_detection(det, frame_idx, frame)
            
            det["verification_status"] = status.value
            det["verification_source"] = source.value
            
            if status == VerificationStatus.VERIFIED:
                results.append(det)
                self._update_stats(source)
            elif status == VerificationStatus.PENDING:
                # Keep pending detections but mark them
                results.append(det)
                self._stats["pending"] += 1
            else:  # REJECTED
                self._stats["rejected"] += 1
                logger.debug(f"Rejected detection: {det.get('label')} @ {det.get('confidence'):.2f}")
        
        # Update track history for temporal gating
        self._update_track_history(results, frame_idx)
        
        return results
    
    def _evaluate_detection(
        self,
        det: Dict[str, Any],
        frame_idx: int,
        frame: Optional[np.ndarray],
    ) -> Tuple[VerificationStatus, VerificationSource]:
        """Evaluate a single detection through gate cascade."""
        
        label = det.get("label", "unknown")
        confidence = det.get("confidence", 0.0)
        hypotheses = det.get("label_hypotheses_topk", [])
        track_id = det.get("track_id", -1)
        
        # Get class-specific threshold
        conf_threshold = self.config.class_confidence_overrides.get(
            label.lower(),
            self.config.confidence_threshold_high,
        )
        
        # Gate 1: High confidence
        if self.config.enable_confidence_gate and confidence >= conf_threshold:
            return VerificationStatus.VERIFIED, VerificationSource.CONFIDENCE
        
        # Gate 2: Margin between hypotheses
        if self.config.enable_margin_gate and len(hypotheses) >= 2:
            margin = hypotheses[0].get("score", 0) - hypotheses[1].get("score", 0)
            
            if margin >= self.config.margin_auto_verify:
                return VerificationStatus.VERIFIED, VerificationSource.MARGIN
            elif margin >= self.config.margin_threshold:
                # Good margin but not auto-verify, continue to other gates
                pass
        
        # Gate 3: Temporal consistency
        if self.config.enable_temporal_gate and track_id >= 0:
            is_consistent, consistency_score = self._check_temporal_consistency(
                track_id, label, det.get("bbox_xyxy")
            )
            
            if is_consistent:
                return VerificationStatus.VERIFIED, VerificationSource.TEMPORAL
        
        # Gate 4: VLM verification (expensive, last resort)
        if (
            self.config.enable_vlm_gate
            and self.vlm_model is not None
            and frame is not None
            and confidence < self.config.vlm_threshold
        ):
            is_valid = self._verify_with_vlm(det, frame)
            
            if is_valid:
                return VerificationStatus.VERIFIED, VerificationSource.VLM
            else:
                return VerificationStatus.REJECTED, VerificationSource.VLM
        
        # Check for always-verify classes
        if label.lower() in self.config.always_verify_classes:
            return VerificationStatus.PENDING, VerificationSource.NONE
        
        # Below low threshold = reject
        if confidence < self.config.confidence_threshold_low:
            return VerificationStatus.REJECTED, VerificationSource.CONFIDENCE
        
        # Uncertain - mark as pending
        return VerificationStatus.PENDING, VerificationSource.NONE
    
    def _check_temporal_consistency(
        self,
        track_id: int,
        label: str,
        bbox: Optional[List[float]],
    ) -> Tuple[bool, float]:
        """
        Check if label is temporally consistent for this track.
        
        Returns (is_consistent, consistency_score).
        """
        if track_id not in self._track_history:
            return False, 0.0
        
        history = self._track_history[track_id]
        
        if len(history) < 2:
            return False, 0.0
        
        # Count label occurrences in recent history
        window = history[-self.config.temporal_window_frames:]
        label_counts = {}
        
        for entry in window:
            entry_label = entry.get("label", "unknown")
            label_counts[entry_label] = label_counts.get(entry_label, 0) + 1
        
        # Check if current label is consistent
        current_count = label_counts.get(label, 0)
        consistency = current_count / len(window)
        
        is_consistent = consistency >= self.config.temporal_consistency_threshold
        
        return is_consistent, consistency
    
    def _verify_with_vlm(
        self,
        det: Dict[str, Any],
        frame: np.ndarray,
    ) -> bool:
        """
        Verify detection using VLM description.
        
        Returns True if VLM confirms the label.
        """
        if self.vlm_model is None:
            return False
        
        # Extract crop
        bbox = det.get("bbox_xyxy", [0, 0, 100, 100])
        x1, y1, x2, y2 = [int(v) for v in bbox]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(frame.shape[1], x2), min(frame.shape[0], y2)
        
        if x2 <= x1 or y2 <= y1:
            return False
        
        crop = frame[y1:y2, x1:x2]
        
        # TODO: Implement actual VLM verification
        # For now, pass through
        return True
    
    def _update_track_history(
        self,
        detections: List[Dict[str, Any]],
        frame_idx: int,
    ) -> None:
        """Update track history for temporal gating."""
        for det in detections:
            track_id = det.get("track_id", -1)
            if track_id < 0:
                continue
            
            if track_id not in self._track_history:
                self._track_history[track_id] = []
            
            self._track_history[track_id].append({
                "frame_idx": frame_idx,
                "label": det.get("label", "unknown"),
                "confidence": det.get("confidence", 0.0),
                "bbox": det.get("bbox_xyxy"),
            })
            
            # Keep only recent history
            max_history = self.config.temporal_window_frames * 2
            if len(self._track_history[track_id]) > max_history:
                self._track_history[track_id] = self._track_history[track_id][-max_history:]
    
    def _update_stats(self, source: VerificationSource) -> None:
        """Update verification statistics."""
        if source == VerificationSource.CONFIDENCE:
            self._stats["verified_by_confidence"] += 1
        elif source == VerificationSource.TEMPORAL:
            self._stats["verified_by_temporal"] += 1
        elif source == VerificationSource.MARGIN:
            self._stats["verified_by_margin"] += 1
        elif source == VerificationSource.VLM:
            self._stats["verified_by_vlm"] += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """Get gate statistics."""
        total = self._stats["total_processed"]
        if total == 0:
            return self._stats.copy()
        
        stats = self._stats.copy()
        stats["verification_rate"] = (
            (stats["verified_by_confidence"] + stats["verified_by_temporal"] +
             stats["verified_by_margin"] + stats["verified_by_vlm"])
            / total
        )
        stats["rejection_rate"] = stats["rejected"] / total
        
        return stats
    
    def reset(self) -> None:
        """Reset state and statistics."""
        self._track_history.clear()
        for key in self._stats:
            self._stats[key] = 0


def apply_evidence_gates(
    detections: List[Dict[str, Any]],
    config: Optional[EvidenceGatesConfig] = None,
    frame_idx: int = 0,
    frame: Optional[np.ndarray] = None,
) -> List[Dict[str, Any]]:
    """
    Convenience function to apply gates to detections.
    
    For video processing, create EvidenceGates instance once
    to maintain temporal state.
    """
    gates = EvidenceGates.from_config(config)
    return gates.apply(detections, frame_idx, frame)
