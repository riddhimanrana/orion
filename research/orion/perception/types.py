"""
Perception Engine Data Types & Contracts
========================================

Clean, typed data structures for Phase 1 (Perception).

These are the canonical types that flow through:
    Frame → Observation → PerceptionEntity → Description

Author: Orion Research Team
Date: October 2025
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple, Dict, Any

import numpy as np


class ObjectClass(str, Enum):
    """COCO object classes (80 classes from YOLO11)"""
    # People & animals
    PERSON = "person"
    BICYCLE = "bicycle"
    CAR = "car"
    MOTORCYCLE = "motorcycle"
    AIRPLANE = "airplane"
    BUS = "bus"
    TRAIN = "train"
    TRUCK = "truck"
    BOAT = "boat"
    
    # Traffic infrastructure
    TRAFFIC_LIGHT = "traffic light"
    FIRE_HYDRANT = "fire hydrant"
    STOP_SIGN = "stop sign"
    PARKING_METER = "parking meter"
    BENCH = "bench"
    
    # Animals
    BIRD = "bird"
    CAT = "cat"
    DOG = "dog"
    HORSE = "horse"
    SHEEP = "sheep"
    COW = "cow"
    ELEPHANT = "elephant"
    BEAR = "bear"
    ZEBRA = "zebra"
    GIRAFFE = "giraffe"
    
    # Accessories
    BACKPACK = "backpack"
    UMBRELLA = "umbrella"
    HANDBAG = "handbag"
    TIE = "tie"
    SUITCASE = "suitcase"
    
    # Sports
    FRISBEE = "frisbee"
    SKIS = "skis"
    SNOWBOARD = "snowboard"
    SPORTS_BALL = "sports ball"
    KITE = "kite"
    BASEBALL_BAT = "baseball bat"
    BASEBALL_GLOVE = "baseball glove"
    SKATEBOARD = "skateboard"
    SURFBOARD = "surfboard"
    TENNIS_RACKET = "tennis racket"
    
    # Tableware & food
    BOTTLE = "bottle"
    WINE_GLASS = "wine glass"
    CUP = "cup"
    FORK = "fork"
    KNIFE = "knife"
    SPOON = "spoon"
    BOWL = "bowl"
    BANANA = "banana"
    APPLE = "apple"
    SANDWICH = "sandwich"
    ORANGE = "orange"
    BROCCOLI = "broccoli"
    CARROT = "carrot"
    HOT_DOG = "hot dog"
    PIZZA = "pizza"
    DONUT = "donut"
    CAKE = "cake"
    
    # Furniture
    CHAIR = "chair"
    COUCH = "couch"
    POTTED_PLANT = "potted plant"
    BED = "bed"
    DINING_TABLE = "dining table"
    TOILET = "toilet"
    
    # Electronics
    TV = "tv"
    LAPTOP = "laptop"
    MOUSE = "mouse"
    REMOTE = "remote"
    KEYBOARD = "keyboard"
    CELL_PHONE = "cell phone"
    MICROWAVE = "microwave"
    OVEN = "oven"
    TOASTER = "toaster"
    SINK = "sink"
    REFRIGERATOR = "refrigerator"
    
    # Misc
    BOOK = "book"
    CLOCK = "clock"
    VASE = "vase"
    SCISSORS = "scissors"
    TEDDY_BEAR = "teddy bear"
    HAIR_DRIER = "hair drier"
    TOOTHBRUSH = "toothbrush"
    
    UNKNOWN = "unknown"


class SpatialZone(str, Enum):
    """Coarse spatial zones in frame"""
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"
    TOP = "top"
    MIDDLE = "middle"
    BOTTOM = "bottom"
    UNKNOWN = "unknown"


@dataclass
class SpatialContext:
    """Rich spatial context for an observation"""
    zone_type: str  # ceiling, wall_upper, wall_middle, wall_lower, floor
    confidence: float
    x_position: str  # left, center, right
    y_position: str  # top, middle, bottom
    reasoning: List[str] = field(default_factory=list)


@dataclass
class BoundingBox:
    """Bounding box representation [x1, y1, x2, y2]"""
    x1: float
    y1: float
    x2: float
    y2: float
    
    @property
    def width(self) -> float:
        return self.x2 - self.x1
    
    @property
    def height(self) -> float:
        return self.y2 - self.y1
    
    @property
    def area(self) -> float:
        return self.width * self.height
    
    @property
    def center(self) -> Tuple[float, float]:
        return ((self.x1 + self.x2) / 2.0, (self.y1 + self.y2) / 2.0)
    
    def to_list(self) -> List[float]:
        """Convert to [x1, y1, x2, y2] list"""
        return [self.x1, self.y1, self.x2, self.y2]
    
    @staticmethod
    def from_list(bbox: List[float]) -> "BoundingBox":
        """Create from [x1, y1, x2, y2] list"""
        return BoundingBox(float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]))


@dataclass
class Observation:
    """
    Single detection of an object in a frame.
    
    This is the atomic unit that flows through the perception pipeline.
    Multiple observations of the same object are later clustered into
    a PerceptionEntity.
    """
    
    # Spatial information
    bounding_box: BoundingBox
    centroid: Tuple[float, float]  # (x, y) center
    
    # Detection information
    object_class: ObjectClass
    confidence: float  # 0-1, from YOLO
    
    # Visual information
    visual_embedding: np.ndarray  # CLIP embedding (normalized L2)
    
    # Temporal information
    frame_number: int
    timestamp: float  # seconds since start
    
    # Metadata
    temp_id: str  # Temporary ID before clustering
    
    # Optional: Cropped region for description
    image_patch: Optional[np.ndarray] = None
    spatial_zone: Optional["SpatialContext"] = None
    raw_yolo_class: Optional[str] = None  # For debugging
    frame_width: Optional[float] = None
    frame_height: Optional[float] = None
    
    # Placeholder for Phase 2
    entity_id: Optional[str] = None
    rich_description: Optional[str] = None
    scene_id: Optional[str] = None
    location_id: Optional[str] = None

    # Open-vocabulary semantics (non-committal; used to delay canonical labels)
    candidate_labels: Optional[List[Dict[str, Any]]] = None
    """Top-k candidate label hypotheses, e.g. [{label, score, source}, ...]."""

    candidate_group: Optional[str] = None
    """Prompt group name used for candidate labeling (for debugging/analysis)."""

    # Optional: FastVLM semantic verifier metadata (Phase 1.75)
    vlm_description: Optional[str] = None
    """FastVLM description of the crop used for semantic verification (if enabled)."""

    vlm_similarity: Optional[float] = None
    """Cosine similarity between label text and VLM description embedding (if computed)."""

    vlm_is_valid: Optional[bool] = None
    """Whether the semantic verifier considered the detection label plausible."""
    
    # Optional: CLIP scene filter metadata (Phase 1.25)
    scene_similarity: Optional[float] = None
    """Cosine similarity between detection label and scene caption embedding (CLIP)."""
    
    scene_filter_reason: Optional[str] = None
    """Reason from scene filter (fits_scene, does_not_fit_scene, etc.)."""
    
    def __post_init__(self):
        """Validate observation"""
        if not isinstance(self.visual_embedding, np.ndarray):
            raise TypeError("visual_embedding must be np.ndarray")
        
        if self.confidence < 0 or self.confidence > 1:
            raise ValueError(f"confidence must be in [0, 1], got {self.confidence}")
        
        # Validate embedding is normalized
        norm = float(np.linalg.norm(self.visual_embedding))
        if norm > 1.01 or norm < 0.99:
            # Auto-normalize if slightly off
            self.visual_embedding = self.visual_embedding / norm if norm > 0 else self.visual_embedding

        if self.frame_width is not None and self.frame_width <= 0:
            raise ValueError("frame_width must be positive when provided")

        if self.frame_height is not None and self.frame_height <= 0:
            raise ValueError("frame_height must be positive when provided")


@dataclass
class PerceptionEntity:
    """
    Clustered entity from Phase 1.
    
    Multiple observations of the same object are merged into a single entity
    with averaged visual embedding and selected for description.
    """
    
    entity_id: str
    object_class: ObjectClass
    observations: List[Observation] = field(default_factory=list)
    
    # Aggregated properties
    average_embedding: Optional[np.ndarray] = None
    first_seen_frame: int = 0
    last_seen_frame: int = 0
    appearance_count: int = 0
    
    # Description
    description: Optional[str] = None
    description_frame: Optional[int] = None  # Frame used for description
    
    # Quality improvements (optional)
    corrected_class: Optional[str] = None  # Class correction result
    correction_confidence: Optional[float] = None  # Correction confidence score

    # Canonical open-vocab label (resolved via HDBSCAN clustering on candidate labels)
    canonical_label: Optional[str] = None
    """Stable fine-grained label derived from candidate label clustering."""
    canonical_confidence: Optional[float] = None
    """Confidence (0-1) of the canonical label assignment."""
    
    def __post_init__(self):
        """Validate entity"""
        if not self.observations:
            raise ValueError("PerceptionEntity must have at least one observation")
        
        self.appearance_count = len(self.observations)
        self.first_seen_frame = min(obs.frame_number for obs in self.observations)
        self.last_seen_frame = max(obs.frame_number for obs in self.observations)
    
    def compute_average_embedding(self) -> np.ndarray:
        """Compute average visual embedding across all observations"""
        if not self.observations:
            raise ValueError("No observations to average")
        
        embeddings = np.array([obs.visual_embedding for obs in self.observations])
        avg = np.mean(embeddings, axis=0)
        
        # Normalize
        norm = np.linalg.norm(avg)
        if norm > 0:
            avg = avg / norm
        
        self.average_embedding = avg
        return avg
    
    def get_best_observation(self) -> Observation:
        """
        Select best observation for description.
        
        Criteria (in order):
        1. Highest confidence
        2. Largest bbox area
        3. Closest to frame center
        """
        if not self.observations:
            raise ValueError("No observations available")
        
        best = self.observations[0]
        
        for obs in self.observations[1:]:
            # Compare by confidence
            if obs.confidence > best.confidence:
                best = obs
            elif obs.confidence == best.confidence:
                # Tie-break by bbox area
                if obs.bounding_box.area > best.bounding_box.area:
                    best = obs
        
        return best
    
    def get_timeline(self) -> List[Observation]:
        """Get observations in chronological order"""
        return sorted(self.observations, key=lambda obs: obs.timestamp)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization"""
        d = {
            "entity_id": self.entity_id,
            "object_class": self.object_class.value,
            "appearance_count": self.appearance_count,
            "first_seen_frame": self.first_seen_frame,
            "last_seen_frame": self.last_seen_frame,
            "description": self.description,
            "description_frame": self.description_frame,
            "canonical_label": self.canonical_label,
            "canonical_confidence": round(self.canonical_confidence, 4) if self.canonical_confidence else None,
            "observations": [
                {
                    "frame": obs.frame_number,
                    "timestamp": obs.timestamp,
                    "bbox": obs.bounding_box.to_list(),
                    "confidence": obs.confidence,
                    "candidate_labels": obs.candidate_labels,
                }
                for obs in self.observations
            ],
        }
        return d


