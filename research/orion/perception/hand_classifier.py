"""Hand classification + keypoint extraction using MediaPipe."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class HandClassifier:
    """Thin wrapper around MediaPipe Hands for per-frame detections."""

    def __init__(
        self,
        max_hands: int = 2,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.3,
        model_complexity: int = 1,
    ) -> None:
        try:
            import mediapipe as mp  # type: ignore
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise ImportError(
                "mediapipe is required for HandClassifier. Install with `pip install mediapipe`."
            ) from exc

        self._mp = mp
        self._hands = mp.solutions.hands.Hands(
            static_image_mode=False,
            max_num_hands=max_hands,
            model_complexity=model_complexity,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )
        self.max_hands = max_hands
        self.min_detection_confidence = min_detection_confidence
        self.min_tracking_confidence = min_tracking_confidence
        self.model_complexity = model_complexity

    def close(self) -> None:
        if self._hands:
            self._hands.close()
            self._hands = None

    def __del__(self) -> None:  # pragma: no cover - destructor safety
        self.close()

    def _landmarks_to_bbox(
        self,
        landmarks: Any,
        width: int,
        height: int,
    ) -> Dict[str, Any]:
        xs = [lm.x * width for lm in landmarks]
        ys = [lm.y * height for lm in landmarks]
        x_min, x_max = float(np.clip(min(xs), 0, width - 1)), float(np.clip(max(xs), 0, width - 1))
        y_min, y_max = float(np.clip(min(ys), 0, height - 1)), float(np.clip(max(ys), 0, height - 1))
        bbox = [x_min, y_min, x_max, y_max]
        centroid = [float(0.5 * (x_min + x_max)), float(0.5 * (y_min + y_max))]
        keypoints = [[float(x), float(y)] for x, y in zip(xs, ys)]
        return {"bbox": bbox, "centroid": centroid, "hand_keypoints": keypoints}

    def detect_frame(
        self,
        frame: np.ndarray,
        frame_idx: int,
        timestamp: float,
    ) -> List[Dict[str, Any]]:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self._hands.process(rgb)
        detections: List[Dict[str, Any]] = []
        if not results.multi_hand_landmarks:
            return detections

        handedness = results.multi_handedness or []
        height, width = frame.shape[:2]

        for idx, hand_landmarks in enumerate(results.multi_hand_landmarks):
            converted = self._landmarks_to_bbox(hand_landmarks.landmark, width, height)
            score = self.min_detection_confidence
            label = "unknown"
            if handedness and idx < len(handedness):
                cl = handedness[idx].classification[0]
                score = float(cl.score)
                label = cl.label

            det = {
                "bbox": converted["bbox"],
                "centroid": converted["centroid"],
                "category": "hand",
                "confidence": float(score),
                "frame_id": frame_idx,
                "timestamp": timestamp,
                "frame_width": width,
                "frame_height": height,
                "hand_keypoints": converted["hand_keypoints"],
                "handedness": label.lower(),
            }
            detections.append(det)
        return detections

    def detect_video(
        self,
        video_path: str | Path,
        target_fps: Optional[float] = None,
        max_frames: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise ValueError(f"Cannot open video for hand classification: {video_path}")

        original_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        if target_fps is None or target_fps >= original_fps:
            sample_rate = 1
            effective_fps = original_fps
        else:
            sample_rate = max(1, int(round(original_fps / target_fps)))
            effective_fps = original_fps / sample_rate

        logger.info(
            "HandClassifier: processing every %s frame(s) → %.2ffps",
            sample_rate,
            effective_fps,
        )

        frame_idx = 0
        processed = 0
        detections: List[Dict[str, Any]] = []

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % sample_rate == 0:
                timestamp = frame_idx / original_fps
                detections.extend(self.detect_frame(frame, frame_idx, timestamp))
                processed += 1
                if max_frames is not None and processed >= max_frames:
                    break
            frame_idx += 1

        cap.release()
        return detections

    def get_model_info(self) -> Dict[str, Any]:
        return {
            "backend": "mediapipe-hands",
            "max_hands": self.max_hands,
            "min_detection_confidence": self.min_detection_confidence,
            "min_tracking_confidence": self.min_tracking_confidence,
            "model_complexity": self.model_complexity,
        }
