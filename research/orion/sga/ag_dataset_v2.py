"""
Action Genome Dataset for Temporal SGA Training (v2)

Properly parses the object_bbox_and_relationship.pkl format from Action Genome.

AG Format:
- Keys: "video_id.mp4/frame_id.png"
- Values: List of objects, each with:
  - class: object category (e.g., "dish", "chair")
  - bbox: (x, y, w, h) or None
  - spatial_relationship: list of predicates from person to this object
  - contacting_relationship: list of contact predicates
  - attention_relationship: list of attention predicates

The relationships are always from "person" (subject) to the object.
"""

from __future__ import annotations

import logging
import pickle
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set

import numpy as np
import torch
from torch.utils.data import Dataset, DataLoader

logger = logging.getLogger(__name__)


# ============================================================================
# ACTION GENOME CONSTANTS
# ============================================================================

# Object classes (index 0 is person/background)
AG_OBJECT_CLASSES = [
    'person',  # 0 - always the subject
    'bag', 'bed', 'blanket', 'book', 'box', 'broom', 'chair', 
    'closet/cabinet', 'clothes', 'cup/glass/bottle', 'dish', 'door', 
    'doorknob', 'doorway', 'floor', 'food', 'groceries', 'laptop', 
    'light', 'medicine', 'mirror', 'paper/notebook', 'phone/camera', 
    'picture', 'pillow', 'refrigerator', 'sandwich', 'shelf', 'shoe', 
    'sofa/couch', 'table', 'television', 'towel', 'vacuum', 'window'
]

AG_OBJECT_TO_IDX = {cls: idx for idx, cls in enumerate(AG_OBJECT_CLASSES)}

# Spatial predicates
AG_SPATIAL_PREDICATES = [
    'above', 'beneath', 'in_front_of', 'behind', 'on_the_side_of', 'in'
]

# Contact predicates
AG_CONTACT_PREDICATES = [
    'carrying', 'covered_by', 'drinking_from', 'eating', 
    'have_it_on_the_back', 'holding', 'leaning_on', 'lying_on', 
    'not_contacting', 'other_relationship', 'sitting_on', 'standing_on', 
    'touching', 'twisting', 'wearing', 'wiping', 'writing_on'
]

# Combined predicates for SGA evaluation
AG_ALL_PREDICATES = AG_SPATIAL_PREDICATES + AG_CONTACT_PREDICATES
AG_PREDICATE_TO_IDX = {pred: idx for idx, pred in enumerate(AG_ALL_PREDICATES)}
AG_IDX_TO_PREDICATE = {idx: pred for pred, idx in AG_PREDICATE_TO_IDX.items()}


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class FrameAnnotation:
    """Parsed annotation for a single frame."""
    video_id: str
    frame_id: str
    frame_num: int  # Numeric frame index
    objects: List[Dict]  # List of object annotations
    
    def get_relations(self) -> List[Tuple[str, str, str]]:
        """Get all (subject, predicate, object) triplets."""
        triplets = []
        for obj in self.objects:
            obj_class = obj['class']
            
            # Spatial relations
            for pred in obj.get('spatial_relationship') or []:
                triplets.append(('person', pred, obj_class))
            
            # Contact relations
            for pred in obj.get('contacting_relationship') or []:
                triplets.append(('person', pred, obj_class))
        
        return triplets


@dataclass
class VideoAnnotation:
    """All annotations for a single video."""
    video_id: str
    frames: Dict[int, FrameAnnotation]  # frame_num -> annotation
    
    def get_ordered_frames(self) -> List[FrameAnnotation]:
        """Get frames ordered by frame number."""
        return [self.frames[k] for k in sorted(self.frames.keys())]
    
    def num_frames(self) -> int:
        return len(self.frames)


# ============================================================================
# DATASET
# ============================================================================

