"""
Perception Engine Configuration
==============================

Validated configuration for Phase 1 (Perception & Tracking).

Supports preset configs (fast/balanced/accurate) and custom values.
All fields are validated with meaningful error messages.

Author: Orion Research Team
Date: October 2025
"""

from dataclasses import dataclass, field
from typing import Literal, Optional

import logging

from .types import DEFAULT_INTRINSICS_PRESET, INTRINSICS_PRESETS, ObjectClass

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# YOLO-World prompt presets
#
# Key design: Stage-1 detection should be high-recall and low-commitment.
# Using 100+ fine-grained prompts in YOLO-World set_classes() tends to cause
# prompt collapse/noisy semantics and slows the pipeline.
# ---------------------------------------------------------------------------

YOLOWORLD_PROMPT_COARSE = (
    "person . face . hand . "
    "container . bottle . cup . "
    "bag . box . "
    "furniture . chair . table . "
    "electronic device . phone . laptop . "
    "text . "
    "door . window . "
    ""  # background class marker; empty string handled by yoloworld_categories()
)

# Full COCO-80 vocabulary (from ObjectClass enum) for high-recall Stage-1 runs.
YOLOWORLD_PROMPT_COCO = " . ".join([cls.value for cls in ObjectClass]) + " . "

# The previous default (~100 class indoor vocabulary) is kept as a preset for
# research/ablation runs.
YOLOWORLD_PROMPT_INDOOR_FULL = (
    # =============================================================
    # GENERAL INDOOR VOCABULARY (~100 classes)
    # Comprehensive list for indoor scene understanding
    # =============================================================
    "person . "
    "chair . couch . sofa . armchair . stool . bench . office chair . "
    "table . desk . coffee table . dining table . counter . shelf . "
    "cabinet . drawer . dresser . wardrobe . closet . bookshelf . nightstand . "
    "bed . pillow . blanket . mattress . "
    "monitor . laptop . keyboard . mouse . computer . tablet . "
    "tv . television . remote . speaker . headphones . game controller . "
    "phone . cell phone . smartphone . "
    "printer . router . charger . cable . outlet . switch . lamp . "
    "refrigerator . microwave . oven . stove . toaster . blender . coffee maker . "
    "sink . faucet . plate . bowl . cup . mug . glass . bottle . "
    "fork . knife . spoon . pan . pot . cutting board . "
    "backpack . bag . handbag . suitcase . umbrella . wallet . keys . "
    "glasses . sunglasses . watch . hat . jacket . shoe . "
    "picture frame . painting . poster . mirror . clock . vase . plant . "
    "curtain . rug . carpet . towel . "
    "box . basket . bin . trash can . recycling bin . "
    "door . window . doorknob . handle . "
    "book . notebook . pen . pencil . paper . magazine . "
    "toy . ball . doll . stuffed animal . "
    "food . fruit . apple . banana . orange . sandwich . pizza . "
    "dog . cat . bird . "
    ""  # background class
)


