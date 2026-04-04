"""
Base Tracker Protocol & Utilities
=================================

Defines the interface for all trackers and provides common motion utilities.
"""

import math
from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Dict, List, Optional, Protocol, Sequence, Tuple, Union

import numpy as np

Vector2 = Tuple[float, float]
BBox = Sequence[Union[float, int]]


class TrackerProtocol(Protocol):
    """Minimal protocol all trackers should satisfy."""

    def update(
        self,
        detections: List[Dict],
        embeddings: Optional[List[np.ndarray]] = None,
        camera_pose: Optional[np.ndarray] = None,
        frame_idx: int = 0,
    ) -> List[Any]:
        """Update tracker state with detections for a single frame.

        Returns a list of confirmed track objects (implementation-defined).
        """
        ...

    def get_statistics(self) -> Dict:
        """Return tracker stats for monitoring/telemetry."""
        ...


def bbox_to_centroid(bbox: BBox) -> Vector2:
    x1, y1, x2, y2 = map(float, bbox)
    return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)


def bbox_area(bbox: BBox) -> float:
    x1, y1, x2, y2 = map(float, bbox)
    return max(0.0, x2 - x1) * max(0.0, y2 - y1)


def bbox_overlap_area(box_a: BBox, box_b: BBox) -> float:
    ax1, ay1, ax2, ay2 = map(float, box_a)
    bx1, by1, bx2, by2 = map(float, box_b)
    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)
    if inter_x2 <= inter_x1 or inter_y2 <= inter_y1:
        return 0.0
    return (inter_x2 - inter_x1) * (inter_y2 - inter_y1)


def calculate_distance(point_a: Vector2, point_b: Vector2) -> float:
    return math.hypot(point_a[0] - point_b[0], point_a[1] - point_b[1])


@dataclass
class MotionData:
    centroid: Vector2
    velocity: Vector2
    speed: float
    direction: float
    timestamp: float

    def is_moving_towards(
        self,
        target: Vector2,
        angle_threshold: float = math.pi / 4,
        min_speed: float = 0.5,
    ) -> bool:
        if self.speed < min_speed:
            return False
        dx = target[0] - self.centroid[0]
        dy = target[1] - self.centroid[1]
        distance = math.hypot(dx, dy)
        if distance == 0.0:
            return True
        dot = self.velocity[0] * dx + self.velocity[1] * dy
        cos_angle = dot / (self.speed * distance)
        cos_angle = max(-1.0, min(1.0, cos_angle))
        angle = math.acos(cos_angle)
        return angle <= angle_threshold


class MotionTracker:
    """Simple centroid-based motion tracker with sliding-window smoothing."""

    def __init__(self, smoothing_window: int = 5):
        self.smoothing_window = max(1, int(smoothing_window))
        self.history: Dict[str, Deque[Tuple[float, Vector2]]] = {}
        self._last_motion: Dict[str, MotionData] = {}

    def update(self, object_id: str, timestamp: float, bbox: BBox) -> MotionData:
        centroid = bbox_to_centroid(bbox)
        history = self.history.setdefault(object_id, deque(maxlen=self.smoothing_window))
        history.append((timestamp, centroid))

        if len(history) < 2:
            motion = MotionData(centroid=centroid, velocity=(0.0, 0.0), speed=0.0, direction=0.0, timestamp=timestamp)
            self._last_motion[object_id] = motion
            return motion

        oldest_ts, oldest_centroid = history[0]
        newest_ts, newest_centroid = history[-1]
        dt = max(newest_ts - oldest_ts, 1e-6)
        velocity = (
            (newest_centroid[0] - oldest_centroid[0]) / dt,
            (newest_centroid[1] - oldest_centroid[1]) / dt,
        )
        speed = math.hypot(*velocity)
        direction = math.atan2(velocity[1], velocity[0]) if speed > 0 else 0.0
        motion = MotionData(centroid=centroid, velocity=velocity, speed=speed, direction=direction, timestamp=timestamp)
        self._last_motion[object_id] = motion
        return motion

    def get_motion_at_time(self, object_id: str) -> Optional[MotionData]:
        return self._last_motion.get(object_id)