class ActionGenomeDatasetV2(Dataset):
    """
    PyTorch Dataset for Action Genome SGA training.
    
    Properly handles the AG pickle format where:
    - Relations are per-object (from person to object)
    - Frames are identified by "video/frame.png" keys
    """
    
    def __init__(
        self,
        annotation_path: str,
        split: str = 'train',
        input_fraction: float = 0.5,
        max_objects: int = 15,
        max_observed_frames: int = 10,
        max_future_frames: int = 5,
        min_frames: int = 5,
        min_relations: int = 1,
        frame_stride: int = 1,
    ):
        """
        Args:
            annotation_path: Path to object_bbox_and_relationship.pkl
            split: 'train' or 'test'
            input_fraction: F - fraction of frames to observe
            max_objects: Maximum objects per frame  
            max_observed_frames: Max frames to input
            max_future_frames: Max future frames to predict
            min_frames: Minimum frames required per video
            min_relations: Minimum relations required in future
            frame_stride: Stride for subsampling frames
        """
        self.split = split
        self.input_fraction = input_fraction
        self.max_objects = max_objects
        self.max_observed_frames = max_observed_frames
        self.max_future_frames = max_future_frames
        self.min_frames = min_frames
        self.min_relations = min_relations
        self.frame_stride = frame_stride
        
        # Load and parse annotations
        self.videos = self._load_annotations(annotation_path)
        
        # Filter and split
        self.video_ids = self._get_split_videos()
        
        logger.info(
            f"Loaded {len(self.video_ids)} videos for {split} split "
            f"(F={input_fraction}, {sum(v.num_frames() for v in [self.videos[vid] for vid in self.video_ids])} frames)"
        )
    
    def _load_annotations(self, path: str) -> Dict[str, VideoAnnotation]:
        """Load and parse AG annotations."""
        logger.info(f"Loading annotations from {path}...")
        
        with open(path, 'rb') as f:
            raw_data = pickle.load(f)
        
        # Group by video
        video_frames = defaultdict(dict)
        
        for key, objects in raw_data.items():
            # Parse key: "video_id.mp4/frame_id.png"
            parts = key.split('/')
            video_id = parts[0]
            frame_name = parts[1] if len(parts) > 1 else key
            
            # Extract frame number
            try:
                frame_num = int(frame_name.replace('.png', ''))
            except ValueError:
                continue
            
            # Create frame annotation
            frame = FrameAnnotation(
                video_id=video_id,
                frame_id=frame_name,
                frame_num=frame_num,
                objects=objects,
            )
            
            video_frames[video_id][frame_num] = frame
        
        # Create video annotations
        videos = {}
        for video_id, frames in video_frames.items():
            videos[video_id] = VideoAnnotation(
                video_id=video_id,
                frames=frames,
            )
        
        logger.info(f"Parsed {len(videos)} videos with {sum(v.num_frames() for v in videos.values())} frames")
        
        return videos
    
    def _get_split_videos(self) -> List[str]:
        """Get video IDs for train/test split."""
        # Filter videos with enough frames
        valid_videos = []
        
        for vid, video in self.videos.items():
            if video.num_frames() < self.min_frames:
                continue
            
            # Check if future portion has relations
            frames = video.get_ordered_frames()
            split_idx = int(len(frames) * self.input_fraction)
            future_frames = frames[split_idx:]
            
            future_relations = 0
            for frame in future_frames:
                future_relations += len(frame.get_relations())
            
            if future_relations >= self.min_relations:
                valid_videos.append(vid)
        
        # Sort for reproducibility
        valid_videos.sort()
        
        # 70/30 split
        split_idx = int(len(valid_videos) * 0.7)
        
        if self.split == 'train':
            return valid_videos[:split_idx]
        else:
            return valid_videos[split_idx:]
    
    def __len__(self) -> int:
        return len(self.video_ids)
    
    def __getitem__(self, idx: int) -> Dict:
        """Get a training sample."""
        video_id = self.video_ids[idx]
        video = self.videos[video_id]
        
        # Get ordered frames
        frames = video.get_ordered_frames()
        
        # Subsample if too many frames
        if len(frames) > (self.max_observed_frames + self.max_future_frames) * 2:
            frames = frames[::self.frame_stride]
        
        # Split into observed and future
        split_idx = int(len(frames) * self.input_fraction)
        split_idx = max(1, min(split_idx, len(frames) - 1))
        
        observed_frames = frames[:split_idx][-self.max_observed_frames:]
        future_frames = frames[split_idx:][:self.max_future_frames]
        
        # Collect all unique objects across all frames
        all_objects = self._collect_objects(observed_frames + future_frames)
        
        # Create object index mapping (person is always 0)
        object_to_idx = {'person': 0}
        for i, obj in enumerate(all_objects):
            if obj not in object_to_idx:
                object_to_idx[obj] = len(object_to_idx)
        
        num_objects = min(len(object_to_idx), self.max_objects)
        
        # Encode observed frames
        class_ids, bboxes, mask = self._encode_frames(
            observed_frames, object_to_idx, num_objects
        )
        
        # Extract future relations as targets
        future_relations = self._extract_relations(
            future_frames, object_to_idx, num_objects
        )
        
        return {
            'video_id': video_id,
            'class_ids': class_ids,
            'bboxes': bboxes,
            'object_mask': mask,
            'frame_mask': torch.ones(len(observed_frames), dtype=torch.bool),
            'future_relations': future_relations,
            'num_observed_frames': len(observed_frames),
            'num_future_frames': len(future_frames),
            'num_objects': num_objects,
        }
    
    def _collect_objects(self, frames: List[FrameAnnotation]) -> List[str]:
        """Collect unique object classes from frames."""
        objects = set()
        for frame in frames:
            for obj in frame.objects:
                obj_class = obj.get('class', 'unknown')
                if obj_class in AG_OBJECT_TO_IDX:
                    objects.add(obj_class)
        return sorted(list(objects))
    
    def _encode_frames(
        self,
        frames: List[FrameAnnotation],
        object_to_idx: Dict[str, int],
        num_objects: int,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Encode frames into tensors."""
        num_frames = len(frames)
        
        class_ids = torch.zeros(num_frames, num_objects, dtype=torch.long)
        bboxes = torch.zeros(num_frames, num_objects, 4)
        mask = torch.zeros(num_frames, num_objects, dtype=torch.bool)
        
        for f_idx, frame in enumerate(frames):
            # Person is always present at index 0
            class_ids[f_idx, 0] = AG_OBJECT_TO_IDX.get('person', 0)
            mask[f_idx, 0] = True
            
            for obj in frame.objects:
                obj_class = obj.get('class', 'unknown')
                
                if obj_class not in object_to_idx:
                    continue
                
                obj_idx = object_to_idx[obj_class]
                if obj_idx >= num_objects:
                    continue
                
                # Class ID
                class_id = AG_OBJECT_TO_IDX.get(obj_class, 0)
                class_ids[f_idx, obj_idx] = class_id
                
                # Bbox (x, y, w, h) -> normalize assuming 480p video
                bbox = obj.get('bbox')
                if bbox and len(bbox) == 4:
                    x, y, w, h = bbox
                    # Normalize to 0-1 (assuming 854x480 resolution)
                    bboxes[f_idx, obj_idx] = torch.tensor([
                        x / 854.0, y / 480.0, 
                        (x + w) / 854.0, (y + h) / 480.0
                    ])
                
                mask[f_idx, obj_idx] = True
        
        return class_ids, bboxes, mask
    
    def _extract_relations(
        self,
        frames: List[FrameAnnotation],
        object_to_idx: Dict[str, int],
        num_objects: int,
    ) -> List[Tuple[int, int, int, int]]:
        """
        Extract ground truth relations from future frames.
        
        Returns list of (future_frame_idx, subject_idx, predicate_idx, object_idx)
        """
        relations = []
        
        for f_idx, frame in enumerate(frames):
            for obj in frame.objects:
                obj_class = obj.get('class', 'unknown')
                
                if obj_class not in object_to_idx:
                    continue
                
                obj_idx = object_to_idx[obj_class]
                if obj_idx >= num_objects:
                    continue
                
                # Subject is always person (index 0)
                subj_idx = 0
                
                # Spatial relations
                for pred in obj.get('spatial_relationship') or []:
                    if pred in AG_PREDICATE_TO_IDX:
                        pred_idx = AG_PREDICATE_TO_IDX[pred]
                        relations.append((f_idx, subj_idx, pred_idx, obj_idx))
                
                # Contact relations
                for pred in obj.get('contacting_relationship') or []:
                    if pred in AG_PREDICATE_TO_IDX:
                        pred_idx = AG_PREDICATE_TO_IDX[pred]
                        relations.append((f_idx, subj_idx, pred_idx, obj_idx))
        
        return relations


def collate_fn(batch: List[Dict]) -> Dict:
    """Collate samples into a batch."""
    batch_size = len(batch)
    
    # Find max dimensions
    max_frames = max(s['num_observed_frames'] for s in batch)
    max_objects = max(s['num_objects'] for s in batch)
    max_future = max(s['num_future_frames'] for s in batch)
    num_pairs = max_objects * (max_objects - 1)
    
    # Initialize tensors
    class_ids = torch.zeros(batch_size, max_frames, max_objects, dtype=torch.long)
    bboxes = torch.zeros(batch_size, max_frames, max_objects, 4)
    object_mask = torch.zeros(batch_size, max_frames, max_objects, dtype=torch.bool)
    frame_mask = torch.zeros(batch_size, max_frames, dtype=torch.bool)
    
    target_predicates = torch.full(
        (batch_size, max_future, num_pairs), 
        fill_value=-1,  # Ignore in loss
        dtype=torch.long
    )
    target_existence = torch.zeros(batch_size, max_future, num_pairs)
    
    # Fill tensors
    for b, sample in enumerate(batch):
        nf = sample['num_observed_frames']
        no = sample['num_objects']
        
        class_ids[b, :nf, :no] = sample['class_ids']
        bboxes[b, :nf, :no] = sample['bboxes']
        object_mask[b, :nf, :no] = sample['object_mask']
        frame_mask[b, :nf] = sample['frame_mask']
        
        # Fill targets from future relations
        for (future_idx, subj_idx, pred_idx, obj_idx) in sample['future_relations']:
            if future_idx >= max_future:
                continue
            if subj_idx >= max_objects or obj_idx >= max_objects:
                continue
            
            # Compute pair index (for all subject-object pairs)
            # Pair index = subj * (num_objects - 1) + adjusted_obj
            adj_obj = obj_idx if obj_idx < subj_idx else obj_idx - 1
            pair_idx = subj_idx * (max_objects - 1) + adj_obj
            
            if pair_idx >= num_pairs:
                continue
            
            target_predicates[b, future_idx, pair_idx] = pred_idx
            target_existence[b, future_idx, pair_idx] = 1.0
    
    return {
        'class_ids': class_ids,
        'bboxes': bboxes,
        'object_mask': object_mask,
        'frame_mask': frame_mask,
        'target_predicates': target_predicates,
        'target_existence': target_existence,
        'num_future_frames': max_future,
        'video_ids': [s['video_id'] for s in batch],
    }


def create_dataloaders(
    annotation_path: str,
    input_fraction: float = 0.5,
    batch_size: int = 8,
    num_workers: int = 0,
) -> Tuple[DataLoader, DataLoader]:
    """Create train and val dataloaders."""
    train_ds = ActionGenomeDatasetV2(
        annotation_path=annotation_path,
        split='train',
        input_fraction=input_fraction,
    )
    
    val_ds = ActionGenomeDatasetV2(
        annotation_path=annotation_path,
        split='test',
        input_fraction=input_fraction,
    )
    
    train_loader = DataLoader(
        train_ds,
        batch_size=batch_size,
        shuffle=True,
        num_workers=num_workers,
        collate_fn=collate_fn,
        drop_last=True,
    )
    
    val_loader = DataLoader(
        val_ds,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        collate_fn=collate_fn,
    )
    
    return train_loader, val_loader


if __name__ == "__main__":
    import sys
    
    # Test the dataset
    path = "datasets/ActionGenome/annotations/action_genome_v1.0/object_bbox_and_relationship.pkl"
    
    if not Path(path).exists():
        print(f"File not found: {path}")
        sys.exit(1)
    
    print("Testing ActionGenomeDatasetV2...")
    
    dataset = ActionGenomeDatasetV2(
        annotation_path=path,
        split='train',
        input_fraction=0.5,
    )
    
    print(f"Dataset size: {len(dataset)}")
    
    # Get a sample
    sample = dataset[0]
    print(f"\nSample from video: {sample['video_id']}")
    print(f"  Observed frames: {sample['num_observed_frames']}")
    print(f"  Future frames: {sample['num_future_frames']}")
    print(f"  Num objects: {sample['num_objects']}")
    print(f"  Class IDs shape: {sample['class_ids'].shape}")
    print(f"  Future relations: {len(sample['future_relations'])}")
    
    if sample['future_relations']:
        f, s, p, o = sample['future_relations'][0]
        print(f"  Example relation: frame={f}, subj={s}, pred={AG_IDX_TO_PREDICATE.get(p, p)}, obj={o}")
    
    # Test collation
    batch = collate_fn([dataset[i] for i in range(min(4, len(dataset)))])
    print(f"\nBatch:")
    print(f"  class_ids: {batch['class_ids'].shape}")
    print(f"  target_predicates: {batch['target_predicates'].shape}")
    print(f"  target_existence sum: {batch['target_existence'].sum().item()}")
    
    print("\n✓ Dataset test passed!")