@dataclass
class DetectionConfig:
    """Detection backend configuration (YOLO, YOLO-World, GroundingDINO, or OpenVocab)."""

    backend: Literal["yolo", "yoloworld", "groundingdino", "hybrid", "openvocab", "dinov3"] = "dinov3"
    """Primary detector to use for frame observations. Options: 'yolo', 'yoloworld',
    'groundingdino', 'hybrid', 'openvocab', 'dinov3'

    New default: 'dinov3' — this uses DINOv3 for proposal classification/refinement
    on top of an underlying proposer (GroundingDINO or YOLO) to improve label
    quality while preserving the existing proposal generation logic.
    """

    # Model specific settings
    model: str = "IDEA-Research/grounding-dino-tiny"
    """Model identifier.
    GroundingDINO: 'IDEA-Research/grounding-dino-tiny' or 'IDEA-Research/grounding-dino-base'
    YOLO (legacy): 'yolo11n', 'yolo11s', 'yolo11m', 'yolo11x'
    """

    # Detection thresholds (shared)
    confidence_threshold: float = 0.25
    """Minimum detection confidence (0-1). Raised from 0.20 to reduce false positives."""

    iou_threshold: float = 0.45
    """NMS IoU threshold for overlapping boxes."""

    # Temporal consistency filtering (NEW)
    enable_temporal_filtering: bool = True
    """If True, reject detections that don't persist across multiple frames."""

    min_consecutive_frames: int = 2
    """Minimum consecutive frames a detection must appear in to be accepted."""

    temporal_iou_threshold: float = 0.5
    """IoU threshold for matching detections across frames."""

    temporal_memory_frames: int = 5
    """Number of previous frames to keep for temporal matching."""

    # Adaptive confidence thresholding (NEW)
    enable_adaptive_confidence: bool = True
    """If True, adjust confidence threshold based on frame density."""

    adaptive_high_density_threshold: int = 20
    """If detections exceed this count, raise confidence threshold."""

    adaptive_confidence_boost: float = 0.10
    """Amount to increase confidence threshold in high-density frames."""

    # Depth-based validation (NEW)
    enable_depth_validation: bool = True
    """If True, reject detections with impossible spatial properties."""

    max_object_height_meters: float = 3.5
    """Maximum plausible object height in meters (e.g., reject 10m tall chair)."""

    min_object_height_meters: float = 0.02
    """Minimum plausible object height in meters (2cm, filters noise)."""

    # Filtering
    min_object_size: int = 24
    """Minimum object size in pixels (smaller ignored)."""

    max_bbox_area_ratio: float = 0.90
    """If bbox area / frame area exceeds this ratio, treat as suspicious background-like box."""

    max_bbox_area_lowconf_threshold: float = 0.25
    """Drop very large boxes when their confidence is below this threshold."""

    max_aspect_ratio: float = 9.0
    """If aspect ratio exceeds this (wide or tall) AND confidence is low, treat as likely false positive."""

    aspect_ratio_lowconf_threshold: float = 0.22
    """Confidence cutoff for the aspect-ratio filter."""

    # Class-specific area constraints (added per Gemini audit feedback)
    class_max_area_ratios: dict = None
    """Per-class max bbox area ratios. Keys are lowercase class names (e.g., 'person': 0.50).
    Detections exceeding their class-specific limit are filtered out.
    Falls back to max_bbox_area_ratio if class not specified."""

    class_confidence_thresholds: dict = None
    """Per-class minimum confidence thresholds. Keys are lowercase class names (e.g., 'hand': 0.60).
    Detections below their class-specific threshold are filtered out.
    Falls back to confidence_threshold if class not specified.
    Added per Gemini audit: 'hand' and 'laptop' often hallucinated on background features."""

    class_agnostic_nms: bool = False
    """If True, apply class-agnostic NMS to suppress overlapping boxes of different classes.
    This eliminates duplicate tracks (e.g., 'box' + 'laptop' + 'notebook' for same object)."""

    class_agnostic_nms_iou: float = 0.65
    """IoU threshold for class-agnostic NMS. Higher = more aggressive suppression."""

    # Class-specific NMS thresholds (from deep research: small objects need lower IoU)
    class_specific_nms_iou: dict = None
    """Per-class NMS IoU thresholds. Keys are lowercase class names.
    Small objects (clock, remote, scissors) need lower IoU to avoid over-suppression.
    Example: {'clock': 0.3, 'remote': 0.35, 'scissors': 0.3}"""

    # Hybrid detection mode (YOLO + GroundingDINO)
    enable_hybrid_detection: bool = False
    """If True, use HybridDetector combining YOLO11x speed with GroundingDINO recall.
    YOLO runs always; GDINO triggers on low-detection frames or specific queries."""

    hybrid_min_detections: int = 3
    """If YOLO finds fewer than this many objects, trigger GroundingDINO."""

    hybrid_always_verify: list = None
    """List of class names to always verify with GroundingDINO.
    Default: ['remote', 'clock', 'vase', 'scissors', 'toothbrush']"""

    # Cropping
    bbox_padding_percent: float = 0.1
    """Padding to add around bounding boxes when cropping (percentage of box size)."""

    # YOLO-World specific options (v2 primary detector)
    yoloworld_model: str = "yolov8x-worldv2.pt"
    """YOLO-World model weights file. Use yolov8x-worldv2.pt for best accuracy."""

    yoloworld_prompt_preset: Literal["coarse", "indoor_full", "coco", "custom"] = "coco"
    """Prompt preset for YOLO-World when yoloworld_use_custom_classes=True.

    - coco: full COCO-80 vocabulary for high recall
    - coarse: small, stable super-categories
    - indoor_full: legacy ~100 class indoor vocabulary (ablation/research)
    - custom: use yoloworld_prompt as provided
    """

    yoloworld_prompt: str = ""
    """Dot-separated prompt for YOLO-World when yoloworld_prompt_preset='custom'."""

    yoloworld_use_custom_classes: bool = True
    """If True, constrain YOLO-World via `set_classes(yoloworld_categories())`. If False, run YOLO-World with its default/open vocabulary."""

    # Candidate open-vocab labeling (non-committal hypotheses, stored in detections)
    # NOTE: This is CLIP-based and can be used with ANY detector backend.
    yoloworld_enable_candidate_labels: bool = False
    """If True, attach top-k CLIP-based candidate labels (unused by default when crop refinement is enabled)."""

    # Crop-level refinement using YOLO-World on selected detections
    yoloworld_enable_crop_refinement: bool = True
    """If True, run YOLO-World on crops of generic/coarse detections with fine-grained prompts (taxonomy-driven)."""

    yoloworld_refinement_confidence: float = 0.15
    """Confidence threshold for crop refinement detections."""

    yoloworld_refinement_every_n_sampled_frames: int = 4
    """Run crop refinement every N sampled frames (not raw video frames)."""

    yoloworld_refinement_max_crops_per_class: int = 3
    """Maximum number of detection crops to refine per coarse class per sampled frame."""

    yoloworld_refinement_top_k: int = 5
    """Top-k candidate labels to keep from crop refinement."""

    yoloworld_candidate_top_k: int = 5
    """Top-k candidate labels to store per detection."""

    yoloworld_candidate_prompt_groups: str = "electronics,containers,kitchen,office,personal_items,architecture"
    """Comma-separated prompt groups used for candidate labeling (see orion/perception/open_vocab.py)."""

    yoloworld_candidate_rotate_every_frames: int = 4
    """Rotate candidate prompt groups every N sampled frames to cover long-tail labels over time."""

    # ===========================================
    # OpenVocab backend options (Propose → Label)
    # ===========================================
    openvocab_proposer: Literal["owl", "yolo_clip", "yoloworld_clip"] = "yolo_clip"
    """Proposal generator for openvocab backend.
    - 'owl': OWL-ViT2 class-agnostic proposals (HuggingFace model)
    - 'yolo_clip': YOLO11 proposals + CLIP visual embeddings (fallback, faster)
    - 'yoloworld_clip': YOLO-World proposals + CLIP label scoring (strong open-vocab baseline)
    """

    openvocab_vocab_preset: Literal["lvis", "coco", "objects365"] = "lvis"
    """Vocabulary bank preset for label matching.
    - 'lvis': ~1200 fine-grained LVIS categories
    - 'coco': 80 COCO classes (faster, less coverage)
    - 'objects365': 365 Objects365 classes
    """

    openvocab_top_k: int = 5
    """Number of candidate labels to store per detection."""

    openvocab_min_similarity: float = 0.20
    """Minimum CLIP similarity threshold for label matching (0-1)."""

    openvocab_enable_evidence_gates: bool = True
    """If True, apply evidence gates (temporal, margin, VLM) for label verification."""

    openvocab_confidence_gate: float = 0.50
    """Confidence threshold for automatic verification (bypass gates if above)."""

    openvocab_margin_gate: float = 0.10
    """Minimum margin between top-2 hypotheses for confident labeling."""

    openvocab_temporal_window: int = 5
    """Number of frames for temporal consistency check."""

    openvocab_temporal_threshold: float = 0.60
    """Fraction of frames where label must appear for temporal verification."""

    openvocab_vlm_gate: bool = False
    """If True, escalate ambiguous detections to VLM for verification (slower)."""

    def __post_init__(self):
        """Validate detection config."""
        if self.backend not in {"yolo", "yoloworld", "groundingdino", "hybrid", "openvocab", "dinov3"}:
            raise ValueError(
                "backend must be 'yolo', 'yoloworld', 'groundingdino', 'hybrid', 'openvocab', or 'dinov3', "
                f"got {self.backend}"
            )

        # Model validation
        valid_yolo = {"yolo11n", "yolo11s", "yolo11m", "yolo11x"}
        valid_gdino = {"IDEA-Research/grounding-dino-tiny", "IDEA-Research/grounding-dino-base"}
        if self.backend in {"yolo", "hybrid"}:
            if self.model not in valid_yolo:
                logger.warning(
                    "DetectionConfig: backend=%s expects YOLO model, got %s",
                    self.backend,
                    self.model,
                )
        elif self.backend in {"groundingdino", "dinov3"}:
            if self.model not in valid_gdino:
                logger.warning(
                    "DetectionConfig: backend=%s expects GroundingDINO model, got %s",
                    self.backend,
                    self.model,
                )
        else:
            valid_models = valid_yolo | valid_gdino
            if self.model not in valid_models:
                logger.warning(f"Model {self.model} not in standard set. Proceeding anyway.")

        # Threshold validation
        if not (0 <= self.confidence_threshold <= 1):
            raise ValueError(f"confidence_threshold must be in [0, 1], got {self.confidence_threshold}")

        if not (0 <= self.iou_threshold <= 1):
            raise ValueError(f"iou_threshold must be in [0, 1], got {self.iou_threshold}")

        # Size validation
        if self.min_object_size < 1:
            raise ValueError(f"min_object_size must be >= 1, got {self.min_object_size}")

        if not (0.0 < float(self.max_bbox_area_ratio) <= 1.0):
            raise ValueError(
                f"max_bbox_area_ratio must be in (0, 1], got {self.max_bbox_area_ratio}"
            )
        if not (0.0 <= float(self.max_bbox_area_lowconf_threshold) <= 1.0):
            raise ValueError(
                "max_bbox_area_lowconf_threshold must be in [0, 1], "
                f"got {self.max_bbox_area_lowconf_threshold}"
            )

        # Padding validation
        if self.bbox_padding_percent < 0:
            raise ValueError(f"bbox_padding_percent must be >= 0, got {self.bbox_padding_percent}")

        # Initialize class_max_area_ratios if None (default per-class limits)
        if self.class_max_area_ratios is None:
            object.__setattr__(self, 'class_max_area_ratios', {})
        
        # Validate class-agnostic NMS threshold
        if not (0.0 <= self.class_agnostic_nms_iou <= 1.0):
            raise ValueError(
                f"class_agnostic_nms_iou must be in [0, 1], got {self.class_agnostic_nms_iou}"
            )

        if self.backend == "yoloworld":
            if self.yoloworld_use_custom_classes:
                if self.yoloworld_prompt_preset == "custom" and not self.yoloworld_prompt.strip():
                    raise ValueError(
                        "yoloworld_prompt cannot be empty when yoloworld_prompt_preset='custom' and yoloworld_use_custom_classes=True"
                    )

            if self.yoloworld_candidate_top_k < 1:
                raise ValueError("yoloworld_candidate_top_k must be >= 1")
            if self.yoloworld_candidate_rotate_every_frames < 1:
                raise ValueError("yoloworld_candidate_rotate_every_frames must be >= 1")

            if self.yoloworld_refinement_top_k < 1:
                raise ValueError("yoloworld_refinement_top_k must be >= 1")

            if self.yoloworld_refinement_every_n_sampled_frames < 1:
                raise ValueError("yoloworld_refinement_every_n_sampled_frames must be >= 1")
            if self.yoloworld_refinement_max_crops_per_class < 1:
                raise ValueError("yoloworld_refinement_max_crops_per_class must be >= 1")

        # Validate openvocab backend options
        if self.backend == "openvocab":
            if self.openvocab_proposer not in {"owl", "yolo_clip", "yoloworld_clip"}:
                raise ValueError(
                    "openvocab_proposer must be one of 'owl', 'yolo_clip', or 'yoloworld_clip', "
                    f"got {self.openvocab_proposer}"
                )
            if self.openvocab_vocab_preset not in {"lvis", "coco", "objects365"}:
                raise ValueError(
                    f"openvocab_vocab_preset must be 'lvis', 'coco', or 'objects365', got {self.openvocab_vocab_preset}"
                )
            if self.openvocab_top_k < 1:
                raise ValueError(f"openvocab_top_k must be >= 1, got {self.openvocab_top_k}")
            if not (0.0 <= self.openvocab_min_similarity <= 1.0):
                raise ValueError(
                    f"openvocab_min_similarity must be in [0, 1], got {self.openvocab_min_similarity}"
                )
            if not (0.0 <= self.openvocab_confidence_gate <= 1.0):
                raise ValueError(
                    f"openvocab_confidence_gate must be in [0, 1], got {self.openvocab_confidence_gate}"
                )
            if not (0.0 <= self.openvocab_margin_gate <= 1.0):
                raise ValueError(
                    f"openvocab_margin_gate must be in [0, 1], got {self.openvocab_margin_gate}"
                )
            if self.openvocab_temporal_window < 1:
                raise ValueError(f"openvocab_temporal_window must be >= 1, got {self.openvocab_temporal_window}")
            if not (0.0 <= self.openvocab_temporal_threshold <= 1.0):
                raise ValueError(
                    f"openvocab_temporal_threshold must be in [0, 1], got {self.openvocab_temporal_threshold}"
                )

        # Validate candidate prompt groups early (applies for any backend).
        if self.yoloworld_enable_candidate_labels:
            try:
                from orion.perception.open_vocab import resolve_prompt_groups

                raw = getattr(self, "yoloworld_candidate_prompt_groups", "")
                group_names = [g.strip() for g in str(raw).split(",") if g.strip()]
                # If empty, runtime will default to all groups.
                if group_names:
                    resolve_prompt_groups(group_names)
            except Exception as e:
                raise ValueError(f"Invalid yoloworld_candidate_prompt_groups: {e}")

        logger.debug(
            f"DetectionConfig validated: backend={self.backend}, model={self.model}, "
            f"conf_thresh={self.confidence_threshold}, iou_thresh={self.iou_threshold}"
        )

    def yoloworld_categories(self) -> list[str]:
        """Return normalized category list for YOLO-World prompts.
        
        Note: Empty string ('') is preserved as a background class per Ultralytics docs,
        which can improve detection performance in some scenarios.
        """
        if self.yoloworld_prompt_preset == "coarse":
            prompt = YOLOWORLD_PROMPT_COARSE
        elif self.yoloworld_prompt_preset == "indoor_full":
            prompt = YOLOWORLD_PROMPT_INDOOR_FULL
        elif self.yoloworld_prompt_preset == "coco":
            prompt = YOLOWORLD_PROMPT_COCO
        else:
            prompt = self.yoloworld_prompt

        categories = []
        for token in prompt.split('.'):
            stripped = token.strip()
            categories.append(stripped)  # Keep all including empty string
        # Remove trailing empties except one (if present for background class)
        while len(categories) > 1 and categories[-1] == '' and categories[-2] == '':
            categories.pop()
        return categories

    def grounding_categories(self) -> list[str]:
        """Return normalized category list for GroundingDINO prompts.
        
        Uses the same prompt settings as YOLO-World for consistency in research.
        """
        return self.yoloworld_categories()


