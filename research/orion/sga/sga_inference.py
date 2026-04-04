"""
Scene Graph Anticipation Inference & Evaluation

This script runs the full SGA pipeline:
1. Load video and split into observed/future by fraction F
2. Run perception on observed frames to build scene graph
3. Use temporal model to predict future relations
4. Rank predictions by confidence
5. Evaluate against ground-truth future relations

This follows the PROPER SGA protocol:
- Predictions are ONLY for future frames (not observed)
- Evaluation compares future predictions to future GT
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
from collections import defaultdict

import numpy as np
import torch

from .temporal_model import TemporalSGAModel, TemporalSGAConfig, load_pretrained
from .ag_dataset import AG_OBJECT_CLASSES, AG_ALL_PREDICATES, AG_OBJECT_TO_IDX, AG_PREDICATE_TO_IDX
from .loader import AGDataBundle, AGVideo, AGRelation, load_action_genome

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class FuturePrediction:
    """A single predicted future relation."""
    subject_class: str
    predicate: str
    object_class: str
    confidence: float
    future_frame_idx: int  # Which future frame (0 = first future frame)
    
    def as_triplet(self) -> Tuple[str, str, str]:
        return (self.subject_class, self.predicate, self.object_class)


@dataclass
class SGAResult:
    """Result of SGA inference for a single video."""
    video_id: str
    input_fraction: float
    
    # Split info
    num_observed_frames: int
    num_future_frames: int
    
    # Predictions (sorted by confidence)
    predictions: List[FuturePrediction]
    
    # Ground truth future relations
    gt_future_relations: Set[Tuple[str, str, str]]
    
    def get_top_k_predictions(self, k: int) -> List[FuturePrediction]:
        """Get top-k predictions by confidence."""
        return self.predictions[:k]
    
    def get_unique_predicted_triplets(self) -> Set[Tuple[str, str, str]]:
        """Get unique predicted triplets."""
        return {p.as_triplet() for p in self.predictions}


@dataclass
class SGAEvaluation:
    """Evaluation metrics for SGA."""
    input_fraction: float
    num_videos: int
    
    # Aggregate metrics
    recall_at_k: Dict[int, float]      # R@K for K in [10, 20, 50, 100]
    mean_recall_at_k: Dict[int, float]  # mR@K for same K values
    
    # Per-predicate breakdown
    per_predicate_recall: Dict[str, Dict[int, float]]
    
    # Statistics
    total_gt_relations: int
    total_predictions: int
    avg_predictions_per_video: float
    
    def summary(self) -> str:
        """Human-readable summary."""
        lines = [
            f"SGA Evaluation (F={self.input_fraction})",
            f"  Videos: {self.num_videos}",
            f"  Total GT relations: {self.total_gt_relations}",
            f"  Total predictions: {self.total_predictions}",
            "",
            "  Metrics:",
        ]
        
        for k in sorted(self.recall_at_k.keys()):
            r = self.recall_at_k[k]
            mr = self.mean_recall_at_k.get(k, 0)
            lines.append(f"    R@{k}: {r:.2f}%  mR@{k}: {mr:.2f}%")
        
        return "\n".join(lines)


# ============================================================================
# SGA INFERENCE ENGINE
# ============================================================================

class SGAInferenceEngine:
    """
    Run SGA inference on videos.
    
    Pipeline:
    1. Split video into observed/future by fraction F
    2. Encode observed frames
    3. Predict future relations with temporal model
    4. Return ranked predictions
    """
    
    def __init__(
        self,
        model: TemporalSGAModel,
        device: str = "auto",
    ):
        if device == "auto":
            if torch.cuda.is_available():
                device = "cuda"
            elif torch.backends.mps.is_available():
                device = "mps"
            else:
                device = "cpu"
        
        self.device = device
        self.model = model.to(device)
        self.model.eval()
        
        # Index mappings
        self.idx_to_object = AG_OBJECT_CLASSES
        self.idx_to_predicate = AG_ALL_PREDICATES
    
    @torch.no_grad()
    def predict(
        self,
        observed_class_ids: torch.Tensor,
        observed_bboxes: torch.Tensor,
        observed_mask: torch.Tensor = None,
        num_future_frames: int = 4,
        top_k: int = 100,
        confidence_threshold: float = 0.1,
    ) -> List[FuturePrediction]:
        """
        Predict future relations from observed frames.
        
        Args:
            observed_class_ids: (num_frames, num_objects) - class indices
            observed_bboxes: (num_frames, num_objects, 4) - normalized bboxes
            observed_mask: (num_frames, num_objects) - valid objects mask
            num_future_frames: How many future frames to predict
            top_k: Return top-k predictions
            confidence_threshold: Minimum confidence to include
            
        Returns:
            List of FuturePrediction sorted by confidence (descending)
        """
        # Add batch dimension
        class_ids = observed_class_ids.unsqueeze(0).to(self.device)
        bboxes = observed_bboxes.unsqueeze(0).to(self.device)
        
        if observed_mask is not None:
            object_mask = observed_mask.unsqueeze(0).to(self.device)
        else:
            object_mask = (class_ids > 0)  # Assume 0 is background/padding
        
        frame_mask = torch.ones(1, class_ids.size(1), dtype=torch.bool, device=self.device)
        
        # Forward pass
        outputs = self.model(
            class_ids=class_ids,
            bboxes=bboxes,
            object_mask=object_mask,
            frame_mask=frame_mask,
            num_future_frames=num_future_frames,
        )
        
        pred_logits = outputs['predicate_logits']  # (1, num_future, num_pairs, num_preds)
        exist_logits = outputs['existence_logits']  # (1, num_future, num_pairs, 1)
        
        # Convert to probabilities
        pred_probs = torch.softmax(pred_logits, dim=-1)
        exist_probs = torch.sigmoid(exist_logits)
        
        # Get number of objects
        num_objects = class_ids.size(2)
        
        # Generate predictions
        predictions = []
        
        pair_idx = 0
        for i in range(num_objects):
            for j in range(num_objects):
                if i == j:
                    continue
                
                for f in range(num_future_frames):
                    # Existence probability
                    exist_prob = exist_probs[0, f, pair_idx, 0].item()
                    
                    # Predicate probabilities
                    for pred_idx in range(len(self.idx_to_predicate)):
                        pred_prob = pred_probs[0, f, pair_idx, pred_idx].item()
                        
                        # Combined confidence
                        confidence = exist_prob * pred_prob
                        
                        if confidence < confidence_threshold:
                            continue
                        
                        # Get class names
                        subj_class_idx = class_ids[0, -1, i].item()  # From last observed frame
                        obj_class_idx = class_ids[0, -1, j].item()
                        
                        if subj_class_idx >= len(self.idx_to_object) or obj_class_idx >= len(self.idx_to_object):
                            continue
                        
                        subj_class = self.idx_to_object[subj_class_idx]
                        obj_class = self.idx_to_object[obj_class_idx]
                        predicate = self.idx_to_predicate[pred_idx]
                        
                        predictions.append(FuturePrediction(
                            subject_class=subj_class,
                            predicate=predicate,
                            object_class=obj_class,
                            confidence=confidence,
                            future_frame_idx=f,
                        ))
                
                pair_idx += 1
        
        # Sort by confidence
        predictions.sort(key=lambda p: -p.confidence)
        
        # Deduplicate (keep highest confidence for each unique triplet)
        seen = set()
        unique_predictions = []
        for pred in predictions:
            triplet = pred.as_triplet()
            if triplet not in seen:
                seen.add(triplet)
                unique_predictions.append(pred)
        
        return unique_predictions[:top_k]


# ============================================================================
# EVALUATION
# ============================================================================

def evaluate_sga(
    results: List[SGAResult],
    k_values: List[int] = [10, 20, 50, 100],
) -> SGAEvaluation:
    """
    Evaluate SGA results across multiple videos.
    
    Args:
        results: List of SGAResult from inference
        k_values: K values for R@K metrics
        
    Returns:
        SGAEvaluation with aggregate metrics
    """
    if not results:
        raise ValueError("No results to evaluate")
    
    input_fraction = results[0].input_fraction
    
    # Aggregate statistics
    total_gt = 0
    total_preds = 0
    
    # For R@K computation
    all_gt_triplets = set()
    all_pred_triplets_with_conf = []  # (triplet, confidence)
    
    # Per-predicate tracking
    per_pred_gt = defaultdict(set)      # predicate -> set of (subj, obj) tuples
    per_pred_hits = defaultdict(lambda: defaultdict(int))  # predicate -> k -> hits
    
    for result in results:
        total_gt += len(result.gt_future_relations)
        total_preds += len(result.predictions)
        
        # Add GT triplets
        for triplet in result.gt_future_relations:
            all_gt_triplets.add(triplet)
            predicate = triplet[1]
            per_pred_gt[predicate].add((triplet[0], triplet[2]))
        
        # Add predictions with confidence
        for pred in result.predictions:
            triplet = pred.as_triplet()
            all_pred_triplets_with_conf.append((triplet, pred.confidence))
    
    # Sort all predictions by confidence
    all_pred_triplets_with_conf.sort(key=lambda x: -x[1])
    
    # Compute R@K
    recall_at_k = {}
    for k in k_values:
        top_k_triplets = {t for t, c in all_pred_triplets_with_conf[:k]}
        hits = len(top_k_triplets & all_gt_triplets)
        recall = (hits / len(all_gt_triplets) * 100) if all_gt_triplets else 0
        recall_at_k[k] = recall
    
    # Compute mR@K (per-predicate average)
    mean_recall_at_k = {}
    per_predicate_recall = defaultdict(dict)
    
    for k in k_values:
        top_k_preds = all_pred_triplets_with_conf[:k]
        
        per_pred_recall_k = []
        
        for predicate in AG_ALL_PREDICATES:
            gt_set = per_pred_gt.get(predicate, set())
            if not gt_set:
                continue
            
            # Count hits for this predicate
            hits = 0
            for triplet, conf in top_k_preds:
                if triplet[1] == predicate and (triplet[0], triplet[2]) in gt_set:
                    hits += 1
            
            recall = hits / len(gt_set)
            per_pred_recall_k.append(recall)
            per_predicate_recall[predicate][k] = recall * 100
        
        mean_recall = sum(per_pred_recall_k) / len(per_pred_recall_k) if per_pred_recall_k else 0
        mean_recall_at_k[k] = mean_recall * 100
    
    return SGAEvaluation(
        input_fraction=input_fraction,
        num_videos=len(results),
        recall_at_k=recall_at_k,
        mean_recall_at_k=mean_recall_at_k,
        per_predicate_recall=dict(per_predicate_recall),
        total_gt_relations=total_gt,
        total_predictions=total_preds,
        avg_predictions_per_video=total_preds / len(results) if results else 0,
    )


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def run_sga_on_video(
    model: TemporalSGAModel,
    video: AGVideo,
    input_fraction: float = 0.5,
    device: str = "auto",
) -> SGAResult:
    """
    Run SGA on a single AG video.
    
    Args:
        model: Trained temporal SGA model
        video: Action Genome video with annotations
        input_fraction: F - fraction of frames to observe
        device: Device for inference
        
    Returns:
        SGAResult with predictions and GT
    """
    engine = SGAInferenceEngine(model, device)
    
    # Split video
    observed, future = video.split_by_fraction(input_fraction)
    
    # Get observed frame data
    observed_frames = observed.get_ordered_frames()
    
    if not observed_frames:
        return SGAResult(
            video_id=video.video_id,
            input_fraction=input_fraction,
            num_observed_frames=0,
            num_future_frames=0,
            predictions=[],
            gt_future_relations=set(),
        )
    
    # Collect all objects
    all_objects = {}
    for frame in observed_frames:
        for obj_id, obj in frame.objects.items():
            all_objects[obj_id] = obj
    
    object_ids = sorted(all_objects.keys())
    object_id_to_idx = {oid: idx for idx, oid in enumerate(object_ids)}
    
    num_objects = len(object_ids)
    num_frames = len(observed_frames)
    
    # Build tensors
    class_ids = torch.zeros(num_frames, num_objects, dtype=torch.long)
    bboxes = torch.zeros(num_frames, num_objects, 4)
    mask = torch.zeros(num_frames, num_objects, dtype=torch.bool)
    
    for f_idx, frame in enumerate(observed_frames):
        for obj_id, obj in frame.objects.items():
            if obj_id not in object_id_to_idx:
                continue
            o_idx = object_id_to_idx[obj_id]
            
            class_id = AG_OBJECT_TO_IDX.get(obj.category, 0)
            class_ids[f_idx, o_idx] = class_id
            
            if obj.bbox:
                bboxes[f_idx, o_idx] = torch.tensor(obj.bbox[:4])
            
            mask[f_idx, o_idx] = True
    
    # Predict future
    future_frames = future.get_ordered_frames()
    num_future = len(future_frames)
    
    predictions = engine.predict(
        observed_class_ids=class_ids,
        observed_bboxes=bboxes,
        observed_mask=mask,
        num_future_frames=max(1, num_future),
        top_k=100,
    )
    
    # Get GT future relations
    gt_future = set()
    for frame in future_frames:
        for rel in frame.relations:
            triplet = rel.as_triplet()
            gt_future.add(triplet)
    
    return SGAResult(
        video_id=video.video_id,
        input_fraction=input_fraction,
        num_observed_frames=num_frames,
        num_future_frames=num_future,
        predictions=predictions,
        gt_future_relations=gt_future,
    )


# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="SGA Inference and Evaluation")
    
    parser.add_argument(
        '--model_path',
        type=str,
        required=True,
        help='Path to trained model checkpoint'
    )
    parser.add_argument(
        '--annotation_path',
        type=str,
        default='data/ag_ground_truth_full.json',
        help='Path to AG annotations'
    )
    parser.add_argument(
        '--input_fraction',
        type=float,
        default=0.5,
        help='Fraction of frames to observe (F)'
    )
    parser.add_argument(
        '--max_videos',
        type=int,
        default=None,
        help='Maximum videos to evaluate (for testing)'
    )
    parser.add_argument(
        '--output_path',
        type=str,
        default='sga_results.json',
        help='Output path for results'
    )
    
    args = parser.parse_args()
    
    # Load model
    logger.info(f"Loading model from {args.model_path}")
    model = load_pretrained(args.model_path)
    
    # Load data
    logger.info(f"Loading annotations from {args.annotation_path}")
    data = load_action_genome(args.annotation_path)
    
    # Run evaluation
    results = []
    videos = list(data.iter_videos())
    
    if args.max_videos:
        videos = videos[:args.max_videos]
    
    logger.info(f"Running SGA on {len(videos)} videos (F={args.input_fraction})")
    
    for video in videos:
        try:
            result = run_sga_on_video(
                model=model,
                video=video,
                input_fraction=args.input_fraction,
            )
            results.append(result)
        except Exception as e:
            logger.warning(f"Error on video {video.video_id}: {e}")
            continue
    
    # Evaluate
    evaluation = evaluate_sga(results)
    
    # Print results
    print("\n" + "="*60)
    print(evaluation.summary())
    print("="*60)
    
    # Save results
    output = {
        'input_fraction': args.input_fraction,
        'num_videos': len(results),
        'recall_at_k': evaluation.recall_at_k,
        'mean_recall_at_k': evaluation.mean_recall_at_k,
        'per_predicate_recall': evaluation.per_predicate_recall,
        'total_gt_relations': evaluation.total_gt_relations,
        'total_predictions': evaluation.total_predictions,
    }
    
    with open(args.output_path, 'w') as f:
        json.dump(output, f, indent=2)
    
    logger.info(f"Results saved to {args.output_path}")


if __name__ == "__main__":
    main()
