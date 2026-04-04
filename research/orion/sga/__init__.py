"""
Scene Graph Anticipation (SGA) Module

This module implements Scene Graph Anticipation evaluation on Action Genome.
SGA = predicting future scene graph relationships from observed video frames.

Pipeline Parts:
1. Data Loading & Frame Splitting (loader.py)
2. Detection & Tracking (detector.py) 
3. Observed Scene Graph Generation (observed_sgg.py)
4. Future Anticipation Model (anticipator.py)
5. Evaluation Metrics (evaluator.py)
"""

from .loader import (
    ActionGenomeLoader,
    AGVideo,
    AGFrame,
    AGRelation,
    AGObject,
    AGDataBundle,
    load_action_genome,
)

from .detector import (
    SGADetector,
    SGADetectionPipeline,
    SimpleIOUTracker,
    Detection,
    TrackedEntity,
    TrackingResult,
    FrameDetections,
    extract_video_frames,
)

from .observed_sgg import (
    ObservedSceneGraphGenerator,
    SpatialRelationClassifier,
    MotionRelationClassifier,
    SceneGraphNode,
    SceneGraphEdge,
    FrameSceneGraph,
    VideoSceneGraph,
    tracking_result_to_ag_video,
)

from .anticipator import (
    SceneGraphAnticipator,
    TrajectoryPredictor,
    RelationPersistenceModel,
    ContextBasedPredictor,
    AnticipatedRelation,
    AnticipationResult,
    anticipate_from_video,
)

from .evaluator import (
    SGAEvaluator,
    SGAMetrics,
    SGAEvalSummary,
    VideoEvalResult,
    evaluate_sga_on_action_genome,
    print_sga_results_table,
)

# Part 6: Temporal Model (Neural SGA)
from .temporal_model import (
    TemporalSGAModel,
    TemporalSGAConfig,
    SGALoss,
    SpatialEncoder,
    TemporalEncoder,
    AnticipationDecoder,
    create_model as create_temporal_model,
    load_pretrained as load_pretrained_model,
)

from .sga_inference import (
    SGAInferenceEngine,
    FuturePrediction,
    SGAResult,
    SGAEvaluation,
    evaluate_sga,
    run_sga_on_video,
)

__all__ = [
    # Part 1: Data Loading
    "ActionGenomeLoader",
    "AGVideo", 
    "AGFrame",
    "AGRelation",
    "AGObject",
    "AGDataBundle",
    "load_action_genome",
    # Part 2: Detection & Tracking
    "SGADetector",
    "SGADetectionPipeline",
    "SimpleIOUTracker",
    "Detection",
    "TrackedEntity",
    "TrackingResult",
    "FrameDetections",
    "extract_video_frames",
    # Part 3: Scene Graph Generation
    "ObservedSceneGraphGenerator",
    "SpatialRelationClassifier",
    "MotionRelationClassifier",
    "SceneGraphNode",
    "SceneGraphEdge",
    "FrameSceneGraph",
    "VideoSceneGraph",
    "tracking_result_to_ag_video",
    # Part 4: Anticipation
    "SceneGraphAnticipator",
    "TrajectoryPredictor",
    "RelationPersistenceModel",
    "ContextBasedPredictor",
    "AnticipatedRelation",
    "AnticipationResult",
    "anticipate_from_video",
    # Part 5: Evaluation
    "SGAEvaluator",
    "SGAMetrics",
    "SGAEvalSummary",
    "VideoEvalResult",
    "evaluate_sga_on_action_genome",
    "print_sga_results_table",
    # Part 6: Temporal Model
    "TemporalSGAModel",
    "TemporalSGAConfig",
    "SGALoss",
    "SpatialEncoder",
    "TemporalEncoder",
    "AnticipationDecoder",
    "create_temporal_model",
    "load_pretrained_model",
    # Inference
    "SGAInferenceEngine",
    "FuturePrediction",
    "SGAResult",
    "SGAEvaluation",
    "evaluate_sga",
    "run_sga_on_video",
]
