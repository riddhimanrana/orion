"""
YOLO Detection Wrapper
======================

Clean wrapper around YOLO11 for object detection with batch processing,
frame sampling, and standardized output format.

Usage:
    detector = YOLODetector(model_path="models/yolo11m.pt")
    detections = detector.detect_video("video.mp4", target_fps=5)
"""

import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import cv2

logger = logging.getLogger(__name__)


class YOLODetector:
    """
    YOLO11 detector with video processing capabilities.
    
    Features:
    - Automatic frame sampling to target FPS
    - Batch processing for efficiency
    - Confidence filtering
    - Class filtering
    - Progress tracking
    """
    
    def __init__(
        self,
        model_path: Optional[str] = None,
        model_name: str = "yolo11m",
        confidence_threshold: float = 0.25,
        device: str = "mps",
        batch_size: int = 8,
    ):
        """
        Initialize YOLO detector.
        
        Args:
            model_path: Path to YOLO weights file (if None, auto-downloads)
            model_name: YOLO variant (yolo11n/s/m/x)
            confidence_threshold: Minimum detection confidence (0-1)
            device: Device to run on ('cuda', 'mps', 'cpu')
            batch_size: Number of frames to process in batch
        """
        self.model_name = model_name
        self.confidence_threshold = confidence_threshold
        self.device = device
        self.batch_size = batch_size
        
        # Load YOLO model
        try:
            from ultralytics import YOLO
            
            if model_path is None:
                # Auto-download from ultralytics
                logger.info(f"Loading {model_name}...")
                self.model = YOLO(f"{model_name}.pt")
            else:
                logger.info(f"Loading YOLO from {model_path}...")
                self.model = YOLO(model_path)
            
            # Move to device
            self.model.to(device)
            
            logger.info(f"✓ YOLO loaded on {device}")
            
        except Exception as e:
            logger.error(f"Failed to load YOLO: {e}")
            raise
        
        # Get class names
        self.class_names = self.model.names
        logger.info(f"  Loaded {len(self.class_names)} object classes")
    
    def detect_frame(
        self,
        frame: np.ndarray,
        frame_idx: int = 0,
        timestamp: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """
        Detect objects in a single frame.
        
        Args:
            frame: Input frame (H, W, 3) BGR
            frame_idx: Frame number
            timestamp: Time in seconds
            
        Returns:
            List of detection dicts with keys:
                - bbox: [x1, y1, x2, y2]
                - centroid: [x, y]
                - category: str
                - confidence: float
                - frame_id: int
                - timestamp: float
        """
        results = self.model(frame, verbose=False)[0]
        
        detections = []
        boxes = results.boxes
        
        for i in range(len(boxes)):
            conf = float(boxes.conf[i])
            
            # Filter by confidence
            if conf < self.confidence_threshold:
                continue
            
            # Get bbox coordinates
            x1, y1, x2, y2 = boxes.xyxy[i].cpu().numpy()
            
            # Get class
            cls_id = int(boxes.cls[i])
            category = self.class_names[cls_id]
            
            # Compute centroid
            cx = (x1 + x2) / 2.0
            cy = (y1 + y2) / 2.0
            
            detection = {
                "bbox": [float(x1), float(y1), float(x2), float(y2)],
                "centroid": [float(cx), float(cy)],
                "category": category,
                "confidence": conf,
                "frame_id": frame_idx,
                "timestamp": timestamp,
                "frame_width": frame.shape[1],
                "frame_height": frame.shape[0],
            }
            
            detections.append(detection)
        
        return detections
    
    def detect_video(
        self,
        video_path: str,
        target_fps: Optional[float] = None,
        max_frames: Optional[int] = None,
        show_progress: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Detect objects in video with frame sampling.
        
        Args:
            video_path: Path to video file
            target_fps: Target FPS for processing (None = use original)
            max_frames: Maximum frames to process (None = all)
            show_progress: Show progress bar
            
        Returns:
            List of all detections across frames
        """
        cap = cv2.VideoCapture(video_path)
        
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")
        
        # Get video properties
        original_fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        logger.info(f"Video: {width}x{height} @ {original_fps:.1f}fps, {total_frames} frames")
        
        # Determine sampling rate
        if target_fps is None or target_fps >= original_fps:
            sample_rate = 1
            effective_fps = original_fps
        else:
            sample_rate = int(original_fps / target_fps)
            effective_fps = original_fps / sample_rate
        
        logger.info(f"Processing every {sample_rate} frame(s) → {effective_fps:.1f}fps")
        
        # Limit frames if requested
        if max_frames is not None:
            total_frames = min(total_frames, max_frames * sample_rate)
        
        all_detections = []
        frame_idx = 0
        processed_count = 0
        
        # Progress bar
        if show_progress:
            try:
                from tqdm import tqdm
                pbar = tqdm(total=total_frames // sample_rate, desc="Detecting")
            except ImportError:
                pbar = None
        else:
            pbar = None
        
        while True:
            ret, frame = cap.read()
            
            if not ret:
                break
            
            # Sample frames
            if frame_idx % sample_rate == 0:
                timestamp = frame_idx / original_fps
                
                # Detect in frame
                detections = self.detect_frame(frame, frame_idx, timestamp)
                all_detections.extend(detections)
                
                processed_count += 1
                
                if pbar is not None:
                    pbar.update(1)
                
                if max_frames is not None and processed_count >= max_frames:
                    break
            
            frame_idx += 1
        
        cap.release()
        
        if pbar is not None:
            pbar.close()
        
        logger.info(f"✓ Detected {len(all_detections)} objects in {processed_count} frames")
        
        return all_detections
    
    def detect_batch(
        self,
        frames: List[np.ndarray],
        frame_indices: List[int],
        timestamps: List[float],
    ) -> List[Dict[str, Any]]:
        """
        Detect objects in batch of frames (more efficient).
        
        Args:
            frames: List of frames
            frame_indices: Frame numbers
            timestamps: Timestamps in seconds
            
        Returns:
            List of all detections
        """
        # Batch inference
        results = self.model(frames, verbose=False)
        
        all_detections = []
        
        for i, (result, frame_idx, timestamp) in enumerate(zip(results, frame_indices, timestamps)):
            boxes = result.boxes
            frame_h, frame_w = frames[i].shape[:2]
            
            for j in range(len(boxes)):
                conf = float(boxes.conf[j])
                
                if conf < self.confidence_threshold:
                    continue
                
                x1, y1, x2, y2 = boxes.xyxy[j].cpu().numpy()
                cls_id = int(boxes.cls[j])
                category = self.class_names[cls_id]
                
                cx = (x1 + x2) / 2.0
                cy = (y1 + y2) / 2.0
                
                detection = {
                    "bbox": [float(x1), float(y1), float(x2), float(y2)],
                    "centroid": [float(cx), float(cy)],
                    "category": category,
                    "confidence": conf,
                    "frame_id": frame_idx,
                    "timestamp": timestamp,
                    "frame_width": frame_w,
                    "frame_height": frame_h,
                }
                
                all_detections.append(detection)
        
        return all_detections
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get model information."""
        return {
            "model_name": self.model_name,
            "num_classes": len(self.class_names),
            "confidence_threshold": self.confidence_threshold,
            "device": self.device,
            "batch_size": self.batch_size,
        }
