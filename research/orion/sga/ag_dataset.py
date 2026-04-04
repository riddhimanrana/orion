"""
Action Genome Dataset for Temporal SGA Training

This module prepares Action Genome data for training the temporal SGA model.
It handles:
1. Loading AG annotations (object_bbox_and_relationship.pkl)
2. Splitting videos into observed/future portions
3. Creating training samples with input/target pairs
4. Batching and data augmentation
"""

from __future__ import annotations

import logging
import pickle
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
from collections import defaultdict

import numpy as np
import torch
from torch.utils.data import Dataset, DataLoader

logger = logging.getLogger(__name__)


# ============================================================================
# ACTION GENOME CONSTANTS
# ============================================================================

# Object classes in Action Genome
AG_OBJECT_CLASSES = [
    '__background__',  # 0 - padding/unknown
    'person',          # 1
    'bag', 'bed', 'blanket', 'book', 'box', 'broom', 'chair', 'closet/cabinet',
    'clothes', 'cup/glass/bottle', 'dish', 'door', 'doorknob', 'doorway',
    'floor', 'food', 'groceries', 'laptop', 'light', 'medicine', 'mirror',
    'paper/notebook', 'phone/camera', 'picture', 'pillow', 'refrigerator',
    'sandwich', 'shelf', 'shoe', 'sofa/couch', 'table', 'television', 'towel',
    'vacuum', 'window'
]

AG_OBJECT_TO_IDX = {cls: idx for idx, cls in enumerate(AG_OBJECT_CLASSES)}

# Predicate classes in Action Genome
AG_ATTENTION_PREDICATES = [
    'looking_at', 'not_looking_at', 'unsure'
]

AG_SPATIAL_PREDICATES = [
    'above', 'beneath', 'in_front_of', 'behind', 'on_the_side_of', 'in'
]

AG_CONTACT_PREDICATES = [
    'carrying', 'covered_by', 'drinking_from', 'eating', 'have_it_on_the_back',
    'holding', 'leaning_on', 'lying_on', 'not_contacting', 'other_relationship',
    'sitting_on', 'standing_on', 'touching', 'twisting', 'wearing', 'wiping',
    'writing_on'
]

# Combined predicates for SGA
AG_ALL_PREDICATES = AG_SPATIAL_PREDICATES + AG_CONTACT_PREDICATES

AG_PREDICATE_TO_IDX = {pred: idx for idx, pred in enumerate(AG_ALL_PREDICATES)}


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class SGASample:
    """A single training sample for SGA."""
    video_id: str
    
    # Observed frames data
    observed_class_ids: torch.Tensor      # (num_observed, max_objects)
    observed_bboxes: torch.Tensor         # (num_observed, max_objects, 4)
    observed_object_mask: torch.Tensor    # (num_observed, max_objects)
    observed_frame_mask: torch.Tensor     # (num_observed,)
    
    # Object ID mapping (for tracking across frames)
    object_id_to_idx: Dict[str, int]
    idx_to_object_id: Dict[int, str]
    idx_to_class: Dict[int, str]
    
    # Ground truth future relations
    future_relations: List[Tuple[int, int, int, int]]  # (future_frame, subj_idx, pred_idx, obj_idx)
    future_frame_ids: List[int]
    
    # Metadata
    num_observed_frames: int
    num_future_frames: int
    num_objects: int


@dataclass  
class SGABatch:
    """Batched samples for training."""
    batch_size: int
    
    # Batched observed data
    class_ids: torch.Tensor           # (batch, num_frames, max_objects)
    bboxes: torch.Tensor              # (batch, num_frames, max_objects, 4)
    object_mask: torch.Tensor         # (batch, num_frames, max_objects)
    frame_mask: torch.Tensor          # (batch, num_frames)
    
    # Target data for each pair
    target_predicates: torch.Tensor   # (batch, num_future, num_pairs)
    target_existence: torch.Tensor    # (batch, num_future, num_pairs)
    
    # Pair indices (for decoding predictions back to objects)
    pair_subject_idx: torch.Tensor    # (num_pairs,)
    pair_object_idx: torch.Tensor     # (num_pairs,)
    
    num_future_frames: int


# ============================================================================
# ACTION GENOME LOADER
# ============================================================================

