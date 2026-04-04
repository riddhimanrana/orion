"""
Part 2: Detection & Tracking for SGA

This module handles:
1. Object detection in observed video frames (GroundingDINO / YOLO)
2. Multi-object tracking across frames
3. Building tracked entity representations for scene graph generation

Supports three testing modes:
- AGS: Raw video detection (hardest, most realistic)
- PGAGS: Use GT boxes, detect classes
- GAGS: Use GT boxes + classes (easiest)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Sequence
from collections import defaultdict

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Lazy imports for heavy dependencies
_torch = None
_gdino = None
_yolo = None


def _get_torch():
    global _torch
    if _torch is None:
        import torch
        _torch = torch
    return _torch


def _get_device():
    """Get best available device."""
    torch = _get_torch()
    if torch.cuda.is_available():
        return "cuda"
    elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class Detection:
    """Single detection in a frame."""
    bbox: List[float]  # [x1, y1, x2, y2]
    label: str
    confidence: float
    frame_id: int
    embedding: Optional[np.ndarray] = None
    
    def center(self) -> Tuple[float, float]:
        """Get bbox center."""
        return (
            (self.bbox[0] + self.bbox[2]) / 2,
            (self.bbox[1] + self.bbox[3]) / 2
        )
    
    def area(self) -> float:
        """Get bbox area."""
        return max(0, self.bbox[2] - self.bbox[0]) * max(0, self.bbox[3] - self.bbox[1])


@dataclass
class TrackedEntity:
    """An entity tracked across multiple frames."""
    track_id: int
    label: str
    detections: Dict[int, Detection] = field(default_factory=dict)  # frame_id -> Detection
    
    def add_detection(self, det: Detection):
        """Add a detection to this track."""
        self.detections[det.frame_id] = det
    
    def get_frames(self) -> List[int]:
        """Get sorted list of frame IDs where this entity appears."""
        return sorted(self.detections.keys())
    
    def get_bbox_at(self, frame_id: int) -> Optional[List[float]]:
        """Get bbox at specific frame."""
        det = self.detections.get(frame_id)
        return det.bbox if det else None
    
    def get_velocity_at(self, frame_id: int) -> Optional[Tuple[float, float]]:
        """Compute velocity at a frame based on previous detection."""
        frames = self.get_frames()
        idx = frames.index(frame_id) if frame_id in frames else -1
        if idx <= 0:
            return None
        
        prev_frame = frames[idx - 1]
        curr_det = self.detections[frame_id]
        prev_det = self.detections[prev_frame]
        
        cx_curr, cy_curr = curr_det.center()
        cx_prev, cy_prev = prev_det.center()
        
        return (cx_curr - cx_prev, cy_curr - cy_prev)
    
    def first_frame(self) -> int:
        """Get first frame where entity appears."""
        return min(self.detections.keys()) if self.detections else -1
    
    def last_frame(self) -> int:
        """Get last frame where entity appears."""
        return max(self.detections.keys()) if self.detections else -1
    
    def lifespan(self) -> int:
        """Get number of frames this entity spans."""
        return len(self.detections)


@dataclass
class FrameDetections:
    """All detections in a single frame."""
    frame_id: int
    detections: List[Detection] = field(default_factory=list)
    image: Optional[np.ndarray] = None  # BGR frame (optional)
    
    def get_by_label(self, label: str) -> List[Detection]:
        """Get detections with specific label."""
        return [d for d in self.detections if d.label == label]


@dataclass
class TrackingResult:
    """Result of detection + tracking on observed frames."""
    video_id: str
    entities: Dict[int, TrackedEntity]  # track_id -> TrackedEntity
    frame_detections: Dict[int, FrameDetections]  # frame_id -> FrameDetections
    
    def get_entities_at_frame(self, frame_id: int) -> List[TrackedEntity]:
        """Get all entities present in a frame."""
        return [e for e in self.entities.values() if frame_id in e.detections]
    
    def get_entity_pairs_at_frame(self, frame_id: int) -> List[Tuple[TrackedEntity, TrackedEntity]]:
        """Get all entity pairs at a frame (for relation generation)."""
        entities = self.get_entities_at_frame(frame_id)
        pairs = []
        for i, e1 in enumerate(entities):
            for e2 in entities[i+1:]:
                pairs.append((e1, e2))
                pairs.append((e2, e1))  # Both directions
        return pairs
    
    def num_tracks(self) -> int:
        return len(self.entities)
    
    def num_frames(self) -> int:
        return len(self.frame_detections)


# ============================================================================
# ACTION GENOME VOCABULARY
# ============================================================================

# Action Genome object classes (from Charades dataset)
AG_OBJECT_CLASSES = [
    'person', 'bag', 'bed', 'blanket', 'book', 'box', 'broom', 'chair',
    'closet', 'clothes', 'cup', 'dish', 'door', 'doorknob', 'doorway',
    'floor', 'food', 'groceries', 'laptop', 'light', 'medicine', 'mirror',
    'paper', 'phone', 'picture', 'pillow', 'refrigerator', 'sandwich',
    'shelf', 'shoe', 'sofa', 'table', 'television', 'towel', 'vacuum',
    'window'
]


def build_ag_detection_prompt(classes: Optional[List[str]] = None) -> str:
    """
    Build detection prompt for Action Genome classes.
    
    GroundingDINO expects a period-separated string of class names.
    """
    if classes is None:
        classes = AG_OBJECT_CLASSES
    return ". ".join(classes) + "."


# ============================================================================
# SIMPLE IOU TRACKER
# ============================================================================

class SimpleIOUTracker:
    """
    Simple IoU-based multi-object tracker.
    
    Matches detections across frames using IoU + class label.
    """
    
    def __init__(
        self,
        iou_threshold: float = 0.3,
        max_age: int = 30,
        min_hits: int = 1,
    ):
        """
        Args:
            iou_threshold: Minimum IoU for matching
            max_age: Max frames a track can be unmatched before deletion
            min_hits: Minimum detections to confirm a track
        """
        self.iou_threshold = iou_threshold
        self.max_age = max_age
        self.min_hits = min_hits
        
        self.tracks: Dict[int, TrackedEntity] = {}
        self.next_id = 1
        self.track_ages: Dict[int, int] = {}  # frames since last match
    
    def reset(self):
        """Reset tracker state."""
        self.tracks = {}
        self.next_id = 1
        self.track_ages = {}
    
    def update(self, detections: List[Detection]) -> List[Tuple[Detection, int]]:
        """
        Update tracks with new detections.
        
        Args:
            detections: List of detections in current frame
            
        Returns:
            List of (detection, track_id) tuples
        """
        if not detections:
            # Age all tracks
            self._age_tracks()
            return []
        
        frame_id = detections[0].frame_id
        matched = []
        unmatched_dets = list(detections)
        matched_track_ids = set()
        
        # Match detections to existing tracks
        for det in detections:
            best_iou = 0
            best_track_id = None
            
            for track_id, track in self.tracks.items():
                # Must match label
                if track.label != det.label:
                    continue
                
                # Get most recent bbox from track
                track_frames = track.get_frames()
                if not track_frames:
                    continue
                
                last_frame = max(track_frames)
                last_bbox = track.get_bbox_at(last_frame)
                if last_bbox is None:
                    continue
                
                iou = self._calc_iou(det.bbox, last_bbox)
                if iou > best_iou and iou > self.iou_threshold:
                    best_iou = iou
                    best_track_id = track_id
            
            if best_track_id is not None and best_track_id not in matched_track_ids:
                # Match found
                self.tracks[best_track_id].add_detection(det)
                self.track_ages[best_track_id] = 0
                matched.append((det, best_track_id))
                matched_track_ids.add(best_track_id)
                unmatched_dets.remove(det)
        
        # Create new tracks for unmatched detections
        for det in unmatched_dets:
            track_id = self.next_id
            self.next_id += 1
            
            track = TrackedEntity(track_id=track_id, label=det.label)
            track.add_detection(det)
            self.tracks[track_id] = track
            self.track_ages[track_id] = 0
            matched.append((det, track_id))
        
        # Age unmatched tracks
        self._age_tracks(exclude=matched_track_ids)
        
        return matched
    
    def _age_tracks(self, exclude: Optional[set] = None):
        """Age tracks and remove old ones."""
        exclude = exclude or set()
        to_remove = []
        
        for track_id in self.tracks:
            if track_id not in exclude:
                self.track_ages[track_id] = self.track_ages.get(track_id, 0) + 1
                if self.track_ages[track_id] > self.max_age:
                    to_remove.append(track_id)
        
        for track_id in to_remove:
            del self.tracks[track_id]
            del self.track_ages[track_id]
    
    def get_tracks(self, min_length: int = 1) -> Dict[int, TrackedEntity]:
        """Get all tracks with at least min_length detections."""
        return {
            tid: track for tid, track in self.tracks.items()
            if track.lifespan() >= min_length
        }
    
    @staticmethod
    def _calc_iou(box1: List[float], box2: List[float]) -> float:
        """Calculate IoU between two boxes [x1, y1, x2, y2]."""
        x1 = max(box1[0], box2[0])
        y1 = max(box1[1], box2[1])
        x2 = min(box1[2], box2[2])
        y2 = min(box1[3], box2[3])
        
        inter = max(0, x2 - x1) * max(0, y2 - y1)
        area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
        area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
        union = area1 + area2 - inter
        
        return inter / union if union > 0 else 0


# ============================================================================
# DETECTOR WRAPPER
# ============================================================================

class SGADetector:
    """
    Unified detector for SGA pipeline.
    
    Supports:
    - GroundingDINO (zero-shot, preferred)
    - YOLO-World (fallback)
    - Ground truth boxes (GAGS/PGAGS modes)
    """
    
    def __init__(
        self,
        backend: str = "auto",  # "grounding_dino", "yolo", "auto"
        device: Optional[str] = None,
        conf_threshold: float = 0.25,
        classes: Optional[List[str]] = None,
    ):
        """
        Args:
            backend: Detection backend to use
            device: Torch device
            conf_threshold: Detection confidence threshold
            classes: Object classes to detect (default: AG classes)
        """
        self.backend = backend
        self.device = device or _get_device()
        self.conf_threshold = conf_threshold
        self.classes = classes or AG_OBJECT_CLASSES
        
        self._detector = None
        self._backend_name = None
    
    def _init_detector(self):
        """Lazy initialization of detector."""
        if self._detector is not None:
            return
        
        # Try GroundingDINO first
        if self.backend in ("auto", "grounding_dino"):
            try:
                from orion.perception.detectors.grounding_dino import GroundingDINOWrapper
                # Note: MPS has issues with GroundingDINO, use CPU
                gdino_device = "cpu" if self.device == "mps" else self.device
                self._detector = GroundingDINOWrapper(
                    model_id="IDEA-Research/grounding-dino-base",
                    device=gdino_device,
                    use_half_precision=False,
                )
                self._backend_name = "grounding_dino"
                logger.info(f"✓ Initialized GroundingDINO on {gdino_device}")
                return
            except Exception as e:
                logger.warning(f"GroundingDINO init failed: {e}")
        
        # Try YOLO-World
        if self.backend in ("auto", "yolo"):
            try:
                from ultralytics import YOLOWorld
                self._detector = YOLOWorld("yolov8x-worldv2.pt")
                self._detector.to(self.device)
                self._detector.set_classes(self.classes)
                self._backend_name = "yolo"
                logger.info(f"✓ Initialized YOLO-World on {self.device}")
                return
            except Exception as e:
                logger.warning(f"YOLO-World init failed: {e}")
        
        raise RuntimeError("No detection backend available!")
    
    def detect_frame(self, frame_bgr: np.ndarray, frame_id: int) -> List[Detection]:
        """
        Detect objects in a single frame.
        
        Args:
            frame_bgr: BGR image (OpenCV format)
            frame_id: Frame index
            
        Returns:
            List of Detection objects
        """
        self._init_detector()
        
        detections = []
        
        if self._backend_name == "grounding_dino":
            prompt = build_ag_detection_prompt(self.classes)
            raw_dets = self._detector.detect(
                frame_bgr=frame_bgr,
                prompt=prompt,
                box_threshold=self.conf_threshold,
                text_threshold=self.conf_threshold,
                max_detections=50,
            )
            for d in raw_dets:
                detections.append(Detection(
                    bbox=d['bbox'],
                    label=d['label'],
                    confidence=d['confidence'],
                    frame_id=frame_id,
                ))
        
        elif self._backend_name == "yolo":
            results = self._detector.predict(
                source=frame_bgr,
                conf=self.conf_threshold,
                device=self.device,
                verbose=False,
            )
            for result in results:
                boxes = result.boxes
                if boxes is None:
                    continue
                for i in range(len(boxes)):
                    detections.append(Detection(
                        bbox=boxes.xyxy[i].tolist(),
                        label=result.names[int(boxes.cls[i].item())],
                        confidence=float(boxes.conf[i]),
                        frame_id=frame_id,
                    ))
        
        return detections


# ============================================================================
# MAIN DETECTION + TRACKING PIPELINE
# ============================================================================

class SGADetectionPipeline:
    """
    Full detection and tracking pipeline for SGA.
    
    Takes video frames → outputs tracked entities ready for SGG.
    """
    
    def __init__(
        self,
        detector: Optional[SGADetector] = None,
        tracker: Optional[SimpleIOUTracker] = None,
        target_fps: float = 5.0,
        conf_threshold: float = 0.25,
    ):
        """
        Args:
            detector: Detector to use (created if None)
            tracker: Tracker to use (created if None)
            target_fps: Target frame rate for sampling
            conf_threshold: Detection confidence threshold
        """
        self.detector = detector or SGADetector(conf_threshold=conf_threshold)
        self.tracker = tracker or SimpleIOUTracker()
        self.target_fps = target_fps
    
    def process_video(
        self,
        video_path: str,
        start_frame: int = 0,
        end_frame: Optional[int] = None,
        video_id: Optional[str] = None,
    ) -> TrackingResult:
        """
        Process video file with detection + tracking.
        
        Args:
            video_path: Path to video file
            start_frame: First frame to process
            end_frame: Last frame to process (None = all)
            video_id: Video identifier (default: filename)
            
        Returns:
            TrackingResult with tracked entities
        """
        video_path = Path(video_path)
        video_id = video_id or video_path.stem
        
        logger.info(f"Processing video: {video_path}")
        
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")
        
        video_fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frame_interval = max(1, int(video_fps / self.target_fps))
        
        if end_frame is None:
            end_frame = total_frames
        
        logger.info(f"Video FPS: {video_fps:.1f}, sampling every {frame_interval} frames")
        logger.info(f"Processing frames {start_frame} to {end_frame}")
        
        # Reset tracker
        self.tracker.reset()
        
        frame_detections: Dict[int, FrameDetections] = {}
        frame_idx = 0
        processed = 0
        
        while frame_idx < end_frame:
            ret, frame = cap.read()
            if not ret:
                break
            
            if frame_idx >= start_frame and frame_idx % frame_interval == 0:
                # Detect
                detections = self.detector.detect_frame(frame, frame_idx)
                
                # Track
                matched = self.tracker.update(detections)
                
                # Store frame detections
                frame_detections[frame_idx] = FrameDetections(
                    frame_id=frame_idx,
                    detections=detections,
                )
                
                processed += 1
                if processed % 20 == 0:
                    logger.info(f"Processed {processed} frames, {len(self.tracker.tracks)} active tracks")
            
            frame_idx += 1
        
        cap.release()
        
        # Get final tracks
        entities = self.tracker.get_tracks(min_length=1)
        
        logger.info(f"✓ Detection complete: {len(entities)} tracks across {len(frame_detections)} frames")
        
        return TrackingResult(
            video_id=video_id,
            entities=entities,
            frame_detections=frame_detections,
        )
    
    def process_frames(
        self,
        frames: List[np.ndarray],
        frame_ids: List[int],
        video_id: str = "unknown",
    ) -> TrackingResult:
        """
        Process pre-loaded frames with detection + tracking.
        
        Args:
            frames: List of BGR images
            frame_ids: List of frame IDs corresponding to each frame
            video_id: Video identifier
            
        Returns:
            TrackingResult with tracked entities
        """
        logger.info(f"Processing {len(frames)} frames for video {video_id}")
        
        # Reset tracker
        self.tracker.reset()
        
        frame_detections: Dict[int, FrameDetections] = {}
        
        for frame, frame_id in zip(frames, frame_ids):
            # Detect
            detections = self.detector.detect_frame(frame, frame_id)
            
            # Track
            self.tracker.update(detections)
            
            # Store
            frame_detections[frame_id] = FrameDetections(
                frame_id=frame_id,
                detections=detections,
            )
        
        entities = self.tracker.get_tracks(min_length=1)
        
        logger.info(f"✓ Detection complete: {len(entities)} tracks across {len(frame_detections)} frames")
        
        return TrackingResult(
            video_id=video_id,
            entities=entities,
            frame_detections=frame_detections,
        )
    
    def process_with_gt_boxes(
        self,
        frames: List[np.ndarray],
        gt_boxes_per_frame: Dict[int, List[Dict]],
        video_id: str = "unknown",
        mode: str = "gags",  # "gags" or "pgags"
    ) -> TrackingResult:
        """
        Process frames using ground truth boxes (GAGS/PGAGS modes).
        
        Args:
            frames: List of BGR images
            gt_boxes_per_frame: Dict of frame_id -> list of {bbox, label, object_id}
            video_id: Video identifier
            mode: "gags" (GT boxes + labels) or "pgags" (GT boxes only)
            
        Returns:
            TrackingResult with tracked entities
        """
        logger.info(f"Processing {len(frames)} frames in {mode.upper()} mode")
        
        entities: Dict[int, TrackedEntity] = {}
        frame_detections: Dict[int, FrameDetections] = {}
        
        for frame_idx, frame in enumerate(frames):
            if frame_idx not in gt_boxes_per_frame:
                continue
            
            gt_boxes = gt_boxes_per_frame[frame_idx]
            detections = []
            
            for gt in gt_boxes:
                bbox = gt['bbox']
                obj_id = gt.get('object_id', len(entities))
                
                if mode == "gags":
                    # Use GT label
                    label = gt['label']
                else:
                    # PGAGS: detect label from crop
                    x1, y1, x2, y2 = [int(c) for c in bbox]
                    crop = frame[y1:y2, x1:x2]
                    if crop.size > 0:
                        # Run detector on crop to get label
                        crop_dets = self.detector.detect_frame(crop, frame_idx)
                        label = crop_dets[0].label if crop_dets else "unknown"
                    else:
                        label = "unknown"
                
                det = Detection(
                    bbox=bbox,
                    label=label,
                    confidence=1.0,
                    frame_id=frame_idx,
                )
                detections.append(det)
                
                # Add to entity
                if obj_id not in entities:
                    entities[obj_id] = TrackedEntity(track_id=obj_id, label=label)
                entities[obj_id].add_detection(det)
            
            frame_detections[frame_idx] = FrameDetections(
                frame_id=frame_idx,
                detections=detections,
            )
        
        logger.info(f"✓ GT processing complete: {len(entities)} entities")
        
        return TrackingResult(
            video_id=video_id,
            entities=entities,
            frame_detections=frame_detections,
        )


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def extract_video_frames(
    video_path: str,
    frame_ids: Optional[List[int]] = None,
    target_fps: Optional[float] = None,
) -> Tuple[List[np.ndarray], List[int]]:
    """
    Extract frames from video.
    
    Args:
        video_path: Path to video file
        frame_ids: Specific frame IDs to extract (None = all based on fps)
        target_fps: Target FPS for sampling (ignored if frame_ids provided)
        
    Returns:
        (frames, frame_ids) tuple
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {video_path}")
    
    video_fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    if frame_ids is None:
        if target_fps:
            interval = max(1, int(video_fps / target_fps))
            frame_ids = list(range(0, total_frames, interval))
        else:
            frame_ids = list(range(total_frames))
    
    frames = []
    extracted_ids = []
    
    for fid in frame_ids:
        cap.set(cv2.CAP_PROP_POS_FRAMES, fid)
        ret, frame = cap.read()
        if ret:
            frames.append(frame)
            extracted_ids.append(fid)
    
    cap.release()
    return frames, extracted_ids


