"""
Perception Engine Package
=========================

Phase 1 of the Orion pipeline: detection, embeddings, tracking, descriptions, and optional 3D perception.

This package now focuses purely on the perception stage. Graph/scene memory utilities moved to
``orion.graph`` so the folder surface is limited to the active runtime components listed below:

Modules:
    - types: Data structures (Observation, PerceptionEntity, Hand, EntityState3D, etc.)
    - config: Configuration for perception components
    - observer: Frame sampling and YOLO/YOLO-World detection
    - embedder: V-JEPA2 embedding generation for Re-ID
    - tracker: HDBSCAN clustering into entities
    - describer: FastVLM description generation
    - depth: Monocular depth estimation helpers
    - camera_intrinsics: 3D backprojection utilities
    - engine: High-level orchestration

Author: Orion Research Team
Date: October 2025
"""

from .types import (
    ObjectClass,
    SpatialZone,
    BoundingBox,
    Observation,
    PerceptionEntity,
    PerceptionResult,
    CameraIntrinsics,
    EntityState,
)

from .config import (
    DetectionConfig,
    EmbeddingConfig,
    DescriptionConfig,
    PerceptionConfig,
    DepthConfig,
    HandTrackingConfig,
    OcclusionConfig,
    CameraConfig,
    get_fast_config,
    get_balanced_config,
    get_accurate_config,
    get_yoloworld_coarse_config,
    get_yoloworld_precision_config,
)

# IMPORTANT: keep module import lightweight.
# Avoid importing heavy dependencies (torch, transformers, tensorflow) at import time.

__all__ = [
    # Types
    "ObjectClass",
    "SpatialZone",
    "BoundingBox",
    "Observation",
    "PerceptionEntity",
    "PerceptionResult",
    "CameraIntrinsics",
    "EntityState",
    # Config
    "DetectionConfig",
    "EmbeddingConfig",
    "DescriptionConfig",
    "DepthConfig",
    "HandTrackingConfig",
    "OcclusionConfig",
    "CameraConfig",
    # Modules
    "DepthEstimator",
    "Perception3DEngine",
    "PerceptionEngine",
    "camera_intrinsics",
    "PerceptionConfig",
    "get_fast_config",
    "get_balanced_config",
    "get_accurate_config",
]


def __getattr__(name: str):
    if name == "DepthEstimator":
        from .depth import DepthEstimator as _DepthEstimator

        return _DepthEstimator

    if name == "PerceptionEngine":
        from .engine import PerceptionEngine as _PerceptionEngine

        return _PerceptionEngine

    if name in {"Perception3DEngine", "PERCEPTION_3D_AVAILABLE"}:
        try:
            from .perception_3d import Perception3DEngine as _Perception3DEngine

            globals()["Perception3DEngine"] = _Perception3DEngine
            globals()["PERCEPTION_3D_AVAILABLE"] = True
        except Exception:
            globals()["Perception3DEngine"] = None
            globals()["PERCEPTION_3D_AVAILABLE"] = False

        return globals()[name]

    raise AttributeError(f"module 'orion.perception' has no attribute {name!r}")


def __dir__():
    return sorted(list(globals().keys()) + __all__)