@dataclass
class EmbeddingConfig:
    """Re-ID embedding configuration.
    
    V-JEPA2 is the canonical Re-ID backbone for Orion v2.
    It provides 3D-aware video embeddings that handle viewpoint changes
    better than 2D encoders (CLIP/DINO).
    
    CLIP is still used *separately* for candidate-label scoring (open-vocab),
    but not for Re-ID embeddings.
    """
    
    # V-JEPA2 model (the only supported Re-ID backend)
    model: str = "facebook/vjepa2-vitl-fpc64-256"
    """V-JEPA2 model name from HuggingFace."""
    
    embedding_dim: int = 1024
    """Output embedding dimension (V-JEPA2 vitl = 1024)."""

    # Cluster / memory efficiency settings
    use_cluster_embeddings: bool = False
    """If True, aggregate overlapping detections per frame into cluster embeddings to reduce memory."""

    cluster_similarity_threshold: float = 0.65
    """IoU threshold (0-1) to merge detections into same cluster before embedding extraction."""

    max_embeddings_per_entity: int = 25
    """Cap number of stored observation embeddings per entity (older ones downsampled)."""

    # Debug / verbosity
    reid_debug: bool = False
    """If True, print detailed pairwise similarity and merge decisions in Re-ID phase."""
    

    # Device selection
    device: str = "auto"  # "auto", "cuda", "mps", "cpu"
    """Device for embedding model (auto/cuda/mps/cpu)"""

    # Batch processing
    batch_size: int = 16
    """Embeddings per batch. V-JEPA2 is heavier than CLIP; default lowered to 16."""
    
    def __post_init__(self):
        """Validate embedding config."""
        valid_dims = {768, 1024}
        if self.embedding_dim not in valid_dims:
            raise ValueError(
                f"embedding_dim must be one of {valid_dims}, got {self.embedding_dim}"
            )

        if not (0.0 <= self.cluster_similarity_threshold <= 1.0):
            raise ValueError(
                f"cluster_similarity_threshold must be in [0,1], got {self.cluster_similarity_threshold}"
            )
        if self.max_embeddings_per_entity < 1:
            raise ValueError(
                f"max_embeddings_per_entity must be >=1, got {self.max_embeddings_per_entity}"
            )
        
        if self.batch_size < 1:
            raise ValueError(f"batch_size must be >= 1, got {self.batch_size}")
        if self.batch_size > 64:
            logger.warning(f"Large batch_size for V-JEPA2: {self.batch_size}. May cause OOM.")
        valid_devices = {"auto", "cuda", "mps", "cpu"}
        if self.device not in valid_devices:
            raise ValueError(f"device must be one of {valid_devices}, got {self.device}")
        logger.debug(
            f"EmbeddingConfig validated: model={self.model}, "
            f"dim={self.embedding_dim}, batch_size={self.batch_size}, device={self.device}"
        )


