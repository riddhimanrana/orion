"""
Perception Engine
=================

High-level orchestration of the perception pipeline.

Orchestrates the complete Phase 1 flow:
1. Frame observation & detection (observer)
2. Visual embedding generation (embedder)
3. Entity clustering & tracking (tracker)
4. Entity description (describer)

Author: Orion Research Team
Date: October 2025
"""

import os
import logging
import math
import time
from pathlib import Path
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
import json
from dataclasses import dataclass, field

# Initialise logger early so try/except blocks can use it
logger = logging.getLogger(__name__)

from orion.perception.types import (
    Observation,
    PerceptionEntity,
    # PerceptionResult,
    ObjectClass,
    EntityState3D,
    Perception3DResult,
    CameraIntrinsics,
    VisibilityState,
    Hand,
    HandPose,
)
from orion.perception.config import PerceptionConfig
from orion.perception.perception_3d import backproject_point
from orion.perception.observer import FrameObserver
from orion.perception.embedder import VisualEmbedder
from orion.perception.trackers.hdbscan import EntityTracker
from orion.perception.describer import EntityDescriber
# from orion.perception.reid import ReidModel
from orion.perception.depth import DepthEstimator
# from orion.utils.file_utils import find_latest_file
from orion.settings import OrionSettings

# Add this import
from orion.perception.trackers.enhanced import Track


@dataclass
class PerceptionResult:
    """Structured result object for perception pipeline.

    Contains detected entities, raw observations, and metadata about the
    processing pipeline and performance.

    Attributes:
        entities: List of detected entities
        raw_observations: List of raw observation data
        video_path: Path to the input video
        total_frames: Total number of frames in the video
        fps: Frames per second of the video
        duration_seconds: Duration of the video in seconds
        processing_time_seconds: Total processing time in seconds
        metrics: Optional dictionary of additional metrics
    """

    entities: List[PerceptionEntity] = field(default_factory=list)
    raw_observations: List[Observation] = field(default_factory=list)
    video_path: str = ""
    total_frames: int = 0
    fps: float = 0.0
    duration_seconds: float = 0.0
    processing_time_seconds: float = 0.0
    scene_caption: str = ""
    metrics: Optional[Dict[str, float]] = None

    @property
    def total_detections(self) -> int:
        """Total number of raw detections/observations."""
        return len(self.raw_observations)

    @property
    def unique_entities(self) -> int:
        """Total number of unique entities found."""
        return len(self.entities)


# Phase 2: Tracking imports (legacy tracker removed)
TRACKING_AVAILABLE = False

from orion.managers.model_manager import ModelManager
from orion.perception.trackers.base import TrackerProtocol

# Optional enhanced tracker (appearance Re-ID + 3D KF)
try:
    from orion.perception.trackers.enhanced import EnhancedTracker
    ENHANCED_TRACKER_AVAILABLE = True
except Exception as e:
    logging.warning(f"EnhancedTracker import failed: {e}")
    ENHANCED_TRACKER_AVAILABLE = False

# Memgraph Backend
try:
    from orion.graph.backends.memgraph import MemgraphBackend
    MEMGRAPH_AVAILABLE = True
except ImportError as e:
    logging.warning(f"MemgraphBackend import failed: {e}")
    MEMGRAPH_AVAILABLE = False

# CIS Scorer for Stage 4 causal relationships
try:
    from orion.analysis.cis_scorer import CausalInfluenceScorer, CISEdge
    CIS_AVAILABLE = True
except ImportError as e:
    logging.warning(f"CausalInfluenceScorer import failed: {e}")
    CIS_AVAILABLE = False

from orion.perception.spatial_zones import ZoneManager
from orion.utils.profiling import profile, Profiler

# Scene Context Manager for v2
try:
    from orion.perception.scene_context import SceneContextManager, SceneContextConfig
    SCENE_CONTEXT_AVAILABLE = True
except ImportError as e:
    logging.warning(f"SceneContextManager import failed: {e}")
    SCENE_CONTEXT_AVAILABLE = False

# Scene-based semantic filter using CLIP embeddings (legacy)
try:
    from orion.perception.scene_filter import SceneFilter, SceneFilterConfig
    SCENE_FILTER_AVAILABLE = True
except ImportError as e:
    logging.warning(f"SceneFilter import failed: {e}")
    SCENE_FILTER_AVAILABLE = False

# v2: Enhanced semantic filter with scene-type classification and VLM verification
try:
    from orion.perception.semantic_filter_v2 import SemanticFilterV2, SemanticFilterV2Config
    SEMANTIC_FILTER_V2_AVAILABLE = True
except ImportError as e:
    logging.warning(f"SemanticFilterV2 import failed: {e}")
    SEMANTIC_FILTER_V2_AVAILABLE = False


