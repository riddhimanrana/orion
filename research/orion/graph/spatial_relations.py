"""
Spatial Relations Engine
========================

3D-aware spatial relationship computation using depth and tracking data.

This module provides:
1. 3D spatial predicates (ON, NEAR, INSIDE, ABOVE, BELOW)
2. Relationship stability tracking (cooling period before committing)
3. Integration with CIS for causal edges

Coordinate System:
- X: horizontal (left → right)
- Y: vertical (top → bottom in image, but up in 3D world)
- Z: depth (near → far)
- All units in millimeters (mm)
"""

import numpy as np
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class SpatialPredicate(Enum):
    """Types of spatial relationships."""
    NEAR = "near"
    ON = "on"
    INSIDE = "inside"
    ABOVE = "above"
    BELOW = "below"
    LEFT_OF = "left_of"
    RIGHT_OF = "right_of"
    IN_FRONT_OF = "in_front_of"
    BEHIND = "behind"
    TOUCHING = "touching"
    HELD_BY = "held_by"
    CONTAINS = "contains"


@dataclass
class SpatialEdge:
    """A spatial relationship between two entities."""
    subject_id: int
    object_id: int
    predicate: SpatialPredicate
    confidence: float
    distance_mm: float
    
    # Stability tracking
    first_frame: int = 0
    last_frame: int = 0
    consecutive_frames: int = 1
    is_stable: bool = False
    
    # 3D info
    subject_centroid_3d: Optional[Tuple[float, float, float]] = None
    object_centroid_3d: Optional[Tuple[float, float, float]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "subject_id": self.subject_id,
            "object_id": self.object_id,
            "predicate": self.predicate.value,
            "confidence": round(self.confidence, 4),
            "distance_mm": round(self.distance_mm, 1),
            "first_frame": self.first_frame,
            "last_frame": self.last_frame,
            "consecutive_frames": self.consecutive_frames,
            "is_stable": self.is_stable,
        }


@dataclass
class Entity3D:
    """Entity with full 3D spatial information."""
    id: int
    class_name: str
    
    # 3D bounding box [x_min, y_min, z_min, x_max, y_max, z_max] in mm
    bbox_3d: Optional[np.ndarray] = None
    
    # 2D bounding box [x1, y1, x2, y2] in pixels
    bbox_2d: Optional[np.ndarray] = None
    
    # 3D centroid [x, y, z] in mm
    centroid_3d: Optional[np.ndarray] = None
    
    # 3D velocity [vx, vy, vz] in mm/frame
    velocity_3d: Optional[np.ndarray] = None
    
    # Kalman filter state [x, y, z, vx, vy, vz]
    state: Optional[np.ndarray] = None
    
    # Frame dimensions
    frame_width: int = 1920
    frame_height: int = 1080
    
    @property
    def is_person(self) -> bool:
        return "person" in self.class_name.lower()
    
    @property
    def is_furniture(self) -> bool:
        furniture = {"bed", "couch", "sofa", "table", "desk", "chair", "bench", "cabinet"}
        return self.class_name.lower() in furniture
    
    @property
    def is_portable(self) -> bool:
        portable = {"cup", "bottle", "phone", "book", "laptop", "remote", "mouse", "keyboard"}
        return self.class_name.lower() in portable or not self.is_furniture
    
    def get_centroid_3d(self) -> Optional[np.ndarray]:
        """Get 3D centroid from available data."""
        if self.centroid_3d is not None:
            return self.centroid_3d
        if self.state is not None and len(self.state) >= 3:
            return np.array(self.state[:3])
        if self.bbox_3d is not None and len(self.bbox_3d) >= 6:
            return np.array([
                (self.bbox_3d[0] + self.bbox_3d[3]) / 2,
                (self.bbox_3d[1] + self.bbox_3d[4]) / 2,
                (self.bbox_3d[2] + self.bbox_3d[5]) / 2,
            ])
        return None
    
    def get_velocity_3d(self) -> Optional[np.ndarray]:
        """Get 3D velocity from available data."""
        if self.velocity_3d is not None:
            return self.velocity_3d
        if self.state is not None and len(self.state) >= 6:
            return np.array(self.state[3:6])
        return None


