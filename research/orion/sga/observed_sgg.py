"""
Part 3: Observed Scene Graph Generation for SGA

This module generates scene graphs from tracked detections in observed frames.
It takes the output of Part 2 (detection + tracking) and produces:
- Per-frame scene graphs with nodes (objects) and edges (relations)
- Temporal relation features for anticipation

Relation Generation Methods:
1. Spatial heuristics (bbox geometry)
2. Action classifiers (motion-based)
3. VLM verification (optional)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Sequence
from collections import defaultdict

import numpy as np

from .detector import TrackedEntity, TrackingResult, Detection
from .loader import AGRelation, AGObject, AGFrame, AGVideo

logger = logging.getLogger(__name__)


# ============================================================================
# ACTION GENOME PREDICATES
# ============================================================================

# Full Action Genome predicate set (13 predicates)
AG_PREDICATES = [
    'above',           # Spatial: subject is above object
    'behind',          # Spatial: subject is behind object  
    'beneath',         # Spatial: subject is beneath object
    'carrying',        # Contact: subject carries object
    'covered_by',      # Contact: subject is covered by object
    'holding',         # Contact: subject holds object
    'in_front_of',     # Spatial: subject is in front of object
    'lying_on',        # Contact: subject is lying on object
    'not_contacting',  # No contact between subject and object
    'on_the_side_of',  # Spatial: subject is on the side of object
    'sitting_on',      # Contact: subject sits on object
    'standing_on',     # Contact: subject stands on object
    'touching',        # Contact: subject touches object
]

# Predicate categories
SPATIAL_PREDICATES = ['above', 'behind', 'beneath', 'in_front_of', 'on_the_side_of']
CONTACT_PREDICATES = ['carrying', 'covered_by', 'holding', 'lying_on', 'sitting_on', 'standing_on', 'touching']
NO_CONTACT_PREDICATES = ['not_contacting']


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class SceneGraphNode:
    """A node in the scene graph (an object)."""
    node_id: int
    track_id: int
    label: str
    bbox: List[float]
    confidence: float = 1.0
    
    def to_ag_object(self) -> AGObject:
        """Convert to AGObject for evaluation."""
        return AGObject(
            object_id=str(self.track_id),
            category=self.label,
            bbox=self.bbox,
        )


@dataclass
class SceneGraphEdge:
    """An edge in the scene graph (a relation)."""
    subject_id: int  # track_id
    object_id: int   # track_id
    predicate: str
    confidence: float = 1.0
    features: Dict = field(default_factory=dict)  # For anticipation
    
    def to_ag_relation(self, nodes: Dict[int, SceneGraphNode]) -> AGRelation:
        """Convert to AGRelation for evaluation."""
        subj_node = nodes.get(self.subject_id)
        obj_node = nodes.get(self.object_id)
        
        return AGRelation(
            subject=subj_node.to_ag_object() if subj_node else AGObject(str(self.subject_id), "unknown"),
            predicate=self.predicate,
            object=obj_node.to_ag_object() if obj_node else AGObject(str(self.object_id), "unknown"),
            confidence=self.confidence,
        )


@dataclass
class FrameSceneGraph:
    """Scene graph for a single frame."""
    frame_id: int
    nodes: Dict[int, SceneGraphNode] = field(default_factory=dict)  # track_id -> node
    edges: List[SceneGraphEdge] = field(default_factory=list)
    
    def add_node(self, node: SceneGraphNode):
        self.nodes[node.track_id] = node
    
    def add_edge(self, edge: SceneGraphEdge):
        self.edges.append(edge)
    
    def get_triplets(self) -> List[Tuple[str, str, str]]:
        """Get (subject_label, predicate, object_label) triplets."""
        triplets = []
        for edge in self.edges:
            subj = self.nodes.get(edge.subject_id)
            obj = self.nodes.get(edge.object_id)
            if subj and obj:
                triplets.append((subj.label, edge.predicate, obj.label))
        return triplets
    
    def to_ag_frame(self) -> AGFrame:
        """Convert to AGFrame for evaluation."""
        ag_frame = AGFrame(frame_id=self.frame_id, frame_name=str(self.frame_id))
        
        for node in self.nodes.values():
            ag_obj = node.to_ag_object()
            ag_frame.objects[ag_obj.object_id] = ag_obj
        
        for edge in self.edges:
            ag_rel = edge.to_ag_relation(self.nodes)
            ag_frame.relations.append(ag_rel)
        
        return ag_frame


@dataclass
class VideoSceneGraph:
    """Scene graph for entire video (observed portion)."""
    video_id: str
    frame_graphs: Dict[int, FrameSceneGraph] = field(default_factory=dict)
    
    def add_frame_graph(self, fg: FrameSceneGraph):
        self.frame_graphs[fg.frame_id] = fg
    
    def get_all_edges(self) -> List[SceneGraphEdge]:
        """Get all edges across all frames."""
        edges = []
        for fg in self.frame_graphs.values():
            edges.extend(fg.edges)
        return edges
    
    def get_unique_triplets(self) -> set:
        """Get unique (subject, predicate, object) triplets."""
        triplets = set()
        for fg in self.frame_graphs.values():
            triplets.update(fg.get_triplets())
        return triplets
    
    def to_ag_video(self) -> AGVideo:
        """Convert to AGVideo for evaluation."""
        ag_video = AGVideo(video_id=self.video_id)
        for frame_id, fg in self.frame_graphs.items():
            ag_video.frames[frame_id] = fg.to_ag_frame()
        return ag_video
    
    def num_frames(self) -> int:
        return len(self.frame_graphs)
    
    def num_edges(self) -> int:
        return sum(len(fg.edges) for fg in self.frame_graphs.values())


# ============================================================================
# SPATIAL RELATION CLASSIFIER
# ============================================================================

class SpatialRelationClassifier:
    """
    Classify spatial relations between bounding boxes.
    
    Uses geometric heuristics to determine:
    - Relative position (above, below, beside, in front, behind)
    - Contact/overlap (touching, holding, sitting_on, etc.)
    """
    
    def __init__(
        self,
        iou_threshold: float = 0.1,
        distance_threshold: float = 100.0,
        vertical_margin: float = 0.2,
    ):
        self.iou_threshold = iou_threshold
        self.distance_threshold = distance_threshold
        self.vertical_margin = vertical_margin
    
    def classify(
        self,
        subject_bbox: List[float],
        object_bbox: List[float],
        subject_label: str = "",
        object_label: str = "",
    ) -> List[Tuple[str, float]]:
        """
        Classify relation between subject and object.
        
        Args:
            subject_bbox: Subject bounding box [x1, y1, x2, y2]
            object_bbox: Object bounding box [x1, y1, x2, y2]
            subject_label: Subject class name
            object_label: Object class name
            
        Returns:
            List of (predicate, confidence) tuples, sorted by confidence
        """
        relations = []
        
        # Extract bbox properties
        sx1, sy1, sx2, sy2 = subject_bbox
        ox1, oy1, ox2, oy2 = object_bbox
        
        # Centers
        scx, scy = (sx1 + sx2) / 2, (sy1 + sy2) / 2
        ocx, ocy = (ox1 + ox2) / 2, (oy1 + oy2) / 2
        
        # Sizes
        sw, sh = sx2 - sx1, sy2 - sy1
        ow, oh = ox2 - ox1, oy2 - oy1
        s_area = max(sw * sh, 1)
        o_area = max(ow * oh, 1)
        
        # IoU and overlap
        inter_x1 = max(sx1, ox1)
        inter_y1 = max(sy1, oy1)
        inter_x2 = min(sx2, ox2)
        inter_y2 = min(sy2, oy2)
        inter_w = max(0, inter_x2 - inter_x1)
        inter_h = max(0, inter_y2 - inter_y1)
        inter_area = inter_w * inter_h
        
        iou = inter_area / (s_area + o_area - inter_area + 1e-6)
        overlap_subject = inter_area / (s_area + 1e-6)
        overlap_object = inter_area / (o_area + 1e-6)
        
        # Distance between centers
        dist = np.sqrt((scx - ocx) ** 2 + (scy - ocy) ** 2)
        avg_size = (max(sw, sh) + max(ow, oh)) / 2
        norm_dist = dist / (avg_size + 1e-6)
        
        # Vertical relationship
        vertical_diff = scy - ocy  # Positive = subject below object
        
        # Horizontal relationship
        horizontal_diff = scx - ocx  # Positive = subject right of object
        
        # === CONTACT PREDICATES ===
        
        # 'touching' - significant overlap
        if iou > self.iou_threshold:
            relations.append(('touching', min(0.9, 0.5 + iou)))
        
        # 'holding' - subject (person) contains small object
        if subject_label.lower() == 'person' and overlap_object > 0.3 and o_area < s_area * 0.3:
            relations.append(('holding', min(0.85, 0.5 + overlap_object)))
        
        # 'carrying' - similar to holding but for larger objects
        if subject_label.lower() == 'person' and overlap_object > 0.2 and 0.1 < o_area / s_area < 0.5:
            relations.append(('carrying', min(0.75, 0.4 + overlap_object)))
        
        # 'sitting_on' - person's lower body on furniture
        if subject_label.lower() == 'person' and object_label.lower() in ['chair', 'sofa', 'bed', 'floor']:
            # Subject bottom near object top
            if abs(sy2 - oy1) < sh * 0.3 and inter_w > 0:
                relations.append(('sitting_on', 0.7))
        
        # 'standing_on' - person standing on surface
        if subject_label.lower() == 'person' and object_label.lower() in ['floor', 'ground', 'carpet', 'rug']:
            if sy2 > oy1 and inter_w > 0:
                relations.append(('standing_on', 0.75))
        
        # 'lying_on' - subject horizontally on object
        if subject_label.lower() == 'person' and object_label.lower() in ['bed', 'sofa', 'floor']:
            # Wide bbox suggests lying down
            if sw > sh * 1.5 and overlap_subject > 0.3:
                relations.append(('lying_on', 0.7))
        
        # 'covered_by' - object covers subject
        if overlap_subject > 0.5 and o_area > s_area:
            relations.append(('covered_by', min(0.8, overlap_subject)))
        
        # === SPATIAL PREDICATES ===
        
        # 'above' / 'beneath'
        if abs(horizontal_diff) < avg_size * 0.5:  # Vertically aligned
            if vertical_diff < -sh * 0.3:
                relations.append(('above', 0.6 + min(0.3, abs(vertical_diff) / avg_size * 0.1)))
            elif vertical_diff > oh * 0.3:
                relations.append(('beneath', 0.6 + min(0.3, abs(vertical_diff) / avg_size * 0.1)))
        
        # 'in_front_of' / 'behind' - using image depth heuristics
        # Larger/lower objects are typically in front
        if norm_dist < 2.0:
            if s_area > o_area * 1.2 and scy > ocy:
                relations.append(('in_front_of', 0.5))
            elif o_area > s_area * 1.2 and ocy > scy:
                relations.append(('behind', 0.5))
        
        # 'on_the_side_of'
        if abs(vertical_diff) < avg_size * 0.3 and norm_dist < 2.0:
            relations.append(('on_the_side_of', 0.5))
        
        # 'not_contacting' - far apart, no overlap
        if iou < 0.01 and norm_dist > 2.0:
            relations.append(('not_contacting', 0.6))
        
        # Sort by confidence
        relations.sort(key=lambda x: -x[1])
        
        return relations


# ============================================================================
# MOTION-BASED RELATION CLASSIFIER
# ============================================================================

class MotionRelationClassifier:
    """
    Classify relations based on object motion patterns.
    
    Uses velocity and acceleration to detect:
    - holding (stable relative motion)
    - carrying (moving together)
    - throwing/catching (sudden motion changes)
    """
    
    def __init__(
        self,
        holding_velocity_threshold: float = 20.0,
        carrying_velocity_threshold: float = 50.0,
    ):
        self.holding_vel_thresh = holding_velocity_threshold
        self.carrying_vel_thresh = carrying_velocity_threshold
    
    def classify(
        self,
        subject_entity: TrackedEntity,
        object_entity: TrackedEntity,
        frame_id: int,
    ) -> List[Tuple[str, float]]:
        """
        Classify relations based on motion.
        
        Args:
            subject_entity: Subject tracked entity
            object_entity: Object tracked entity
            frame_id: Current frame ID
            
        Returns:
            List of (predicate, confidence) tuples
        """
        relations = []
        
        # Get velocities
        subj_vel = subject_entity.get_velocity_at(frame_id)
        obj_vel = object_entity.get_velocity_at(frame_id)
        
        if subj_vel is None or obj_vel is None:
            return relations
        
        # Relative velocity
        rel_vel = np.sqrt((subj_vel[0] - obj_vel[0])**2 + (subj_vel[1] - obj_vel[1])**2)
        
        # 'holding' - very low relative velocity (moving together)
        if rel_vel < self.holding_vel_thresh:
            # Additional check: object should be near person
            subj_bbox = subject_entity.get_bbox_at(frame_id)
            obj_bbox = object_entity.get_bbox_at(frame_id)
            if subj_bbox and obj_bbox:
                # Check proximity
                scx = (subj_bbox[0] + subj_bbox[2]) / 2
                scy = (subj_bbox[1] + subj_bbox[3]) / 2
                ocx = (obj_bbox[0] + obj_bbox[2]) / 2
                ocy = (obj_bbox[1] + obj_bbox[3]) / 2
                dist = np.sqrt((scx - ocx)**2 + (scy - ocy)**2)
                
                if dist < 150:  # Close enough for holding
                    conf = 0.6 - rel_vel / self.holding_vel_thresh * 0.2
                    relations.append(('holding', conf))
        
        # 'carrying' - moderate velocity but moving together
        subj_speed = np.sqrt(subj_vel[0]**2 + subj_vel[1]**2)
        obj_speed = np.sqrt(obj_vel[0]**2 + obj_vel[1]**2)
        
        if subj_speed > 10 and rel_vel < self.holding_vel_thresh:
            conf = min(0.7, 0.4 + subj_speed / 100)
            relations.append(('carrying', conf))
        
        return relations


# ============================================================================
# SCENE GRAPH GENERATOR
# ============================================================================

class ObservedSceneGraphGenerator:
    """
    Generate scene graphs from tracked detections.
    
    Combines:
    - Spatial relation classifier (geometry-based)
    - Motion relation classifier (velocity-based)
    - Optional: VLM verification
    """
    
    def __init__(
        self,
        spatial_classifier: Optional[SpatialRelationClassifier] = None,
        motion_classifier: Optional[MotionRelationClassifier] = None,
        max_relations_per_pair: int = 2,
        min_confidence: float = 0.3,
    ):
        """
        Args:
            spatial_classifier: Classifier for spatial relations
            motion_classifier: Classifier for motion-based relations
            max_relations_per_pair: Max relations to keep per object pair
            min_confidence: Minimum confidence threshold
        """
        self.spatial_classifier = spatial_classifier or SpatialRelationClassifier()
        self.motion_classifier = motion_classifier or MotionRelationClassifier()
        self.max_relations_per_pair = max_relations_per_pair
        self.min_confidence = min_confidence
    
    def generate(self, tracking_result: TrackingResult) -> VideoSceneGraph:
        """
        Generate scene graph from tracking result.
        
        Args:
            tracking_result: Output from detection + tracking pipeline
            
        Returns:
            VideoSceneGraph with per-frame graphs
        """
        logger.info(f"Generating scene graph for {tracking_result.video_id}")
        
        video_sg = VideoSceneGraph(video_id=tracking_result.video_id)
        
        # Process each frame
        frame_ids = sorted(tracking_result.frame_detections.keys())
        
        for frame_id in frame_ids:
            frame_sg = self._generate_frame_graph(tracking_result, frame_id)
            video_sg.add_frame_graph(frame_sg)
        
        logger.info(
            f"✓ Generated {video_sg.num_frames()} frame graphs, "
            f"{video_sg.num_edges()} total edges"
        )
        
        return video_sg
    
    def _generate_frame_graph(
        self,
        tracking_result: TrackingResult,
        frame_id: int,
    ) -> FrameSceneGraph:
        """Generate scene graph for a single frame."""
        frame_sg = FrameSceneGraph(frame_id=frame_id)
        
        # Get entities present in this frame
        entities = tracking_result.get_entities_at_frame(frame_id)
        
        # Add nodes
        for entity in entities:
            det = entity.detections.get(frame_id)
            if det:
                node = SceneGraphNode(
                    node_id=entity.track_id,
                    track_id=entity.track_id,
                    label=entity.label,
                    bbox=det.bbox,
                    confidence=det.confidence,
                )
                frame_sg.add_node(node)
        
        # Generate edges for all pairs
        for i, subj_entity in enumerate(entities):
            for obj_entity in entities[i+1:]:
                # Skip same entity
                if subj_entity.track_id == obj_entity.track_id:
                    continue
                
                # Get detections
                subj_det = subj_entity.detections.get(frame_id)
                obj_det = obj_entity.detections.get(frame_id)
                
                if not subj_det or not obj_det:
                    continue
                
                # Classify relations (subject -> object)
                relations = self._classify_pair(
                    subj_entity, obj_entity, subj_det, obj_det, frame_id
                )
                
                # Add top relations
                for pred, conf in relations[:self.max_relations_per_pair]:
                    if conf >= self.min_confidence:
                        edge = SceneGraphEdge(
                            subject_id=subj_entity.track_id,
                            object_id=obj_entity.track_id,
                            predicate=pred,
                            confidence=conf,
                        )
                        frame_sg.add_edge(edge)
                
                # Also classify reverse direction (object -> subject)
                reverse_relations = self._classify_pair(
                    obj_entity, subj_entity, obj_det, subj_det, frame_id
                )
                
                for pred, conf in reverse_relations[:self.max_relations_per_pair]:
                    if conf >= self.min_confidence:
                        edge = SceneGraphEdge(
                            subject_id=obj_entity.track_id,
                            object_id=subj_entity.track_id,
                            predicate=pred,
                            confidence=conf,
                        )
                        frame_sg.add_edge(edge)
        
        return frame_sg
    
    def _classify_pair(
        self,
        subject_entity: TrackedEntity,
        object_entity: TrackedEntity,
        subject_det: Detection,
        object_det: Detection,
        frame_id: int,
    ) -> List[Tuple[str, float]]:
        """Classify relations for a subject-object pair."""
        all_relations = []
        
        # Spatial relations
        spatial_rels = self.spatial_classifier.classify(
            subject_det.bbox,
            object_det.bbox,
            subject_entity.label,
            object_entity.label,
        )
        all_relations.extend(spatial_rels)
        
        # Motion relations
        motion_rels = self.motion_classifier.classify(
            subject_entity,
            object_entity,
            frame_id,
        )
        all_relations.extend(motion_rels)
        
        # Deduplicate and sort by confidence
        seen = {}
        for pred, conf in all_relations:
            if pred not in seen or conf > seen[pred]:
                seen[pred] = conf
        
        relations = [(pred, conf) for pred, conf in seen.items()]
        relations.sort(key=lambda x: -x[1])
        
        return relations
    
    def generate_from_ag_video(self, ag_video: AGVideo) -> VideoSceneGraph:
        """
        Generate scene graph directly from Action Genome video data.
        
        This uses GT boxes/labels (GAGS mode) and classifies relations
        using the spatial/motion classifiers.
        
        Args:
            ag_video: Action Genome video with GT annotations
            
        Returns:
            VideoSceneGraph with classified relations
        """
        logger.info(f"Generating scene graph from AGVideo: {ag_video.video_id}")
        
        video_sg = VideoSceneGraph(video_id=ag_video.video_id)
        
        for frame_id, frame in ag_video.frames.items():
            frame_sg = FrameSceneGraph(frame_id=frame_id)
            
            # Get objects list, filter to those with valid bboxes
            obj_list = [obj for obj in frame.get_objects_list() if obj.bbox is not None]
            
            # Add nodes from GT objects
            for obj in obj_list:
                node = SceneGraphNode(
                    node_id=obj.object_id,
                    track_id=obj.object_id,
                    label=obj.category,
                    bbox=obj.bbox,
                    confidence=1.0,  # GT has perfect confidence
                )
                frame_sg.add_node(node)
            
            # Classify relations between all pairs using our classifiers
            for i, subj_obj in enumerate(obj_list):
                for obj_obj in obj_list[i+1:]:
                    if subj_obj.object_id == obj_obj.object_id:
                        continue
                    
                    # Skip if missing bbox
                    if subj_obj.bbox is None or obj_obj.bbox is None:
                        continue
                    
                    # Classify spatial relations
                    spatial_rels = self.spatial_classifier.classify(
                        subj_obj.bbox,
                        obj_obj.bbox,
                        subj_obj.category,
                        obj_obj.category,
                    )
                    
                    # Add top relations
                    for pred, conf in spatial_rels[:self.max_relations_per_pair]:
                        if conf >= self.min_confidence:
                            edge = SceneGraphEdge(
                                subject_id=subj_obj.object_id,
                                object_id=obj_obj.object_id,
                                predicate=pred,
                                confidence=conf,
                            )
                            frame_sg.add_edge(edge)
                    
                    # Reverse direction
                    rev_spatial = self.spatial_classifier.classify(
                        obj_obj.bbox,
                        subj_obj.bbox,
                        obj_obj.category,
                        subj_obj.category,
                    )
                    
                    for pred, conf in rev_spatial[:self.max_relations_per_pair]:
                        if conf >= self.min_confidence:
                            edge = SceneGraphEdge(
                                subject_id=obj_obj.object_id,
                                object_id=subj_obj.object_id,
                                predicate=pred,
                                confidence=conf,
                            )
                            frame_sg.add_edge(edge)
            
            video_sg.add_frame_graph(frame_sg)
        
        logger.info(
            f"✓ Generated {video_sg.num_frames()} frame graphs, "
            f"{video_sg.num_edges()} total edges from AGVideo"
        )
        
        return video_sg


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def tracking_result_to_ag_video(
    tracking_result: TrackingResult,
    generator: Optional[ObservedSceneGraphGenerator] = None,
) -> AGVideo:
    """
    Convert tracking result to AGVideo with scene graphs.
    
    Args:
        tracking_result: Output from detection pipeline
        generator: Scene graph generator (created if None)
        
    Returns:
        AGVideo with relations
    """
    if generator is None:
        generator = ObservedSceneGraphGenerator()
    
    video_sg = generator.generate(tracking_result)
    return video_sg.to_ag_video()


def get_relation_statistics(video_sg: VideoSceneGraph) -> Dict:
    """
    Compute statistics about generated scene graph.
    
    Returns dict with:
    - num_frames, num_edges
    - predicate_distribution
    - edges_per_frame
    """
    stats = {
        'num_frames': video_sg.num_frames(),
        'num_edges': video_sg.num_edges(),
    }
    
    # Predicate distribution
    pred_counts = defaultdict(int)
    edges_per_frame = []
    
    for fg in video_sg.frame_graphs.values():
        edges_per_frame.append(len(fg.edges))
        for edge in fg.edges:
            pred_counts[edge.predicate] += 1
    
    stats['predicate_distribution'] = dict(pred_counts)
    
    if edges_per_frame:
        stats['edges_per_frame'] = {
            'min': min(edges_per_frame),
            'max': max(edges_per_frame),
            'mean': sum(edges_per_frame) / len(edges_per_frame),
        }
    
    return stats


# ============================================================================
# CLI TESTING
# ============================================================================

if __name__ == "__main__":
    import argparse
    from .detector import SGADetectionPipeline
    
    parser = argparse.ArgumentParser(description="Test Observed Scene Graph Generation")
    parser.add_argument("--video", required=True, help="Path to video file")
    parser.add_argument("--max-frames", type=int, default=30, help="Max frames")
    parser.add_argument("--fps", type=float, default=3.0, help="Target FPS")
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    print(f"\n{'='*60}")
    print("PART 3: OBSERVED SCENE GRAPH GENERATION TEST")
    print(f"{'='*60}\n")
    
    # Part 2: Detection + Tracking
    print("--- Running Detection + Tracking (Part 2) ---")
    pipeline = SGADetectionPipeline(target_fps=args.fps)
    tracking_result = pipeline.process_video(
        video_path=args.video,
        end_frame=args.max_frames,
    )
    
    print(f"  Tracks: {tracking_result.num_tracks()}")
    print(f"  Frames: {tracking_result.num_frames()}")
    
    # Part 3: Scene Graph Generation
    print("\n--- Generating Scene Graphs (Part 3) ---")
    generator = ObservedSceneGraphGenerator()
    video_sg = generator.generate(tracking_result)
    
    # Statistics
    stats = get_relation_statistics(video_sg)
    print(f"  Frames with graphs: {stats['num_frames']}")
    print(f"  Total edges: {stats['num_edges']}")
    
    if 'edges_per_frame' in stats:
        epf = stats['edges_per_frame']
        print(f"  Edges/frame: min={epf['min']}, max={epf['max']}, mean={epf['mean']:.1f}")
    
    print(f"\n  Predicate distribution:")
    for pred, count in sorted(stats['predicate_distribution'].items(), key=lambda x: -x[1]):
        print(f"    {pred}: {count}")
    
    # Sample frame
    if video_sg.frame_graphs:
        sample_fid = list(video_sg.frame_graphs.keys())[0]
        sample_fg = video_sg.frame_graphs[sample_fid]
        print(f"\n--- Sample Frame {sample_fid} ---")
        print(f"  Nodes: {len(sample_fg.nodes)}")
        for nid, node in sample_fg.nodes.items():
            print(f"    - {node.label} (track {node.track_id})")
        print(f"  Edges: {len(sample_fg.edges)}")
        for edge in sample_fg.edges[:5]:
            subj = sample_fg.nodes.get(edge.subject_id)
            obj = sample_fg.nodes.get(edge.object_id)
            subj_label = subj.label if subj else "?"
            obj_label = obj.label if obj else "?"
            print(f"    - {subj_label} --[{edge.predicate}]--> {obj_label} (conf={edge.confidence:.2f})")
    
    # Unique triplets
    triplets = video_sg.get_unique_triplets()
    print(f"\n  Unique triplets: {len(triplets)}")
    for t in list(triplets)[:10]:
        print(f"    {t[0]} --[{t[1]}]--> {t[2]}")
    
    print(f"\n{'='*60}")
    print("PART 3 COMPLETE ✓")
    print(f"{'='*60}\n")