@dataclass
class DescriptionConfig:
    """FastVLM description generation configuration"""
    
    # Generation settings
    max_tokens: int = 200
    """Maximum tokens per description"""
    
    temperature: float = 0.3
    """Sampling temperature (lower = deterministic, higher = creative)"""

    prompt_template: str = "Describe this object in detail."
    """Prompt template for VLM description generation."""

    sentence_model_name: str = "all-MiniLM-L6-v2"
    """Sentence-transformer model for semantic class correction (e.g., 'sentence-transformers/all-mpnet-base-v2')."""
    
    # Repetition control (addresses FastVLM loop bug)
    repetition_penalty: float = 1.15
    """Penalty for repeating tokens (1.0 = no penalty, >1.0 = discourage repetition).
    Higher values prevent the 'Honor, Honor, Honor...' loop bug in FastVLM."""
    
    no_repeat_ngram_size: int = 3
    """Prevent repeating N-grams of this size (0 = disabled).
    Set to 3 to prevent repeating 3-word phrases."""
    
    # VLM voting for robustness
    enable_voting: bool = False
    """If True, generate multiple descriptions and keep consensus (centroid)."""
    
    num_votes: int = 3
    """Number of descriptions to generate when voting is enabled."""
    
    voting_similarity_threshold: float = 0.7
    """Minimum cosine similarity for a description to be considered part of consensus."""
    
    # Optimization
    describe_once: bool = True
    """Only describe each entity once (from best frame)"""
    
    # Best frame selection weights
    size_weight: float = 0.5
    """Weight for object size"""
    
    centrality_weight: float = 0.3
    """Weight for proximity to image center"""
    
    confidence_weight: float = 0.2
    """Weight for detection confidence"""

    # Sanity checks
    min_crop_size: int = 32
    """Minimum width/height in pixels required to trust a crop"""

    min_crop_std: float = 5.0
    """Minimum grayscale standard deviation to avoid flat/blank crops"""
    
    def __post_init__(self):
        """Validate description config"""
        if self.max_tokens < 1:
            raise ValueError(f"max_tokens must be >= 1, got {self.max_tokens}")
        
        if self.max_tokens > 512:
            logger.warning(f"Very large max_tokens: {self.max_tokens}. Descriptions may be verbose.")
        
        if not (0 <= self.temperature <= 2):
            raise ValueError(f"temperature must be in [0, 2], got {self.temperature}")
        
        # Validate weights sum to ~1.0
        total_weight = self.size_weight + self.centrality_weight + self.confidence_weight
        if abs(total_weight - 1.0) > 0.01:
            logger.warning(
                f"Frame selection weights sum to {total_weight:.2f}, expected 1.0. "
                f"Rescaling..."
            )
            # Auto-rescale
            if total_weight > 0:
                scale = 1.0 / total_weight
                self.size_weight *= scale
                self.centrality_weight *= scale
                self.confidence_weight *= scale

        if self.min_crop_size < 8:
            raise ValueError(f"min_crop_size must be >= 8 pixels, got {self.min_crop_size}")

        if self.min_crop_std < 0:
            raise ValueError(f"min_crop_std must be >= 0, got {self.min_crop_std}")

        if not isinstance(self.sentence_model_name, str) or not self.sentence_model_name.strip():
            raise ValueError("sentence_model_name must be a non-empty string")
        
        logger.debug(
            f"DescriptionConfig validated: max_tokens={self.max_tokens}, "
            f"temperature={self.temperature}, describe_once={self.describe_once}"
        )


