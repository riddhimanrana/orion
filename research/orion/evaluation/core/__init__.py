"""Shared evaluation utilities for SGG/SGA."""

from .types import BBox, ObjectInstance, RelationInstance, FrameGraph, VideoGraph
from .metrics import compute_recall_at_k, compute_mean_recall_at_k
from .runner import EvaluationRunner, load_predictions_jsonl

__all__ = [
    "BBox",
    "ObjectInstance",
    "RelationInstance",
    "FrameGraph",
    "VideoGraph",
    "compute_recall_at_k",
    "compute_mean_recall_at_k",
    "EvaluationRunner",
    "load_predictions_jsonl",
]