@dataclass
class PerceptionResult:
    """Output from Phase 1 (Perception Engine)"""
    
    entities: List[PerceptionEntity]
    raw_observations: List[Observation]
    
    # Metadata
    video_path: str
    total_frames: int
    fps: float
    duration_seconds: float
    
    # Statistics
    total_detections: int = 0
    unique_entities: int = 0
    processing_time_seconds: float = 0.0
    metrics: Optional[Dict[str, Any]] = None  # Optional tracking/telemetry metrics
    
    def __post_init__(self):
        """Compute statistics"""
        self.total_detections = len(self.raw_observations)
        self.unique_entities = len(self.entities)


# ============================================================================
# Phase 1: 3D Perception Types (Depth, Hands, 3D Coordinates)
# ============================================================================

class HandPose(Enum):
    """Hand pose classification."""
    OPEN = "open"
    CLOSED = "closed"
    PINCH = "pinch"
    POINT = "point"
    UNKNOWN = "unknown"


class VisibilityState(Enum):
    """Entity visibility state for occlusion tracking."""
    FULLY_VISIBLE = "fully_visible"
    PARTIALLY_OCCLUDED = "partially_occluded"
    HAND_OCCLUDED = "hand_occluded"
    OFF_SCREEN = "off_screen"
    UNKNOWN = "unknown"


