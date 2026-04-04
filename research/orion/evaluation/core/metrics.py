"""Metric utilities for scene graph evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Tuple

from .types import BBox, RelationInstance


def bbox_iou_xyxy(a: BBox, b: BBox) -> float:
    inter_x1 = max(a.x1, b.x1)
    inter_y1 = max(a.y1, b.y1)
    inter_x2 = min(a.x2, b.x2)
    inter_y2 = min(a.y2, b.y2)
    inter_w = max(0.0, inter_x2 - inter_x1)
    inter_h = max(0.0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h
    if inter_area == 0:
        return 0.0
    area_a = max(0.0, a.x2 - a.x1) * max(0.0, a.y2 - a.y1)
    area_b = max(0.0, b.x2 - b.x1) * max(0.0, b.y2 - b.y1)
    union = area_a + area_b - inter_area
    return inter_area / union if union > 0 else 0.0


def match_relations(
    predictions: Sequence[RelationInstance],
    ground_truth: Sequence[RelationInstance],
) -> Tuple[int, int]:
    """Match relations by (subject_id, predicate, object_id)."""

    if not ground_truth:
        return 0, 0
    gt_set = {(rel.subject_id, rel.predicate, rel.object_id) for rel in ground_truth}
    pred_set = {(rel.subject_id, rel.predicate, rel.object_id) for rel in predictions}
    hits = len(gt_set.intersection(pred_set))
    return hits, len(gt_set)


def compute_recall_at_k(
    predictions: Sequence[RelationInstance],
    ground_truth: Sequence[RelationInstance],
    k: int,
) -> float:
    """Recall@K for a single frame."""

    if not ground_truth:
        return 0.0
    sorted_preds = sorted(predictions, key=lambda r: r.score, reverse=True)[:k]
    hits, total = match_relations(sorted_preds, ground_truth)
    return hits / total if total else 0.0


def compute_mean_recall_at_k(
    predictions: Sequence[RelationInstance],
    ground_truth: Sequence[RelationInstance],
    k: int,
) -> float:
    """Mean recall@K across predicate classes."""

    if not ground_truth:
        return 0.0
    per_predicate: Dict[str, List[RelationInstance]] = {}
    for rel in ground_truth:
        per_predicate.setdefault(rel.predicate, []).append(rel)

    sorted_preds = sorted(predictions, key=lambda r: r.score, reverse=True)[:k]
    predicate_recalls: List[float] = []
    for predicate, gt_rels in per_predicate.items():
        pred_rels = [rel for rel in sorted_preds if rel.predicate == predicate]
        hits, total = match_relations(pred_rels, gt_rels)
        predicate_recalls.append(hits / total if total else 0.0)
    return sum(predicate_recalls) / len(predicate_recalls) if predicate_recalls else 0.0


@dataclass
class MetricSummary:
    """Aggregated metrics across frames or videos."""

    recall_at_k: Dict[int, float]
    mean_recall_at_k: Dict[int, float]

    def to_dict(self) -> Dict[str, float]:
        output: Dict[str, float] = {}
        for k, value in self.recall_at_k.items():
            output[f"R@{k}"] = value
        for k, value in self.mean_recall_at_k.items():
            output[f"mR@{k}"] = value
        return output
