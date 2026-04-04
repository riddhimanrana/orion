"""Action Genome SGA evaluator (fraction-based)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence

from ..core.metrics import MetricSummary
from ..core.runner import EvaluationRunner
from ..core.types import VideoGraph


@dataclass
class SGAFractionResult:
    fraction: float
    metrics: MetricSummary


def evaluate_sga(
    gt_graphs: Dict[str, VideoGraph],
    pred_graphs: Dict[str, VideoGraph],
    top_ks: Sequence[int],
    fraction: float,
) -> SGAFractionResult:
    runner = EvaluationRunner(top_ks=top_ks)
    clipped_gt: List[VideoGraph] = []

    for video_id, gt in gt_graphs.items():
        frames = gt.ordered_frames()
        if len(frames) < 2:
            continue
        obs_len = max(1, int(len(frames) * fraction))
        obs_len = min(obs_len, len(frames) - 1)
        future_frames = frames[obs_len:]
        future_graph = VideoGraph(video_id=video_id)
        future_graph.frames = {frame.frame_index: frame for frame in future_frames}
        clipped_gt.append(future_graph)

    results = runner.run(clipped_gt, pred_graphs)
    summary = runner.summarize(results, top_ks=top_ks)
    return SGAFractionResult(fraction=fraction, metrics=summary)
