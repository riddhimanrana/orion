"""
Unified Configuration for Orion
================================

Clean, centralized configuration for all components and external services.

Architecture:
    YOLO11x → Detection
    CLIP    → Re-ID embeddings
    FastVLM → Descriptions
    Gemma3  → Q&A (via Ollama)
    Neo4j   → Knowledge graph storage
    Docker  → Container orchestration

Author: Orion Research Team
Date: October 2025
"""

import logging
import os
from dataclasses import dataclass, field
from typing import Literal, Any

from orion.perception.config import PerceptionConfig, get_fast_config as get_fast_perception_config

# Placeholder for SemanticConfig (module doesn't exist yet)
@dataclass
class SemanticConfig:
    """Placeholder for semantic stage configuration."""
    pass


@dataclass
class VideoConfig:
    """Video processing configuration"""
    
    # Frame sampling
    target_fps: float = 4.0
    """Target FPS for processing (lower = faster)"""
    
    # Frame selection (optional scene detection)
    use_scene_detection: bool = False
    """Enable scene change detection for intelligent frame selection"""
    
    scene_detection_threshold: float = 0.15
    """Threshold for scene change detection (lower = more sensitive)"""


@dataclass
class DetectionConfig:
    """YOLO detection configuration"""
    
    # Model
    model: Literal["yolo11n", "yolo11s", "yolo11m", "yolo11x"] = "yolo11x"
    """YOLO model variant (n=fastest, x=most accurate)"""
    
    # Detection thresholds
    confidence_threshold: float = 0.25
    """Minimum confidence for detection (lower = more detections)"""
    
    iou_threshold: float = 0.45
    """NMS IoU threshold for overlapping boxes"""
    
    # Object filtering
    min_object_size: int = 32
    """Minimum object size in pixels (smaller objects ignored)"""
    
    bbox_padding_percent: float = 0.10
    """Padding around bounding boxes when cropping (0.10 = 10%)"""
    
    # Confidence-based entity filtering
    high_confidence_threshold: float = 0.6
    """High confidence detections are trusted"""
    
    low_confidence_threshold: float = 0.4
    """Low confidence detections are skipped"""


@dataclass
class EmbeddingConfig:
    """CLIP embedding configuration"""
    
    # Model
    model: str = "openai/clip-vit-base-patch32"
    """CLIP model to use"""
    
    embedding_dim: int = 512
    """Embedding dimension (ViT-B/32 = 512, ViT-L/14 = 768)"""
    
    # Multimodal settings
    use_text_conditioning: bool = True
    """Condition embeddings on YOLO class (helps detect misclassifications)"""
    
    # Batch processing
    batch_size: int = 32
    """Number of images to embed at once (higher = faster but more memory)"""


@dataclass
class ClusteringConfig:
    """HDBSCAN clustering configuration"""
    
    # Core parameters
    min_cluster_size: int = 3
    """Minimum appearances to form an entity"""
    
    min_samples: int = 1
    """Minimum samples in neighborhood (lower = more aggressive)"""
    
    # Distance metric
    metric: Literal["euclidean", "cosine"] = "euclidean"
    """Distance metric for clustering"""
    
    # CLIP-optimized epsilon
    cluster_selection_epsilon: float = 0.35
    """Max distance to merge clusters (tuned for CLIP's 512-dim space)"""
    """Max distance to merge clusters (tuned for CLIP's 512-dim space)"""
    
    # State change detection
    state_change_threshold: float = 0.75
    """Cosine similarity threshold for detecting state changes"""
    
    min_state_duration_frames: int = 2
    """State change must persist for this many frames"""