@dataclass
class SemanticVerificationConfig:
    """FastVLM-based semantic verification for detections (optional).

    This stage is meant to be:
    - low-frequency (run on a small subset of detections)
    - non-destructive by default (do not drop detections)
    - used primarily to re-rank open-vocab candidate label hypotheses
      and attach audit metadata (description + similarity).
    """

    enabled: bool = False
    """Enable FastVLM semantic verification/reranking."""

    mode: Literal["candidates_only", "low_confidence", "all"] = "candidates_only"
    """Which detections to verify:

    - candidates_only: only detections that already have candidate_labels
    - low_confidence: candidate_labels OR confidence below `low_confidence_threshold`
    - all: verify the top-N detections per frame
    """

    every_n_sampled_frames: int = 10
    """Run verification every N sampled frames (not raw video frames)."""

    max_detections_per_frame: int = 6
    """Cap number of detections verified per sampled frame."""

    similarity_threshold: float = 0.25
    """Similarity threshold used for the verifier's `is_valid` flag."""

    low_confidence_threshold: float = 0.35
    """Confidence cutoff used when mode='low_confidence'."""

    rerank_candidates: bool = True
    """If True, re-rank `candidate_labels` using the VLM description."""

    rerank_blend: float = 0.6
    """Blend factor for candidate reranking (see SemanticFilter.rerank_candidate_labels)."""

    attach_metadata: bool = True
    """If True, attach `vlm_description` / `vlm_similarity` / `vlm_is_valid` to detections."""

    description_prompt: str = "Describe this object in one sentence. Be specific about what it is."
    """Prompt used for VLM description generation."""

    max_tokens: int = 50
    temperature: float = 0.1

    def __post_init__(self):
        if self.every_n_sampled_frames < 1:
            raise ValueError("every_n_sampled_frames must be >= 1")
        if self.max_detections_per_frame < 1:
            raise ValueError("max_detections_per_frame must be >= 1")
        if not (0.0 <= float(self.similarity_threshold) <= 1.0):
            raise ValueError("similarity_threshold must be in [0,1]")
        if not (0.0 <= float(self.low_confidence_threshold) <= 1.0):
            raise ValueError("low_confidence_threshold must be in [0,1]")
        if not (0.0 <= float(self.rerank_blend) <= 1.0):
            raise ValueError("rerank_blend must be in [0,1]")
        if self.max_tokens < 1:
            raise ValueError("max_tokens must be >= 1")
        if not (0.0 <= float(self.temperature) <= 2.0):
            raise ValueError("temperature must be in [0,2]")


@dataclass
class DepthConfig:
    """Depth estimation configuration for Phase 1 3D perception."""

    model_name: Literal["depth_anything_v3", "depth_anything_v2"] = "depth_anything_v2"
    model_size: Literal["small", "base", "large"] = "small"
    device: Optional[str] = None  # auto-detect by default
    half_precision: bool = True
    max_depth_mm: float = 10000.0

    def __post_init__(self):
        if self.max_depth_mm <= 0:
            raise ValueError(f"max_depth_mm must be > 0, got {self.max_depth_mm}")
        if self.model_size not in {"small", "base", "large"}:
            raise ValueError(
                f"model_size must be one of ['small', 'base', 'large'], got {self.model_size}"
            )


