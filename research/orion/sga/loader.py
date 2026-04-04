"""
Part 1: Action Genome Data Loading & Frame Splitting

This module handles:
1. Loading Action Genome ground truth annotations
2. Grouping by video → frame structure
3. Splitting videos into observed/future by input fraction F
4. Providing clean data structures for downstream pipeline

Key Concept - Input Fraction (F):
- F = 0.3 → model sees first 30% of frames → predicts last 70% (hardest)
- F = 0.9 → model sees first 90% of frames → predicts last 10% (easiest)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Sequence
from collections import defaultdict

logger = logging.getLogger(__name__)


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class AGObject:
    """An object instance in a frame."""
    object_id: str
    category: str
    bbox: Optional[List[float]] = None  # [x1, y1, x2, y2] or [x, y, w, h]
    
    def __hash__(self):
        return hash(self.object_id)
    
    def __eq__(self, other):
        if not isinstance(other, AGObject):
            return False
        return self.object_id == other.object_id


@dataclass
class AGRelation:
    """A relation (triplet) between two objects."""
    subject: AGObject
    predicate: str
    object: AGObject
    confidence: float = 1.0
    is_causal: bool = False
    
    def as_triplet(self) -> Tuple[str, str, str]:
        """Return (subject_category, predicate, object_category) tuple."""
        return (self.subject.category, self.predicate, self.object.category)
    
    def as_triplet_with_ids(self) -> Tuple[str, str, str, str, str]:
        """Return (subject_id, subject_cat, predicate, object_id, object_cat) tuple."""
        return (
            self.subject.object_id, 
            self.subject.category, 
            self.predicate, 
            self.object.object_id,
            self.object.category
        )


@dataclass
class AGFrame:
    """A single frame with objects and relations."""
    frame_id: int
    frame_name: str  # e.g., "000089.png"
    objects: Dict[str, AGObject] = field(default_factory=dict)
    relations: List[AGRelation] = field(default_factory=list)
    
    def get_triplets(self) -> List[Tuple[str, str, str]]:
        """Get all (subject, predicate, object) triplets."""
        return [rel.as_triplet() for rel in self.relations]
    
    def get_objects_list(self) -> List[AGObject]:
        """Get list of objects in this frame."""
        return list(self.objects.values())


@dataclass
class AGVideo:
    """A video containing multiple frames with scene graphs."""
    video_id: str
    frames: Dict[int, AGFrame] = field(default_factory=dict)
    
    def get_ordered_frames(self) -> List[AGFrame]:
        """Get frames ordered by frame_id."""
        return [self.frames[fid] for fid in sorted(self.frames.keys())]
    
    def num_frames(self) -> int:
        """Total number of annotated frames."""
        return len(self.frames)
    
    def get_all_relations(self) -> List[AGRelation]:
        """Get all relations across all frames."""
        relations = []
        for frame in self.frames.values():
            relations.extend(frame.relations)
        return relations
    
    def get_unique_predicates(self) -> set:
        """Get set of unique predicates in this video."""
        predicates = set()
        for frame in self.frames.values():
            for rel in frame.relations:
                predicates.add(rel.predicate)
        return predicates
    
    def split_by_fraction(
        self, 
        fraction: float,
        min_observed: int = 1,
        min_future: int = 1
    ) -> Tuple[AGVideo, AGVideo]:
        """
        Split video into observed and future portions.
        
        Args:
            fraction: Input fraction F (0.0-1.0). Model sees first F frames.
            min_observed: Minimum number of observed frames (default: 1)
            min_future: Minimum number of future frames (default: 1)
            
        Returns:
            (observed_video, future_video) tuple
            
        Example:
            If video has 20 frames and fraction=0.5:
            - observed_video contains frames 0-9 (first 50%)
            - future_video contains frames 10-19 (last 50%)
        """
        ordered_frames = self.get_ordered_frames()
        total = len(ordered_frames)
        
        if total < min_observed + min_future:
            logger.warning(
                f"Video {self.video_id} has only {total} frames, "
                f"need at least {min_observed + min_future} for split"
            )
            # Return what we can
            split_idx = max(min_observed, min(total - min_future, int(total * fraction)))
        else:
            split_idx = max(min_observed, int(total * fraction))
            split_idx = min(split_idx, total - min_future)
        
        # Build observed video
        observed = AGVideo(video_id=self.video_id)
        for frame in ordered_frames[:split_idx]:
            observed.frames[frame.frame_id] = frame
        
        # Build future video
        future = AGVideo(video_id=self.video_id)
        for frame in ordered_frames[split_idx:]:
            future.frames[frame.frame_id] = frame
        
        return observed, future
    
    def get_frame_range(self) -> Tuple[int, int]:
        """Get (min_frame_id, max_frame_id)."""
        if not self.frames:
            return (0, 0)
        frame_ids = list(self.frames.keys())
        return (min(frame_ids), max(frame_ids))


@dataclass
class AGDataBundle:
    """Container for loaded Action Genome data."""
    videos: Dict[str, AGVideo]
    predicates: List[str]
    object_classes: List[str]
    metadata: Dict = field(default_factory=dict)
    
    def iter_videos(self) -> Sequence[AGVideo]:
        """Iterate over all videos."""
        return list(self.videos.values())
    
    def get_video(self, video_id: str) -> Optional[AGVideo]:
        """Get a specific video by ID."""
        return self.videos.get(video_id)
    
    def num_videos(self) -> int:
        return len(self.videos)
    
    def total_frames(self) -> int:
        return sum(v.num_frames() for v in self.videos.values())
    
    def total_relations(self) -> int:
        return sum(len(v.get_all_relations()) for v in self.videos.values())


# ============================================================================
# LOADER
# ============================================================================

class ActionGenomeLoader:
    """
    Load Action Genome dataset from various formats.
    
    Supports:
    1. Orion's ag_ground_truth_full.json format (list of relation entries)
    2. AG's object_bbox_and_relationship.pkl format (if available)
    """
    
    # Action Genome predicates
    AG_PREDICATES = [
        'above', 'behind', 'beneath', 'carrying', 'covered_by', 'holding',
        'in_front_of', 'lying_on', 'not_contacting', 'on_the_side_of',
        'sitting_on', 'standing_on', 'touching'
    ]
    
    # Action Genome object classes (subset)
    AG_OBJECT_CLASSES = [
        'person', 'bag', 'bed', 'blanket', 'book', 'box', 'broom', 'chair',
        'closet', 'clothes', 'cup', 'dish', 'door', 'doorknob', 'doorway',
        'floor', 'food', 'groceries', 'laptop', 'light', 'medicine', 'mirror',
        'paper', 'phone', 'picture', 'pillow', 'refrigerator', 'sandwich',
        'shelf', 'shoe', 'sofa', 'table', 'television', 'towel', 'vacuum',
        'window'
    ]
    
    def __init__(self, data_path: Optional[str] = None):
        """
        Initialize loader.
        
        Args:
            data_path: Path to AG data file (JSON or PKL)
        """
        self.data_path = Path(data_path) if data_path else None
        self._cache: Optional[AGDataBundle] = None
    
    def load(
        self, 
        max_videos: Optional[int] = None,
        split: Optional[str] = None,  # 'train', 'test', or None for all
        min_frames_per_video: int = 2,
    ) -> AGDataBundle:
        """
        Load Action Genome data.
        
        Args:
            max_videos: Limit number of videos (for testing)
            split: 'train', 'test', or None for all
            min_frames_per_video: Skip videos with fewer frames
            
        Returns:
            AGDataBundle containing all loaded videos
        """
        if self._cache is not None:
            return self._filter_cache(max_videos, split, min_frames_per_video)
        
        if self.data_path is None:
            raise ValueError("No data_path specified")
        
        if not self.data_path.exists():
            raise FileNotFoundError(f"Data file not found: {self.data_path}")
        
        # Detect format and load
        if self.data_path.suffix == '.json':
            bundle = self._load_json_format(self.data_path)
        elif self.data_path.suffix == '.pkl':
            bundle = self._load_pkl_format(self.data_path)
        else:
            raise ValueError(f"Unknown format: {self.data_path.suffix}")
        
        self._cache = bundle
        return self._filter_cache(max_videos, split, min_frames_per_video)
    
    def _filter_cache(
        self, 
        max_videos: Optional[int],
        split: Optional[str],
        min_frames_per_video: int
    ) -> AGDataBundle:
        """Filter cached data by criteria."""
        if self._cache is None:
            raise ValueError("No data loaded")
        
        filtered_videos = {}
        for vid, video in self._cache.videos.items():
            # Filter by min frames
            if video.num_frames() < min_frames_per_video:
                continue
            
            # Filter by split (if split metadata available)
            if split and 'split' in self._cache.metadata:
                video_split = self._cache.metadata.get('splits', {}).get(vid)
                if video_split and video_split != split:
                    continue
            
            filtered_videos[vid] = video
            
            if max_videos and len(filtered_videos) >= max_videos:
                break
        
        return AGDataBundle(
            videos=filtered_videos,
            predicates=self._cache.predicates,
            object_classes=self._cache.object_classes,
            metadata=self._cache.metadata,
        )
    
    def _load_json_format(self, path: Path) -> AGDataBundle:
        """
        Load from Orion's ag_ground_truth_full.json format.
        
        Format: List of relation entries, each with:
        - agent_id: "VIDEO/person/FRAME.png"
        - patient_id: "VIDEO/object/FRAME.png"  
        - metadata: {video_id, frame_id, relationship_type, agent_category, patient_category}
        """
        logger.info(f"Loading Action Genome from JSON: {path}")
        
        with open(path, 'r') as f:
            data = json.load(f)
        
        logger.info(f"Loaded {len(data)} relation entries")
        
        # Group by video -> frame -> relations
        videos: Dict[str, AGVideo] = {}
        predicates_seen = set()
        objects_seen = set()
        
        for entry in data:
            meta = entry.get('metadata', {})
            video_id = meta.get('video_id', '')
            frame_name = meta.get('frame_id', '')  # e.g., "000089.png"
            
            if not video_id or not frame_name:
                continue
            
            # Parse frame ID from name
            try:
                frame_id = int(frame_name.replace('.png', '').replace('.jpg', ''))
            except ValueError:
                continue
            
            # Get or create video
            if video_id not in videos:
                videos[video_id] = AGVideo(video_id=video_id)
            video = videos[video_id]
            
            # Get or create frame
            if frame_id not in video.frames:
                video.frames[frame_id] = AGFrame(frame_id=frame_id, frame_name=frame_name)
            frame = video.frames[frame_id]
            
            # Create objects
            agent_cat = meta.get('agent_category', 'unknown')
            patient_cat = meta.get('patient_category', 'unknown')
            
            agent_id = entry.get('agent_id', f"{video_id}/{agent_cat}/{frame_id}")
            patient_id = entry.get('patient_id', f"{video_id}/{patient_cat}/{frame_id}")
            
            # Add objects to frame
            if agent_id not in frame.objects:
                frame.objects[agent_id] = AGObject(
                    object_id=agent_id,
                    category=agent_cat,
                )
            if patient_id not in frame.objects:
                frame.objects[patient_id] = AGObject(
                    object_id=patient_id,
                    category=patient_cat,
                )
            
            # Create relation
            predicate = meta.get('relationship_type', 'unknown')
            relation = AGRelation(
                subject=frame.objects[agent_id],
                predicate=predicate,
                object=frame.objects[patient_id],
                confidence=entry.get('confidence', 1.0),
                is_causal=entry.get('is_causal', False),
            )
            frame.relations.append(relation)
            
            predicates_seen.add(predicate)
            objects_seen.add(agent_cat)
            objects_seen.add(patient_cat)
        
        logger.info(
            f"Loaded {len(videos)} videos, "
            f"{sum(v.num_frames() for v in videos.values())} frames, "
            f"{len(predicates_seen)} predicates"
        )
        
        return AGDataBundle(
            videos=videos,
            predicates=sorted(predicates_seen),
            object_classes=sorted(objects_seen),
            metadata={'source': 'json', 'path': str(path)},
        )
    
    def _load_pkl_format(self, path: Path) -> AGDataBundle:
        """
        Load from Action Genome's official object_bbox_and_relationship.pkl format.
        
        This requires the original AG dataset structure.
        """
        import pickle
        
        logger.info(f"Loading Action Genome from PKL: {path}")
        
        with open(path, 'rb') as f:
            data = pickle.load(f)
        
        # PKL format structure depends on AG version
        # Typical: Dict[video_id -> Dict[frame_id -> annotations]]
        videos: Dict[str, AGVideo] = {}
        predicates_seen = set()
        objects_seen = set()
        
        # Handle different PKL structures
        if isinstance(data, dict):
            for video_id, video_data in data.items():
                video = AGVideo(video_id=video_id)
                
                if isinstance(video_data, dict):
                    for frame_key, frame_data in video_data.items():
                        try:
                            frame_id = int(frame_key)
                        except (ValueError, TypeError):
                            continue
                        
                        frame = AGFrame(frame_id=frame_id, frame_name=str(frame_key))
                        
                        # Extract objects and relations based on PKL structure
                        # This needs to be adapted based on actual AG PKL format
                        if 'objects' in frame_data:
                            for obj_data in frame_data['objects']:
                                obj = AGObject(
                                    object_id=obj_data.get('id', str(len(frame.objects))),
                                    category=obj_data.get('class', 'unknown'),
                                    bbox=obj_data.get('bbox'),
                                )
                                frame.objects[obj.object_id] = obj
                                objects_seen.add(obj.category)
                        
                        if 'relations' in frame_data:
                            for rel_data in frame_data['relations']:
                                subj_id = str(rel_data.get('subject', 0))
                                obj_id = str(rel_data.get('object', 0))
                                pred = rel_data.get('predicate', 'unknown')
                                
                                if subj_id in frame.objects and obj_id in frame.objects:
                                    relation = AGRelation(
                                        subject=frame.objects[subj_id],
                                        predicate=pred,
                                        object=frame.objects[obj_id],
                                    )
                                    frame.relations.append(relation)
                                    predicates_seen.add(pred)
                        
                        video.frames[frame_id] = frame
                
                if video.num_frames() > 0:
                    videos[video_id] = video
        
        logger.info(f"Loaded {len(videos)} videos from PKL")
        
        return AGDataBundle(
            videos=videos,
            predicates=sorted(predicates_seen) or self.AG_PREDICATES,
            object_classes=sorted(objects_seen) or self.AG_OBJECT_CLASSES,
            metadata={'source': 'pkl', 'path': str(path)},
        )


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def load_action_genome(
    data_path: str,
    max_videos: Optional[int] = None,
    split: Optional[str] = None,
    min_frames: int = 2,
) -> AGDataBundle:
    """
    Convenience function to load Action Genome data.
    
    Args:
        data_path: Path to data file (JSON or PKL)
        max_videos: Limit number of videos
        split: 'train', 'test', or None
        min_frames: Minimum frames per video
        
    Returns:
        AGDataBundle with loaded videos
    """
    loader = ActionGenomeLoader(data_path)
    return loader.load(
        max_videos=max_videos,
        split=split,
        min_frames_per_video=min_frames,
    )


def split_videos_by_fraction(
    videos: Sequence[AGVideo],
    fraction: float,
) -> List[Tuple[AGVideo, AGVideo]]:
    """
    Split multiple videos by input fraction.
    
    Args:
        videos: List of videos to split
        fraction: Input fraction F (0.0-1.0)
        
    Returns:
        List of (observed, future) video tuples
    """
    splits = []
    for video in videos:
        observed, future = video.split_by_fraction(fraction)
        if observed.num_frames() > 0 and future.num_frames() > 0:
            splits.append((observed, future))
    return splits


def get_video_statistics(bundle: AGDataBundle) -> Dict:
    """
    Compute statistics about the loaded data.
    
    Returns dict with:
    - num_videos, total_frames, total_relations
    - frames_per_video (min, max, mean)
    - relations_per_frame (min, max, mean)
    - predicate_distribution
    """
    stats = {
        'num_videos': bundle.num_videos(),
        'total_frames': bundle.total_frames(),
        'total_relations': bundle.total_relations(),
        'predicates': bundle.predicates,
        'num_predicates': len(bundle.predicates),
    }
    
    # Frames per video
    frames_per_video = [v.num_frames() for v in bundle.videos.values()]
    if frames_per_video:
        stats['frames_per_video'] = {
            'min': min(frames_per_video),
            'max': max(frames_per_video),
            'mean': sum(frames_per_video) / len(frames_per_video),
        }
    
    # Relations per frame
    relations_per_frame = []
    for video in bundle.videos.values():
        for frame in video.frames.values():
            relations_per_frame.append(len(frame.relations))
    
    if relations_per_frame:
        stats['relations_per_frame'] = {
            'min': min(relations_per_frame),
            'max': max(relations_per_frame),
            'mean': sum(relations_per_frame) / len(relations_per_frame),
        }
    
    # Predicate distribution
    pred_counts = defaultdict(int)
    for video in bundle.videos.values():
        for rel in video.get_all_relations():
            pred_counts[rel.predicate] += 1
    stats['predicate_distribution'] = dict(pred_counts)
    
    return stats


# ============================================================================
# CLI TESTING
# ============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test AG data loading")
    parser.add_argument("--data", default="data/ag_ground_truth_full.json", help="Path to AG data")
    parser.add_argument("--max-videos", type=int, default=10, help="Max videos to load")
    parser.add_argument("--fraction", type=float, default=0.5, help="Input fraction for split test")
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO)
    
    # Load data
    print(f"\n{'='*60}")
    print("PART 1: ACTION GENOME DATA LOADING TEST")
    print(f"{'='*60}\n")
    
    bundle = load_action_genome(args.data, max_videos=args.max_videos)
    
    # Print statistics
    stats = get_video_statistics(bundle)
    print(f"Loaded {stats['num_videos']} videos")
    print(f"Total frames: {stats['total_frames']}")
    print(f"Total relations: {stats['total_relations']}")
    print(f"Predicates ({stats['num_predicates']}): {stats['predicates']}")
    
    if 'frames_per_video' in stats:
        fpv = stats['frames_per_video']
        print(f"Frames/video: min={fpv['min']}, max={fpv['max']}, mean={fpv['mean']:.1f}")
    
    if 'relations_per_frame' in stats:
        rpf = stats['relations_per_frame']
        print(f"Relations/frame: min={rpf['min']}, max={rpf['max']}, mean={rpf['mean']:.1f}")
    
    # Test split
    print(f"\n--- Testing fraction split (F={args.fraction}) ---")
    
    for video in list(bundle.videos.values())[:3]:
        observed, future = video.split_by_fraction(args.fraction)
        print(f"\nVideo: {video.video_id}")
        print(f"  Total frames: {video.num_frames()}")
        print(f"  Observed frames: {observed.num_frames()} (first {args.fraction*100:.0f}%)")
        print(f"  Future frames: {future.num_frames()} (last {(1-args.fraction)*100:.0f}%)")
        print(f"  Observed relations: {len(observed.get_all_relations())}")
        print(f"  Future relations: {len(future.get_all_relations())}")
    
    print(f"\n{'='*60}")
    print("PART 1 COMPLETE ✓")
    print(f"{'='*60}\n")