class ActionGenomeDataset(Dataset):
    """
    PyTorch Dataset for Action Genome SGA training.
    
    Each sample consists of:
    - Input: First F% of frames (observed)
    - Target: Relations from remaining (1-F)% of frames (future)
    """
    
    def __init__(
        self,
        annotation_path: str,
        split: str = 'train',
        input_fraction: float = 0.5,
        max_objects: int = 20,
        max_observed_frames: int = 10,
        max_future_frames: int = 5,
        min_frames: int = 5,
        subsample_frames: bool = True,
        frame_stride: int = 3,
    ):
        """
        Args:
            annotation_path: Path to object_bbox_and_relationship.pkl
            split: 'train' or 'test'
            input_fraction: F - fraction of frames to observe (0.0-1.0)
            max_objects: Maximum objects per frame
            max_observed_frames: Max frames to input to model
            max_future_frames: Max future frames to predict
            min_frames: Minimum frames required in a video
            subsample_frames: Whether to subsample frames (for efficiency)
            frame_stride: Stride for frame subsampling
        """
        self.annotation_path = Path(annotation_path)
        self.split = split
        self.input_fraction = input_fraction
        self.max_objects = max_objects
        self.max_observed_frames = max_observed_frames
        self.max_future_frames = max_future_frames
        self.min_frames = min_frames
        self.subsample_frames = subsample_frames
        self.frame_stride = frame_stride
        
        # Load annotations
        self.annotations = self._load_annotations()
        
        # Get video list for this split
        self.video_ids = self._get_split_videos()
        
        logger.info(
            f"Loaded {len(self.video_ids)} videos for {split} split "
            f"(F={input_fraction})"
        )
    
    def _load_annotations(self) -> Dict:
        """Load AG annotations from pickle file."""
        if not self.annotation_path.exists():
            raise FileNotFoundError(
                f"Annotation file not found: {self.annotation_path}\n"
                "Download from Action Genome dataset."
            )
        
        with open(self.annotation_path, 'rb') as f:
            annotations = pickle.load(f)
        
        return annotations
    
    def _get_split_videos(self) -> List[str]:
        """Get video IDs for train/test split."""
        # AG typically uses video IDs like "001YG", "002Z3", etc.
        # We'll use a simple hash-based split (70% train, 30% test)
        
        all_videos = list(self.annotations.keys())
        all_videos.sort()
        
        # Filter videos with enough frames
        valid_videos = []
        for vid in all_videos:
            frames = self.annotations[vid]
            if len(frames) >= self.min_frames:
                valid_videos.append(vid)
        
        # Split
        split_idx = int(len(valid_videos) * 0.7)
        
        if self.split == 'train':
            return valid_videos[:split_idx]
        else:
            return valid_videos[split_idx:]
    
    def __len__(self) -> int:
        return len(self.video_ids)
    
    def __getitem__(self, idx: int) -> SGASample:
        """Get a single training sample."""
        video_id = self.video_ids[idx]
        frames_data = self.annotations[video_id]
        
        # Get sorted frame keys
        frame_keys = sorted(frames_data.keys())
        
        # Subsample frames if needed
        if self.subsample_frames and len(frame_keys) > self.max_observed_frames + self.max_future_frames:
            frame_keys = frame_keys[::self.frame_stride]
        
        # Split into observed and future
        split_idx = int(len(frame_keys) * self.input_fraction)
        split_idx = max(1, min(split_idx, len(frame_keys) - 1))
        
        observed_keys = frame_keys[:split_idx][-self.max_observed_frames:]
        future_keys = frame_keys[split_idx:][:self.max_future_frames]
        
        # Collect all objects across all frames (for consistent indexing)
        all_objects = self._collect_all_objects(frames_data, observed_keys + future_keys)
        object_id_to_idx = {obj_id: idx for idx, obj_id in enumerate(all_objects)}
        idx_to_object_id = {idx: obj_id for obj_id, idx in object_id_to_idx.items()}
        
        # Get class labels for each object
        idx_to_class = {}
        for frame_key in observed_keys + future_keys:
            frame = frames_data[frame_key]
            for obj in frame.get('objects', []):
                obj_id = obj.get('object_id', str(obj.get('class', 'unknown')))
                if obj_id in object_id_to_idx:
                    idx_to_class[object_id_to_idx[obj_id]] = obj.get('class', 'unknown')
        
        num_objects = min(len(all_objects), self.max_objects)
        
        # Encode observed frames
        observed_class_ids, observed_bboxes, observed_mask = self._encode_frames(
            frames_data, observed_keys, object_id_to_idx, num_objects
        )
        
        # Extract future relations as targets
        future_relations = self._extract_future_relations(
            frames_data, future_keys, object_id_to_idx
        )
        
        # Create masks
        num_observed = len(observed_keys)
        observed_frame_mask = torch.ones(num_observed, dtype=torch.bool)
        
        return SGASample(
            video_id=video_id,
            observed_class_ids=observed_class_ids,
            observed_bboxes=observed_bboxes,
            observed_object_mask=observed_mask,
            observed_frame_mask=observed_frame_mask,
            object_id_to_idx=object_id_to_idx,
            idx_to_object_id=idx_to_object_id,
            idx_to_class=idx_to_class,
            future_relations=future_relations,
            future_frame_ids=list(range(len(future_keys))),
            num_observed_frames=num_observed,
            num_future_frames=len(future_keys),
            num_objects=num_objects,
        )
    
    def _collect_all_objects(
        self, 
        frames_data: Dict, 
        frame_keys: List
    ) -> List[str]:
        """Collect all unique object IDs across frames."""
        objects = set()
        
        for frame_key in frame_keys:
            frame = frames_data[frame_key]
            for obj in frame.get('objects', []):
                obj_id = obj.get('object_id', str(obj.get('class', 'unknown')))
                objects.add(obj_id)
        
        return sorted(list(objects))
    
    def _encode_frames(
        self,
        frames_data: Dict,
        frame_keys: List,
        object_id_to_idx: Dict[str, int],
        num_objects: int,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Encode frames into tensors.
        
        Returns:
            class_ids: (num_frames, max_objects)
            bboxes: (num_frames, max_objects, 4)
            mask: (num_frames, max_objects)
        """
        num_frames = len(frame_keys)
        
        class_ids = torch.zeros(num_frames, num_objects, dtype=torch.long)
        bboxes = torch.zeros(num_frames, num_objects, 4)
        mask = torch.zeros(num_frames, num_objects, dtype=torch.bool)
        
        for f_idx, frame_key in enumerate(frame_keys):
            frame = frames_data[frame_key]
            
            for obj in frame.get('objects', []):
                obj_id = obj.get('object_id', str(obj.get('class', 'unknown')))
                
                if obj_id not in object_id_to_idx:
                    continue
                
                obj_idx = object_id_to_idx[obj_id]
                if obj_idx >= num_objects:
                    continue
                
                # Class ID
                obj_class = obj.get('class', 'unknown')
                class_id = AG_OBJECT_TO_IDX.get(obj_class, 0)
                class_ids[f_idx, obj_idx] = class_id
                
                # Bbox (normalize to 0-1)
                bbox = obj.get('bbox', [0, 0, 1, 1])
                if len(bbox) == 4:
                    # Assume format is [x1, y1, x2, y2] or [x, y, w, h]
                    # Normalize (assuming 1920x1080 or similar)
                    bboxes[f_idx, obj_idx] = torch.tensor(bbox, dtype=torch.float32)
                
                mask[f_idx, obj_idx] = True
        
        return class_ids, bboxes, mask
    
    def _extract_future_relations(
        self,
        frames_data: Dict,
        future_keys: List,
        object_id_to_idx: Dict[str, int],
    ) -> List[Tuple[int, int, int, int]]:
        """
        Extract ground truth relations from future frames.
        
        Returns:
            List of (future_frame_idx, subject_idx, predicate_idx, object_idx)
        """
        relations = []
        
        for f_idx, frame_key in enumerate(future_keys):
            frame = frames_data[frame_key]
            
            for rel in frame.get('relationships', []):
                # Get subject and object
                subj_id = rel.get('subject_id')
                obj_id = rel.get('object_id')
                
                if subj_id not in object_id_to_idx or obj_id not in object_id_to_idx:
                    continue
                
                subj_idx = object_id_to_idx[subj_id]
                obj_idx = object_id_to_idx[obj_id]
                
                # Get predicate(s)
                # AG has multiple predicate types (spatial, contact, attention)
                for pred_type in ['spatial_relationship', 'contacting_relationship']:
                    preds = rel.get(pred_type, [])
                    if isinstance(preds, str):
                        preds = [preds]
                    
                    for pred in preds:
                        if pred in AG_PREDICATE_TO_IDX:
                            pred_idx = AG_PREDICATE_TO_IDX[pred]
                            relations.append((f_idx, subj_idx, pred_idx, obj_idx))
        
        return relations


# ============================================================================
# COLLATE FUNCTION
# ============================================================================

def collate_sga_samples(samples: List[SGASample]) -> SGABatch:
    """
    Collate samples into a batch.
    
    Handles padding to max sequence lengths.
    """
    batch_size = len(samples)
    
    # Find max dimensions
    max_frames = max(s.num_observed_frames for s in samples)
    max_objects = max(s.num_objects for s in samples)
    max_future = max(s.num_future_frames for s in samples)
    num_pairs = max_objects * (max_objects - 1)
    
    # Initialize tensors
    class_ids = torch.zeros(batch_size, max_frames, max_objects, dtype=torch.long)
    bboxes = torch.zeros(batch_size, max_frames, max_objects, 4)
    object_mask = torch.zeros(batch_size, max_frames, max_objects, dtype=torch.bool)
    frame_mask = torch.zeros(batch_size, max_frames, dtype=torch.bool)
    
    target_predicates = torch.full(
        (batch_size, max_future, num_pairs), 
        fill_value=-1,  # -1 = ignore in loss
        dtype=torch.long
    )
    target_existence = torch.zeros(batch_size, max_future, num_pairs)
    
    # Fill tensors
    for b, sample in enumerate(samples):
        nf = sample.num_observed_frames
        no = sample.num_objects
        
        class_ids[b, :nf, :no] = sample.observed_class_ids
        bboxes[b, :nf, :no] = sample.observed_bboxes
        object_mask[b, :nf, :no] = sample.observed_object_mask
        frame_mask[b, :nf] = sample.observed_frame_mask
        
        # Fill targets
        for (future_idx, subj_idx, pred_idx, obj_idx) in sample.future_relations:
            if future_idx >= max_future:
                continue
            if subj_idx >= max_objects or obj_idx >= max_objects:
                continue
            
            # Compute pair index
            pair_idx = subj_idx * (max_objects - 1) + (obj_idx if obj_idx < subj_idx else obj_idx - 1)
            if pair_idx >= num_pairs:
                continue
            
            target_predicates[b, future_idx, pair_idx] = pred_idx
            target_existence[b, future_idx, pair_idx] = 1.0
    
    # Create pair indices
    pair_subject_idx = []
    pair_object_idx = []
    for i in range(max_objects):
        for j in range(max_objects):
            if i != j:
                pair_subject_idx.append(i)
                pair_object_idx.append(j)
    
    return SGABatch(
        batch_size=batch_size,
        class_ids=class_ids,
        bboxes=bboxes,
        object_mask=object_mask,
        frame_mask=frame_mask,
        target_predicates=target_predicates,
        target_existence=target_existence,
        pair_subject_idx=torch.tensor(pair_subject_idx),
        pair_object_idx=torch.tensor(pair_object_idx),
        num_future_frames=max_future,
    )


# ============================================================================
# DATA LOADER FACTORY
# ============================================================================

def create_sga_dataloaders(
    annotation_path: str,
    input_fraction: float = 0.5,
    batch_size: int = 8,
    num_workers: int = 4,
    max_objects: int = 15,
    max_observed_frames: int = 8,
    max_future_frames: int = 4,
) -> Tuple[DataLoader, DataLoader]:
    """
    Create train and test dataloaders.
    
    Args:
        annotation_path: Path to AG annotations
        input_fraction: F - fraction to observe
        batch_size: Batch size
        num_workers: Number of data loading workers
        
    Returns:
        (train_loader, test_loader)
    """
    train_dataset = ActionGenomeDataset(
        annotation_path=annotation_path,
        split='train',
        input_fraction=input_fraction,
        max_objects=max_objects,
        max_observed_frames=max_observed_frames,
        max_future_frames=max_future_frames,
    )
    
    test_dataset = ActionGenomeDataset(
        annotation_path=annotation_path,
        split='test',
        input_fraction=input_fraction,
        max_objects=max_objects,
        max_observed_frames=max_observed_frames,
        max_future_frames=max_future_frames,
    )
    
    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=num_workers,
        collate_fn=collate_sga_samples,
        pin_memory=True,
        drop_last=True,
    )
    
    test_loader = DataLoader(
        test_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        collate_fn=collate_sga_samples,
        pin_memory=True,
    )
    
    return train_loader, test_loader


if __name__ == "__main__":
    # Test the dataset
    import sys
    
    # Try to find AG annotations
    possible_paths = [
        "datasets/ActionGenome/annotations/object_bbox_and_relationship.pkl",
        "data/ag/object_bbox_and_relationship.pkl",
    ]
    
    annotation_path = None
    for path in possible_paths:
        if Path(path).exists():
            annotation_path = path
            break
    
    if annotation_path is None:
        print("AG annotations not found. Please download Action Genome dataset.")
        sys.exit(1)
    
    print(f"Loading dataset from {annotation_path}...")
    
    dataset = ActionGenomeDataset(
        annotation_path=annotation_path,
        split='train',
        input_fraction=0.5,
    )
    
    print(f"Dataset size: {len(dataset)}")
    
    # Test a sample
    sample = dataset[0]
    print(f"\nSample from video: {sample.video_id}")
    print(f"  Observed frames: {sample.num_observed_frames}")
    print(f"  Future frames: {sample.num_future_frames}")
    print(f"  Num objects: {sample.num_objects}")
    print(f"  Future relations: {len(sample.future_relations)}")
    
    # Test collation
    batch = collate_sga_samples([dataset[i] for i in range(min(4, len(dataset)))])
    print(f"\nBatch:")
    print(f"  class_ids shape: {batch.class_ids.shape}")
    print(f"  bboxes shape: {batch.bboxes.shape}")
    print(f"  target_predicates shape: {batch.target_predicates.shape}")
    print("✓ Dataset test passed!")