@dataclass
class HandTrackingConfig:
    """MediaPipe hand tracking configuration."""

    max_num_hands: int = 2
    min_detection_confidence: float = 0.5
    min_tracking_confidence: float = 0.5
    device: Optional[str] = None

    def __post_init__(self):
        if self.max_num_hands < 1:
            raise ValueError("max_num_hands must be >= 1")
        for name, value in (
            ("min_detection_confidence", self.min_detection_confidence),
            ("min_tracking_confidence", self.min_tracking_confidence),
        ):
            if not (0.0 <= value <= 1.0):
                raise ValueError(f"{name} must be in [0,1], got {value}")


@dataclass
class OcclusionConfig:
    """Occlusion detection configuration."""

    depth_margin_mm: float = 100.0
    occlusion_threshold: float = 0.3

    def __post_init__(self):
        if self.depth_margin_mm < 0:
            raise ValueError("depth_margin_mm must be >= 0")
        if not (0.0 <= self.occlusion_threshold <= 1.0):
            raise ValueError("occlusion_threshold must be in [0,1]")


@dataclass
class CameraConfig:
    """Camera metadata for auto estimating intrinsics."""

    width: int = 1920
    height: int = 1080
    fx: Optional[float] = None
    fy: Optional[float] = None
    cx: Optional[float] = None
    cy: Optional[float] = None
    auto_estimate: bool = True
    intrinsics_preset: Optional[str] = DEFAULT_INTRINSICS_PRESET

    def __post_init__(self):
        if self.width <= 0 or self.height <= 0:
            raise ValueError("width and height must be positive")
        if self.intrinsics_preset and self.intrinsics_preset not in INTRINSICS_PRESETS:
            raise ValueError(
                f"Unknown intrinsics preset '{self.intrinsics_preset}'. "
                f"Valid presets: {list(INTRINSICS_PRESETS.keys())}"
            )

    def resolve_intrinsics(self, width: int, height: int) -> "CameraIntrinsics":
        """Resolve intrinsics using preset or manual overrides."""
        from .types import CameraIntrinsics

        if self.intrinsics_preset:
            preset = INTRINSICS_PRESETS[self.intrinsics_preset]
            return CameraIntrinsics(
                fx=preset.fx,
                fy=preset.fy,
                cx=preset.cx,
                cy=preset.cy,
                width=width,
                height=height,
            )

        if not self.auto_estimate and all(
            value is not None for value in (self.fx, self.fy, self.cx, self.cy)
        ):
            return CameraIntrinsics(
                fx=float(self.fx),
                fy=float(self.fy),
                cx=float(self.cx),
                cy=float(self.cy),
                width=width,
                height=height,
            )

        return CameraIntrinsics.auto_estimate(width=width, height=height)


@dataclass
class TrackingConfig:
    """Configuration for the enhanced tracker."""
    max_age: int = 30  # Increased from 1 to 30 for more stable tracking
    min_hits: int = 2  # Reduced from 3 for faster track confirmation
    iou_threshold: float = 0.25  # Slightly lower for better occlusion handling
    appearance_threshold: float = 0.60  # Balanced for V-JEPA (neither too strict nor too loose)
    reid_window_frames: int = 90
    class_belief_lr: float = 0.3
    max_distance_pixels: float = 120.0  # Balanced gating for reasonable motion
    max_distance_3d_mm: float = 2000.0  # More permissive for depth uncertainty
    ttl_frames: int = 30

    match_threshold: float = 0.55
    """Max allowed match cost in EnhancedTracker assignment (lower = stricter)."""
    
    # Per-class threshold file (overrides appearance_threshold for specific classes)
    use_per_class_thresholds: bool = True
    """If True, load per-class thresholds from JSON file."""
    
    per_class_threshold_file: str = "reid_thresholds_vjepa2.json"
    """JSON file with per-class Re-ID thresholds (relative to orion/perception/)."""


