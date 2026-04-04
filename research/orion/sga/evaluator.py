"""
Part 5: SGA Evaluation Metrics

This module computes standard Scene Graph Anticipation metrics:
- R@K (Recall at K): % of GT triplets found in top-K predictions
- mR@K (Mean Recall at K): Average recall per predicate class

Evaluation Protocol:
1. Given predictions for future frames
2. Compare against ground truth future relations
3. A prediction matches if (subject_class, predicate, object_class) matches GT
4. Optionally: require bbox IoU > threshold for matching

Supports multiple input fractions (F) for comprehensive evaluation.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple
from collections import defaultdict

import numpy as np

from .loader import AGVideo, AGRelation, AGDataBundle, load_action_genome
from .anticipator import AnticipationResult, AnticipatedRelation

logger = logging.getLogger(__name__)


# ============================================================================
# METRIC DATA STRUCTURES
# ============================================================================

@dataclass
class SGAMetrics:
    """Container for SGA evaluation metrics."""
    # Recall@K for each K value
    recall_at_k: Dict[int, float] = field(default_factory=dict)
    # Mean Recall@K (per-predicate average)
    mean_recall_at_k: Dict[int, float] = field(default_factory=dict)
    # Per-predicate recall breakdown
    per_predicate_recall: Dict[str, Dict[int, float]] = field(default_factory=dict)
    # Additional statistics
    num_gt_triplets: int = 0
    num_predictions: int = 0
    num_matched: Dict[int, int] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'R@K': {f'R@{k}': v for k, v in self.recall_at_k.items()},
            'mR@K': {f'mR@{k}': v for k, v in self.mean_recall_at_k.items()},
            'per_predicate': self.per_predicate_recall,
            'num_gt_triplets': self.num_gt_triplets,
            'num_predictions': self.num_predictions,
            'num_matched': self.num_matched,
        }
    
    def summary_string(self) -> str:
        """Human-readable summary."""
        lines = []
        lines.append(f"GT Triplets: {self.num_gt_triplets}, Predictions: {self.num_predictions}")
        
        for k in sorted(self.recall_at_k.keys()):
            r = self.recall_at_k[k]
            mr = self.mean_recall_at_k.get(k, 0)
            matched = self.num_matched.get(k, 0)
            lines.append(f"  R@{k}: {r:.2f}%  mR@{k}: {mr:.2f}%  (matched: {matched})")
        
        return "\n".join(lines)


@dataclass
class VideoEvalResult:
    """Evaluation result for a single video."""
    video_id: str
    fraction: float
    metrics: SGAMetrics
    gt_triplets: Set[Tuple[str, str, str]]
    pred_triplets: List[Tuple[str, str, str, float]]  # With confidence


@dataclass
class SGAEvalSummary:
    """Summary across multiple videos and fractions."""
    fraction: float
    num_videos: int
    aggregate_metrics: SGAMetrics
    per_video_metrics: Dict[str, SGAMetrics] = field(default_factory=dict)


# ============================================================================
# TRIPLET MATCHING
# ============================================================================

def normalize_class(cls: str) -> str:
    """Normalize class name for matching."""
    cls = cls.lower().strip().replace('_', ' ')
    
    # Common mappings
    mappings = {
        'adult': 'person', 'man': 'person', 'woman': 'person',
        'child': 'person', 'baby': 'person', 'boy': 'person', 'girl': 'person',
        'couch': 'sofa', 'settee': 'sofa',
        'cellphone': 'phone', 'mobile': 'phone',
        'tv': 'television', 'monitor': 'television',
        'carpet': 'floor', 'rug': 'floor',
    }
    
    return mappings.get(cls, cls)


def normalize_predicate(pred: str) -> str:
    """Normalize predicate for matching."""
    pred = pred.lower().strip().replace('_', ' ')
    
    # Ensure consistency with AG predicates
    mappings = {
        'in front of': 'in_front_of',
        'on the side of': 'on_the_side_of',
        'lying on': 'lying_on',
        'sitting on': 'sitting_on',
        'standing on': 'standing_on',
        'covered by': 'covered_by',
        'not contacting': 'not_contacting',
    }
    
    # Convert spaces to underscores for AG format
    normalized = mappings.get(pred, pred.replace(' ', '_'))
    return normalized


def triplet_matches(
    pred_triplet: Tuple[str, str, str],
    gt_triplet: Tuple[str, str, str],
    normalize: bool = True,
) -> bool:
    """Check if predicted triplet matches ground truth."""
    if normalize:
        pred_subj = normalize_class(pred_triplet[0])
        pred_pred = normalize_predicate(pred_triplet[1])
        pred_obj = normalize_class(pred_triplet[2])
        
        gt_subj = normalize_class(gt_triplet[0])
        gt_pred = normalize_predicate(gt_triplet[1])
        gt_obj = normalize_class(gt_triplet[2])
    else:
        pred_subj, pred_pred, pred_obj = pred_triplet
        gt_subj, gt_pred, gt_obj = gt_triplet
    
    return pred_subj == gt_subj and pred_pred == gt_pred and pred_obj == gt_obj


# ============================================================================
# MAIN EVALUATOR
# ============================================================================

class SGAEvaluator:
    """
    Evaluate Scene Graph Anticipation predictions.
    
    Computes R@K and mR@K comparing predicted future relations
    against ground truth future relations.
    """
    
    def __init__(
        self,
        top_ks: Sequence[int] = (10, 20, 50, 100),
        normalize_names: bool = True,
    ):
        """
        Args:
            top_ks: K values for R@K computation
            normalize_names: Whether to normalize class/predicate names
        """
        self.top_ks = list(top_ks)
        self.normalize = normalize_names
    
    def evaluate_video(
        self,
        predictions: List[AnticipatedRelation],
        gt_future: AGVideo,
        fraction: float = 0.5,
    ) -> VideoEvalResult:
        """
        Evaluate predictions for a single video.
        
        Args:
            predictions: Predicted relations for future frames
            gt_future: Ground truth future video (future portion only)
            fraction: Observation fraction (for reporting)
            
        Returns:
            VideoEvalResult with metrics
        """
        # Collect ground truth triplets
        gt_triplets: Set[Tuple[str, str, str]] = set()
        gt_by_predicate: Dict[str, Set[Tuple[str, str, str]]] = defaultdict(set)
        
        for rel in gt_future.get_all_relations():
            triplet = rel.as_triplet()
            if self.normalize:
                triplet = (
                    normalize_class(triplet[0]),
                    normalize_predicate(triplet[1]),
                    normalize_class(triplet[2]),
                )
            gt_triplets.add(triplet)
            gt_by_predicate[triplet[1]].add(triplet)
        
        # Sort predictions by confidence
        sorted_preds = sorted(predictions, key=lambda r: -r.confidence)
        
        # Convert to triplets with confidence
        pred_triplets = []
        for p in sorted_preds:
            triplet = p.as_triplet()
            if self.normalize:
                triplet = (
                    normalize_class(triplet[0]),
                    normalize_predicate(triplet[1]),
                    normalize_class(triplet[2]),
                )
            pred_triplets.append((*triplet, p.confidence))
        
        # Compute metrics
        metrics = self._compute_metrics(pred_triplets, gt_triplets, gt_by_predicate)
        
        return VideoEvalResult(
            video_id=gt_future.video_id,
            fraction=fraction,
            metrics=metrics,
            gt_triplets=gt_triplets,
            pred_triplets=pred_triplets,
        )
    
    def evaluate_from_ag_relations(
        self,
        predictions: List[AGRelation],
        gt_future: AGVideo,
        fraction: float = 0.5,
    ) -> VideoEvalResult:
        """
        Evaluate using AGRelation format predictions.
        
        Args:
            predictions: Predicted AGRelations
            gt_future: Ground truth future video
            fraction: Observation fraction
            
        Returns:
            VideoEvalResult with metrics
        """
        # Convert AGRelations to AnticipatedRelations
        anticipated = []
        for i, rel in enumerate(predictions):
            anticipated.append(AnticipatedRelation(
                subject_id=i,
                subject_label=rel.subject.category,
                predicate=rel.predicate,
                object_id=i + 1000,
                object_label=rel.object.category,
                confidence=rel.confidence,
                predicted_frame=0,
                source='external',
            ))
        
        return self.evaluate_video(anticipated, gt_future, fraction)
    
    def _compute_metrics(
        self,
        pred_triplets: List[Tuple[str, str, str, float]],
        gt_triplets: Set[Tuple[str, str, str]],
        gt_by_predicate: Dict[str, Set[Tuple[str, str, str]]],
    ) -> SGAMetrics:
        """Compute R@K and mR@K metrics."""
        metrics = SGAMetrics(
            num_gt_triplets=len(gt_triplets),
            num_predictions=len(pred_triplets),
        )
        
        if not gt_triplets:
            # No ground truth - return zeros
            for k in self.top_ks:
                metrics.recall_at_k[k] = 0.0
                metrics.mean_recall_at_k[k] = 0.0
                metrics.num_matched[k] = 0
            return metrics
        
        # Compute R@K
        for k in self.top_ks:
            top_k = set((t[0], t[1], t[2]) for t in pred_triplets[:k])
            matched = gt_triplets.intersection(top_k)
            
            metrics.num_matched[k] = len(matched)
            metrics.recall_at_k[k] = len(matched) / len(gt_triplets) * 100
        
        # Compute mR@K (mean per-predicate recall)
        for k in self.top_ks:
            top_k = set((t[0], t[1], t[2]) for t in pred_triplets[:k])
            
            predicate_recalls = []
            for predicate, gt_rels in gt_by_predicate.items():
                # Filter top_k to this predicate
                pred_rels = {t for t in top_k if t[1] == predicate}
                matched = gt_rels.intersection(pred_rels)
                
                recall = len(matched) / len(gt_rels) * 100 if gt_rels else 0
                predicate_recalls.append(recall)
                
                # Store per-predicate recall
                if predicate not in metrics.per_predicate_recall:
                    metrics.per_predicate_recall[predicate] = {}
                metrics.per_predicate_recall[predicate][k] = recall
            
            metrics.mean_recall_at_k[k] = (
                sum(predicate_recalls) / len(predicate_recalls)
                if predicate_recalls else 0
            )
        
        return metrics
    
    def evaluate_batch(
        self,
        predictions_by_video: Dict[str, List[AnticipatedRelation]],
        gt_futures_by_video: Dict[str, AGVideo],
        fraction: float = 0.5,
    ) -> SGAEvalSummary:
        """
        Evaluate multiple videos and aggregate metrics.
        
        Args:
            predictions_by_video: Dict of video_id -> predicted relations
            gt_futures_by_video: Dict of video_id -> GT future video
            fraction: Observation fraction
            
        Returns:
            SGAEvalSummary with aggregated metrics
        """
        per_video_metrics = {}
        
        # Accumulators for aggregation
        all_gt_triplets: Set[Tuple[str, str, str]] = set()
        all_pred_triplets: List[Tuple[str, str, str, float]] = []
        all_gt_by_predicate: Dict[str, Set[Tuple[str, str, str]]] = defaultdict(set)
        
        for video_id, gt_video in gt_futures_by_video.items():
            preds = predictions_by_video.get(video_id, [])
            
            result = self.evaluate_video(preds, gt_video, fraction)
            per_video_metrics[video_id] = result.metrics
            
            # Accumulate for macro metrics
            all_gt_triplets.update(result.gt_triplets)
            all_pred_triplets.extend(result.pred_triplets)
            
            for triplet in result.gt_triplets:
                all_gt_by_predicate[triplet[1]].add(triplet)
        
        # Sort all predictions by confidence
        all_pred_triplets.sort(key=lambda x: -x[3])
        
        # Compute aggregate metrics
        aggregate_metrics = self._compute_metrics(
            all_pred_triplets, all_gt_triplets, all_gt_by_predicate
        )
        
        return SGAEvalSummary(
            fraction=fraction,
            num_videos=len(gt_futures_by_video),
            aggregate_metrics=aggregate_metrics,
            per_video_metrics=per_video_metrics,
        )


# ============================================================================
# FULL SGA EVALUATION PIPELINE
# ============================================================================

def evaluate_sga_on_action_genome(
    predictions_by_video: Dict[str, List[AnticipatedRelation]],
    ag_data_path: str,
    fractions: Sequence[float] = (0.3, 0.5, 0.7, 0.9),
    top_ks: Sequence[int] = (10, 20, 50, 100),
    max_videos: Optional[int] = None,
) -> Dict[float, SGAEvalSummary]:
    """
    Full SGA evaluation on Action Genome dataset.
    
    Args:
        predictions_by_video: Dict of video_id -> predictions
        ag_data_path: Path to AG ground truth data
        fractions: Input fractions to evaluate
        top_ks: K values for R@K
        max_videos: Limit number of videos
        
    Returns:
        Dict of fraction -> SGAEvalSummary
    """
    logger.info(f"Loading Action Genome data from {ag_data_path}")
    bundle = load_action_genome(ag_data_path, max_videos=max_videos)
    
    evaluator = SGAEvaluator(top_ks=top_ks)
    results = {}
    
    for fraction in fractions:
        logger.info(f"\n=== Evaluating at fraction F={fraction} ===")
        
        # Split each video by fraction
        gt_futures = {}
        for video_id, video in bundle.videos.items():
            if video_id not in predictions_by_video:
                continue
            
            observed, future = video.split_by_fraction(fraction)
            if future.num_frames() > 0:
                gt_futures[video_id] = future
        
        logger.info(f"Evaluating {len(gt_futures)} videos")
        
        summary = evaluator.evaluate_batch(
            predictions_by_video=predictions_by_video,
            gt_futures_by_video=gt_futures,
            fraction=fraction,
        )
        
        results[fraction] = summary
        
        # Log summary
        logger.info(f"F={fraction}: {summary.aggregate_metrics.summary_string()}")
    
    return results


def print_sga_results_table(results: Dict[float, SGAEvalSummary]):
    """Print results in a formatted table."""
    print("\n" + "=" * 70)
    print("           SCENE GRAPH ANTICIPATION (SGA) RESULTS")
    print("=" * 70)
    
    # Header
    fractions = sorted(results.keys())
    ks = sorted(results[fractions[0]].aggregate_metrics.recall_at_k.keys())
    
    print(f"\n{'Fraction':<10}", end="")
    for k in ks:
        print(f"{'R@' + str(k):<10}{'mR@' + str(k):<10}", end="")
    print()
    print("-" * 70)
    
    # Data rows
    for f in fractions:
        metrics = results[f].aggregate_metrics
        print(f"F={f:<7}", end="")
        for k in ks:
            r = metrics.recall_at_k.get(k, 0)
            mr = metrics.mean_recall_at_k.get(k, 0)
            print(f"{r:>8.2f}% {mr:>8.2f}%", end="")
        print()
    
    print("=" * 70)
    print(f"\nTotal videos evaluated: {results[fractions[0]].num_videos}")
    print("=" * 70 + "\n")


# ============================================================================
# CLI TESTING
# ============================================================================

if __name__ == "__main__":
    import argparse
    from .loader import load_action_genome
    from .anticipator import SceneGraphAnticipator, AnticipationResult
    from .detector import SGADetectionPipeline, TrackingResult
    from .observed_sgg import ObservedSceneGraphGenerator
    
    parser = argparse.ArgumentParser(description="Test SGA Evaluation")
    parser.add_argument("--data", default="data/ag_ground_truth_full.json", help="AG data path")
    parser.add_argument("--max-videos", type=int, default=5, help="Max videos")
    parser.add_argument("--fraction", type=float, default=0.5, help="Input fraction")
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    print(f"\n{'='*60}")
    print("PART 5: SGA EVALUATION TEST")
    print(f"{'='*60}\n")
    
    # Load AG data
    print("--- Loading Action Genome Data ---")
    bundle = load_action_genome(args.data, max_videos=args.max_videos)
    print(f"  Loaded {bundle.num_videos()} videos")
    
    # For testing, we'll use GT relations as "predictions" to verify metrics
    # In real usage, predictions come from the anticipator
    print("\n--- Testing Evaluation with GT as Predictions ---")
    
    evaluator = SGAEvaluator(top_ks=[10, 20, 50])
    
    for video_id, video in list(bundle.videos.items())[:3]:
        # Split video
        observed, future = video.split_by_fraction(args.fraction)
        
        if future.num_frames() == 0:
            continue
        
        # Use GT future relations as predictions (should get 100% recall)
        gt_relations = future.get_all_relations()
        predictions = [
            AnticipatedRelation(
                subject_id=i,
                subject_label=rel.subject.category,
                predicate=rel.predicate,
                object_id=i + 1000,
                object_label=rel.object.category,
                confidence=1.0 - i * 0.001,  # Decreasing confidence
                predicted_frame=0,
                source='gt_test',
            )
            for i, rel in enumerate(gt_relations)
        ]
        
        result = evaluator.evaluate_video(predictions, future, args.fraction)
        
        print(f"\n  Video: {video_id}")
        print(f"    GT triplets: {len(result.gt_triplets)}")
        print(f"    Predictions: {len(predictions)}")
        print(f"    {result.metrics.summary_string()}")
    
    # Test with partial predictions
    print("\n--- Testing with Partial Predictions ---")
    
    video = list(bundle.videos.values())[0]
    observed, future = video.split_by_fraction(args.fraction)
    gt_relations = future.get_all_relations()
    
    # Only predict half the relations
    half = len(gt_relations) // 2
    predictions = [
        AnticipatedRelation(
            subject_id=i,
            subject_label=rel.subject.category,
            predicate=rel.predicate,
            object_id=i + 1000,
            object_label=rel.object.category,
            confidence=1.0 - i * 0.01,
            predicted_frame=0,
            source='partial_test',
        )
        for i, rel in enumerate(gt_relations[:half])
    ]
    
    result = evaluator.evaluate_video(predictions, future, args.fraction)
    print(f"  Half predictions test:")
    print(f"    GT: {len(result.gt_triplets)}, Pred: {len(predictions)}")
    print(f"    {result.metrics.summary_string()}")
    
    # Per-predicate breakdown
    print(f"\n  Per-predicate R@50:")
    for pred, recalls in result.metrics.per_predicate_recall.items():
        if 50 in recalls:
            print(f"    {pred}: {recalls[50]:.1f}%")
    
    print(f"\n{'='*60}")
    print("PART 5 COMPLETE ✓")
    print(f"{'='*60}\n")

