"""
Open-Vocabulary Detection Pipeline
==================================

Integrates the propose→label architecture for true open-vocabulary detection:
1. Class-agnostic proposals (OWL-ViT or YOLO fallback)
2. Visual embedding extraction (CLIP)
3. Vocabulary bank matching (LVIS ~1200 labels)
4. Evidence gating (temporal + confidence)
5. Optional VLM verification for low-confidence

This replaces the hand-picked prompt approach (GroundingDINO, YOLO-World)
with a promptless, vocabulary-bank-driven system.

Usage:
    pipeline = OpenVocabPipeline.from_config(config)
    detections = pipeline.detect(frame, frame_idx=0)
    # Each detection has label_hypotheses_topk, not just single label

Author: Orion Research Team
Date: January 2026
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class OpenVocabConfig:
    """Configuration for open-vocabulary detection pipeline."""
    
    # Proposal backend
    proposer_type: str = "yoloworld_clip"
    """Proposal backend: 'owl' (OWL-ViT), 'yolo_clip' (YOLO + CLIP), 'yoloworld_clip' (YOLO-World + CLIP)."""
    
    proposer_model: str = "google/owlv2-base-patch16-ensemble"
    """Model for proposals (OWL-ViT model name or YOLO weights)."""
    
    # YOLO-World vocabulary for proposals
    yoloworld_classes: Optional[List[str]] = None
    """Custom classes for YOLO-World proposer. If None, uses indoor defaults."""
    
    # Vocabulary bank
    vocab_preset: str = "lvis"
    """Vocabulary bank: 'lvis', 'coco', 'objects365'."""
    
    vocab_bank_cache: str = "models/_cache/vocab_bank"
    """Cache directory for vocabulary embeddings."""
    
    # Embedding
    embedding_model: str = "openai/clip-vit-base-patch32"
    """CLIP model for visual embeddings."""
    
    # Hypothesis settings
    top_k: int = 5
    """Number of label hypotheses per detection."""
    
    min_similarity: float = 0.20
    """Minimum similarity for hypothesis inclusion."""
    
    # Detection threshold
    detection_confidence: float = 0.20
    """Minimum detection/proposal confidence."""
    
    # Evidence gating (see evidence_gates.py)
    enable_evidence_gates: bool = True
    """Enable multi-level evidence gating."""
    
    confidence_gate: float = 0.50
    """Auto-verify if above this confidence."""
    
    margin_gate: float = 0.10
    """Minimum margin between top-2 hypotheses."""
    
    temporal_window: int = 5
    """Number of frames for temporal consistency."""
    
    temporal_threshold: float = 0.60
    """Fraction of frames label must appear."""
    
    vlm_gate: bool = False
    """Enable VLM verification for uncertain detections."""
    
    vlm_model: str = "fastvlm-0.5b"
    """VLM model for verification."""
    
    # NMS
    nms_iou_threshold: float = 0.50
    """NMS IoU threshold for final detections."""
    
    # Device
    device: str = "auto"
    """Device: 'cuda', 'mps', 'cpu', or 'auto'."""
    
    # Optional pre-initialized models (for reuse from ModelManager)
    yolo_model: Optional[Any] = None
    """Pre-initialized YOLO model (optional, for yolo_clip proposer)."""
    
    # Legacy field aliases for backward compatibility
    proposer_backend: Optional[str] = None
    vocab_bank_preset: Optional[str] = None
    top_k_hypotheses: Optional[int] = None
    min_hypothesis_similarity: Optional[float] = None
    proposer_threshold: Optional[float] = None
    enable_temporal_gating: Optional[bool] = None
    temporal_consistency_frames: Optional[int] = None
    enable_confidence_gating: Optional[bool] = None
    confidence_gate_threshold: Optional[float] = None
    enable_vlm_verification: Optional[bool] = None
    vlm_verification_threshold: Optional[float] = None
    
    def __post_init__(self):
        """Apply legacy field aliases."""
        # Map legacy to new fields
        if self.proposer_backend is not None:
            self.proposer_type = self.proposer_backend
        if self.vocab_bank_preset is not None:
            # Map preset names
            preset_map = {"lvis1200": "lvis", "coco80": "coco"}
            self.vocab_preset = preset_map.get(self.vocab_bank_preset, self.vocab_bank_preset)
        if self.top_k_hypotheses is not None:
            self.top_k = self.top_k_hypotheses
        if self.min_hypothesis_similarity is not None:
            self.min_similarity = self.min_hypothesis_similarity
        if self.proposer_threshold is not None:
            self.detection_confidence = self.proposer_threshold
        if self.enable_temporal_gating is not None:
            self.enable_evidence_gates = self.enable_evidence_gates or self.enable_temporal_gating
        if self.temporal_consistency_frames is not None:
            self.temporal_window = self.temporal_consistency_frames
        if self.enable_confidence_gating is not None:
            self.enable_evidence_gates = self.enable_evidence_gates or self.enable_confidence_gating
        if self.confidence_gate_threshold is not None:
            self.confidence_gate = self.confidence_gate_threshold
        if self.enable_vlm_verification is not None:
            self.vlm_gate = self.enable_vlm_verification
        if self.vlm_verification_threshold is not None:
            # Map to confidence_gate if provided
            pass


class OpenVocabPipeline:
    """
    End-to-end open-vocabulary detection pipeline.
    
    Combines:
    - OWL-ViT or YOLO for class-agnostic proposals
    - CLIP for visual embeddings
    - Vocabulary bank for label hypotheses
    - Evidence gates for verification
    """
    
    def __init__(
        self,
        config: OpenVocabConfig,
        proposer: Any = None,
        vocab_bank: Any = None,
        clip_model: Any = None,
    ):
        self.config = config
        self.proposer = proposer
        self.vocab_bank = vocab_bank
        self.clip_model = clip_model
        
        # Statistics
        self._frame_count = 0
        self._total_proposals = 0
        self._total_detections = 0
        
        # Temporal buffer for consistency gating
        self._temporal_buffer: Dict[int, List[Dict]] = {}  # track_id -> recent hypotheses
        
        logger.info(f"OpenVocabPipeline initialized: proposer={config.proposer_backend}")
    
    @classmethod
    def from_config(
        cls,
        config: Optional[OpenVocabConfig] = None,
        device: str = "auto",
    ) -> "OpenVocabPipeline":
        """
        Create pipeline from configuration with all components.
        
        Args:
            config: Pipeline configuration
            device: Override device setting
            
        Returns:
            Initialized pipeline
        """
        config = config or OpenVocabConfig()
        if device != "auto":
            config.device = device
        
        resolved_device = cls._resolve_device(config.device)
        
        # Load vocabulary bank
        from orion.perception.vocab_bank import VocabularyBank
        
        logger.info(f"Loading vocabulary bank: {config.vocab_preset}")
        vocab_bank = VocabularyBank.from_preset(
            preset=config.vocab_preset,
            cache_dir=config.vocab_bank_cache,
            embedding_model=config.embedding_model,
            device=resolved_device,
        )
        
        # Load proposer
        from orion.perception.detectors.owl_proposer import (
            OWLProposer,
            OWLProposerConfig,
            OWLProposerFallback,
        )
        
        proposer_config = OWLProposerConfig(
            model_name=config.proposer_model,
            device=resolved_device,
            objectness_threshold=config.detection_confidence,
            vocab_bank_preset=config.vocab_preset,
            top_k_hypotheses=config.top_k,
            min_similarity=config.min_similarity,
        )
        
        proposer = None
        clip_model = None
        
        if config.proposer_type == "owl":
            try:
                proposer = OWLProposer(proposer_config, vocab_bank=vocab_bank)
                proposer._load_model()  # Test loading
            except Exception as e:
                logger.warning(f"OWL-ViT not available, falling back to YOLO-World+CLIP: {e}")
                config.proposer_type = "yoloworld_clip"
        
        if config.proposer_type == "yoloworld_clip":
            # Use YOLO-World for better open-vocab proposals
            from ultralytics import YOLO
            
            # Load YOLO-World model
            yolo_world = YOLO("yolov8m-worldv2.pt")
            yolo_world.to(resolved_device)
            
            # Set classes for YOLO-World
            yoloworld_classes = config.yoloworld_classes or cls._get_default_yoloworld_classes()
            yolo_world.set_classes(yoloworld_classes)
            
            # Load CLIP for refined embeddings
            clip_model = cls._load_clip(config.embedding_model, resolved_device)
            
            proposer = OWLProposerFallback(
                config=proposer_config,
                yolo_model=yolo_world,
                clip_model=clip_model,
                vocab_bank=vocab_bank,
            )
            logger.info(f"Using YOLO-World proposer with {len(yoloworld_classes)} classes")
        
        elif config.proposer_type == "yolo_clip" or proposer is None:
            # Fallback to vanilla YOLO + CLIP
            yolo_model = config.yolo_model
            if yolo_model is None:
                from ultralytics import YOLO
                yolo_model = YOLO("yolo11m.pt")
                yolo_model.to(resolved_device)
            
            # Load CLIP for embeddings
            clip_model = cls._load_clip(config.embedding_model, resolved_device)
            
            proposer = OWLProposerFallback(
                config=proposer_config,
                yolo_model=yolo_model,
                clip_model=clip_model,
                vocab_bank=vocab_bank,
            )
            logger.info("Using YOLO+CLIP proposer (limited to COCO classes)")
        
        return cls(
            config=config,
            proposer=proposer,
            vocab_bank=vocab_bank,
            clip_model=clip_model,
        )
    
    @staticmethod
    def _resolve_device(device: str) -> str:
        """Resolve 'auto' to actual device."""
        if device != "auto":
            return device
        
        import torch
        if torch.cuda.is_available():
            return "cuda"
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"
        return "cpu"
    
    @staticmethod
    def _get_default_yoloworld_classes() -> List[str]:
        """Default classes for YOLO-World open-vocab detection."""
        return [
            # People
            "person", "face", "hand",
            # Electronics
            "laptop", "computer", "monitor", "tv", "keyboard", "mouse", 
            "phone", "tablet", "remote", "camera", "speaker", "headphones",
            # Furniture
            "chair", "couch", "table", "desk", "bed", "shelf", "cabinet",
            # Containers
            "cup", "mug", "glass", "bottle", "bowl", "plate", "box", "bag",
            "backpack", "vase", "basket",
            # Decor
            "picture frame", "painting", "clock", "mirror", "lamp", "plant",
            "flowers", "candle", "book", "pillow", "blanket", "rug",
            # Kitchen
            "refrigerator", "microwave", "oven", "sink", "pan", "pot",
            # Other
            "door", "window", "curtain", "stairs",
            "",  # Background class per Ultralytics guidance
        ]
    
    @staticmethod
    def _load_clip(model_name: str, device: str) -> Any:
        """Load CLIP model for visual embeddings."""
        try:
            from transformers import CLIPModel
            
            model = CLIPModel.from_pretrained(model_name)
            model.to(device)
            model.eval()
            return model
        except Exception as e:
            logger.warning(f"Failed to load CLIP: {e}")
            return None
    
    def detect(
        self,
        frame: np.ndarray,
        frame_idx: int = 0,
        timestamp: float = 0.0,
        track_states: Optional[Dict[int, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Run open-vocabulary detection on a frame.
        
        Args:
            frame: BGR frame from OpenCV
            frame_idx: Frame number
            timestamp: Timestamp in seconds
            track_states: Optional existing track states for temporal gating
            
        Returns:
            List of detections with label_hypotheses_topk
        """
        self._frame_count += 1
        
        # Step 1: Generate proposals
        proposals = self.proposer.propose(frame, frame_idx, timestamp)
        self._total_proposals += len(proposals)
        
        # Step 2: Apply evidence gates
        if self.config.enable_evidence_gates:
            proposals = self._apply_confidence_gate(proposals)
        
            if track_states:
                proposals = self._apply_temporal_gate(proposals, track_states)
        
        # Step 3: VLM verification for uncertain detections
        if self.config.vlm_gate:
            proposals = self._apply_vlm_verification(proposals, frame)
        
        # Step 4: NMS on final detections
        proposals = self._apply_nms(proposals)
        
        self._total_detections += len(proposals)
        
        # Step 5: Format output
        detections = []
        for p in proposals:
            det = {
                "frame_idx": frame_idx,
                "timestamp": timestamp,
                "bbox": p.get("bbox_xyxy", p.get("bbox", [])),
                "bbox_xyxy": p.get("bbox_xyxy", p.get("bbox", [])),
                "centroid": p.get("centroid", [
                    (p["bbox_xyxy"][0] + p["bbox_xyxy"][2]) / 2,
                    (p["bbox_xyxy"][1] + p["bbox_xyxy"][3]) / 2,
                ] if "bbox_xyxy" in p else []),
                "label": p.get("label", "unknown"),
                "confidence": p.get("confidence", p.get("objectness", 0.0)),
                "label_hypotheses": p.get("label_hypotheses", []),
                "verification_status": p.get("verification_status", "unverified"),
                "verification_source": p.get("verification_source"),
                "proposal_confidence": p.get("objectness", p.get("confidence", 0.0)),
                "detector_source": f"openvocab_{self.config.proposer_type}",
                "frame_width": p.get("frame_width", frame.shape[1]),
                "frame_height": p.get("frame_height", frame.shape[0]),
            }
            detections.append(det)
        
        return detections
    
    def _apply_confidence_gate(
        self,
        proposals: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Gate detections by confidence threshold."""
        gated = []
        
        for p in proposals:
            confidence = p.get("confidence", p.get("objectness", 0.0))
            
            if confidence >= self.config.confidence_gate:
                p["verification_status"] = "verified"
                p["verification_source"] = "confidence"
                gated.append(p)
            elif p.get("label_hypotheses"):
                # Check margin between top hypotheses
                hypotheses = p.get("label_hypotheses", [])
                if len(hypotheses) >= 2:
                    margin = hypotheses[0].get("score", 0) - hypotheses[1].get("score", 0)
                    if margin >= self.config.margin_gate:
                        p["verification_status"] = "verified"
                        p["verification_source"] = "margin"
                        gated.append(p)
                        continue
                # Has hypotheses, mark for potential verification
                p["verification_status"] = "pending"
                gated.append(p)
            else:
                # Low confidence + no hypotheses = skip
                logger.debug(f"Confidence gate rejected: {confidence}")
        
        return gated
    
    def _apply_temporal_gate(
        self,
        proposals: List[Dict[str, Any]],
        track_states: Dict[int, Any],
    ) -> List[Dict[str, Any]]:
        """
        Gate labels by temporal consistency.
        
        If a track has been assigned label X for N frames, and new proposal
        says Y, require higher evidence for Y.
        """
        # TODO: Implement temporal consistency checking
        # For now, pass through
        return proposals
    
    def _apply_vlm_verification(
        self,
        proposals: List[Dict[str, Any]],
        frame: np.ndarray,
    ) -> List[Dict[str, Any]]:
        """
        Use VLM to verify uncertain detections.
        
        For detections below vlm_verification_threshold, ask VLM
        "What is this object?" and compare to hypotheses.
        """
        # TODO: Implement VLM verification
        # For now, pass through
        return proposals
    
    def _apply_nms(
        self,
        proposals: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Apply NMS to final detections."""
        if len(proposals) <= 1:
            return proposals
        
        import torch
        from torchvision.ops import nms
        
        boxes = torch.tensor(
            [p["bbox_xyxy"] for p in proposals],
            dtype=torch.float32,
        )
        scores = torch.tensor(
            [p.get("confidence", p.get("objectness", 0.0)) for p in proposals],
            dtype=torch.float32,
        )
        
        keep_indices = nms(boxes, scores, self.config.nms_iou_threshold)
        
        return [proposals[i] for i in keep_indices.tolist()]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get pipeline statistics."""
        return {
            "frame_count": self._frame_count,
            "total_proposals": self._total_proposals,
            "total_detections": self._total_detections,
            "avg_proposals_per_frame": (
                self._total_proposals / self._frame_count
                if self._frame_count > 0 else 0
            ),
            "avg_detections_per_frame": (
                self._total_detections / self._frame_count
                if self._frame_count > 0 else 0
            ),
        }


# Convenience function for quick testing
def detect_open_vocab(
    frame: np.ndarray,
    frame_idx: int = 0,
    config: Optional[OpenVocabConfig] = None,
    device: str = "auto",
) -> List[Dict[str, Any]]:
    """
    One-shot open-vocabulary detection.
    
    For video processing, use OpenVocabPipeline.from_config() instead
    to avoid reloading models per frame.
    """
    pipeline = OpenVocabPipeline.from_config(config, device)
    return pipeline.detect(frame, frame_idx)
