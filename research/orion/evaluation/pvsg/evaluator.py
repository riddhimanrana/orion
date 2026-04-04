"""PVSG SGG evaluator."""

from __future__ import annotations

from typing import Dict, List, Sequence

from ..core.metrics import MetricSummary
from ..core.runner import EvaluationRunner
from ..core.types import VideoGraph
from .adapter import build_video_graph
from .loader import PVSGBundle


def evaluate_pvsg(bundle: PVSGBundle, predictions: Dict[str, VideoGraph], top_ks: Sequence[int]) -> MetricSummary:
    gt_videos: List[VideoGraph] = [build_video_graph(entry) for entry in bundle.iter_entries()]
    runner = EvaluationRunner(top_ks=top_ks)
    results = runner.run(gt_videos, predictions)
    return runner.summarize(results, top_ks=top_ks)
