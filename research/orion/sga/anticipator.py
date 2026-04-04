"""
Part 4: Future Scene Graph Anticipation Model

This module predicts FUTURE scene graph relations from OBSERVED frames.
This is the core SGA task: given the first F% of a video, predict
what relationships will occur in the remaining (1-F)% of the video.

Anticipation Strategies:
1. Temporal extrapolation (trajectory-based)
2. Relation persistence (relations likely to continue)
3. Context-based prediction (common action sequences)
4. Motion-based prediction (velocity → future position)

The anticipator takes:
- Observed VideoSceneGraph (from Part 3)
- Tracked entities with motion features
And outputs:
- Predicted relations for future frames
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Sequence, Set
from collections import defaultdict
import math

import numpy as np

from .loader import AGRelation, AGObject, AGVideo, AGFrame
from .detector import TrackedEntity, TrackingResult
from .observed_sgg import (
    VideoSceneGraph, FrameSceneGraph, SceneGraphEdge, SceneGraphNode,
    AG_PREDICATES, SPATIAL_PREDICATES, CONTACT_PREDICATES,
)

logger = logging.getLogger(__name__)


# ============================================================================
# ANTICIPATION STRATEGIES
# ============================================================================

@dataclass
class AnticipatedRelation:
    """A predicted future relation."""
    subject_id: int
    subject_label: str
    predicate: str
    object_id: int
    object_label: str
    confidence: float
    predicted_frame: int  # Frame where this is predicted to occur
    source: str = "unknown"  # Which strategy generated this
    
    def as_triplet(self) -> Tuple[str, str, str]:
        """Return (subject_label, predicate, object_label)."""
        return (self.subject_label, self.predicate, self.object_label)
    
    def to_ag_relation(self) -> AGRelation:
        """Convert to AGRelation for evaluation."""
        return AGRelation(
            subject=AGObject(str(self.subject_id), self.subject_label),
            predicate=self.predicate,
            object=AGObject(str(self.object_id), self.object_label),
            confidence=self.confidence,
        )


@dataclass
class AnticipationResult:
    """Result of future anticipation."""
    video_id: str
    observed_frames: List[int]
    future_frames: List[int]
    predictions: List[AnticipatedRelation]
    
    def get_predictions_for_frame(self, frame_id: int) -> List[AnticipatedRelation]:
        """Get predictions for a specific future frame."""
        return [p for p in self.predictions if p.predicted_frame == frame_id]
    
    def get_top_k(self, k: int) -> List[AnticipatedRelation]:
        """Get top-k predictions by confidence."""
        sorted_preds = sorted(self.predictions, key=lambda x: -x.confidence)
        return sorted_preds[:k]
    
    def get_unique_triplets(self) -> Set[Tuple[str, str, str]]:
        """Get unique predicted triplets."""
        return {p.as_triplet() for p in self.predictions}
    
    def to_ag_relations(self) -> List[AGRelation]:
        """Convert all predictions to AGRelations."""
        return [p.to_ag_relation() for p in self.predictions]


# ============================================================================
# TRAJECTORY PREDICTOR
# ============================================================================

class TrajectoryPredictor:
    """
    Predict future object positions using linear extrapolation.
    
    Uses velocity from observed frames to estimate where objects
    will be in future frames.
    """
    
    def __init__(self, max_extrapolation_frames: int = 30):
        self.max_extrapolation = max_extrapolation_frames
    
    def predict_position(
        self,
        entity: TrackedEntity,
        target_frame: int,
    ) -> Optional[List[float]]:
        """
        Predict bbox at future frame using linear extrapolation.
        
        Args:
            entity: Tracked entity with detection history
            target_frame: Frame to predict position for
            
        Returns:
            Predicted bbox [x1, y1, x2, y2] or None
        """
        frames = entity.get_frames()
        if len(frames) < 2:
            return None
        
        # Get last two frames for velocity
        last_frame = max(frames)
        if target_frame <= last_frame:
            return entity.get_bbox_at(target_frame)
        
        # Don't extrapolate too far
        if target_frame - last_frame > self.max_extrapolation:
            return None
        
        # Get velocity at last frame
        velocity = entity.get_velocity_at(last_frame)
        if velocity is None:
            # Use constant position
            return entity.get_bbox_at(last_frame)
        
        # Get last bbox
        last_bbox = entity.get_bbox_at(last_frame)
        if last_bbox is None:
            return None
        
        # Extrapolate
        frames_ahead = target_frame - last_frame
        dx = velocity[0] * frames_ahead
        dy = velocity[1] * frames_ahead
        
        # Apply to bbox
        x1, y1, x2, y2 = last_bbox
        return [x1 + dx, y1 + dy, x2 + dx, y2 + dy]
    
    def predict_interaction(
        self,
        entity1: TrackedEntity,
        entity2: TrackedEntity,
        target_frame: int,
        distance_threshold: float = 150.0,
    ) -> Optional[float]:
        """
        Predict if two entities will be close enough to interact.
        
        Returns proximity score (0-1) or None if can't predict.
        """
        bbox1 = self.predict_position(entity1, target_frame)
        bbox2 = self.predict_position(entity2, target_frame)
        
        if bbox1 is None or bbox2 is None:
            return None
        
        # Calculate distance between centers
        cx1 = (bbox1[0] + bbox1[2]) / 2
        cy1 = (bbox1[1] + bbox1[3]) / 2
        cx2 = (bbox2[0] + bbox2[2]) / 2
        cy2 = (bbox2[1] + bbox2[3]) / 2
        
        dist = math.sqrt((cx1 - cx2)**2 + (cy1 - cy2)**2)
        
        if dist > distance_threshold:
            return 0.0
        
        return max(0, 1.0 - dist / distance_threshold)


# ============================================================================
# RELATION PERSISTENCE MODEL
# ============================================================================

class RelationPersistenceModel:
    """
    Model that predicts relations will persist from observed to future frames.
    
    Key insight: Many relations (sitting_on, holding, etc.) tend to persist
    over time unless there's evidence of change.
    """
    
    # Predicates likely to persist
    PERSISTENT_PREDICATES = {
        'sitting_on': 0.9,      # High persistence
        'lying_on': 0.85,
        'standing_on': 0.8,
        'holding': 0.7,         # Medium persistence
        'carrying': 0.75,
        'touching': 0.5,        # Lower persistence
        'in_front_of': 0.6,
        'behind': 0.6,
        'above': 0.7,
        'beneath': 0.7,
        'on_the_side_of': 0.5,
        'covered_by': 0.6,
        'not_contacting': 0.3,  # Low persistence (likely to change)
    }
    
    def __init__(self, decay_rate: float = 0.05):
        """
        Args:
            decay_rate: How much confidence decays per frame into future
        """
        self.decay_rate = decay_rate
    
    def predict_persistence(
        self,
        observed_sg: VideoSceneGraph,
        future_frame: int,
    ) -> List[AnticipatedRelation]:
        """
        Predict which observed relations will persist into future.
        
        Args:
            observed_sg: Scene graph from observed frames
            future_frame: Target future frame
            
        Returns:
            List of anticipated relations
        """
        predictions = []
        
        # Get last observed frame
        observed_frames = sorted(observed_sg.frame_graphs.keys())
        if not observed_frames:
            return predictions
        
        last_observed = max(observed_frames)
        frames_ahead = future_frame - last_observed
        
        # Get relations from recent frames (weighted by recency)
        relation_counts = defaultdict(lambda: {'count': 0, 'max_conf': 0, 'last_frame': 0})
        
        for frame_id in observed_frames[-5:]:  # Last 5 frames
            fg = observed_sg.frame_graphs[frame_id]
            for edge in fg.edges:
                key = (edge.subject_id, edge.predicate, edge.object_id)
                relation_counts[key]['count'] += 1
                relation_counts[key]['max_conf'] = max(
                    relation_counts[key]['max_conf'], 
                    edge.confidence
                )
                relation_counts[key]['last_frame'] = max(
                    relation_counts[key]['last_frame'],
                    frame_id
                )
                # Store labels
                subj_node = fg.nodes.get(edge.subject_id)
                obj_node = fg.nodes.get(edge.object_id)
                if subj_node and obj_node:
                    relation_counts[key]['subject_label'] = subj_node.label
                    relation_counts[key]['object_label'] = obj_node.label
        
        # Generate predictions
        for (subj_id, pred, obj_id), info in relation_counts.items():
            if 'subject_label' not in info:
                continue
            
            # Base persistence probability
            base_persistence = self.PERSISTENT_PREDICATES.get(pred, 0.5)
            
            # Boost for consistent relations
            consistency_boost = min(0.2, info['count'] * 0.05)
            
            # Decay over time
            time_decay = self.decay_rate * frames_ahead
            
            # Final confidence
            confidence = (base_persistence + consistency_boost) * info['max_conf']
            confidence = max(0.1, confidence - time_decay)
            
            predictions.append(AnticipatedRelation(
                subject_id=subj_id,
                subject_label=info['subject_label'],
                predicate=pred,
                object_id=obj_id,
                object_label=info['object_label'],
                confidence=confidence,
                predicted_frame=future_frame,
                source='persistence',
            ))
        
        return predictions


# ============================================================================
# CONTEXT-BASED PREDICTOR
# ============================================================================

class ContextBasedPredictor:
    """
    Predict future relations based on common action sequences.
    
    Example: if person is 'standing_on' floor and 'near' chair,
    they might 'sit_on' the chair next.
    """
    
    # Common action transitions (current_predicate -> likely_next)
    PREDICATE_TRANSITIONS = {
        'standing_on': ['sitting_on', 'lying_on', 'walking_on'],
        'holding': ['carrying', 'touching', 'not_contacting'],
        'carrying': ['holding', 'not_contacting'],
        'touching': ['holding', 'not_contacting'],
        'not_contacting': ['touching', 'holding'],
        'sitting_on': ['standing_on', 'lying_on'],
        'lying_on': ['sitting_on', 'standing_on'],
    }
    
    # Object-specific likely predicates
    OBJECT_PREDICATES = {
        'chair': ['sitting_on', 'standing_on', 'touching'],
        'sofa': ['sitting_on', 'lying_on'],
        'bed': ['lying_on', 'sitting_on'],
        'floor': ['standing_on', 'lying_on', 'sitting_on'],
        'table': ['touching', 'above', 'in_front_of'],
        'phone': ['holding', 'touching'],
        'cup': ['holding', 'touching'],
        'book': ['holding', 'touching'],
        'bag': ['carrying', 'holding'],
        'door': ['touching', 'in_front_of'],
    }
    
    def __init__(self, transition_confidence: float = 0.4):
        self.transition_confidence = transition_confidence
    
    def predict_transitions(
        self,
        observed_sg: VideoSceneGraph,
        tracking_result: TrackingResult,
        future_frames: List[int],
    ) -> List[AnticipatedRelation]:
        """
        Predict relation transitions based on context.
        
        Args:
            observed_sg: Observed scene graph
            tracking_result: Tracking info for entities
            future_frames: List of future frame IDs
            
        Returns:
            List of anticipated relations
        """
        predictions = []
        
        if not future_frames:
            return predictions
        
        # Get current state from last observed frames
        current_relations = self._get_recent_relations(observed_sg)
        
        # Get entities
        entities = tracking_result.entities
        
        # Predict based on transitions
        for (subj_id, pred, obj_id), info in current_relations.items():
            # Get possible transitions
            next_preds = self.PREDICATE_TRANSITIONS.get(pred, [])
            
            for next_pred in next_preds:
                # Predict for middle future frame
                target_frame = future_frames[len(future_frames) // 2]
                
                predictions.append(AnticipatedRelation(
                    subject_id=subj_id,
                    subject_label=info['subject_label'],
                    predicate=next_pred,
                    object_id=obj_id,
                    object_label=info['object_label'],
                    confidence=self.transition_confidence * info['confidence'],
                    predicted_frame=target_frame,
                    source='transition',
                ))
        
        # Predict based on object types
        for subj_id, subj_entity in entities.items():
            if subj_entity.label.lower() != 'person':
                continue
            
            for obj_id, obj_entity in entities.items():
                if subj_id == obj_id:
                    continue
                
                obj_label = obj_entity.label.lower()
                likely_preds = self.OBJECT_PREDICATES.get(obj_label, [])
                
                for pred in likely_preds:
                    # Check if this relation already exists
                    key = (subj_id, pred, obj_id)
                    if key in current_relations:
                        continue
                    
                    target_frame = future_frames[len(future_frames) // 2]
                    
                    predictions.append(AnticipatedRelation(
                        subject_id=subj_id,
                        subject_label=subj_entity.label,
                        predicate=pred,
                        object_id=obj_id,
                        object_label=obj_entity.label,
                        confidence=self.transition_confidence * 0.5,
                        predicted_frame=target_frame,
                        source='object_context',
                    ))
        
        return predictions
    
    def _get_recent_relations(
        self, 
        observed_sg: VideoSceneGraph,
        num_frames: int = 3,
    ) -> Dict:
        """Get relations from most recent frames."""
        relations = {}
        
        frames = sorted(observed_sg.frame_graphs.keys())[-num_frames:]
        
        for frame_id in frames:
            fg = observed_sg.frame_graphs[frame_id]
            for edge in fg.edges:
                key = (edge.subject_id, edge.predicate, edge.object_id)
                
                subj_node = fg.nodes.get(edge.subject_id)
                obj_node = fg.nodes.get(edge.object_id)
                
                if subj_node and obj_node:
                    if key not in relations or edge.confidence > relations[key]['confidence']:
                        relations[key] = {
                            'subject_label': subj_node.label,
                            'object_label': obj_node.label,
                            'confidence': edge.confidence,
                        }
        
        return relations


# ============================================================================
# MAIN ANTICIPATOR
# ============================================================================

class SceneGraphAnticipator:
    """
    Main anticipation model combining multiple strategies.
    
    Takes observed scene graphs and predicts future relations.
    """
    
    def __init__(
        self,
        trajectory_predictor: Optional[TrajectoryPredictor] = None,
        persistence_model: Optional[RelationPersistenceModel] = None,
        context_predictor: Optional[ContextBasedPredictor] = None,
        # Weights for combining strategies
        persistence_weight: float = 0.5,
        trajectory_weight: float = 0.3,
        context_weight: float = 0.2,
    ):
        """
        Args:
            trajectory_predictor: For motion-based prediction
            persistence_model: For relation persistence
            context_predictor: For context-based transitions
            *_weight: Weights for combining predictions
        """
        self.trajectory_predictor = trajectory_predictor or TrajectoryPredictor()
        self.persistence_model = persistence_model or RelationPersistenceModel()
        self.context_predictor = context_predictor or ContextBasedPredictor()
        
        self.persistence_weight = persistence_weight
        self.trajectory_weight = trajectory_weight
        self.context_weight = context_weight
    
    def anticipate(
        self,
        observed_sg: VideoSceneGraph,
        tracking_result: TrackingResult,
        future_frames: List[int],
        max_predictions: int = 100,
    ) -> AnticipationResult:
        """
        Anticipate future scene graph relations.
        
        Args:
            observed_sg: Scene graph from observed frames
            tracking_result: Tracking result with entity motion
            future_frames: List of future frame IDs to predict
            max_predictions: Maximum predictions to return
            
        Returns:
            AnticipationResult with predicted relations
        """
        logger.info(
            f"Anticipating {len(future_frames)} future frames "
            f"from {observed_sg.num_frames()} observed frames"
        )
        
        all_predictions = []
        
        # 1. Persistence-based predictions
        for frame_id in future_frames:
            preds = self.persistence_model.predict_persistence(observed_sg, frame_id)
            for p in preds:
                p.confidence *= self.persistence_weight
            all_predictions.extend(preds)
        
        # 2. Trajectory-based predictions
        trajectory_preds = self._predict_from_trajectories(
            observed_sg, tracking_result, future_frames
        )
        for p in trajectory_preds:
            p.confidence *= self.trajectory_weight
        all_predictions.extend(trajectory_preds)
        
        # 3. Context-based predictions
        context_preds = self.context_predictor.predict_transitions(
            observed_sg, tracking_result, future_frames
        )
        for p in context_preds:
            p.confidence *= self.context_weight
        all_predictions.extend(context_preds)
        
        # Aggregate and deduplicate
        aggregated = self._aggregate_predictions(all_predictions)
        
        # Sort by confidence and limit
        aggregated.sort(key=lambda x: -x.confidence)
        final_predictions = aggregated[:max_predictions]
        
        logger.info(f"✓ Generated {len(final_predictions)} future predictions")
        
        return AnticipationResult(
            video_id=observed_sg.video_id,
            observed_frames=sorted(observed_sg.frame_graphs.keys()),
            future_frames=future_frames,
            predictions=final_predictions,
        )
    
    def _predict_from_trajectories(
        self,
        observed_sg: VideoSceneGraph,
        tracking_result: TrackingResult,
        future_frames: List[int],
    ) -> List[AnticipatedRelation]:
        """Generate predictions from trajectory extrapolation."""
        predictions = []
        
        entities = tracking_result.entities
        
        # For each pair of entities
        for subj_id, subj_entity in entities.items():
            for obj_id, obj_entity in entities.items():
                if subj_id >= obj_id:
                    continue
                
                # Check if they'll be close in future
                for frame_id in future_frames:
                    proximity = self.trajectory_predictor.predict_interaction(
                        subj_entity, obj_entity, frame_id
                    )
                    
                    if proximity is None or proximity < 0.3:
                        continue
                    
                    # If close, predict likely relations
                    likely_preds = self._get_likely_predicates(
                        subj_entity.label, obj_entity.label
                    )
                    
                    for pred, base_conf in likely_preds:
                        predictions.append(AnticipatedRelation(
                            subject_id=subj_id,
                            subject_label=subj_entity.label,
                            predicate=pred,
                            object_id=obj_id,
                            object_label=obj_entity.label,
                            confidence=base_conf * proximity,
                            predicted_frame=frame_id,
                            source='trajectory',
                        ))
        
        return predictions
    
    def _get_likely_predicates(
        self,
        subject_label: str,
        object_label: str,
    ) -> List[Tuple[str, float]]:
        """Get likely predicates for a subject-object pair."""
        predicates = []
        
        subj = subject_label.lower()
        obj = object_label.lower()
        
        # Person-specific predicates
        if subj == 'person':
            if obj in ['chair', 'sofa', 'bed']:
                predicates.extend([
                    ('sitting_on', 0.6),
                    ('lying_on', 0.3),
                    ('touching', 0.4),
                ])
            elif obj in ['floor', 'ground']:
                predicates.extend([
                    ('standing_on', 0.7),
                    ('sitting_on', 0.3),
                ])
            elif obj in ['phone', 'cup', 'book', 'bag']:
                predicates.extend([
                    ('holding', 0.6),
                    ('touching', 0.4),
                ])
            elif obj in ['door', 'window']:
                predicates.extend([
                    ('in_front_of', 0.5),
                    ('touching', 0.3),
                ])
            else:
                # Default for person
                predicates.extend([
                    ('touching', 0.4),
                    ('in_front_of', 0.3),
                ])
        else:
            # Object-object relations
            predicates.extend([
                ('above', 0.3),
                ('on_the_side_of', 0.3),
                ('touching', 0.2),
            ])
        
        return predicates
    
    def _aggregate_predictions(
        self,
        predictions: List[AnticipatedRelation],
    ) -> List[AnticipatedRelation]:
        """Aggregate duplicate predictions, combining confidence."""
        aggregated = {}
        
        for pred in predictions:
            # Key by triplet (ignore frame for aggregation)
            key = (pred.subject_id, pred.predicate, pred.object_id)
            
            if key not in aggregated:
                aggregated[key] = pred
            else:
                # Combine confidences (max or weighted sum)
                existing = aggregated[key]
                existing.confidence = max(existing.confidence, pred.confidence)
                # Keep track of sources
                if pred.source not in existing.source:
                    existing.source = f"{existing.source}+{pred.source}"
        
        return list(aggregated.values())
    
    def anticipate_from_scene_graph(
        self,
        observed_sg: VideoSceneGraph,
        future_frame_ids: List[int],
        max_predictions: int = 100,
    ) -> List[AnticipatedRelation]:
        """
        Simplified anticipation using only observed scene graph (no tracking).
        
        Uses persistence-based prediction only (most reliable without tracking).
        
        Args:
            observed_sg: Scene graph from observed frames
            future_frame_ids: List of future frame IDs to predict
            max_predictions: Maximum predictions to return
            
        Returns:
            List of anticipated relations
        """
        all_predictions = []
        
        # Persistence-based predictions (most important for SGA)
        for frame_id in future_frame_ids:
            preds = self.persistence_model.predict_persistence(observed_sg, frame_id)
            all_predictions.extend(preds)
        
        # Aggregate and sort
        final_predictions = self._aggregate_predictions(all_predictions)
        final_predictions.sort(key=lambda r: -r.confidence)
        
        return final_predictions[:max_predictions]


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def anticipate_from_video(
    video_path: str,
    fraction: float = 0.5,
    target_fps: float = 5.0,
) -> Tuple[AnticipationResult, VideoSceneGraph]:
    """
    Full pipeline: video → anticipation.
    
    Args:
        video_path: Path to video file
        fraction: Observation fraction (0.0-1.0)
        target_fps: Target FPS for processing
        
    Returns:
        (anticipation_result, observed_scene_graph)
    """
    from .detector import SGADetectionPipeline
    from .observed_sgg import ObservedSceneGraphGenerator
    
    # Detect and track
    pipeline = SGADetectionPipeline(target_fps=target_fps)
    tracking_result = pipeline.process_video(video_path)
    
    # Get frame split
    all_frames = sorted(tracking_result.frame_detections.keys())
    split_idx = int(len(all_frames) * fraction)
    observed_frames = all_frames[:split_idx]
    future_frames = all_frames[split_idx:]
    
    # Generate observed scene graph (only for observed frames)
    generator = ObservedSceneGraphGenerator()
    
    # Create filtered tracking result for observed only
    observed_tracking = TrackingResult(
        video_id=tracking_result.video_id,
        entities=tracking_result.entities,
        frame_detections={
            fid: fd for fid, fd in tracking_result.frame_detections.items()
            if fid in observed_frames
        },
    )
    
    observed_sg = generator.generate(observed_tracking)
    
    # Anticipate
    anticipator = SceneGraphAnticipator()
    result = anticipator.anticipate(
        observed_sg=observed_sg,
        tracking_result=tracking_result,
        future_frames=future_frames,
    )
    
    return result, observed_sg


# ============================================================================
# CLI TESTING
# ============================================================================

if __name__ == "__main__":
    import argparse
    from .detector import SGADetectionPipeline
    from .observed_sgg import ObservedSceneGraphGenerator
    
    parser = argparse.ArgumentParser(description="Test Future Anticipation")
    parser.add_argument("--video", required=True, help="Path to video file")
    parser.add_argument("--max-frames", type=int, default=60, help="Max frames")
    parser.add_argument("--fraction", type=float, default=0.5, help="Observation fraction")
    parser.add_argument("--fps", type=float, default=3.0, help="Target FPS")
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    print(f"\n{'='*60}")
    print("PART 4: FUTURE SCENE GRAPH ANTICIPATION TEST")
    print(f"{'='*60}\n")
    
    # Detection + Tracking
    print("--- Running Detection + Tracking ---")
    pipeline = SGADetectionPipeline(target_fps=args.fps)
    tracking_result = pipeline.process_video(
        video_path=args.video,
        end_frame=args.max_frames,
    )
    print(f"  Tracks: {tracking_result.num_tracks()}")
    print(f"  Frames: {tracking_result.num_frames()}")
    
    # Split into observed/future
    all_frames = sorted(tracking_result.frame_detections.keys())
    split_idx = int(len(all_frames) * args.fraction)
    observed_frames = all_frames[:split_idx]
    future_frames = all_frames[split_idx:]
    
    print(f"\n  Split at fraction={args.fraction}:")
    print(f"    Observed frames: {len(observed_frames)}")
    print(f"    Future frames: {len(future_frames)}")
    
    # Generate observed scene graph
    print("\n--- Generating Observed Scene Graph ---")
    
    observed_tracking = TrackingResult(
        video_id=tracking_result.video_id,
        entities=tracking_result.entities,
        frame_detections={
            fid: fd for fid, fd in tracking_result.frame_detections.items()
            if fid in observed_frames
        },
    )
    
    generator = ObservedSceneGraphGenerator()
    observed_sg = generator.generate(observed_tracking)
    print(f"  Observed frames with graphs: {observed_sg.num_frames()}")
    print(f"  Observed edges: {observed_sg.num_edges()}")
    
    # Anticipate future
    print("\n--- Anticipating Future Relations (Part 4) ---")
    anticipator = SceneGraphAnticipator()
    result = anticipator.anticipate(
        observed_sg=observed_sg,
        tracking_result=tracking_result,
        future_frames=future_frames,
    )
    
    print(f"  Total predictions: {len(result.predictions)}")
    print(f"  Unique triplets: {len(result.get_unique_triplets())}")
    
    # Show top predictions
    print(f"\n--- Top 15 Predictions ---")
    for pred in result.get_top_k(15):
        print(
            f"  [{pred.source}] {pred.subject_label} --[{pred.predicate}]--> "
            f"{pred.object_label} (conf={pred.confidence:.3f})"
        )
    
    # Prediction source distribution
    source_counts = defaultdict(int)
    for pred in result.predictions:
        for src in pred.source.split('+'):
            source_counts[src] += 1
    
    print(f"\n--- Prediction Sources ---")
    for src, count in sorted(source_counts.items(), key=lambda x: -x[1]):
        print(f"  {src}: {count}")
    
    print(f"\n{'='*60}")
    print("PART 4 COMPLETE ✓")
    print(f"{'='*60}\n")