@dataclass
class DescriptionConfig:
    """FastVLM description configuration"""
    
    # Generation settings
    max_tokens: int = 200
    """Maximum tokens per description"""
    
    temperature: float = 0.3
    """Sampling temperature (lower = more deterministic)"""
    
    # Smart description (describe once per entity)
    describe_once: bool = True
    """Only describe each entity once (from best frame)"""
    
    # Best frame selection
    size_weight: float = 0.5
    """Weight for object size in best frame selection"""
    
    centrality_weight: float = 0.3
    """Weight for object centrality (closer to image center)"""
    
    confidence_weight: float = 0.2
    """Weight for detection confidence"""


@dataclass
class PerformanceConfig:
    """Performance optimization settings"""
    
    # Parallel processing
    use_multiprocessing: bool = False
    """Enable multiprocessing for descriptions (experimental)"""
    
    num_workers: int = 2
    """Number of worker processes"""
    
    # Memory management
    clear_cache_after_phase: bool = True
    """Clear GPU cache after each phase"""
    
    # Batch processing
    enable_batching: bool = True
    """Batch process embeddings and descriptions"""


@dataclass
class LoggingConfig:
    """Logging configuration"""
    
    level: int = logging.INFO
    """Logging level"""
    
    show_progress: bool = True
    """Show progress bars"""
    
    verbose: bool = False
    """Verbose output (debug info)"""


@dataclass
class CorrectionConfig:
    """Class correction and semantic enrichment configuration"""
    
    use_llm: bool = False
    """Use LLM for class extraction (slower). Default: False"""
    
    enable_canonical_labels: bool = True
    """Emit canonical_label (e.g., 'knob') separate from mapped COCO class"""
    
    infer_part_of: bool = True
    """Infer PART_OF relations (e.g., knob -> door) when possible"""
    
    infer_events: bool = True
    """Infer simple events like OPENS_DOOR and ENTERS_ROOM from cues"""

    enable_llm_cache: bool = True
    """Reuse LLM corrections when the same object description reappears."""

    llm_cache_size: int = 256
    """Maximum cached correction entries to retain in memory."""

    llm_confidence_floor: float = 0.45
    """Below this detection confidence, route objects to LLM review."""

    llm_confidence_ceiling: float = 0.65
    """Above this confidence (and matching description), skip LLM calls."""


@dataclass
class Neo4jConfig:
    """Neo4j database configuration"""
    
    uri: str = "neo4j://127.0.0.1:7687"
    """Neo4j connection URI (bolt or neo4j protocol)"""
    
    user: str = "neo4j"
    """Neo4j username"""
    
    password_env_var: str = "ORION_NEO4J_PASSWORD"
    """Environment variable name for Neo4j password (for security)"""
    
    @property
    def password(self) -> str:
        """Get password from environment variable"""
        pwd = os.getenv(self.password_env_var, "")
        if not pwd:
            raise ValueError(f"Neo4j password not set in {self.password_env_var}")
        return pwd


@dataclass
class OllamaConfig:
    """Ollama configuration for Q&A and embeddings"""
    
    base_url: str = "http://localhost:11434"
    """Ollama server URL"""
    
    qa_model: str = "gemma3:4b"
    """Model for Q&A tasks"""
    
    embedding_model: str = "openai/clip-vit-base-patch32"
    """Model for text embeddings (if using Ollama for embeddings)"""


@dataclass
class AsyncConfig:
    """Asynchronous processing configuration"""
    
    # Enable async processing
    enable_async: bool = True
    """Enable true asynchronous perception with fast/slow decoupling"""
    
    # Queue configuration
    max_queue_size: int = 100
    """Maximum detection tasks in queue before backpressure"""
    
    # Description strategy
    describe_strategy: Literal["best_frame", "first_appearance", "periodic"] = "first_appearance"
    """
    Strategy for VLM descriptions:
    - best_frame: Describe highest quality detection per entity (post-clustering)
    - first_appearance: Describe on first appearance of entity
    - periodic: Describe every N frames
    """
    
    description_interval_frames: int = 30
    """For periodic strategy: describe every N frames"""
    
    # Worker configuration
    num_description_workers: int = 2
    """Number of concurrent VLM workers (1-4 recommended)"""
    
    # Buffering
    enable_frame_buffer: bool = True
    """Buffer frames for smooth processing"""
    
    frame_buffer_size: int = 30
    """Number of frames to buffer"""
    
    # Backpressure handling
    enable_backpressure: bool = True
    """Slow down fast loop when queue is full"""
    
    backpressure_threshold: float = 0.8
    """Trigger backpressure at 80% queue capacity"""
    
    # Progress reporting
    report_interval_seconds: float = 5.0
    """Report progress every N seconds"""