@dataclass
class PerceptionConfig:
    """Complete perception engine configuration"""
    
    detection: DetectionConfig = field(default_factory=DetectionConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    description: DescriptionConfig = field(default_factory=DescriptionConfig)
    semantic_verification: SemanticVerificationConfig = field(default_factory=SemanticVerificationConfig)
    depth: DepthConfig = field(default_factory=DepthConfig)
    hand_tracking: HandTrackingConfig = field(default_factory=HandTrackingConfig)
    occlusion: OcclusionConfig = field(default_factory=OcclusionConfig)
    camera: CameraConfig = field(default_factory=CameraConfig)
    tracking: TrackingConfig = field(default_factory=TrackingConfig)
    
    # General settings
    target_fps: float = 4.0
    """Target frames per second for processing"""
    
    use_scene_detection: bool = False
    """Enable intelligent scene change detection for frame sampling"""
    
    # 3D Perception settings
    enable_3d: bool = False
    """Enable 3D perception (depth, 3D coordinates, occlusion) - DEPRECATED, use V-JEPA for 3D-awareness."""
    
    enable_depth: bool = False
    """Enable depth estimation stage (Phase 1 3D) - DEPRECATED, removed in v2."""
    
    enable_hands: bool = False
    """Enable hand tracking (MediaPipe) - disabled by default in v2."""
    
    # TODO: Hand tracking (future implementation with HOT3D dataset)
    # enable_hands: bool = False
    # """Enable hand tracking (requires HOT3D-trained model, not yet implemented)"""
    
    enable_occlusion: bool = False
    """Enable occlusion detection - DEPRECATED in v2, requires depth which is removed."""
    
    # Phase 2: Tracking settings
    enable_tracking: bool = False
    """Enable temporal entity tracking with Bayesian beliefs"""

    # Clustering / HDBSCAN tuning
    clustering_min_cluster_size: int = 4
    """Minimum cluster size for HDBSCAN entity grouping (>=2)."""

    clustering_min_samples: int = 1
    """Minimum samples parameter for HDBSCAN (>=1)."""

    clustering_cluster_selection_epsilon: float = 0.5
    """Epsilon for HDBSCAN cluster selection (lower = more clusters)."""

    # Memgraph configuration
    use_memgraph: bool = False
    """Enable Memgraph backend for real-time graph updates"""
    
    memgraph_host: str = "127.0.0.1"
    """Memgraph host address"""
    
    memgraph_port: int = 7687
    """Memgraph port"""
    
    # Stage 4: CIS (Causal Influence Scoring) configuration
    enable_cis: bool = False
    """Enable Causal Influence Scoring for hand-object and object-object relationships"""
    
    cis_threshold: float = 0.50
    """Minimum CIS score to persist an influence edge to Memgraph"""
    
    cis_compute_every_n_frames: int = 5
    """Compute CIS edges every N frames (1 = every frame, 5 = every 5 frames)"""
    
    cis_temporal_buffer_size: int = 30
    """Number of frames to buffer for temporal CIS analysis (sliding window)"""
    
    cis_depth_gate_mm: float = 2000.0
    """Maximum depth disparity (mm) for valid causal relationships. 
    Objects on different depth planes cannot causally influence each other."""
    
    # Stage 5: Batch sync configuration
    memgraph_batch_size: int = 10
    """Number of frames to buffer before atomic commit to Memgraph"""
    
    memgraph_sync_observations: bool = True
    """Enable syncing observations to Memgraph"""
    
    memgraph_sync_cis: bool = True
    """Enable syncing CIS edges to Memgraph"""

    def __post_init__(self):
        """Validate perception config"""
        if self.target_fps <= 0:
            raise ValueError(f"target_fps must be > 0, got {self.target_fps}")
        
        # Validate 3D perception dependencies
        if self.enable_occlusion and not self.enable_3d:
            logger.warning(
                "enable_occlusion set but enable_3d=False. "
                "Setting enable_3d=True automatically."
            )
            self.enable_3d = True
        if self.enable_occlusion and not self.enable_depth:
            logger.warning(
                "enable_occlusion=True requires enable_depth=True. Enabling depth automatically."
            )
            self.enable_depth = True
        
        logger.debug(
            f"PerceptionConfig validated: target_fps={self.target_fps}, "
            f"scene_detection={self.use_scene_detection}, "
            f"3d_enabled={self.enable_3d}"
        )

        # Clustering parameter validation
        if self.clustering_min_cluster_size < 2:
            logger.warning(
                f"clustering_min_cluster_size={self.clustering_min_cluster_size} too small; forcing 2"
            )
            self.clustering_min_cluster_size = 2
        if self.clustering_min_samples < 1:
            logger.warning(
                f"clustering_min_samples={self.clustering_min_samples} invalid; forcing 1"
            )
            self.clustering_min_samples = 1
        if self.clustering_cluster_selection_epsilon < 0:
            logger.warning(
                f"clustering_cluster_selection_epsilon={self.clustering_cluster_selection_epsilon} < 0; forcing 0.0"
            )
            self.clustering_cluster_selection_epsilon = 0.0


# Preset configurations
def get_ultra_fast_config() -> PerceptionConfig:
    """
    Ultra-fast mode: maximum speed, minimum quality.
    
    Use for real-time previews or very fast iteration.
    """
    return PerceptionConfig(
        detection=DetectionConfig(
            backend="yolo",
            model="yolo11n",
            confidence_threshold=0.5,
        ),
        embedding=EmbeddingConfig(
            batch_size=32,
            use_cluster_embeddings=True,
        ),
        description=DescriptionConfig(
            max_tokens=50,
        ),
        target_fps=1.0,
        enable_3d=False,
        enable_depth=False,
        enable_tracking=False,
        enable_occlusion=False,
        use_memgraph=False,
    )


def get_fast_config() -> PerceptionConfig:
    """
    Fast mode: prioritize speed over accuracy
    
    Use for quick iteration, demos, testing
    """
    return PerceptionConfig(
        detection=DetectionConfig(
            backend="yolo",
            model="yolo11n",
            confidence_threshold=0.4,
        ),
        embedding=EmbeddingConfig(
            batch_size=16,
            use_cluster_embeddings=True,
        ),
        description=DescriptionConfig(
            max_tokens=100,
            temperature=0.5,
        ),
        target_fps=2.0,
        enable_3d=False,
        enable_depth=False,
        enable_occlusion=False,
    )


def get_balanced_config() -> PerceptionConfig:
    """
    Balanced mode: good accuracy with reasonable speed
    
    Uses YOLO11m for reliable detection on Apple Silicon.
    Recommended for production use.
    """
    return PerceptionConfig(
        detection=DetectionConfig(
            backend="yolo",  # Use YOLO for MPS compatibility
            model="yolo11m",  # Medium model for balanced quality/speed
            confidence_threshold=0.35,
        ),
        embedding=EmbeddingConfig(
            batch_size=16,
        ),
        description=DescriptionConfig(
            max_tokens=200,
            temperature=0.3,
        ),
        target_fps=4.0,
        enable_tracking=True,
    )


def get_accurate_config() -> PerceptionConfig:
    """
    Accurate mode: maximum quality (slowest)
    
    Uses YOLO11x for best detection quality with V-JEPA2 for Re-ID.
    """
    return PerceptionConfig(
        detection=DetectionConfig(
            backend="yolo",  # Use YOLO11x for best quality
            model="yolo11x",  # Largest YOLO model
            confidence_threshold=0.2,  # Lower threshold for more recall
        ),
        embedding=EmbeddingConfig(
            batch_size=8,
            device="auto",
        ),
        description=DescriptionConfig(
            max_tokens=300,
            temperature=0.2,
        ),
        target_fps=8.0,
        enable_3d=False,
        enable_tracking=True,
        clustering_cluster_selection_epsilon=0.5,
    )


def get_vjepa_config() -> PerceptionConfig:
    """
    V-JEPA2 mode: Uses V-JEPA2 for embeddings and disables depth.
    
    Best for Re-ID accuracy without 3D overhead.
    """
    return PerceptionConfig(
        detection=DetectionConfig(
            backend="yolo",
            model="yolo11x",
            confidence_threshold=0.25,
        ),
        embedding=EmbeddingConfig(
            batch_size=16,
            device="auto",
        ),
        description=DescriptionConfig(
            max_tokens=200,
        ),
        target_fps=4.0,
        enable_3d=False,
        enable_depth=False,
        enable_tracking=True,
    )


def get_yoloworld_coarse_config() -> PerceptionConfig:
    """YOLO-World coarse Stage 1 + V-JEPA2 Stage 2 + canonicalization Stage 3.

    Intended for iterative tuning runs on a GPU box (e.g., Lambda):
    - Stage 1: YOLO-World with a small, stable prompt preset to avoid prompt collapse
    - Stage 1.5: CLIP candidate labels (fine-grained hypotheses)
    - Stage 2: V-JEPA2 embeddings for tracking/Re-ID
    - Stage 3: HDBSCAN-based canonical label resolution
    """
    det = DetectionConfig(
        backend="yoloworld",
        yoloworld_prompt_preset="coarse",
        yoloworld_use_custom_classes=True,
        yoloworld_enable_candidate_labels=True,
        yoloworld_candidate_top_k=5,
        confidence_threshold=0.25,  # Balanced for recall + precision
    )
    return PerceptionConfig(
        detection=det,
        embedding=EmbeddingConfig(batch_size=16, device="auto"),
        description=DescriptionConfig(max_tokens=200, temperature=0.3),
        target_fps=5.0,
        enable_tracking=True,
        use_memgraph=False,
    )


def get_yoloworld_precision_config() -> PerceptionConfig:
    """YOLO-World precision-focused config based on Gemini validation feedback.
    
    Key changes from coarse config:
    - Higher confidence threshold (0.55) to reduce hallucinations on walls/architectural surfaces
    - Stricter aspect ratio filtering (max 8.0, threshold 0.45) to reject sliver detections
    - Lower max bbox area ratio (0.85) to reject full-frame hallucinations
    - Tighter NMS IoU (0.40) for class-agnostic suppression of redundant boxes
    - Class-specific area constraints for person/door (prevent full-frame hallucinations)
    - Class-agnostic NMS enabled to eliminate duplicate tracks
    
    Trade-off: May miss some objects but greatly reduces false positives.
    """
    det = DetectionConfig(
        backend="yoloworld",
        yoloworld_prompt_preset="coarse",
        yoloworld_use_custom_classes=True,
        yoloworld_enable_candidate_labels=True,
        yoloworld_candidate_top_k=5,
        # Higher confidence to reduce background clutter (Gemini v4: suggests 0.75-0.8)
        confidence_threshold=0.60,
        # Tighter NMS to reduce redundant boxes on same object
        iou_threshold=0.40,
        # Reject very large boxes (often false positives)
        max_bbox_area_ratio=0.80,
        max_bbox_area_lowconf_threshold=0.55,
        # Stricter aspect ratio filtering to reject sliver detections
        max_aspect_ratio=6.0,
        aspect_ratio_lowconf_threshold=0.50,
        # Per-class area constraints (prevent oversized hallucinations)
        # Based on Gemini audits: many false positives are oversized boxes
        class_max_area_ratios={
            "person": 0.50,    # Person max 50% of frame
            "door": 0.60,      # Door max 60% of frame
            "window": 0.50,    # Window max 50% of frame
            "laptop": 0.25,    # Laptop max 25% of frame (reduced)
            "keyboard": 0.20,  # Keyboard max 20% of frame
            "phone": 0.10,     # Phone max 10% of frame (reduced)
            "cell phone": 0.10, # Cell phone max 10%
            "hand": 0.15,      # Hand max 15% of frame (reduced)
            "remote": 0.10,    # Remote max 10%
            "mouse": 0.08,     # Mouse max 8%
            "book": 0.30,      # Book max 30%
            "bottle": 0.15,    # Bottle max 15%
        },
        # Per-class confidence thresholds (higher for noisy classes per Gemini audit)
        # These classes are often hallucinated on background features
        class_confidence_thresholds={
            "hand": 0.65,      # Higher threshold - often hallucinated on door handles
            "laptop": 0.65,    # Higher threshold - often hallucinated on beds/surfaces
            "keyboard": 0.70,  # Very high - often hallucinated on text/lines
            "bed": 0.70,       # Very high - often hallucinated on flat surfaces
            "sink": 0.75,      # Very high - rare, often misdetected
            "remote": 0.65,    # Higher threshold - often hallucinated on small objects
            "mouse": 0.65,     # Higher threshold - often hallucinated
            "window": 0.65,    # Higher threshold - often hallucinated on edges
            "door": 0.65,      # Higher threshold - often hallucinated on edges
            "cell phone": 0.65, # Higher threshold
            "person": 0.55,    # Standard threshold
        },
        # Enable class-agnostic NMS to eliminate duplicate tracks (box + laptop + notebook)
        class_agnostic_nms=True,
        # Lowered from 0.65 to 0.50 per Gemini recommendation for stricter suppression
        class_agnostic_nms_iou=0.50,
    )
    return PerceptionConfig(
        detection=det,
        embedding=EmbeddingConfig(batch_size=16, device="auto"),
        description=DescriptionConfig(max_tokens=200, temperature=0.3),
        target_fps=5.0,
        enable_tracking=True,
        use_memgraph=False,
    )