# ============================================================================
# CLI TESTING
# ============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test SGA Detection + Tracking")
    parser.add_argument("--video", required=True, help="Path to video file")
    parser.add_argument("--max-frames", type=int, default=50, help="Max frames to process")
    parser.add_argument("--conf", type=float, default=0.25, help="Detection confidence")
    parser.add_argument("--fps", type=float, default=5.0, help="Target FPS")
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    print(f"\n{'='*60}")
    print("PART 2: SGA DETECTION + TRACKING TEST")
    print(f"{'='*60}\n")
    
    # Create pipeline
    pipeline = SGADetectionPipeline(
        target_fps=args.fps,
        conf_threshold=args.conf,
    )
    
    # Process video
    result = pipeline.process_video(
        video_path=args.video,
        end_frame=args.max_frames,
    )
    
    # Print results
    print(f"\n--- Results ---")
    print(f"Video: {result.video_id}")
    print(f"Frames processed: {result.num_frames()}")
    print(f"Tracks found: {result.num_tracks()}")
    
    print(f"\n--- Track Details ---")
    for track_id, entity in list(result.entities.items())[:10]:
        frames = entity.get_frames()
        print(f"  Track {track_id}: {entity.label} ({entity.lifespan()} detections, frames {min(frames)}-{max(frames)})")
    
    # Sample frame analysis
    if result.frame_detections:
        sample_frame = list(result.frame_detections.keys())[0]
        frame_dets = result.frame_detections[sample_frame]
        print(f"\n--- Sample Frame {sample_frame} ---")
        print(f"  Detections: {len(frame_dets.detections)}")
        for det in frame_dets.detections[:5]:
            print(f"    - {det.label}: conf={det.confidence:.2f}, bbox={[int(b) for b in det.bbox]}")
    
    print(f"\n{'='*60}")
    print("PART 2 COMPLETE ✓")
    print(f"{'='*60}\n")