class PerceptionEngine:
    """High-level orchestrator for the perception pipeline."""

    def __init__(self, config: PerceptionConfig, db_manager=None, verbose: bool = False):
        """
        Initialize perception engine.
        
        Args:
            config: Perception configuration (uses defaults if None)
            verbose: Enable verbose logging
        """
        self.config = config or PerceptionConfig()
        self.verbose = verbose
        self.memgraph = db_manager
        self.zone_manager = ZoneManager()
        
        # Model manager (lazy loading)
        self.model_manager = ModelManager.get_instance()
        # Update model names from config before they're loaded
        if self.config.detection.backend in {"yolo", "hybrid"}:
            self.model_manager.yolo_model_name = self.config.detection.model
        if self.config.detection.backend in {"groundingdino", "dinov3"}:
            self.model_manager.gdino_model_name = self.config.detection.model
        
        # Pipeline components (initialized lazily)
        self.observer: Optional[FrameObserver] = None
        self.embedder: Optional[VisualEmbedder] = None
        self.tracker: Optional[EntityTracker] = None
        self.describer: Optional[EntityDescriber] = None
        # self.reid_model: Optional[ReidModel] = None
        self.depth_estimator: Optional[DepthEstimator] = None
        self.enhanced_tracker: Optional[TrackerProtocol] = None
        
        # Scene context manager for v2 (FastVLM scene captions)
        self.scene_context: Optional[SceneContextManager] = None
        
        # Scene-based semantic filter (CLIP embeddings)
        self.scene_filter: Optional[SceneFilter] = None

        # Optional: open-vocab candidate labeler (non-committal hypotheses)
        self._open_vocab_labeler = None

        # Tracking history
        self.tracking_history: Dict[int, List[Track]] = {}  # To store track history
        
        # Stage 4: CIS scorer and temporal buffer
        self.cis_scorer = None
        self._cis_buffer: Dict[int, List[Track]] = {}  # Sliding window of recent tracks
        self._cis_edges: List = []  # Buffered CIS edges for batch commit
        
        # Stage 5: Memgraph batch buffers
        self._observation_buffer: List[Dict] = []
        self._relation_buffer: List[Dict] = []
        
        self._initialize_components()

    def _initialize_components(self):
        """Initializes all perception components based on the config."""
        settings = OrionSettings.load()

        use_hybrid = (
            self.config.detection.backend == "hybrid"
            or bool(getattr(self.config.detection, "enable_hybrid_detection", False))
        )
        
        # YOLO-World detector
        yoloworld_model = None
        if self.config.detection.backend == "yoloworld":
            logger.info("Initializing YOLO-World detector...")
            # Set model name and classes before loading
            self.model_manager.yoloworld_model_name = self.config.detection.yoloworld_model
            self.model_manager.yoloworld_classes = (
                self.config.detection.yoloworld_categories()
                if getattr(self.config.detection, "yoloworld_use_custom_classes", True)
                else None
            )
            yoloworld_model = self.model_manager.yoloworld

        # Frame observer
        gdino_model = None
        gdino_processor = None
        if self.config.detection.backend in {"groundingdino", "dinov3"} or use_hybrid:
            gdino_model, gdino_processor = self.model_manager.gdino

        hybrid_detector = None
        if use_hybrid:
            try:
                from orion.perception.hybrid_detector import HybridDetector, HybridDetectorConfig

                always_verify = getattr(self.config.detection, "hybrid_always_verify", None)
                if not always_verify:
                    always_verify = ["remote", "clock", "vase", "scissors", "toothbrush"]

                hybrid_cfg = HybridDetectorConfig(
                    primary_backend="yolo",
                    primary_model=str(self.config.detection.model),
                    primary_confidence=float(self.config.detection.confidence_threshold),
                    secondary_backend="groundingdino",
                    secondary_model=str(getattr(self.model_manager, "gdino_model_name", "IDEA-Research/grounding-dino-tiny")),
                    secondary_confidence=0.30,
                    min_detections_for_skip=int(getattr(self.config.detection, "hybrid_min_detections", 3)),
                    always_verify_classes=list(always_verify),
                )

                hybrid_detector = HybridDetector(
                    config=hybrid_cfg,
                    yolo_model=self.model_manager.yolo,
                    gdino_model=gdino_model,
                    gdino_processor=gdino_processor,
                    device=str(getattr(self.model_manager, "device", "cpu")),
                )
            except Exception as e:
                logger.error(f"Failed to initialize HybridDetector: {e}")
                raise

        # OpenVocab pipeline (Propose → Label architecture)
        openvocab_pipeline = None
        if self.config.detection.backend == "openvocab":
            logger.info("Initializing OpenVocab pipeline (Propose → Label)...")
            try:
                from orion.perception.open_vocab_pipeline import OpenVocabPipeline, OpenVocabConfig
                
                openvocab_cfg = OpenVocabConfig(
                    proposer_type=self.config.detection.openvocab_proposer,
                    vocab_preset=self.config.detection.openvocab_vocab_preset,
                    top_k=self.config.detection.openvocab_top_k,
                    min_similarity=self.config.detection.openvocab_min_similarity,
                    enable_evidence_gates=self.config.detection.openvocab_enable_evidence_gates,
                    confidence_gate=self.config.detection.openvocab_confidence_gate,
                    margin_gate=self.config.detection.openvocab_margin_gate,
                    temporal_window=self.config.detection.openvocab_temporal_window,
                    temporal_threshold=self.config.detection.openvocab_temporal_threshold,
                    vlm_gate=self.config.detection.openvocab_vlm_gate,
                    detection_confidence=self.config.detection.confidence_threshold,
                    device=str(getattr(self.model_manager, "device", "auto")),
                    # Reuse YOLO model from model_manager for yolo_clip proposer
                    yolo_model=self.model_manager.yolo if self.config.detection.openvocab_proposer == "yolo_clip" else None,
                )
                openvocab_pipeline = OpenVocabPipeline.from_config(openvocab_cfg)
                logger.info(f"OpenVocab pipeline initialized: proposer={openvocab_cfg.proposer_type}, vocab={openvocab_cfg.vocab_preset}")
            except Exception as e:
                logger.error(f"Failed to initialize OpenVocab pipeline: {e}")
                raise

        self.observer = FrameObserver(
            config=self.config.detection,
            detector_backend=("hybrid" if use_hybrid else self.config.detection.backend),
            yolo_model=self.model_manager.yolo if (self.config.detection.backend == "yolo" or use_hybrid) else None,
            yoloworld_model=yoloworld_model,
            gdino_model=gdino_model,
            gdino_processor=gdino_processor,
            hybrid_detector=hybrid_detector,
            openvocab_pipeline=openvocab_pipeline,
            target_fps=self.config.target_fps,
            enable_3d=self.config.enable_3d,
            enable_occlusion=self.config.enable_occlusion,
        )
        # Visual embedder (always V-JEPA2 for Re-ID)
        self.embedder = VisualEmbedder(config=self.config.embedding)
        # Entity tracker (optional, can be None)
        self.tracker = EntityTracker(self.config)
        # Entity describer
        # NOTE:
        # - The ClassCorrector is designed around COCO-style class names.
        # - When using YOLO-World (open-vocab prompts), applying COCO corrections can
        #   produce nonsensical "corrections" (e.g., bottle → sheep) that hurt quality.
        #   Keep class correction enabled only for COCO-based YOLO backends.
        enable_class_correction = self.config.detection.backend == "yolo"
        self.describer = EntityDescriber(
            vlm_model=self.model_manager.fastvlm,
            config=self.config.description,
            enable_class_correction=enable_class_correction,
            enable_spatial_analysis=True,
        )
        # self.reid_model = ReidModel(self.config.reid)
        # self.depth_estimator = DepthEstimator(self.config.depth.model_name)
        self.depth_estimator = None
        
        # Load per-class Re-ID thresholds if enabled
        per_class_thresholds = {}
        if self.config.tracking.use_per_class_thresholds:
            threshold_file = Path(__file__).parent / self.config.tracking.per_class_threshold_file
            if threshold_file.exists():
                import json
                with open(threshold_file, 'r') as f:
                    per_class_thresholds = json.load(f)
                logger.info(f"✓ Loaded per-class thresholds from {threshold_file.name} ({len(per_class_thresholds)} classes)")
            else:
                logger.warning(f"Per-class threshold file not found: {threshold_file}")
        
        self.enhanced_tracker = EnhancedTracker(
            max_age=self.config.tracking.max_age,
            min_hits=self.config.tracking.min_hits,
            iou_threshold=self.config.tracking.iou_threshold,
            appearance_threshold=self.config.tracking.appearance_threshold,
            max_distance_pixels=self.config.tracking.max_distance_pixels,
            max_distance_3d_mm=self.config.tracking.max_distance_3d_mm,
            match_threshold=self.config.tracking.match_threshold,
            per_class_thresholds=per_class_thresholds,
        )
        
        # Scene Context Manager (v2: FastVLM scene captions for context-aware filtering)
        if SCENE_CONTEXT_AVAILABLE:
            # Resolve device for scene context
            import torch
            device = self.config.embedding.device
            if device == "auto":
                if torch.cuda.is_available():
                    device = "cuda"
                elif getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
                    device = "mps"
                else:
                    device = "cpu"
            
            scene_config = SceneContextConfig(
                device=device,
                update_interval_frames=int(self.config.target_fps * 2),  # Every ~2 seconds
            )
            self.scene_context = SceneContextManager(config=scene_config)
            logger.info(f"✓ SceneContextManager initialized (update every {scene_config.update_interval_frames} frames)")
            
            # Initialize legacy scene filter for CLIP-based semantic filtering (fallback)
            if SCENE_FILTER_AVAILABLE:
                scene_filter_cfg = SceneFilterConfig(
                    device=device,
                    min_similarity=0.56,  # Validated: refrigerator@0.549 was false positive
                    soft_threshold=0.50,
                    soft_min_confidence=0.4,
                )
                self.scene_filter = SceneFilter(scene_filter_cfg)
                logger.info(f"✓ SceneFilter (legacy) initialized (min_sim={scene_filter_cfg.min_similarity})")
            else:
                self.scene_filter = None
                
            # Initialize v2 semantic filter with scene-type classification
            self.semantic_filter_v2 = None
            if SEMANTIC_FILTER_V2_AVAILABLE:
                try:
                    sf_v2_cfg = SemanticFilterV2Config(
                        device=device,
                        min_similarity=0.30,  # SentenceTransformer scale (different from CLIP)
                        high_confidence_threshold=0.45,
                        enable_vlm_verification=True,
                    )
                    # Pass FastVLM for verification (via scene_context.vlm)
                    vlm = getattr(self.scene_context, '_vlm', None)
                    self.semantic_filter_v2 = SemanticFilterV2(config=sf_v2_cfg, vlm=vlm)
                    logger.info("✓ SemanticFilterV2 initialized (scene-type classification + VLM verification)")
                except Exception as e:
                    logger.warning(f"SemanticFilterV2 init failed: {e}")
                    self.semantic_filter_v2 = None
        else:
            self.scene_context = None
            self.scene_filter = None
            self.semantic_filter_v2 = None
            logger.warning("SceneContextManager not available")

        # Stage 4: Initialize CIS scorer if enabled
        if getattr(self.config, 'enable_cis', False) and CIS_AVAILABLE:
            try:
                self.cis_scorer = CausalInfluenceScorer(
                    cis_threshold=getattr(self.config, 'cis_threshold', 0.50),
                    depth_gate_mm=getattr(self.config, 'cis_depth_gate_mm', 2000.0),
                    enable_depth_gating=True,
                )
                logger.info(f"✓ CausalInfluenceScorer initialized (threshold={self.config.cis_threshold})")
            except Exception as e:
                logger.warning(f"CIS scorer init failed: {e}")
                self.cis_scorer = None
        elif getattr(self.config, 'enable_cis', False) and not CIS_AVAILABLE:
            logger.warning("CIS enabled but CausalInfluenceScorer not available")

        logger.info("✓ All components initialized\n")

    def _ensure_open_vocab_labeler(self):
        """Lazily initialize the open-vocab candidate labeler."""
        if self._open_vocab_labeler is not None:
            return

        det_cfg = self.config.detection
        # Candidate labeling is CLIP-based and can be used with ANY detector backend.
        # We keep the existing config field name for backward compatibility.
        if not getattr(det_cfg, "yoloworld_enable_candidate_labels", False):
            self._open_vocab_labeler = False
            return

        try:
            from orion.perception.candidate_labeler import OpenVocabCandidateLabeler
            from orion.perception.open_vocab import PromptSchedule, resolve_prompt_groups

            group_names = [
                g.strip() for g in getattr(det_cfg, "yoloworld_candidate_prompt_groups", "").split(",")
                if g.strip()
            ]

            # If no groups were configured, default to all known groups.
            if not group_names:
                group_names = list(resolve_prompt_groups(None).keys())

            schedule = PromptSchedule(
                group_names=group_names,
                rotate_every_frames=int(getattr(det_cfg, "yoloworld_candidate_rotate_every_frames", 4)),
            )

            # This may download CLIP weights if not cached.
            clip = self.model_manager.clip
            self._open_vocab_labeler = OpenVocabCandidateLabeler(
                clip_embedder=clip,
                prompt_schedule=schedule,
                top_k=int(getattr(det_cfg, "yoloworld_candidate_top_k", 5)),
            )
            logger.info(
                "✓ Open-vocab candidate labeling enabled (%s groups, top_k=%s)",
                len(group_names),
                getattr(det_cfg, "yoloworld_candidate_top_k", 5),
            )
        except Exception as e:
            logger.warning("Open-vocab candidate labeling disabled (init failed): %s", e)
            self._open_vocab_labeler = False

    def _run_semantic_verification(
        self,
        detections: List[dict],
        *,
        scene_context: str = "",
    ) -> None:
        """Optionally run FastVLM semantic verification on a small subset of detections.

        This is designed to improve open-vocab label quality without destabilizing
        tracking: it re-ranks candidate label hypotheses and attaches audit metadata.
        """
        cfg = getattr(self.config, "semantic_verification", None)
        if not cfg or not getattr(cfg, "enabled", False):
            return

        if not detections:
            return

        # FastVLM is already managed/loaded by ModelManager.
        vlm = getattr(self.model_manager, "fastvlm", None)
        if vlm is None:
            logger.warning("Semantic verification enabled, but FastVLM is unavailable; skipping")
            return

        try:
            # Local import to avoid hard dependency at module import time.
            from orion.perception.filters import SemanticFilter, SemanticFilterConfig
        except Exception as e:
            logger.warning("Semantic verification unavailable (filters import failed): %s", e)
            return

        # Build filter config from verification config (bridge two config types).
        filter_cfg = SemanticFilterConfig(
            similarity_threshold=float(getattr(cfg, "similarity_threshold", 0.25)),
            description_prompt=str(getattr(cfg, "description_prompt", "Describe this object in one sentence.")),
            max_tokens=int(getattr(cfg, "max_tokens", 50)),
            temperature=float(getattr(cfg, "temperature", 0.1)),
            # If we have no scene context, do not spend cycles on scene embedding.
            use_scene_context=bool(scene_context.strip()),
        )
        sem_filter = SemanticFilter(filter_cfg, vlm_model=vlm)

        # Group by sampled frame id and run periodically on the sampled frame index.
        by_frame: Dict[int, List[dict]] = {}
        for det in detections:
            try:
                by_frame.setdefault(int(det.get("frame_number", 0)), []).append(det)
            except Exception:
                by_frame.setdefault(0, []).append(det)

        verified = 0
        reranked = 0
        attempted = 0

        # Heavy deps only if we actually run.
        try:
            import cv2
            from PIL import Image
        except Exception as e:
            logger.warning("Semantic verification unavailable (cv2/PIL import failed): %s", e)
            return

        for sample_idx, frame_id in enumerate(sorted(by_frame.keys())):
            if (sample_idx % int(getattr(cfg, "every_n_sampled_frames", 10))) != 0:
                continue

            frame_dets = by_frame[frame_id]

            # Choose candidates to verify.
            mode = str(getattr(cfg, "mode", "candidates_only"))
            selected: List[dict] = []
            for det in frame_dets:
                crop = det.get("crop")
                if crop is None:
                    continue

                has_candidates = bool(det.get("candidate_labels"))
                conf = float(det.get("confidence", 0.0) or 0.0)

                if mode == "candidates_only":
                    if not has_candidates:
                        continue
                elif mode == "low_confidence":
                    if not has_candidates and conf >= float(getattr(cfg, "low_confidence_threshold", 0.35)):
                        continue
                elif mode == "all":
                    pass
                else:
                    # Unknown mode: default to candidates_only.
                    if not has_candidates:
                        continue

                selected.append(det)

            if not selected:
                continue

            selected.sort(key=lambda d: float(d.get("confidence", 0.0) or 0.0), reverse=True)
            selected = selected[: int(getattr(cfg, "max_detections_per_frame", 6))]

            for det in selected:
                attempted += 1

                crop = det.get("crop")
                if crop is None:
                    continue

                # Convert crop (BGR np.ndarray) -> PIL Image (RGB)
                try:
                    crop_rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB) if getattr(crop, "shape", None) is not None else crop
                    pil = Image.fromarray(crop_rgb)
                except Exception:
                    continue

                label = str(det.get("object_class", det.get("label", "unknown")))
                res = sem_filter.filter_single(
                    pil,
                    label,
                    track_id=int(det.get("track_id", det.get("temp_id", -1)) if str(det.get("track_id", "")).isdigit() else -1),
                    confidence=float(det.get("confidence", 0.0) or 0.0),
                    scene_context=scene_context or None,
                )
                verified += 1

                if bool(getattr(cfg, "attach_metadata", True)):
                    det["vlm_description"] = res.description
                    det["vlm_similarity"] = float(res.similarity)
                    det["vlm_is_valid"] = bool(res.is_valid)
                    if res.reason:
                        det["vlm_reason"] = str(res.reason)

                if bool(getattr(cfg, "rerank_candidates", True)) and det.get("candidate_labels"):
                    before = det.get("candidate_labels")
                    det["candidate_labels"] = sem_filter.rerank_candidate_labels(
                        res.description,
                        before,
                        blend=float(getattr(cfg, "rerank_blend", 0.6)),
                        top_k=None,
                    )
                    reranked += 1

        if attempted:
            logger.info(
                "  ✓ Semantic verification: attempted=%d verified=%d reranked=%d (every_n_sampled_frames=%s, max_per_frame=%s)",
                attempted,
                verified,
                reranked,
                getattr(cfg, "every_n_sampled_frames", 10),
                getattr(cfg, "max_detections_per_frame", 6),
            )

    @profile("engine_process_video")
    def process_video(self, video_path: str, save_visualizations: bool = False, output_dir: str = "results") -> PerceptionResult:
        """
        Process video through complete perception pipeline.
        
        Args:
            video_path: Path to video file
            save_visualizations: If True, export camera intrinsics and tracking/entity data for visualization
            output_dir: Directory to save visualization data
            
        Returns:
            PerceptionResult with entities and observations
        """
        # Ensure output directory exists
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        # === FIX: Get actual video dimensions and update config ===
        try:
            import cv2
            cap = cv2.VideoCapture(video_path)
            if cap.isOpened():
                actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                
                if self.config.camera.width != actual_width or self.config.camera.height != actual_height:
                    logger.warning(
                        f"Camera config resolution ({self.config.camera.width}x{self.config.camera.height}) "
                        f"does not match video resolution ({actual_width}x{actual_height}). "
                        f"Updating config to match video."
                    )
                    self.config.camera.width = actual_width
                    self.config.camera.height = actual_height
                
                # Update observer's 3D engine with correct intrinsics
                if self.observer:
                    correct_intrinsics = self.config.camera.resolve_intrinsics(
                        width=actual_width, height=actual_height
                    )
                    self.observer.update_camera_intrinsics(correct_intrinsics)

            cap.release()
        except Exception as e:
            logger.error(f"Failed to read video dimensions to update config: {e}")
        # === END FIX ===

        logger.info("\n" + "="*80)
        logger.info("PERCEPTION ENGINE - PHASE 1")
        logger.info("="*80)
        
        start_time = time.time()
        metrics_timings: dict = {}
        
        # Initialize pipeline components
        # self._initialize_components()
        
        # Step 0: Generate scene context using SceneContextManager (v2)
        # Sample multiple frames (0%, 25%, 50%, 75%) to handle multi-room videos
        scene_caption = ""
        scene_snapshot = None
        all_scene_captions = []
        
        if self.scene_context is not None:
            try:
                import cv2
                cap = cv2.VideoCapture(video_path)
                if cap.isOpened():
                    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                    
                    # Sample frames at 0%, 25%, 50%, 75% of video
                    sample_positions = [0, int(total_frames * 0.25), int(total_frames * 0.5), int(total_frames * 0.75)]
                    
                    for sample_idx, frame_pos in enumerate(sample_positions):
                        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_pos)
                        ret, frame = cap.read()
                        if ret:
                            snapshot = self.scene_context.update(frame, frame_idx=frame_pos, force=True)
                            if snapshot.caption:
                                all_scene_captions.append(snapshot.caption)
                                if sample_idx == 0:
                                    scene_snapshot = snapshot
                                    scene_caption = snapshot.caption
                    
                    if all_scene_captions:
                        logger.info(f"Scene Context (v2, {len(all_scene_captions)} samples):")
                        for i, cap_text in enumerate(all_scene_captions):
                            logger.info(f"  [{i}] {cap_text[:100]}...")
                        
                        # Use first scene for initial context
                        if scene_snapshot:
                            logger.info(f"  Objects mentioned: {scene_snapshot.objects_mentioned}")
                            
                cap.release()
            except Exception as e:
                logger.warning(f"Failed to generate scene context: {e}")
        elif self.describer:
            # Fallback to legacy describer if SceneContextManager unavailable
            try:
                import cv2
                cap = cv2.VideoCapture(video_path)
                if cap.isOpened():
                    ret, frame = cap.read()
                    if ret:
                        scene_caption = self.describer.describe_scene(frame)
                        logger.info(f"Scene Context (legacy): {scene_caption}")
                cap.release()
            except Exception as e:
                logger.warning(f"Failed to generate scene context: {e}")

        # Pass scene context to observer for early-stage filtering
        if scene_snapshot is not None and hasattr(self.observer, 'set_scene_context'):
            self.observer.set_scene_context(scene_snapshot.objects_mentioned)
            logger.info(f"  → Observer scene context filtering enabled for: {scene_snapshot.objects_mentioned}")
        
        # Set up scene filter with CLIP embeddings
        if self.scene_filter is not None and scene_caption:
            self.scene_filter.set_scene(scene_caption)

        # Step 1: Observe & detect
        t0 = time.time()
        detections = self.observer.process_video(video_path)
        metrics_timings["detection_seconds"] = time.time() - t0
        
        # Step 1.25: Scene-based semantic filtering
        # First try SemanticFilterV2 (preferred), fallback to legacy CLIP-based filter
        if self.semantic_filter_v2 is not None and detections:
            # Use multi-scene mode if multiple captions available
            if all_scene_captions and len(all_scene_captions) > 1:
                self.semantic_filter_v2.set_multi_scene(all_scene_captions, frame_idx=0)
            elif scene_caption:
                self.semantic_filter_v2.set_scene(scene_caption, frame_idx=0)
            
            if self.semantic_filter_v2._current_scene:
                before_count = len(detections)
                detections = self.semantic_filter_v2.filter_detections(detections, in_place=True)
                after_count = len(detections)
                if before_count != after_count:
                    logger.info(f"  SemanticFilterV2: {before_count} → {after_count} detections "
                               f"({before_count - after_count} removed)")
                    # Log scene type
                    scene_type = self.semantic_filter_v2._current_scene.scene_type
                    blacklist = self.semantic_filter_v2._current_scene.blacklist
                    logger.info(f"    Scene type: {scene_type}")
                    if blacklist:
                        logger.info(f"    Blacklisted labels: {sorted(blacklist)}")
        elif self.scene_filter is not None and scene_caption and detections:
            # Fallback to legacy CLIP-based filter
            before_count = len(detections)
            detections = self.scene_filter.filter_detections(detections, in_place=True)
            after_count = len(detections)
            if before_count != after_count:
                logger.info(f"  Scene filter (legacy): {before_count} → {after_count} detections "
                           f"({before_count - after_count} removed)")

        # Step 1.5: Attach open-vocab candidate label hypotheses (non-committal)
        self._ensure_open_vocab_labeler()
        if self._open_vocab_labeler not in (None, False) and detections:
            try:
                by_frame: dict[int, list[dict]] = {}
                for det in detections:
                    by_frame.setdefault(int(det.get("frame_number", 0)), []).append(det)
                # Rotate prompt groups on the *sampled* frame index rather than the raw
                # video frame id. Raw ids can skip large intervals (e.g. 0, 6, 12, ...),
                # causing uneven prompt-group coverage.
                for sample_idx, frame_id in enumerate(sorted(by_frame.keys())):
                    frame_dets = by_frame[frame_id]
                    self._open_vocab_labeler.attach_candidates(frame_dets, frame_number=sample_idx)

                # Lightweight coverage metric for debugging/tuning.
                dets_with_cands = sum(1 for d in detections if d.get("candidate_labels"))
                logger.info(
                    "  ✓ Candidate labels attached: %d/%d detections (%.1f%%)",
                    dets_with_cands,
                    len(detections),
                    100.0 * dets_with_cands / max(1, len(detections)),
                )
            except Exception as e:
                logger.warning("Candidate labeling failed: %s", e)

        # Step 1.75: Optional FastVLM semantic verification / candidate reranking
        try:
            self._run_semantic_verification(detections, scene_context=scene_caption)
        except Exception as e:
            logger.warning("Semantic verification failed: %s", e)
        
        # NOTE: SLAM is intentionally disabled/removed from the perception engine.
        # Depth-only 3D lifting can still be enabled via Perception3DEngine.
        
        # Step 2: Embed detections
        t0 = time.time()
        detections = self.embedder.embed_detections(detections)
        metrics_timings["embedding_seconds"] = time.time() - t0

        # Optional: run enhanced 3D+appearance tracker for per-frame identities
        if self.config.enable_tracking and self.enhanced_tracker is not None:
            t0 = time.time()
            try:
                self._run_enhanced_tracking(detections)
                self._save_tracking_results(output_dir)
            except Exception as e:
                logging.warning(f"Enhanced tracking failed: {e}")
            finally:
                metrics_timings["tracking_seconds"] = time.time() - t0
        
        # Step 3: Convert detections to Observation objects
        observations = self._detections_to_observations(detections)
        
        # Step 4: Cluster into entities
        t0 = time.time()
        entities = self.tracker.cluster_observations(observations)
        metrics_timings["clustering_seconds"] = time.time() - t0
        
        # Step 4.5: Phase 5 Re-ID - Semantic deduplication using embedding similarity
        t0 = time.time()
        entities = self._reid_deduplicate_entities(entities)
        metrics_timings["reid_seconds"] = time.time() - t0

        # Step 4.6: Canonical label resolution (HDBSCAN on candidate labels)
        t0 = time.time()
        try:
            from orion.perception.canonical_labeler import canonicalize_entities
            num_canonical = canonicalize_entities(entities)
            logger.info(f"  ✓ Canonical labels: {num_canonical}/{len(entities)} entities")
        except Exception as e:
            logger.warning(f"Canonical labeling failed: {e}")
        metrics_timings["canonicalization_seconds"] = time.time() - t0

        # Step 5: Describe entities
        t0 = time.time()
        if self.describer:
            entities = self.describer.describe_entities(entities)
        metrics_timings["description_seconds"] = time.time() - t0

        if self.config.use_memgraph and self.memgraph is not None:
            try:
                self._sync_memgraph_entities(entities)
            except Exception as e:
                logging.warning(f"Memgraph sync failed: {e}")
        
        # Get video metadata (approximate from observations)
        total_frames = max([obs.frame_number for obs in observations]) if observations else 0
        fps = self.config.target_fps
        duration = max([obs.timestamp for obs in observations]) if observations else 0.0
        
        # Build result with optional tracking metrics
        result_metrics = {}
        if self.enhanced_tracker is not None:
            try:
                stats = self.enhanced_tracker.get_statistics()
                keys = [k for k in ["total_tracks", "confirmed_tracks", "active_tracks", "id_switches"] if k in stats]
                result_metrics.update({k: stats[k] for k in keys})
            except Exception as e:
                logger.warning(f"Exception during profiling stats save: {e}")

        # Add aggregate timings and run stats
        elapsed_total = time.time() - start_time
        metrics_timings["total_seconds"] = elapsed_total
        
        # Save profiling stats
        Profiler().save_stats(Path(output_dir) / "profiling_stats.json")

        # Frame and detection stats
        try:
            sampled_frames = len({int(d["frame_number"]) for d in detections})
        except Exception as e:
            logger.warning(f"Exception calculating sampled_frames: {e}")
            sampled_frames = 0
        result_metrics.update({
            "timings": metrics_timings,
            "sampled_frames": sampled_frames,
            "detections_per_sampled_frame": (len(detections) / sampled_frames) if sampled_frames else 0.0,
            "embedding_backend": "vjepa2",
            "embedding_dim": self.config.embedding.embedding_dim,
            "detector_backend": self.config.detection.backend,
            "detector_model": (
                self.config.detection.model
                if self.config.detection.backend == "yolo"
                else self.config.detection.yoloworld_model
            ),
            "cluster_embeddings": int(sum(1 for d in detections if 'cluster_rep_id' in d and d.get('cluster_size'))),
            "avg_cluster_size": float(np.mean([d.get('cluster_size',1) for d in detections if d.get('cluster_size')])) if any(d.get('cluster_size') for d in detections) else 1.0,
        })

        # Inject Re-ID metrics if available
        if hasattr(self, "_reid_metrics") and isinstance(self._reid_metrics, dict):
            result_metrics["reid"] = self._reid_metrics

        result = PerceptionResult(
            entities=entities,
            raw_observations=observations,
            video_path=video_path,
            total_frames=total_frames,
            fps=fps,
            duration_seconds=duration,
            processing_time_seconds=elapsed_total,
            scene_caption=scene_caption,
            metrics=result_metrics or None,
        )

        elapsed = elapsed_total
        logger.info("PERCEPTION COMPLETE")
        logger.info("="*80)
        logger.info(f"  Total detections: {result.total_detections}")
        logger.info(f"  Unique entities: {result.unique_entities}")
        logger.info(f"  Processing time: {elapsed:.2f}s")
        logger.info("="*80 + "\n")
        
        # Export visualization data if requested
        if save_visualizations:
            self._export_visualization_data(result, output_dir)
            self._save_tracking_results(output_dir)
            
        return result

    def _export_visualization_data(self, result: PerceptionResult, output_dir: str):
        """Export camera intrinsics and tracking/entity data for visualization."""
        from pathlib import Path
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Exporting visualization data to {output_dir}/...")

        # 1. Export camera intrinsics (preset or config derived)
        intrinsics_file = output_path / "camera_intrinsics.json"
        camera_intrinsics = self.config.camera.resolve_intrinsics(
            width=self.config.camera.width,
            height=self.config.camera.height,
        )
        intrinsics_payload = {
            "fx": camera_intrinsics.fx,
            "fy": camera_intrinsics.fy,
            "cx": camera_intrinsics.cx,
            "cy": camera_intrinsics.cy,
            "width": camera_intrinsics.width,
            "height": camera_intrinsics.height,
            "preset": self.config.camera.intrinsics_preset,
            "note": "Values derived from selected intrinsics preset or overrides",
        }
        with open(intrinsics_file, "w") as f:
            json.dump(intrinsics_payload, f, indent=2)
        logger.info(f"  ✓ Saved camera intrinsics: {intrinsics_file}")

        # 2. Export tracking/entity data
        entities_file = output_path / "entities.json"
        entities_data = {
            "total_entities": len(result.entities),
            "entities": []
        }
        
        for i, entity in enumerate(result.entities):
            best_obs = entity.get_best_observation()
            entity_dict = {
                "id": i,
                "class": entity.object_class.value if hasattr(entity.object_class, 'value') else str(entity.object_class),
                "confidence": float(best_obs.confidence),
                "observation_count": len(entity.observations),
                "first_frame": entity.first_seen_frame,
                "last_frame": entity.last_seen_frame,
                "description": entity.description or "No description",
            }
            entities_data["entities"].append(entity_dict)
        
        # Add tracking events if EnhancedTracker is available
        if self.enhanced_tracker is not None:
            try:
                stats = self.enhanced_tracker.get_statistics()
                entities_data["tracking_stats"] = {
                    "total_tracks": stats.get("total_tracks", 0),
                    "confirmed_tracks": stats.get("confirmed_tracks", 0),
                    "id_switches": stats.get("id_switches", 0),
                }
            except Exception:
                pass
        
        with open(entities_file, 'w') as f:
            json.dump(entities_data, f, indent=2)
        logger.info(f"  ✓ Saved tracking data: {entities_file}")
        
        logger.info("✓ Visualization data export complete\n")
    
    def process_frame(
        self,
        frame: np.ndarray,
        detections: List[dict],
        frame_number: int = 0,
        timestamp: float = 0.0,
    ) -> Perception3DResult:
        """Lightweight per-frame processing used in unit tests and debugging.

        This path bypasses the heavy observer/embedder stack and instead consumes
        caller-provided detections (typically synthetic). It still produces
        structured 3D metadata so downstream tests can exercise depth/occlusion
        logic without requiring full model execution.
        """
        start = time.time()
        height, width = frame.shape[:2]
        intrinsics = self._resolve_intrinsics(width, height)

        depth_value = None
        depth_map: Optional[np.ndarray] = None
        # if self.config.enable_depth:
        #     estimator = self._get_depth_estimator()
        #     if estimator is not None:
        #         try:
        #             depth_map, _ = estimator.estimate(frame)
        #             if depth_map is not None:
        #                 depth_map = depth_map.astype(np.float32)
        #                 depth_map = np.clip(depth_map, 0.0, self.config.depth.max_depth_mm)
        #                 valid = depth_map[(depth_map > 0) & np.isfinite(depth_map)]
        #                 if valid.size > 0:
        #                     depth_value = float(np.median(valid))
        #                 else:
        _value = None
        #         except Exception as exc:
        #             logger.warning(f"Depth estimation failed for frame {frame_number}: {exc}")
        #     if depth_map is None:
        #         depth_value = min(self.config.depth.max_depth_mm, 1500.0)
        #         depth_map = np.full((height, width), depth_value, dtype=np.float32)

        entities: List[EntityState3D] = []
        for idx, det in enumerate(detections):
            bbox = det.get("bbox") or det.get("bbox_2d_px")
            if bbox is None:
                continue
            x1, y1, x2, y2 = map(float, bbox)
            centroid_u = (x1 + x2) / 2.0
            centroid_v = (y1 + y2) / 2.0
            centroid_2d = (centroid_u, centroid_v)

            centroid_3d = None
            bbox_3d = None
            depth_mean_mm = None
            depth_variance = None
            if depth_value is not None:
                centroid_3d = backproject_point(centroid_u, centroid_v, depth_value, intrinsics)
                bbox_3d = (
                    backproject_point(x1, y1, depth_value, intrinsics),
                    backproject_point(x2, y2, depth_value, intrinsics),
                )
                depth_mean_mm = depth_value
                depth_variance = 25.0  # Stub variance for tests

            entities.append(
                EntityState3D(
                    entity_id=str(det.get("entity_id", f"entity_{idx}")),
                    frame_number=frame_number,
                    timestamp=timestamp,
                    class_label=str(det.get("class", det.get("label", "unknown"))),
                    class_confidence=float(det.get("confidence", 0.0)),
                    bbox_2d_px=(int(x1), int(y1), int(x2), int(y2)),
                    centroid_2d_px=centroid_2d,
                    centroid_3d_mm=centroid_3d,
                    bbox_3d_mm=bbox_3d,
                    depth_mean_mm=depth_mean_mm,
                    depth_variance_mm2=depth_variance,
                    visibility_state=VisibilityState.FULLY_VISIBLE,
                    occlusion_ratio=0.0,
                    occluded_by=None,
                    metadata={"source": det.get("source", "mock")},
                )
            )

        hands: List[Hand] = []
        if self.config.enable_hands:
            palm_depth = depth_value or 800.0
            landmarks_2d = [(0.5, 0.5)] * 21
            landmarks_3d = [(0.0, 0.0, palm_depth)] * 21
            hands.append(
                Hand(
                    id="hand_stub",
                    landmarks_2d=landmarks_2d,
                    landmarks_3d=landmarks_3d,
                    palm_center_3d=(0.0, 0.0, palm_depth),
                    pose=HandPose.UNKNOWN,
                    confidence=0.0,
                    handedness="Unknown",
                )
            )

        processing_ms = (time.time() - start) * 1000.0
        return Perception3DResult(
            frame_number=frame_number,
            timestamp=timestamp,
            entities=entities,
            hands=hands,
            depth_map=depth_map,
            camera_intrinsics=intrinsics,
            processing_time_ms=processing_ms,
            metadata={
                "detections_processed": len(entities),
                "depth_enabled": self.config.enable_depth,
                "hands_enabled": self.config.enable_hands,
            },
        )

    def _resolve_intrinsics(self, width: int, height: int) -> CameraIntrinsics:
        """Resolve camera intrinsics using the runtime camera config."""
        return self.config.camera.resolve_intrinsics(width=width, height=height)

    def _get_depth_estimator(self) -> Optional[DepthEstimator]:
        """Lazily initialize and return the shared depth estimator."""
        return None
    
    def _sync_memgraph_entities(self, entities: List[PerceptionEntity]):
        """Push entity observations and relations to Memgraph."""
        if not self.memgraph:
            return

        frame_entries: Dict[int, List[Tuple[int, Observation]]] = {}

        for entity in entities:
            try:
                entity_numeric_id = self._entity_str_to_int(entity.entity_id)
            except Exception as e:
                logger.debug(f"Unable to parse entity_id {entity.entity_id} for Memgraph: {e}")
                continue

            zone_id = self.zone_manager.assign_zone(entity)

            embedding = entity.average_embedding
            if embedding is None:
                try:
                    embedding = entity.compute_average_embedding()
                except Exception as e:
                    logger.warning(f"Failed to compute average embedding for entity {entity.entity_id}: {e}")
                    embedding = None

            embedding_payload = (
                embedding.astype(float).tolist()
                if isinstance(embedding, np.ndarray)
                else (embedding.tolist() if hasattr(embedding, "tolist") else None)
            )

            class_name = (
                entity.object_class.value
                if hasattr(entity.object_class, "value")
                else str(entity.object_class)
            )
            caption_payload = entity.description
            caption_written = False
            embedding_written = False

            for obs in entity.observations:
                bbox = obs.bounding_box.to_list()
                try:
                    self.memgraph.add_entity_observation(
                        entity_id=entity_numeric_id,
                        frame_idx=obs.frame_number,
                        timestamp=obs.timestamp,
                        bbox=bbox,
                        class_name=class_name,
                        confidence=float(obs.confidence),
                        zone_id=zone_id,
                        caption=(
                            caption_payload
                            if caption_payload and not caption_written
                            else None
                        ),
                        embedding=embedding_payload if not embedding_written else None,
                    )
                    embedding_written = True if embedding_payload and not embedding_written else embedding_written
                    caption_written = True if caption_payload and not caption_written else caption_written
                    frame_entries.setdefault(obs.frame_number, []).append((entity_numeric_id, obs))
                except Exception as exc:
                    logger.debug(
                        f"Memgraph observation write failed for {entity.entity_id}: {exc}"
                    )

        self._emit_spatial_relationships(frame_entries)

    def _emit_spatial_relationships(
        self, frame_entries: Dict[int, List[Tuple[int, Observation]]]
    ):
        """Derive simple NEAR relationships per frame and send to Memgraph."""
        if not self.memgraph:
            return

        near_threshold = getattr(self.config, "memgraph_near_threshold", 0.15)

        for frame_idx, entries in frame_entries.items():
            if len(entries) < 2:
                continue
            for i in range(len(entries)):
                entity_a, obs_a = entries[i]
                center_a = obs_a.bounding_box.center
                for j in range(i + 1, len(entries)):
                    entity_b, obs_b = entries[j]
                    center_b = obs_b.bounding_box.center
                    dist = math.dist(center_a, center_b)
                    diag = self._estimate_frame_diag(obs_a, obs_b)
                    if diag <= 0:
                        continue
                    norm_dist = dist / diag
                    if norm_dist <= near_threshold:
                        confidence = max(
                            0.1,
                            1.0 - (norm_dist / max(near_threshold, 1e-3))
                        )
                        try:
                            self.memgraph.add_spatial_relationship(
                                entity1_id=entity_a,
                                entity2_id=entity_b,
                                relationship_type="NEAR",
                                confidence=float(confidence),
                                frame_idx=frame_idx,
                            )
                        except Exception as exc:
                            logger.debug(f"Memgraph relation write failed: {exc}")

    @staticmethod
    def _estimate_frame_diag(obs_a: Observation, obs_b: Observation) -> float:
        """Best-effort estimate of frame diagonal for normalization."""
        for obs in (obs_a, obs_b):
            if obs.frame_width and obs.frame_height:
                return math.hypot(obs.frame_width, obs.frame_height)
        width = max(obs_a.bounding_box.width, obs_b.bounding_box.width)
        height = max(obs_a.bounding_box.height, obs_b.bounding_box.height)
        return math.hypot(width, height) * 3.0

    @staticmethod
    def _entity_str_to_int(entity_id: str) -> int:
        """Convert entity_id strings like 'entity_12' into stable ints."""
        if entity_id.isdigit():
            return int(entity_id)
        digits = "".join(ch for ch in entity_id if ch.isdigit())
        if digits:
            return int(digits)
        return abs(hash(entity_id)) % (2 ** 31)

    def _reid_deduplicate_entities(self, entities: List[PerceptionEntity]) -> List[PerceptionEntity]:
        """Phase 5: Adaptive Re-ID semantic deduplication.

        Dynamically derives per-class similarity thresholds, applies spatial distance
        veto, temporal overlap heuristics, and low-observation rescue merges, then
        downsamples embeddings for memory efficiency. Metrics stored in `self._reid_metrics`.
        Verbose pairwise printing gated by `EmbeddingConfig.reid_debug`.
        """
        if len(entities) <= 1:
            return entities
        
        logger.info("="*80)
        logger.info("PHASE 5: RE-ID SEMANTIC DEDUPLICATION")
        logger.info("="*80)
        logger.info(f"Input entities: {len(entities)}")
        
        # Extract average embeddings (compute if missing)
        embeddings: List[np.ndarray] = []
        valid_entities: List[PerceptionEntity] = []
        for entity in entities:
            if entity.average_embedding is None:
                try:
                    entity.compute_average_embedding()
                except Exception as e:
                    logger.warning(f"Entity {entity.entity_id} missing average embedding and could not compute: {e}")
                    continue
            embeddings.append(entity.average_embedding)
            valid_entities.append(entity)

        if len(valid_entities) < 2:
            logger.warning(f"Not enough entities with embeddings for Re-ID ({len(valid_entities)} entities)")
            return entities

        emb_arr = np.vstack(embeddings)
        norms = np.linalg.norm(emb_arr, axis=1, keepdims=True) + 1e-8
        emb_norm = emb_arr / norms
        similarity_matrix = emb_norm @ emb_norm.T

        # Group indices per class
        class_groups: Dict[str, List[int]] = {}
        for i, ent in enumerate(valid_entities):
            cls = ent.object_class.value if hasattr(ent.object_class, 'value') else str(ent.object_class)
            class_groups.setdefault(cls, []).append(i)

        # Derive dynamic thresholds & collect stats
        backend = getattr(self.config.embedding, 'backend', 'clip')
        base_threshold = 0.55 if backend == 'dinov3' else 0.65
        class_thresholds: Dict[str, float] = {}
        similarity_stats: Dict[str, Dict[str, float]] = {}
        for cls, idxs in class_groups.items():
            if len(idxs) < 2:
                class_thresholds[cls] = base_threshold
                continue
            sims: List[float] = []
            for a_i in range(len(idxs)):
                for b_i in range(a_i+1, len(idxs)):
                    sims.append(float(similarity_matrix[idxs[a_i], idxs[b_i]]))
            if sims:
                sims_arr = np.array(sims)
                median = float(np.median(sims_arr))
                mean = float(np.mean(sims_arr))
                std = float(np.std(sims_arr))
                p95 = float(np.percentile(sims_arr, 95))
                # Dynamic threshold heuristic
                dyn = max(base_threshold, min(0.90, median - 0.05 if median > base_threshold else median + 0.05))
                class_thresholds[cls] = dyn
                similarity_stats[cls] = {"mean": mean, "std": std, "median": median, "p95": p95, "threshold": dyn, "pair_count": float(len(sims_arr))}
            else:
                class_thresholds[cls] = base_threshold

        if getattr(self.config.embedding, 'reid_debug', False):
            print("\n" + "="*80)
            print("PHASE 5: SIMILARITY ANALYSIS (Adaptive)")
            print("="*80)
            for cls, stats in similarity_stats.items():
                print(f"Class {cls}: median={stats['median']:.3f} mean={stats['mean']:.3f} std={stats['std']:.3f} p95={stats['p95']:.3f} -> threshold={stats['threshold']:.3f}")

        # Prepare centroid cache
        def entity_centroid(ent: PerceptionEntity) -> Tuple[float, float]:
            xs, ys = [], []
            for obs in ent.observations:
                xs.append(obs.centroid[0])
                ys.append(obs.centroid[1])
            return (float(np.mean(xs)), float(np.mean(ys)))

        centroids = [entity_centroid(e) for e in valid_entities]
        # Frame size heuristic from first observation if available
        fw = valid_entities[0].observations[0].frame_width or 1.0
        fh = valid_entities[0].observations[0].frame_height or 1.0
        diag = (fw**2 + fh**2) ** 0.5 if fw > 0 and fh > 0 else 1.0

        merged_flags = [False] * len(valid_entities)
        merged_entities: List[PerceptionEntity] = []
        merges_count = 0
        per_class_merge_counts: Dict[str, int] = {cls:0 for cls in class_groups}
        temporal_overlap_base = 0.50

        max_embeddings_per_entity = getattr(self.config.embedding, 'max_embeddings_per_entity', None)

        for i in range(len(valid_entities)):
            if merged_flags[i]:
                continue
            ent_i = valid_entities[i]
            cls_i = ent_i.object_class.value if hasattr(ent_i.object_class, 'value') else str(ent_i.object_class)
            threshold_i = class_thresholds.get(cls_i, base_threshold)
            similar_indices = [i]
            # Deterministic sampling seed for reproducible downsampling behavior
            np.random.seed(42)
            for j in range(i+1, len(valid_entities)):
                if merged_flags[j]:
                    continue
                ent_j = valid_entities[j]
                if ent_i.object_class != ent_j.object_class:
                    continue
                sim = float(similarity_matrix[i, j])
                # Temporal overlap
                f_i_min, f_i_max = ent_i.first_seen_frame, ent_i.last_seen_frame
                f_j_min, f_j_max = ent_j.first_seen_frame, ent_j.last_seen_frame
                overlap_start = max(f_i_min, f_j_min)
                overlap_end = min(f_i_max, f_j_max)
                overlap_frames = max(0, overlap_end - overlap_start)
                dur_i = f_i_max - f_i_min + 1
                dur_j = f_j_max - f_j_min + 1
                overlap_ratio = overlap_frames / min(dur_i, dur_j) if min(dur_i, dur_j) > 0 else 0.0
                # Spatial distance veto (normalized)
                dx = centroids[i][0] - centroids[j][0]
                dy = centroids[i][1] - centroids[j][1]
                spatial_dist_norm = ((dx*dx + dy*dy) ** 0.5) / diag
                spatial_veto = spatial_dist_norm > 0.60 and sim < (threshold_i + 0.05)
                # Low observation merge heuristic
                low_obs_merge = (len(ent_i.observations) <= 3 or len(ent_j.observations) <= 3) and sim >= (threshold_i * 0.4)
                # Merge conditions
                should_merge = (
                    (sim >= threshold_i and not spatial_veto) or
                    (sim >= threshold_i * 0.85 and overlap_ratio >= temporal_overlap_base) or
                    (sim >= threshold_i * 0.5 and overlap_ratio >= 0.85) or
                    low_obs_merge
                )
                if should_merge:
                    similar_indices.append(j)
                    merged_flags[j] = True
                    merges_count += 1
                    per_class_merge_counts[cls_i] += 1
                    if getattr(self.config.embedding, 'reid_debug', False):
                        print(f"  MERGE {ent_i.entity_id} + {ent_j.entity_id} sim={sim:.3f} overlap={overlap_ratio:.2f} dist={spatial_dist_norm:.2f} th={threshold_i:.3f}")
            if len(similar_indices) == 1:
                merged_entities.append(ent_i)
                continue
            # Consolidate observations
            all_obs: List[Observation] = []
            for idx in similar_indices:
                all_obs.extend(valid_entities[idx].observations)
            merged = PerceptionEntity(
                entity_id=f"merged_{ent_i.entity_id}",
                object_class=ent_i.object_class,
                observations=all_obs,
            )
            
            # Back-populate merged entity_id to observations
            for obs in all_obs:
                obs.entity_id = merged.entity_id
                
            # Compute average embedding with optional downsampling
            obs_embeddings = [obs.visual_embedding for obs in all_obs]
            if max_embeddings_per_entity and len(obs_embeddings) > max_embeddings_per_entity:
                # Random but deterministic subset (seed could be configurable)
                subset_idx = np.random.choice(len(obs_embeddings), size=max_embeddings_per_entity, replace=False)
                obs_embeddings = [obs_embeddings[k] for k in subset_idx]
            avg_emb = np.mean(obs_embeddings, axis=0)
            norm = np.linalg.norm(avg_emb)
            merged.average_embedding = avg_emb / norm if norm > 0 else avg_emb
            merged_entities.append(merged)
            logger.info(f"  Merged {len(similar_indices)} entities into {merged.entity_id} ({cls_i})")

        reduction = len(valid_entities) - len(merged_entities)
        logger.info(f"Output entities: {len(merged_entities)} (reduced by {reduction})")
        logger.info("="*80 + "\n")

        # Store metrics for inclusion in final result
        self._reid_metrics = {
            "backend": backend,
            "base_threshold": base_threshold,
            "class_thresholds": class_thresholds,
            "similarity_stats": similarity_stats,
            "merges_total": merges_count,
            "per_class_merges": per_class_merge_counts,
            "reduction": reduction,
        }

        return merged_entities
    
    def _detections_to_observations(self, detections: List[dict]) -> List[Observation]:
        """
        Convert detection dicts to Observation objects.
        
        Args:
            detections: List of detection dicts
            
        Returns:
            List of Observation objects
        """
        observations = []
        
        for i, det in enumerate(detections):
            # Map class name to ObjectClass enum
            try:
                object_class = ObjectClass(det["object_class"])
            except ValueError:
                object_class = ObjectClass.UNKNOWN
            
            obs = Observation(
                bounding_box=det["bounding_box"],
                centroid=det["centroid"],
                object_class=object_class,
                confidence=det["confidence"],
                visual_embedding=det["embedding"],
                frame_number=det["frame_number"],
                timestamp=det["timestamp"],
                temp_id=f"obs_{i}",
                image_patch=det.get("crop"),
                spatial_zone=det.get("spatial_zone"),
                raw_yolo_class=det.get("object_class"),
                frame_width=det.get("frame_width"),
                frame_height=det.get("frame_height"),
                candidate_labels=det.get("candidate_labels"),
                candidate_group=det.get("candidate_group"),
                vlm_description=det.get("vlm_description"),
                vlm_similarity=det.get("vlm_similarity"),
                vlm_is_valid=det.get("vlm_is_valid"),
                scene_similarity=det.get("scene_similarity"),
                scene_filter_reason=det.get("scene_filter_reason"),
            )
            
            observations.append(obs)
        
        return observations

    def _run_enhanced_tracking(self, detections: List[dict]) -> None:
        """Run EnhancedTracker over detections grouped by frame.
        
        Also computes CIS edges if enabled and buffers for batch Memgraph sync.
        """
        if self.enhanced_tracker is None:
            return

        # Group detections by frame
        by_frame: dict[int, List[dict]] = {}
        for det in detections:
            by_frame.setdefault(int(det["frame_number"]), []).append(det)

        # CIS computation settings
        cis_compute_every = getattr(self.config, 'cis_compute_every_n_frames', 5)
        cis_buffer_size = getattr(self.config, 'cis_temporal_buffer_size', 30)
        memgraph_batch_size = getattr(self.config, 'memgraph_batch_size', 10)
        
        last_stats = {}
        frames_since_memgraph_sync = 0
        
        for fidx in sorted(by_frame.keys()):
            frame_dets = by_frame[fidx]
            # Build arrays for tracker
            converted, embs = self._convert_for_enhanced_tracker(frame_dets)

            # Update tracker (camera_pose intentionally omitted; SLAM is not part of the engine)
            active_tracks = self.enhanced_tracker.update(converted, embs, camera_pose=None, frame_idx=fidx)
            if active_tracks:
                self.tracking_history[fidx] = active_tracks
                
                # Update CIS temporal buffer (sliding window)
                self._cis_buffer[fidx] = active_tracks
                # Trim buffer to size
                if len(self._cis_buffer) > cis_buffer_size:
                    oldest = min(self._cis_buffer.keys())
                    del self._cis_buffer[oldest]
                
                # Compute CIS edges if enabled and on schedule
                if self.cis_scorer is not None and (fidx % cis_compute_every) == 0:
                    try:
                        fps = self.config.target_fps or 30.0
                        timestamp = fidx / fps
                        cis_edges = self.cis_scorer.compute_frame_edges(
                            entities=active_tracks,
                            frame_id=fidx,
                            timestamp=timestamp,
                        )
                        if cis_edges:
                            self._cis_edges.extend(cis_edges)
                            logger.debug(f"Frame {fidx}: computed {len(cis_edges)} CIS edges")
                    except Exception as e:
                        logger.warning(f"CIS computation failed at frame {fidx}: {e}")
                
                # Buffer observations for batch Memgraph sync
                if self.memgraph and getattr(self.config, 'memgraph_sync_observations', True):
                    for track in active_tracks:
                        obs_dict = self._track_to_observation_dict(track, fidx)
                        self._observation_buffer.append(obs_dict)
            
            last_stats = self.enhanced_tracker.get_statistics()
            frames_since_memgraph_sync += 1
            
            # Batch commit to Memgraph
            if frames_since_memgraph_sync >= memgraph_batch_size:
                self._flush_memgraph_buffers()
                frames_since_memgraph_sync = 0

        # Final flush
        self._flush_memgraph_buffers()

        if last_stats:
            cis_count = len(self._cis_edges) if hasattr(self, '_cis_edges') else 0
            logger.info(
                f"  EnhancedTracker: total_tracks={last_stats.get('total_tracks', 0)}, "
                f"confirmed={last_stats.get('confirmed_tracks', 0)}, cis_edges={cis_count}"
            )

    def _track_to_observation_dict(self, track: Track, frame_idx: int) -> Dict:
        """Convert a Track to an observation dict for Memgraph batch insert."""
        fps = self.config.target_fps or 30.0
        timestamp = frame_idx / fps
        
        bbox = track.bbox_2d.tolist() if isinstance(track.bbox_2d, np.ndarray) else track.bbox_2d
        
        return {
            'entity_id': int(track.id),
            'frame_idx': frame_idx,
            'timestamp': timestamp,
            'class_name': str(track.class_name),
            'confidence': float(track.confidence),
            'bbox': bbox,
            'depth_mm': float(track.depth_mm) if track.depth_mm is not None else None,
            'vlm_description': getattr(track, 'vlm_description', None),
            'embedding_id': getattr(track, 'embedding_id', None),
        }

    def _flush_memgraph_buffers(self) -> None:
        """Flush buffered observations and CIS edges to Memgraph."""
        if not self.memgraph:
            return
        
        # Flush observations
        if self._observation_buffer:
            try:
                # Use enhanced batch method if available
                if hasattr(self.memgraph, 'add_observations_batch_with_vlm'):
                    self.memgraph.add_observations_batch_with_vlm(self._observation_buffer)
                else:
                    self.memgraph.add_observations_batch(self._observation_buffer)
                logger.debug(f"Flushed {len(self._observation_buffer)} observations to Memgraph")
            except Exception as e:
                logger.warning(f"Memgraph observation flush failed: {e}")
            self._observation_buffer = []
        
        # Flush CIS edges
        if self._cis_edges and getattr(self.config, 'memgraph_sync_cis', True):
            try:
                if hasattr(self.memgraph, 'add_cis_relationships_batch'):
                    # Convert CISEdge objects to dicts
                    cis_dicts = []
                    for edge in self._cis_edges:
                        cis_dicts.append({
                            'agent_id': edge.agent_id,
                            'patient_id': edge.patient_id,
                            'relationship_type': edge.relation_type.upper(),
                            'cis_score': edge.cis_score,
                            'frame_idx': edge.frame_id,
                            'timestamp': edge.timestamp,
                            'influence_type': edge.components.interaction_type,
                            'components': {
                                'temporal': edge.components.temporal,
                                'spatial': edge.components.spatial,
                                'motion': edge.components.motion,
                                'semantic': edge.components.semantic,
                                'hand_bonus': edge.components.hand_bonus,
                                'distance_3d_mm': edge.components.distance_3d_mm,
                            }
                        })
                    self.memgraph.add_cis_relationships_batch(cis_dicts)
                    logger.debug(f"Flushed {len(cis_dicts)} CIS edges to Memgraph")
            except Exception as e:
                logger.warning(f"Memgraph CIS flush failed: {e}")
            self._cis_edges = []

    def _convert_for_enhanced_tracker(self, frame_dets: List[dict]) -> Tuple[List[dict], List[Optional[np.ndarray]]]:
        """Convert observer/embedder detections to EnhancedTracker format.

        Required keys by EnhancedTracker per detection:
          - bbox_3d: [x, y, z, w, h, d] (mm)
          - bbox_2d: [x1, y1, x2, y2]
          - class_name: str
          - confidence: float
          - depth_mm: float
        """
        import numpy as _np  # local import to avoid hard dependency at module load

        converted: List[dict] = []
        embeddings: List[Optional[_np.ndarray]] = []

        for det in frame_dets:
            # 2D bbox
            bb = det.get("bounding_box")
            if bb is None:
                # Fallback: skip if no bbox present
                continue
            x1, y1, x2, y2 = float(bb.x1), float(bb.y1), float(bb.x2), float(bb.y2)
            w_px = max(1.0, x2 - x1)
            h_px = max(1.0, y2 - y1)

            # 3D center (prefer centroid_3d_mm if available)
            c3d = det.get("centroid_3d_mm")
            depth_mm = float(det.get("depth_mm", 0.0) or 0.0)
            if c3d is not None and len(c3d) == 3:
                cx_mm, cy_mm, cz_mm = float(c3d[0]), float(c3d[1]), float(c3d[2])
            else:
                # Fallback: approximate using 2D centroid (pixels) and depth
                c2d = det.get("centroid", ((x1 + x2) / 2.0, (y1 + y2) / 2.0))
                cx_mm, cy_mm, cz_mm = float(c2d[0]), float(c2d[1]), depth_mm

            # Approximate size in mm using pixel extents as a proxy
            # (relative values suffice for cost scaling inside EnhancedTracker)
            size_mm = _np.array([w_px, h_px, max(w_px, h_px)], dtype=_np.float32)

            converted.append({
                'bbox_3d': _np.array([cx_mm, cy_mm, cz_mm, *size_mm.tolist()], dtype=_np.float32),
                'bbox_2d': _np.array([x1, y1, x2, y2], dtype=_np.float32),
                'class_name': str(det.get("object_class", "unknown")),
                'confidence': float(det.get("confidence", 0.0)),
                'depth_mm': depth_mm,
            })

            # Prefer V-JEPA2 embeddings for appearance/Re-ID consistency.
            # (CLIP embeddings may exist for candidate label scoring but are not the identity backbone.)
            emb = det.get("embedding", det.get("clip_embedding"))
            embeddings.append(emb if emb is not None else None)

        return converted, embeddings

    def _save_tracking_results(self, output_dir: str):
        """Saves tracking history to a JSONL file."""
        if not self.tracking_history:
            logging.warning("No tracking history to save.")
            return

        output_path = os.path.join(output_dir, "tracks.jsonl")
        try:
            # Get FPS for timestamp calculation. Fallback to a default if not available.
            fps = self.config.target_fps or 30.0

            with open(output_path, 'w') as f:
                for frame_idx, tracks in self.tracking_history.items():
                    for track in tracks:
                        # Calculate timestamp in milliseconds
                        timestamp_msec = (frame_idx / fps) * 1000
                        track_data = {
                            "frame_id": frame_idx,
                            "timestamp": timestamp_msec,
                            "track_id": track.id,
                            "class_name": track.class_name,
                            "bbox_2d": track.bbox_2d.tolist(),
                            "bbox_3d": track.bbox_3d.tolist() if track.bbox_3d is not None else None,
                            "confidence": track.confidence,
                        }
                        f.write(json.dumps(track_data) + '\n')
            logging.info(f"Tracking results saved to {output_path}")
        except Exception as e:
            logging.warning(f"Failed to save tracking results: {e}")


# ============================================================================
# CONVENIENCE FUNCTION
# ============================================================================

def run_perception(
    video_path: str,
    config: Optional[PerceptionConfig] = None,
    verbose: bool = False,
) -> PerceptionResult:
    """
    Convenience function to run perception pipeline.
    
    Args:
        video_path: Path to video file
        config: Optional perception configuration
        verbose: Enable verbose logging
        
    Returns:
        PerceptionResult with entities and observations
        
    Example:
        >>> from orion.perception.engine import run_perception
        >>> result = run_perception("video.mp4")
        >>> print(f"Found {result.unique_entities} entities")
    """
    engine = PerceptionEngine(config=config, verbose=verbose)
    return engine.process_video(video_path)