@dataclass
class CameraIntrinsics:
    """Camera calibration parameters for 3D backprojection."""
    
    fx: float  # focal length x (pixels)
    fy: float  # focal length y (pixels)
    cx: float  # principal point x (pixels)
    cy: float  # principal point y (pixels)
    width: int  # image width
    height: int  # image height
    
    @classmethod
    def auto_estimate(cls, width: int, height: int) -> "CameraIntrinsics":
        """Auto-estimate camera intrinsics for typical smartphone/egocentric cameras."""
        fov_deg = 65.0  # typical phone FOV
        fov_rad = fov_deg * np.pi / 180.0
        fx = width / (2.0 * np.tan(fov_rad / 2.0))
        fy = fx  # square pixels
        cx = width / 2.0
        cy = height / 2.0
        return cls(fx, fy, cx, cy, width, height)


@dataclass
class Hand:
    """Hand detection with 3D landmarks from MediaPipe."""
    
    id: str
    landmarks_2d: List[Tuple[float, float]]  # 21 joints normalized
    landmarks_3d: List[Tuple[float, float, float]]  # 21 joints in mm
    palm_center_3d: Tuple[float, float, float]  # (X, Y, Z) in mm
    pose: HandPose
    confidence: float
    handedness: str  # "Left" or "Right"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "landmarks_2d": self.landmarks_2d,
            "landmarks_3d": self.landmarks_3d,
            "palm_center_3d": self.palm_center_3d,
            "pose": self.pose.value,
            "confidence": self.confidence,
            "handedness": self.handedness,
        }