class SpatialRelationEngine:
    """
    Computes 3D spatial relationships between entities.
    
    Features:
    - 3D-aware predicates using depth data
    - Relationship stability tracking (requires N frames to confirm)
    - Support surface detection (ON relationship)
    - Containment detection (INSIDE/CONTAINS relationship)
    - Hand-object proximity (HELD_BY relationship)
    """
    
    def __init__(
        self,
        # Distance thresholds (mm)
        near_threshold_mm: float = 300.0,      # 30cm for NEAR
        touching_threshold_mm: float = 50.0,   # 5cm for TOUCHING
        on_vertical_gap_mm: float = 100.0,     # 10cm max gap for ON
        on_horizontal_overlap: float = 0.3,    # 30% horizontal overlap for ON
        held_by_threshold_mm: float = 150.0,   # 15cm for HELD_BY
        
        # Stability settings
        stability_frames: int = 5,  # Frames before edge is "stable"
        max_gap_frames: int = 3,    # Max frames edge can disappear and still be continued
        
        # Confidence settings
        min_confidence: float = 0.3,
    ):
        self.near_threshold_mm = near_threshold_mm
        self.touching_threshold_mm = touching_threshold_mm
        self.on_vertical_gap_mm = on_vertical_gap_mm
        self.on_horizontal_overlap = on_horizontal_overlap
        self.held_by_threshold_mm = held_by_threshold_mm
        self.stability_frames = stability_frames
        self.max_gap_frames = max_gap_frames
        self.min_confidence = min_confidence
        
        # Edge history for stability tracking
        # Key: (subject_id, object_id, predicate)
        self._edge_history: Dict[Tuple[int, int, str], SpatialEdge] = {}
        self._last_frame: int = -1
    
    def compute_frame_relations(
        self,
        entities: List[Entity3D],
        frame_id: int,
        hand_keypoints: Optional[Dict[int, List[Tuple[float, float, float]]]] = None,
    ) -> List[SpatialEdge]:
        """
        Compute all spatial relations for a single frame.
        
        Args:
            entities: List of Entity3D objects in this frame
            frame_id: Current frame index
            hand_keypoints: Optional {person_id: [3D keypoints]} for hand detection
        
        Returns:
            List of SpatialEdge objects
        """
        edges: List[SpatialEdge] = []
        
        # Clean up old unstable edges
        if frame_id - self._last_frame > self.max_gap_frames:
            self._cleanup_stale_edges(frame_id)
        self._last_frame = frame_id
        
        n = len(entities)
        for i in range(n):
            A = entities[i]
            for j in range(n):
                if i == j:
                    continue
                B = entities[j]
                
                # Compute all applicable relations
                frame_edges = self._compute_pairwise_relations(A, B, frame_id, hand_keypoints)
                edges.extend(frame_edges)
        
        # Update stability tracking
        for edge in edges:
            self._update_edge_stability(edge, frame_id)
        
        return edges
    
    def _compute_pairwise_relations(
        self,
        A: Entity3D,
        B: Entity3D,
        frame_id: int,
        hand_keypoints: Optional[Dict[int, List[Tuple[float, float, float]]]] = None,
    ) -> List[SpatialEdge]:
        """Compute all spatial relations between entity A and B."""
        edges: List[SpatialEdge] = []
        
        # Get 3D positions
        pos_a = A.get_centroid_3d()
        pos_b = B.get_centroid_3d()
        
        if pos_a is None or pos_b is None:
            # Fall back to 2D-only relations
            return self._compute_2d_relations(A, B, frame_id)
        
        # 3D distance
        dist_3d = np.linalg.norm(pos_a - pos_b)
        
        # === NEAR ===
        if dist_3d <= self.near_threshold_mm:
            conf = 1.0 - (dist_3d / self.near_threshold_mm)
            if conf >= self.min_confidence:
                edges.append(SpatialEdge(
                    subject_id=A.id,
                    object_id=B.id,
                    predicate=SpatialPredicate.NEAR,
                    confidence=conf,
                    distance_mm=dist_3d,
                    first_frame=frame_id,
                    last_frame=frame_id,
                    subject_centroid_3d=tuple(pos_a),
                    object_centroid_3d=tuple(pos_b),
                ))
        
        # === TOUCHING ===
        if dist_3d <= self.touching_threshold_mm:
            conf = 1.0 - (dist_3d / self.touching_threshold_mm)
            edges.append(SpatialEdge(
                subject_id=A.id,
                object_id=B.id,
                predicate=SpatialPredicate.TOUCHING,
                confidence=min(1.0, conf * 1.2),
                distance_mm=dist_3d,
                first_frame=frame_id,
                last_frame=frame_id,
            ))
        
        # === ON (A on B) ===
        on_conf = self._compute_on_relation(A, B, pos_a, pos_b)
        if on_conf >= self.min_confidence:
            edges.append(SpatialEdge(
                subject_id=A.id,
                object_id=B.id,
                predicate=SpatialPredicate.ON,
                confidence=on_conf,
                distance_mm=dist_3d,
                first_frame=frame_id,
                last_frame=frame_id,
            ))
        
        # === ABOVE / BELOW ===
        if A.bbox_3d is not None and B.bbox_3d is not None:
            vertical_diff = pos_a[1] - pos_b[1]  # Y axis
            if abs(vertical_diff) > 100:  # 10cm vertical separation
                if vertical_diff < 0:  # A is above B (lower Y in image coords)
                    edges.append(SpatialEdge(
                        subject_id=A.id,
                        object_id=B.id,
                        predicate=SpatialPredicate.ABOVE,
                        confidence=min(1.0, abs(vertical_diff) / 500),
                        distance_mm=dist_3d,
                        first_frame=frame_id,
                        last_frame=frame_id,
                    ))
                else:  # A is below B
                    edges.append(SpatialEdge(
                        subject_id=A.id,
                        object_id=B.id,
                        predicate=SpatialPredicate.BELOW,
                        confidence=min(1.0, abs(vertical_diff) / 500),
                        distance_mm=dist_3d,
                        first_frame=frame_id,
                        last_frame=frame_id,
                    ))
        
        # === IN_FRONT_OF / BEHIND ===
        depth_diff = pos_a[2] - pos_b[2]  # Z axis
        if abs(depth_diff) > 200:  # 20cm depth separation
            if depth_diff < 0:  # A is in front of B (smaller Z)
                edges.append(SpatialEdge(
                    subject_id=A.id,
                    object_id=B.id,
                    predicate=SpatialPredicate.IN_FRONT_OF,
                    confidence=min(1.0, abs(depth_diff) / 1000),
                    distance_mm=dist_3d,
                    first_frame=frame_id,
                    last_frame=frame_id,
                ))
            else:  # A is behind B
                edges.append(SpatialEdge(
                    subject_id=A.id,
                    object_id=B.id,
                    predicate=SpatialPredicate.BEHIND,
                    confidence=min(1.0, abs(depth_diff) / 1000),
                    distance_mm=dist_3d,
                    first_frame=frame_id,
                    last_frame=frame_id,
                ))
        
        # === HELD_BY (A held by person B) ===
        if B.is_person and A.is_portable:
            held_conf = self._compute_held_by_relation(A, B, hand_keypoints)
            if held_conf >= self.min_confidence:
                edges.append(SpatialEdge(
                    subject_id=A.id,
                    object_id=B.id,
                    predicate=SpatialPredicate.HELD_BY,
                    confidence=held_conf,
                    distance_mm=dist_3d,
                    first_frame=frame_id,
                    last_frame=frame_id,
                ))
        
        # === CONTAINS / INSIDE ===
        if A.bbox_3d is not None and B.bbox_3d is not None:
            contains_conf = self._compute_containment(A, B)
            if contains_conf >= self.min_confidence:
                # A contains B
                edges.append(SpatialEdge(
                    subject_id=A.id,
                    object_id=B.id,
                    predicate=SpatialPredicate.CONTAINS,
                    confidence=contains_conf,
                    distance_mm=dist_3d,
                    first_frame=frame_id,
                    last_frame=frame_id,
                ))
        
        return edges
    
    def _compute_on_relation(
        self,
        A: Entity3D,
        B: Entity3D,
        pos_a: np.ndarray,
        pos_b: np.ndarray,
    ) -> float:
        """
        Compute confidence for "A is on B" relationship.
        
        Criteria:
        1. A is above B (lower Y value in 3D)
        2. Vertical gap is small (within threshold)
        3. Horizontal overlap is significant
        4. A should be smaller/portable, B should be surface-like
        """
        # Class filtering: portable on furniture/surface
        if A.is_furniture or (A.is_person and not B.is_furniture):
            return 0.0
        
        # Get vertical relationship (Y axis, note: in 3D, lower Y = higher position)
        vertical_gap = pos_b[1] - pos_a[1]  # B.y - A.y
        
        # A should be "on top" (higher in world = lower Y in image coords usually)
        # But in 3D world coords, we assume Y increases upward
        # So A on B means A.y > B.y (A is higher)
        if pos_a[1] <= pos_b[1]:  # A is not above B
            return 0.0
        
        # Check vertical gap
        if vertical_gap > self.on_vertical_gap_mm:
            return 0.0
        
        # Check horizontal overlap using 2D bboxes
        if A.bbox_2d is not None and B.bbox_2d is not None:
            overlap = self._horizontal_overlap_ratio(A.bbox_2d, B.bbox_2d)
            if overlap < self.on_horizontal_overlap:
                return 0.0
        
        # Compute confidence based on vertical gap (closer = higher confidence)
        gap_factor = 1.0 - (abs(vertical_gap) / self.on_vertical_gap_mm)
        
        return gap_factor
    
    def _compute_held_by_relation(
        self,
        obj: Entity3D,
        person: Entity3D,
        hand_keypoints: Optional[Dict[int, List[Tuple[float, float, float]]]] = None,
    ) -> float:
        """Compute confidence for object being held by person."""
        obj_pos = obj.get_centroid_3d()
        if obj_pos is None:
            return 0.0
        
        min_dist = float('inf')
        
        # Check hand keypoints if available
        if hand_keypoints and person.id in hand_keypoints:
            for kp in hand_keypoints[person.id]:
                if kp is not None:
                    dist = np.linalg.norm(np.array(kp) - obj_pos)
                    min_dist = min(min_dist, dist)
        
        # Fallback: estimate hand position from person bbox
        if min_dist == float('inf') and person.bbox_3d is not None:
            # Hands are typically at lower-center of person bbox
            hand_proxy = np.array([
                (person.bbox_3d[0] + person.bbox_3d[3]) / 2,
                person.bbox_3d[4],  # Bottom of bbox
                (person.bbox_3d[2] + person.bbox_3d[5]) / 2,
            ])
            min_dist = np.linalg.norm(hand_proxy - obj_pos)
        
        if min_dist > self.held_by_threshold_mm:
            return 0.0
        
        # Confidence based on distance (closer = higher)
        conf = 1.0 - (min_dist / self.held_by_threshold_mm)
        
        # Boost if object is moving with person (check velocity alignment)
        obj_vel = obj.get_velocity_3d()
        person_vel = person.get_velocity_3d()
        if obj_vel is not None and person_vel is not None:
            obj_speed = np.linalg.norm(obj_vel)
            person_speed = np.linalg.norm(person_vel)
            if obj_speed > 5 and person_speed > 5:
                cosine = np.dot(obj_vel, person_vel) / (obj_speed * person_speed)
                if cosine > 0.8:  # Moving together
                    conf = min(1.0, conf * 1.2)
        
        return conf
    
    def _compute_containment(self, A: Entity3D, B: Entity3D) -> float:
        """Check if A contains B (B is inside A)."""
        if A.bbox_3d is None or B.bbox_3d is None:
            return 0.0
        
        # B's bbox should be fully inside A's bbox
        b_min = B.bbox_3d[:3]
        b_max = B.bbox_3d[3:6]
        a_min = A.bbox_3d[:3]
        a_max = A.bbox_3d[3:6]
        
        # Check each dimension
        inside_count = 0
        for i in range(3):
            if b_min[i] >= a_min[i] and b_max[i] <= a_max[i]:
                inside_count += 1
        
        # Partial containment (at least 2 dimensions inside)
        if inside_count >= 2:
            return 0.5 + (inside_count - 2) * 0.25
        
        return 0.0
    
    def _horizontal_overlap_ratio(self, bbox_a: np.ndarray, bbox_b: np.ndarray) -> float:
        """Compute horizontal overlap ratio between two 2D bboxes."""
        ax1, ay1, ax2, ay2 = bbox_a
        bx1, by1, bx2, by2 = bbox_b
        
        left = max(ax1, bx1)
        right = min(ax2, bx2)
        overlap = max(0.0, right - left)
        
        a_width = max(1e-8, ax2 - ax1)
        b_width = max(1e-8, bx2 - bx1)
        
        return overlap / min(a_width, b_width)
    
    def _compute_2d_relations(
        self,
        A: Entity3D,
        B: Entity3D,
        frame_id: int,
    ) -> List[SpatialEdge]:
        """Fallback: compute relations using only 2D bboxes."""
        edges: List[SpatialEdge] = []
        
        if A.bbox_2d is None or B.bbox_2d is None:
            return edges
        
        # 2D centroid distance
        ax, ay = (A.bbox_2d[0] + A.bbox_2d[2]) / 2, (A.bbox_2d[1] + A.bbox_2d[3]) / 2
        bx, by = (B.bbox_2d[0] + B.bbox_2d[2]) / 2, (B.bbox_2d[1] + B.bbox_2d[3]) / 2
        
        # Normalize by frame diagonal
        diag = np.sqrt(A.frame_width**2 + A.frame_height**2)
        dist_norm = np.sqrt((ax - bx)**2 + (ay - by)**2) / diag
        
        # NEAR (using normalized 2D distance)
        if dist_norm < 0.15:  # Within 15% of diagonal
            conf = 1.0 - (dist_norm / 0.15)
            edges.append(SpatialEdge(
                subject_id=A.id,
                object_id=B.id,
                predicate=SpatialPredicate.NEAR,
                confidence=conf,
                distance_mm=dist_norm * 1000,  # Approximate
                first_frame=frame_id,
                last_frame=frame_id,
            ))
        
        return edges
    
    def _update_edge_stability(self, edge: SpatialEdge, frame_id: int) -> None:
        """Update stability tracking for an edge."""
        key = (edge.subject_id, edge.object_id, edge.predicate.value)
        
        if key in self._edge_history:
            prev = self._edge_history[key]
            
            # Check if this is a continuation
            if frame_id - prev.last_frame <= self.max_gap_frames:
                edge.first_frame = prev.first_frame
                edge.consecutive_frames = prev.consecutive_frames + 1
                edge.is_stable = edge.consecutive_frames >= self.stability_frames
        
        self._edge_history[key] = edge
    
    def _cleanup_stale_edges(self, current_frame: int) -> None:
        """Remove edges that haven't been seen recently."""
        stale_keys = [
            key for key, edge in self._edge_history.items()
            if current_frame - edge.last_frame > self.max_gap_frames
        ]
        for key in stale_keys:
            del self._edge_history[key]
    
    def get_stable_edges(self) -> List[SpatialEdge]:
        """Get all edges that have been stable for the required number of frames."""
        return [
            edge for edge in self._edge_history.values()
            if edge.is_stable
        ]
    
    def reset(self) -> None:
        """Clear edge history."""
        self._edge_history.clear()
        self._last_frame = -1