@dataclass
class RuntimeConfig:
    """Runtime and backend configuration"""
    
    backend: Literal["auto", "torch", "mlx"] = "auto"
    """Compute backend (auto=detect, torch=CUDA/CPU, mlx=Apple Silicon)"""
    
    device: Literal["auto", "cuda", "mps", "cpu"] = "auto"
    """Device selection (auto=detect from backend)"""


@dataclass
class OrionConfig:
    """
    Master configuration for Orion pipeline.
    
    Composition:
        - perception: Phase 1 (detection, embedding, description)
        - semantic: Phase 2 (state changes, events, causality)
        - neo4j: Knowledge graph storage
        - ollama: LLM backend
        - runtime: Backend selection
    
    Usage:
        # Use defaults
        config = OrionConfig()
        
        # Customize perception
        from orion.perception.config import DetectionConfig
        config.perception.detection.model = "yolo11n"
        
        # Customize semantic
        from orion.semantic.config import StateChangeConfig
        config.semantic.state_change.embedding_similarity_threshold = 0.80
        
        # Access
        print(config.perception.detection.confidence_threshold)  # 0.25
        print(config.semantic.causal.cis_threshold)              # 0.55
    """
    
    # Phase 1 & 2 configs (new modular approach)
    perception: PerceptionConfig = field(default_factory=PerceptionConfig)
    semantic: SemanticConfig = field(default_factory=SemanticConfig)
    
    # Infrastructure configs
    neo4j: Neo4jConfig = field(default_factory=Neo4jConfig)
    ollama: OllamaConfig = field(default_factory=OllamaConfig)
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)
    
    # Legacy configs (kept for backward compatibility during transition)
    video: VideoConfig = field(default_factory=VideoConfig)
    detection: DetectionConfig = field(default_factory=DetectionConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    clustering: ClusteringConfig = field(default_factory=ClusteringConfig)
    description: DescriptionConfig = field(default_factory=DescriptionConfig)
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    correction: CorrectionConfig = field(default_factory=CorrectionConfig)
    async_processing: AsyncConfig = field(default_factory=AsyncConfig)
    
    def __post_init__(self):
        """Validate and initialize all configs"""
        # Ensure all configs are properly typed
        if not isinstance(self.perception, PerceptionConfig):
            self.perception = PerceptionConfig()
        if not isinstance(self.semantic, SemanticConfig):
            self.semantic = SemanticConfig()
        if not isinstance(self.neo4j, Neo4jConfig):
            self.neo4j = Neo4jConfig()
        if not isinstance(self.ollama, OllamaConfig):
            self.ollama = OllamaConfig()
        if not isinstance(self.runtime, RuntimeConfig):
            self.runtime = RuntimeConfig()
        
        # Legacy configs (for transition period)
        if not isinstance(self.video, VideoConfig):
            self.video = VideoConfig()
        if not isinstance(self.detection, DetectionConfig):
            self.detection = DetectionConfig()
        if not isinstance(self.embedding, EmbeddingConfig):
            self.embedding = EmbeddingConfig()
        if not isinstance(self.clustering, ClusteringConfig):
            self.clustering = ClusteringConfig()
        if not isinstance(self.description, DescriptionConfig):
            self.description = DescriptionConfig()
        if not isinstance(self.performance, PerformanceConfig):
            self.performance = PerformanceConfig()
        if not isinstance(self.logging, LoggingConfig):
            self.logging = LoggingConfig()
        if not isinstance(self.correction, CorrectionConfig):
            self.correction = CorrectionConfig()
        if not isinstance(self.async_processing, AsyncConfig):
            self.async_processing = AsyncConfig()


# Preset configurations

def get_fast_config() -> OrionConfig:
    """
    Fast preset: Optimized for speed.
    
    - YOLO11n (fastest detector)
    - Lower resolution
    - Less aggressive clustering
    - Fewer descriptions
    """
    return OrionConfig(
        video=VideoConfig(target_fps=2.0),
        detection=DetectionConfig(
            model="yolo11n",
            confidence_threshold=0.35,
        ),
        clustering=ClusteringConfig(
            min_cluster_size=5,
            cluster_selection_epsilon=0.45,
        ),
        performance=PerformanceConfig(enable_batching=True),
        correction=CorrectionConfig(
            use_llm=False,
            enable_canonical_labels=True,
            infer_part_of=True,
            infer_events=True,
        ),
    )


def get_balanced_config() -> OrionConfig:
    """
    Balanced preset: Good speed and accuracy.
    
    - YOLO11m (balanced detector)
    - Standard settings
    - Default clustering
    """
    return OrionConfig(
    detection=DetectionConfig(model="yolo11m"),
        clustering=ClusteringConfig(cluster_selection_epsilon=0.35),
        correction=CorrectionConfig(
            use_llm=False,
            enable_canonical_labels=True,
            infer_part_of=True,
            infer_events=True,
        ),
    )


def get_accurate_config() -> OrionConfig:
    """
    Accurate preset: Optimized for accuracy.
    
    - YOLO11x (most accurate detector)
    - Lower confidence threshold
    - More aggressive clustering
    - More detailed descriptions
    """
    return OrionConfig(
        video=VideoConfig(target_fps=5.0),
        detection=DetectionConfig(
            model="yolo11x",
            confidence_threshold=0.20,
            high_confidence_threshold=0.7,
        ),
        clustering=ClusteringConfig(
            min_cluster_size=2,
            cluster_selection_epsilon=0.30,
        ),
        description=DescriptionConfig(max_tokens=300),
        correction=CorrectionConfig(
            use_llm=False,
            enable_canonical_labels=True,
            infer_part_of=True,
            infer_events=True,
        ),
    )


# ============================================================================
# SEMANTIC UPLIFT PRESETS (Part 2)
# ============================================================================

# Fast processing - loose clustering, fewer events
SEMANTIC_FAST_CONFIG = {
    "MIN_CLUSTER_SIZE": 5,
    "CLUSTER_SELECTION_EPSILON": 0.20,
    "STATE_CHANGE_THRESHOLD": 0.80,
    "TIME_WINDOW_SIZE": 60.0,
    "MIN_EVENTS_PER_WINDOW": 3,
    "LOG_LEVEL": logging.WARNING,
    "DESCRIPTION": "Fast mode - loose clustering, larger windows",
}

# Balanced - default settings
SEMANTIC_BALANCED_CONFIG = {
    "MIN_CLUSTER_SIZE": 3,
    "CLUSTER_SELECTION_EPSILON": 0.15,
    "STATE_CHANGE_THRESHOLD": 0.85,
    "TIME_WINDOW_SIZE": 30.0,
    "MIN_EVENTS_PER_WINDOW": 2,
    "LOG_LEVEL": logging.INFO,
    "DESCRIPTION": "Balanced mode - default settings",
}

# Accurate - tight clustering, more events
SEMANTIC_ACCURATE_CONFIG = {
    "MIN_CLUSTER_SIZE": 2,
    "CLUSTER_SELECTION_EPSILON": 0.10,
    "STATE_CHANGE_THRESHOLD": 0.90,
    "TIME_WINDOW_SIZE": 15.0,
    "MIN_EVENTS_PER_WINDOW": 1,
    "LOG_LEVEL": logging.DEBUG,
    "DESCRIPTION": "Accurate mode - tight clustering, small windows, sensitive to changes",
}

# ============================================================================
# QUERY PRESETS (Part 3)
# ============================================================================

QUERY_BASELINE_CONFIG = {
    "name": "Baseline",
    "description": "Minimal configuration for basic testing",
    "GEMINI_MODEL": "gemini-2.0-flash-exp",
    "GEMINI_TEMPERATURE": 0.3,
    "GEMINI_MAX_TOKENS": 1024,
    "CLIP_MAX_FRAMES": 5,
    "CLIP_FRAME_SAMPLE_RATE": 10,
    "USE_VISION_CONTEXT": True,
    "USE_GRAPH_CONTEXT": True,
    "MAX_GRAPH_RESULTS": 10,
    "RERANK_RESULTS": False,
    "EC15_QUESTION_COUNT": 10,
    "LOTQ_QUESTION_COUNT": 3,
    "SIMILARITY_THRESHOLD": 0.75,
    "TEMPORAL_TOLERANCE_SECONDS": 2.0,
}

QUERY_BALANCED_CONFIG = {
    "name": "Balanced",
    "description": "Balanced quality and performance (recommended)",
    "GEMINI_MODEL": "gemini-2.0-flash-exp",
    "GEMINI_TEMPERATURE": 0.3,
    "GEMINI_MAX_TOKENS": 2048,
    "CLIP_MAX_FRAMES": 10,
    "CLIP_FRAME_SAMPLE_RATE": 5,
    "USE_VISION_CONTEXT": True,
    "USE_GRAPH_CONTEXT": True,
    "MAX_GRAPH_RESULTS": 20,
    "RERANK_RESULTS": True,
    "EC15_QUESTION_COUNT": 15,
    "LOTQ_QUESTION_COUNT": 5,
    "SIMILARITY_THRESHOLD": 0.75,
    "TEMPORAL_TOLERANCE_SECONDS": 2.0,
}

QUERY_HIGH_QUALITY_CONFIG = {
    "name": "High Quality",
    "description": "Maximum quality for research evaluation",
    "GEMINI_MODEL": "gemini-2.0-flash-exp",
    "GEMINI_TEMPERATURE": 0.2,
    "GEMINI_MAX_TOKENS": 4096,
    "CLIP_MAX_FRAMES": 20,
    "CLIP_FRAME_SAMPLE_RATE": 3,
    "USE_VISION_CONTEXT": True,
    "USE_GRAPH_CONTEXT": True,
    "MAX_GRAPH_RESULTS": 50,
    "RERANK_RESULTS": True,
    "EC15_QUESTION_COUNT": 20,
    "LOTQ_QUESTION_COUNT": 10,
    "SIMILARITY_THRESHOLD": 0.80,
    "TEMPORAL_TOLERANCE_SECONDS": 1.5,
}

QUERY_FAST_CONFIG = {
    "name": "Fast",
    "description": "Quick testing with minimal API calls",
    "GEMINI_MODEL": "gemini-2.0-flash-exp",
    "GEMINI_TEMPERATURE": 0.5,
    "GEMINI_MAX_TOKENS": 512,
    "CLIP_MAX_FRAMES": 3,
    "CLIP_FRAME_SAMPLE_RATE": 15,
    "USE_VISION_CONTEXT": True,
    "USE_GRAPH_CONTEXT": True,
    "MAX_GRAPH_RESULTS": 5,
    "RERANK_RESULTS": False,
    "EC15_QUESTION_COUNT": 5,
    "LOTQ_QUESTION_COUNT": 2,
    "SIMILARITY_THRESHOLD": 0.70,
    "TEMPORAL_TOLERANCE_SECONDS": 3.0,
}

# Default configuration
DEFAULT_CONFIG = get_balanced_config()