@dataclass
class EntityState3D:
    """Enhanced entity state with 3D information from depth estimation."""
    
    entity_id: str
    frame_number: int
    timestamp: float
    class_label: str
    class_confidence: float
    bbox_2d_px: Tuple[int, int, int, int]  # (x1, y1, x2, y2)
    centroid_2d_px: Tuple[float, float]
    
    # 3D information from depth
    centroid_3d_mm: Optional[Tuple[float, float, float]] = None  # (X, Y, Z)
    bbox_3d_mm: Optional[Tuple[Tuple[float, float, float], Tuple[float, float, float]]] = None
    depth_mean_mm: Optional[float] = None
    depth_variance_mm2: Optional[float] = None
    
    # Visibility & occlusion
    visibility_state: VisibilityState = VisibilityState.UNKNOWN
    occlusion_ratio: float = 0.0  # 0=fully visible, 1=fully occluded
    occluded_by: Optional[str] = None  # "hand" or entity_id
    
    # Metadata
    embedding: Optional[np.ndarray] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "entity_id": self.entity_id,
            "frame_number": self.frame_number,
            "timestamp": self.timestamp,
            "class_label": self.class_label,
            "class_confidence": self.class_confidence,
            "bbox_2d_px": self.bbox_2d_px,
            "centroid_2d_px": self.centroid_2d_px,
            "centroid_3d_mm": self.centroid_3d_mm,
            "bbox_3d_mm": self.bbox_3d_mm,
            "depth_mean_mm": self.depth_mean_mm,
            "depth_variance_mm2": self.depth_variance_mm2,
            "visibility_state": self.visibility_state.value,
            "occlusion_ratio": self.occlusion_ratio,
            "occluded_by": self.occluded_by,
            "metadata": self.metadata,
        }


# Backwards compatibility alias for tests that import EntityState
EntityState = EntityState3D


@dataclass
class OcclusionInfo:
    """Occlusion information for an entity."""
    
    entity_id: str
    occlusion_ratio: float
    visibility_state: VisibilityState
    occluded_by: Optional[str] = None


@dataclass
class Perception3DResult:
    """Phase 1 3D perception output (depth, hands, 3D entities)."""
    
    frame_number: int
    timestamp: float
    
    # 3D perception data
    entities: List[EntityState3D]
    hands: List[Hand]
    depth_map: Optional[np.ndarray] = None
    camera_intrinsics: Optional[CameraIntrinsics] = None
    camera_pose: Optional[np.ndarray] = None  # 4x4 matrix (world to camera or camera to world)
    
    # Performance
    processing_time_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Camera Intrinsics Presets
# ============================================================================

INTRINSICS_PRESETS: Dict[str, CameraIntrinsics] = {
    "demo_room_iphone15pro_main": CameraIntrinsics(
        fx=1215.0,
        fy=1110.0,
        cx=960.0,
        cy=540.0,
        width=1920,
        height=1080,
    ),
    "legacy_placeholder_640x480": CameraIntrinsics(
        fx=525.0,
        fy=525.0,
        cx=319.5,
        cy=239.5,
        width=640,
        height=480,
    ),
}

DEFAULT_INTRINSICS_PRESET = "demo_room_iphone15pro_main"
