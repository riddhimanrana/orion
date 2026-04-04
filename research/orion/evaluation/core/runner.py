"""Evaluation runner utilities."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

from .metrics import MetricSummary, compute_mean_recall_at_k, compute_recall_at_k
from .types import FrameGraph, RelationInstance, VideoGraph


@dataclass
class EvaluationResult:
    video_id: str
    metrics: MetricSummary
    num_frames: int

    def to_dict(self) -> Dict[str, object]:
        return {
            "video_id": self.video_id,
            "num_frames": self.num_frames,
            **self.metrics.to_dict(),
        }


def load_predictions_jsonl(path: str | Path) -> Dict[str, VideoGraph]:
    """Load predictions from JSONL into VideoGraph objects.

    Expected JSONL schema per line:
    {
      "video_id": "vid123",
      "frame_index": 17,
      "relations": [
         {"subject_id": 0, "predicate": "on", "object_id": 1, "score": 0.83},
         ...
      ]
    }
    """

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Prediction file not found: {path}")
    videos: Dict[str, VideoGraph] = {}
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            record = json.loads(line)
            video_id = str(record["video_id"])
            frame_index = int(record["frame_index"])
            relations = [
                RelationInstance(
                    subject_id=int(rel["subject_id"]),
                    predicate=str(rel["predicate"]),
                    object_id=int(rel["object_id"]),
                    score=float(rel.get("score", 1.0)),
                )
                for rel in record.get("relations", [])
            ]
            video = videos.setdefault(video_id, VideoGraph(video_id=video_id))
            frame = video.frames.get(frame_index)
            if frame is None:
                frame = FrameGraph(frame_index=frame_index)
                video.frames[frame_index] = frame
            frame.relations.extend(relations)
    return videos


class EvaluationRunner:
    """Shared evaluator for computing R@K / mR@K from VideoGraph pairs."""

    def __init__(self, top_ks: Sequence[int]) -> None:
        self.top_ks = list(top_ks)

    def evaluate_video(self, gt: VideoGraph, pred: VideoGraph) -> EvaluationResult:
        recall_totals = {k: 0.0 for k in self.top_ks}
        mean_recall_totals = {k: 0.0 for k in self.top_ks}
        frame_count = 0

        gt_frames = gt.ordered_frames()
        if pred.frames:
            common_indices = sorted(set(gt.frames.keys()) & set(pred.frames.keys()))
            gt_frames = [gt.frames[idx] for idx in common_indices]

        for frame in gt_frames:
            pred_frame = pred.frames.get(frame.frame_index)
            predictions = pred_frame.relations if pred_frame else []
            for k in self.top_ks:
                recall_totals[k] += compute_recall_at_k(predictions, frame.relations, k)
                mean_recall_totals[k] += compute_mean_recall_at_k(predictions, frame.relations, k)
            frame_count += 1

        if frame_count == 0:
            metrics = MetricSummary(recall_at_k=recall_totals, mean_recall_at_k=mean_recall_totals)
        else:
            metrics = MetricSummary(
                recall_at_k={k: v / frame_count for k, v in recall_totals.items()},
                mean_recall_at_k={k: v / frame_count for k, v in mean_recall_totals.items()},
            )
        return EvaluationResult(video_id=gt.video_id, metrics=metrics, num_frames=frame_count)

    def run(self, gt_videos: Iterable[VideoGraph], pred_videos: Dict[str, VideoGraph]) -> List[EvaluationResult]:
        results: List[EvaluationResult] = []
        for gt in gt_videos:
            pred = pred_videos.get(gt.video_id, VideoGraph(video_id=gt.video_id))
            results.append(self.evaluate_video(gt, pred))
        return results

    @staticmethod
    def summarize(results: Sequence[EvaluationResult], top_ks: Sequence[int]) -> MetricSummary:
        if not results:
            return MetricSummary(recall_at_k={k: 0.0 for k in top_ks}, mean_recall_at_k={k: 0.0 for k in top_ks})
        recall_totals = {k: 0.0 for k in top_ks}
        mean_recall_totals = {k: 0.0 for k in top_ks}
        for result in results:
            for k in top_ks:
                recall_totals[k] += result.metrics.recall_at_k[k]
                mean_recall_totals[k] += result.metrics.mean_recall_at_k[k]
        count = len(results)
        return MetricSummary(
            recall_at_k={k: v / count for k, v in recall_totals.items()},
            mean_recall_at_k={k: v / count for k, v in mean_recall_totals.items()},
        )
