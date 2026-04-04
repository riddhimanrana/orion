"""
Enhanced 3D tracker with appearance-based Re-ID (StrongSORT-inspired).

Key improvements over basic IoU tracking:
1. Appearance embeddings (CLIP/FastVLM) for cross-scene Re-ID
2. Camera motion compensation (CMC) using SLAM pose
3. Exponential moving average (EMA) for appearance features
4. NSA Kalman filter for better motion prediction
5. Occlusion handling with feature matching

Performance target: <5ms overhead per frame (real-time compatible)
"""

import numpy as np
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field
from collections import deque
import cv2


@dataclass
class Track:
    """Enhanced track with appearance and motion state."""
    id: int
    class_name: str
    bbox_3d: np.ndarray  # [x, y, z, w, h, d] in mm
    bbox_2d: np.ndarray  # [x1, y1, x2, y2] in pixels
    confidence: float
    
    # Motion state (Kalman filter)
    state: np.ndarray  # [x, y, z, vx, vy, vz]
    covariance: np.ndarray
    
    # Appearance for Re-ID
    appearance_features: deque  # Gallery of embeddings
    avg_appearance: Optional[np.ndarray]  # EMA of features
    
    # Track management
    age: int  # Total frames
    hits: int  # Consecutive detections
    time_since_update: int  # Frames without match
    
    # Depth and zone
    depth_mm: float
    zone_id: Optional[str]

    # Detection provenance / debug metadata (optional)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def velocity(self) -> Optional[np.ndarray]:
        """Get 2D velocity in pixels/frame for spatial matching."""
        if self.state is not None and len(self.state) >= 6:
            return self.state[3:5]  # [vx, vy] in pixels/frame
        return None
    
    def to_dict(self) -> Dict:
        """Convert track to JSON-serializable dictionary."""
        d = {
            'id': int(self.id),
            'track_id': int(self.id),  # Alias for compatibility
            'class_name': str(self.class_name),
            'category': str(self.class_name),  # Alias for compatibility
            'bbox_3d': self.bbox_3d.tolist() if isinstance(self.bbox_3d, np.ndarray) else self.bbox_3d,
            'bbox_2d': self.bbox_2d.tolist() if isinstance(self.bbox_2d, np.ndarray) else self.bbox_2d,
            'bbox': self.bbox_2d.tolist() if isinstance(self.bbox_2d, np.ndarray) else self.bbox_2d,  # Alias
            'confidence': float(self.confidence),
            'depth_mm': float(self.depth_mm) if self.depth_mm is not None else None,
            'zone_id': self.zone_id,
            'age': int(self.age),
            'hits': int(self.hits),
            'time_since_update': int(self.time_since_update),
        }

        # Include selected provenance fields (if present). Kept flat for easier JSONL analytics.
        if isinstance(self.metadata, dict) and self.metadata:
            for k in (
                "detector_source",
                "detector_source_origin",
                "detector_source_last",
                "hybrid_secondary_ran",
                "hybrid_trigger_reason",
                "hybrid_primary_count",
                "hybrid_secondary_count",
                "hybrid_merged_count",
                # Schema v2 hypothesis / verification fields
                "label_hypotheses",
                "verification_status",
                "verification_source",
                "proposal_confidence",
            ):
                if k in self.metadata:
                    d[k] = self.metadata.get(k)

        return d


class KalmanFilter3D:
    """3D Kalman filter for object tracking with velocity."""
    
    def __init__(self, dt: float = 0.033):
        """Initialize 3D Kalman filter.
        
        Args:
            dt: Time step (default 30 FPS = 0.033s)
        """
        # State: [x, y, z, vx, vy, vz]
        self.dt = dt
        self.dim_x = 6
        self.dim_z = 3
        
        # State transition matrix (constant velocity model)
        self.F = np.eye(6)
        self.F[0, 3] = dt  # x += vx * dt
        self.F[1, 4] = dt  # y += vy * dt
        self.F[2, 5] = dt  # z += vz * dt
        
        # Measurement matrix (observe position only)
        self.H = np.zeros((3, 6))
        self.H[0, 0] = 1  # Observe x
        self.H[1, 1] = 1  # Observe y
        self.H[2, 2] = 1  # Observe z
        
        # Process noise (how much we trust motion model)
        self.Q = np.eye(6) * 0.1
        self.Q[3:, 3:] *= 2.0  # Higher noise for velocity
        
        # Measurement noise (how much we trust observations)
        self.R = np.eye(3) * 50.0  # 50mm measurement uncertainty
    
    def predict(self, state: np.ndarray, P: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Predict next state."""
        state = self.F @ state
        P = self.F @ P @ self.F.T + self.Q
        return state, P
    
    def update(self, state: np.ndarray, P: np.ndarray, 
               measurement: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Update state with measurement."""
        # Innovation
        y = measurement - (self.H @ state)
        
        # Innovation covariance
        S = self.H @ P @ self.H.T + self.R
        
        # Kalman gain
        K = P @ self.H.T @ np.linalg.inv(S)
        
        # Update state and covariance
        state = state + K @ y
        P = (np.eye(6) - K @ self.H) @ P
        
        return state, P


class EnhancedTracker:
    """
    StrongSORT-inspired tracker with appearance Re-ID.
    
    Features:
    - 3D Kalman filter with velocity
    - Appearance embedding gallery (max 5 per track)
    - EMA for robust appearance matching
    - Camera motion compensation via SLAM pose
    - Occlusion handling (max 30 frames without detection)
    
    Performance: ~3-5ms overhead per frame
    """
    
    def __init__(
        self,
        max_age: int = 30,  # Max frames without detection before deletion
        min_hits: int = 3,  # Min consecutive hits to confirm track
        iou_threshold: float = 0.3,  # IoU threshold for matching
        appearance_threshold: float = 0.70,  # Cosine similarity threshold (raised for V-JEPA)
        max_distance_pixels: float = 150.0,  # Hard gating for implausible 2D jumps
        max_distance_3d_mm: float = 1500.0,  # Hard gating when 3D is available
        max_distance_frame_ratio: float = 0.15,  # Max distance as fraction of frame diagonal
        match_threshold: float = 0.55,  # Max allowed final cost for a match (tightened)
        max_gallery_size: int = 5,  # Max embeddings per track
        ema_alpha: float = 0.9,  # EMA weight for appearance
        clip_model = None,  # For label verification
        per_class_thresholds: Optional[Dict[str, float]] = None,  # Per-class override
        frame_width: int = 1920,  # Frame width for adaptive distance gating
        frame_height: int = 1080,  # Frame height for adaptive distance gating
    ):
        self.max_age = max_age
        self.min_hits = min_hits
        self.iou_threshold = iou_threshold
        self.appearance_threshold = appearance_threshold
        self.max_distance_pixels = float(max_distance_pixels)
        self.max_distance_3d_mm = float(max_distance_3d_mm)
        self.max_distance_frame_ratio = float(max_distance_frame_ratio)
        self.match_threshold = float(match_threshold)
        self.max_gallery_size = max_gallery_size
        self.ema_alpha = ema_alpha
        self.clip_model = clip_model
        
        # Frame dimensions for adaptive spatial gating
        self.frame_width = frame_width
        self.frame_height = frame_height
        self._frame_diagonal = np.sqrt(frame_width**2 + frame_height**2)
        
        # Per-class thresholds (loaded from JSON or passed in)
        self.per_class_thresholds = per_class_thresholds or {}
        
        # Workspace categories for CLIP verification
        self.workspace_categories = [
            "laptop", "keyboard", "mouse", "monitor", "phone",
            "backpack", "water bottle", "coffee cup",
            "desk", "chair", "cable", "lamp"
        ]
        
        self.tracks: List[Track] = []
        self.next_id = 0
        self.kf = KalmanFilter3D()
        
        # Camera motion compensation
        self.last_camera_pose: Optional[np.ndarray] = None

        # Coarse→fine semantic compatibility for YOLO-World prompt presets.
        # This reduces fragmentation while still preventing wild cross-category switches.
        self._coarse_children = {
            "electronic device": {"laptop", "phone", "monitor", "keyboard", "mouse", "remote", "tablet"},
            "container": {"bottle", "cup", "mug", "glass", "thermos", "food container", "tupperware"},
            "furniture": {"chair", "table", "desk", "couch", "sofa", "bed", "ottoman"},
        }
    
    def get_threshold_for_class(self, class_name: str) -> float:
        """Get the appearance threshold for a specific class."""
        # Normalize class name
        normalized = self._normalize_label(class_name)
        # Check per-class thresholds first
        if normalized in self.per_class_thresholds:
            return self.per_class_thresholds[normalized]
        if class_name in self.per_class_thresholds:
            return self.per_class_thresholds[class_name]
        # Fall back to default
        return self.per_class_thresholds.get("_default", self.appearance_threshold)
    
    def _normalize_label(self, class_name: str) -> str:
        """Normalize YOLO label variants to canonical form."""
        from orion.perception.labels import normalize_label
        return normalize_label(class_name)
    
    def _verify_and_correct_label(self, class_name: str, embedding: Optional[np.ndarray]) -> Tuple[str, float, str]:
        """
        Verify YOLO label using CLIP, correct if needed.
        
        Returns: (final_label, confidence, method)
            method: "yolo_verified", "clip_corrected", "needs_fastvlm"
        """
        if self.clip_model is None or embedding is None:
            return class_name, 1.0, "yolo_only"
        
        from sklearn.metrics.pairwise import cosine_similarity
        
        # Verify YOLO label
        yolo_text_emb = self.clip_model.encode_text(f"a photo of a {class_name}", normalize=True)
        yolo_similarity = cosine_similarity(
            embedding.reshape(1, -1),
            yolo_text_emb.reshape(1, -1)
        )[0][0]
        
        # If YOLO seems reasonable, use it
        if yolo_similarity > 0.28:
            return class_name, yolo_similarity, "yolo_verified"
        
        # Try workspace categories
        best_category = None
        best_score = 0.0
        
        for category in self.workspace_categories:
            cat_text_emb = self.clip_model.encode_text(f"a photo of a {category}", normalize=True)
            score = cosine_similarity(
                embedding.reshape(1, -1),
                cat_text_emb.reshape(1, -1)
            )[0][0]
            
            if score > best_score:
                best_score = score
                best_category = category
        
        # Use better match
        if best_score > yolo_similarity:
            return best_category, best_score, "clip_corrected"
        
        # Unknown object
        if best_score < 0.25:
            return "unknown", best_score, "needs_fastvlm"
        
        return best_category, best_score, "clip_classified"
    
    def update(
        self,
        detections: List[Dict],
        embeddings: Optional[List[np.ndarray]] = None,
        camera_pose: Optional[np.ndarray] = None,
        frame_idx: int = 0,
    ) -> List[Track]:
        """
        Update tracks with new detections.
        
        Args:
            detections: List of detection dicts with keys:
                - bbox_3d: [x, y, z, w, h, d] in mm
                - bbox_2d: [x1, y1, x2, y2] in pixels
                - class_name: str
                - confidence: float
                - depth_mm: float
            embeddings: Optional appearance embeddings (CLIP/FastVLM)
            camera_pose: Optional 4x4 camera pose matrix for CMC
            frame_idx: Current frame index
        
        Returns:
            List of confirmed tracks (hits >= min_hits)
        """
        # 1. Predict all tracks forward
        self._predict_tracks(camera_pose)
        
        # 2. Match detections to tracks
        matches, unmatched_dets, unmatched_tracks = self._match(
            detections, embeddings
        )
        
        # 3. Update matched tracks
        for track_idx, det_idx in matches:
            self._update_track(
                self.tracks[track_idx],
                detections[det_idx],
                embeddings[det_idx] if embeddings else None,
            )
        
        # 4. Mark unmatched tracks
        for track_idx in unmatched_tracks:
            self.tracks[track_idx].time_since_update += 1
        
        # 5. Initialize new tracks for unmatched detections
        for det_idx in unmatched_dets:
            self._initiate_track(
                detections[det_idx],
                embeddings[det_idx] if embeddings else None,
            )
        
        # 6. Delete old tracks
        self.tracks = [
            t for t in self.tracks 
            if t.time_since_update < self.max_age
        ]
        
        # 6.5. Deduplicate overlapping tracks (Gemini audit: merge tracks with >70% IoU)
        self._deduplicate_tracks(iou_threshold=0.70)
        
        # 7. Return confirmed tracks
        return [t for t in self.tracks if t.hits >= self.min_hits]
    
    def _predict_tracks(self, camera_pose: Optional[np.ndarray]):
        """Predict all tracks forward with Kalman filter."""
        for track in self.tracks:
            # Kalman predict
            track.state, track.covariance = self.kf.predict(
                track.state, track.covariance
            )
            
            # Camera motion compensation (CMC)
            if camera_pose is not None and self.last_camera_pose is not None:
                delta_pose = self._compute_camera_motion(
                    self.last_camera_pose, camera_pose
                )
                # Compensate track position for camera motion
                track.state[:3] += delta_pose
            
            track.age += 1
        
        self.last_camera_pose = camera_pose
    
    def _match(
        self,
        detections: List[Dict],
        embeddings: Optional[List[np.ndarray]],
    ) -> Tuple[List[Tuple[int, int]], List[int], List[int]]:
        """
        Match detections to tracks using IoU + appearance.
        
        Returns:
            matches: [(track_idx, det_idx), ...]
            unmatched_dets: [det_idx, ...]
            unmatched_tracks: [track_idx, ...]
        """
        if len(self.tracks) == 0:
            return [], list(range(len(detections))), []
        
        if len(detections) == 0:
            return [], [], list(range(len(self.tracks)))
        
        # Compute cost matrix (IoU + appearance)
        cost_matrix = self._compute_cost_matrix(detections, embeddings)
        
        # Hungarian algorithm for optimal assignment
        matches, unmatched_dets, unmatched_tracks = self._hungarian_matching(
            cost_matrix
        )
        
        return matches, unmatched_dets, unmatched_tracks

    def _labels_compatible(self, det_label_norm: str, track_label_norm: str) -> bool:
        """Return True if labels are identical or compatible via coarse→fine mapping."""
        if det_label_norm == track_label_norm:
            return True

        # Allow either side to be a coarse parent of the other.
        det_children = self._coarse_children.get(det_label_norm)
        if det_children and track_label_norm in det_children:
            return True
        track_children = self._coarse_children.get(track_label_norm)
        if track_children and det_label_norm in track_children:
            return True

        return False

    @staticmethod
    def _bbox_iou_xyxy(a: List[float], b: List[float]) -> float:
        """IoU for xyxy bboxes."""
        ax1, ay1, ax2, ay2 = a
        bx1, by1, bx2, by2 = b
        inter_x1 = max(ax1, bx1)
        inter_y1 = max(ay1, by1)
        inter_x2 = min(ax2, bx2)
        inter_y2 = min(ay2, by2)
        iw = max(0.0, inter_x2 - inter_x1)
        ih = max(0.0, inter_y2 - inter_y1)
        inter = iw * ih
        if inter <= 0.0:
            return 0.0
        area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
        area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
        union = area_a + area_b - inter
        return float(inter / union) if union > 0.0 else 0.0
    
    def _compute_cost_matrix(
        self,
        detections: List[Dict],
        embeddings: Optional[List[np.ndarray]],
    ) -> np.ndarray:
        """
        Compute cost matrix using balanced spatial-semantic-appearance matching.
        
        V-JEPA2 embeddings are 3D-aware and more discriminative than CLIP,
        so we give appearance stronger weight while still using spatial/semantic
        as hard gates to prevent implausible matches.
        
        Cost = 0.25*spatial + 0.10*size + 0.10*semantic + 0.55*appearance
        
        Deep Research Update (v3):
        - Increased appearance weight from 0.45 to 0.55 (V-JEPA2 is strong)
        - Decreased spatial weight from 0.30 to 0.25 (wearable cameras move fast)
        - Added confidence-aware gating for low-confidence detections
        """
        def get_bbox(det: Dict) -> List[float]:
            """Get bbox from detection, handling both bbox_2d and bbox keys."""
            return det.get('bbox_2d', det.get('bbox', [0, 0, 100, 100]))
        
        num_tracks = len(self.tracks)
        num_dets = len(detections)
        
        cost_matrix = np.zeros((num_tracks, num_dets))
        
        # Frame diagonal for normalizing distances (use actual frame dims or default)
        frame_diag = self._frame_diagonal if hasattr(self, '_frame_diagonal') else np.sqrt(1920**2 + 1080**2)
        
        # Adaptive max distance: 15% of frame diagonal (prevents cross-room ID switches)
        adaptive_max_dist = frame_diag * self.max_distance_frame_ratio
        # Use the more restrictive of adaptive and fixed thresholds
        effective_max_dist = min(self.max_distance_pixels, adaptive_max_dist) if self.max_distance_pixels > 0 else adaptive_max_dist
        
        for t_idx, track in enumerate(self.tracks):
            for d_idx, det in enumerate(detections):
                # Get bbox (handles both bbox_2d and bbox keys)
                det_bbox = get_bbox(det)
                
                # Deep Research: Gate very low confidence detections more strictly
                det_conf = det.get('confidence', 0.5)
                if det_conf < 0.20:
                    # Extremely low confidence - require very strong appearance match
                    if embeddings is None or track.avg_appearance is None:
                        cost_matrix[t_idx, d_idx] = 999.0
                        continue
                
                # 1. Spatial cost: distance between predicted and detected position
                det_center = np.array([
                    (det_bbox[0] + det_bbox[2]) / 2,
                    (det_bbox[1] + det_bbox[3]) / 2
                ], dtype=np.float64)
                
                # Use 2D bbox center from track (not 3D backprojection)
                track_center = np.array([
                    (track.bbox_2d[0] + track.bbox_2d[2]) / 2.0,
                    (track.bbox_2d[1] + track.bbox_2d[3]) / 2.0
                ], dtype=np.float64)
                
                # Add velocity prediction if available (Kalman-predicted location)
                if hasattr(track, 'velocity') and track.velocity is not None:
                    track_center = track_center + track.velocity[:2].astype(np.float64)
                
                spatial_dist = np.linalg.norm(det_center - track_center)
                spatial_cost = min(1.0, spatial_dist / frame_diag)

                # Hard gate: implausible 2D jump (prevents identity drift across frame)
                # Uses adaptive threshold based on frame size (15% of diagonal)
                if spatial_dist > effective_max_dist:
                    cost_matrix[t_idx, d_idx] = 999.0
                    continue
                
                # 2. Size cost: bbox area change (use 2D bbox)
                det_area = (det_bbox[2] - det_bbox[0]) * (det_bbox[3] - det_bbox[1])
                track_area = (track.bbox_2d[2] - track.bbox_2d[0]) * \
                            (track.bbox_2d[3] - track.bbox_2d[1])
                
                if track_area > 0:
                    size_ratio = det_area / track_area
                    # Allow 2x growth/shrink before heavy penalty
                    if 0.5 < size_ratio < 2.0:
                        size_cost = abs(1.0 - size_ratio)
                    else:
                        size_cost = 1.0
                else:
                    size_cost = 0.5
                
                # 3. Semantic cost: class mismatch (use normalized labels)
                det_label = det.get('class_name', det.get('category', 'unknown'))
                det_normalized = self._normalize_label(det_label)
                track_normalized = self._normalize_label(track.class_name)

                if not self._labels_compatible(det_normalized, track_normalized):
                    cost_matrix[t_idx, d_idx] = 999.0
                    continue

                # Compatible but not identical: add a small semantic penalty
                semantic_cost = 0.0 if det_normalized == track_normalized else 0.25
                
                # 4. Appearance cost: weak signal (CLIP not discriminative enough)
                appearance_cost = 0.5  # Neutral default
                if embeddings is not None and track.avg_appearance is not None:
                    similarity = self._cosine_similarity(
                        track.avg_appearance, embeddings[d_idx]
                    )
                    appearance_cost = 1.0 - similarity

                    # Hard gate: appearance must clear per-class threshold (prevents ID switches)
                    thresh = self.get_threshold_for_class(track.class_name)
                    if similarity < float(thresh):
                        # If boxes overlap strongly, allow a little more leeway (occlusion / motion blur)
                        iou = self._bbox_iou_xyxy(track.bbox_2d.tolist(), det_bbox)
                        if iou < float(self.iou_threshold):
                            cost_matrix[t_idx, d_idx] = 999.0
                            continue
                
                # Combined cost with balanced weights for V-JEPA2 (Deep Research v3)
                # V-JEPA2 is highly discriminative, so appearance gets dominant weight
                # Reduced spatial weight to handle wearable camera jitter
                cost_matrix[t_idx, d_idx] = (
                    0.25 * spatial_cost +
                    0.10 * size_cost +
                    0.10 * semantic_cost +
                    0.55 * appearance_cost
                )
        
        return cost_matrix
    
    def _hungarian_matching(
        self, cost_matrix: np.ndarray
    ) -> Tuple[List[Tuple[int, int]], List[int], List[int]]:
        """Hungarian algorithm for optimal assignment with spatial-semantic threshold."""
        from scipy.optimize import linear_sum_assignment
        
        # Find optimal assignment
        track_indices, det_indices = linear_sum_assignment(cost_matrix)
        
        # Filter by threshold (configurable; lowered to prevent cross-room ID switches)
        matches = []
        for t_idx, d_idx in zip(track_indices, det_indices):
            if cost_matrix[t_idx, d_idx] < self.match_threshold:
                matches.append((t_idx, d_idx))
        
        # Unmatched detections and tracks
        matched_det_indices = set([d for _, d in matches])
        matched_track_indices = set([t for t, _ in matches])
        
        unmatched_dets = [
            i for i in range(cost_matrix.shape[1])
            if i not in matched_det_indices
        ]
        unmatched_tracks = [
            i for i in range(cost_matrix.shape[0])
            if i not in matched_track_indices
        ]
        
        return matches, unmatched_dets, unmatched_tracks
    
    def _update_track(
        self,
        track: Track,
        detection: Dict,
        embedding: Optional[np.ndarray],
    ):
        """Update track with matched detection."""
        # Handle both 3D and 2D-only detections
        bbox_3d = detection.get('bbox_3d')
        bbox_2d = detection.get('bbox_2d', detection.get('bbox'))
        depth_mm = detection.get('depth_mm', 0.0)
        
        if bbox_3d is not None:
            measurement = bbox_3d[:3]
        elif bbox_2d is not None:
            x1, y1, x2, y2 = bbox_2d
            measurement = np.array([(x1 + x2) / 2, (y1 + y2) / 2, track.state[2]])  # Keep previous Z
        else:
            measurement = track.state[:3]  # Keep previous position
        
        # Kalman update with measurement
        track.state, track.covariance = self.kf.update(
            track.state, track.covariance, measurement
        )
        
        # Update bounding box (use measurement, not predicted)
        if bbox_3d is not None:
            track.bbox_3d = bbox_3d
        track.bbox_2d = bbox_2d
        track.confidence = detection['confidence']
        track.depth_mm = depth_mm

        # Preserve detector provenance / hybrid debug metadata on the track.
        if hasattr(track, "metadata") and isinstance(track.metadata, dict):
            # Track the detector source of the *current* update, while keeping the origin source.
            det_src = detection.get("detector_source")
            if det_src is not None:
                track.metadata.setdefault("detector_source_origin", det_src)
                track.metadata["detector_source_last"] = det_src
                # Backwards-compatible field: historically this was the only field serialized.
                track.metadata["detector_source"] = det_src

            for k in (
                "hybrid_secondary_ran",
                "hybrid_trigger_reason",
                "hybrid_primary_count",
                "hybrid_secondary_count",
                "hybrid_merged_count",
                # Schema v2 hypothesis / verification fields
                "label_hypotheses",
                "label_hypotheses_topk",
                "verification_status",
                "verification_source",
                "proposal_confidence",
            ):
                if k in detection:
                    # Map label_hypotheses_topk to label_hypotheses for consistency
                    key = "label_hypotheses" if k == "label_hypotheses_topk" else k
                    track.metadata[key] = detection.get(k)
        
        # Update appearance (EMA)
        if embedding is not None:
            if track.avg_appearance is None:
                track.avg_appearance = embedding
            else:
                track.avg_appearance = (
                    self.ema_alpha * track.avg_appearance +
                    (1 - self.ema_alpha) * embedding
                )
            
            # Add to gallery
            track.appearance_features.append(embedding)
            if len(track.appearance_features) > self.max_gallery_size:
                track.appearance_features.popleft()
        
        # Update track state
        track.hits += 1
        track.time_since_update = 0
    
    def _initiate_track(self, detection: Dict, embedding: Optional[np.ndarray]):
        """Create new track from unmatched detection."""
        # Handle both 3D and 2D-only detections
        bbox_3d = detection.get('bbox_3d')
        bbox_2d = detection.get('bbox_2d', detection.get('bbox'))
        depth_mm = detection.get('depth_mm', 0.0)
        
        # Handle class_name vs category key (different detectors use different keys)
        raw_label = detection.get('class_name', detection.get('category', 'unknown'))
        
        if bbox_3d is not None:
            pos = bbox_3d[:3]
        elif bbox_2d is not None:
            # Use 2D center + default depth if no 3D available
            x1, y1, x2, y2 = bbox_2d
            pos = np.array([(x1 + x2) / 2, (y1 + y2) / 2, 1000.0])  # Default 1m depth
        else:
            pos = np.array([0.0, 0.0, 1000.0])
        
        # Verify and correct label using CLIP
        corrected_label, label_confidence, method = self._verify_and_correct_label(
            raw_label,
            embedding
        )
        
        # Initialize Kalman state: [x, y, z, vx, vy, vz]
        state = np.zeros(6)
        state[:3] = pos
        covariance = np.eye(6) * 1000.0  # High initial uncertainty
        
        # Initialize appearance
        appearance_features = deque(maxlen=self.max_gallery_size)
        if embedding is not None:
            appearance_features.append(embedding)

        # Capture detector provenance / hybrid metadata at creation time.
        meta: Dict[str, Any] = {}

        det_src = detection.get("detector_source")
        if det_src is not None:
            meta["detector_source_origin"] = det_src
            meta["detector_source_last"] = det_src
            meta["detector_source"] = det_src

        for k in (
            "hybrid_secondary_ran",
            "hybrid_trigger_reason",
            "hybrid_primary_count",
            "hybrid_secondary_count",
            "hybrid_merged_count",
            # Schema v2 hypothesis / verification fields
            "label_hypotheses",
            "label_hypotheses_topk",
            "verification_status",
            "verification_source",
            "proposal_confidence",
        ):
            if k in detection:
                # Map label_hypotheses_topk to label_hypotheses for consistency
                key = "label_hypotheses" if k == "label_hypotheses_topk" else k
                meta[key] = detection.get(k)
        
        track = Track(
            id=self.next_id,
            class_name=corrected_label,  # Use corrected label, not YOLO's guess
            bbox_3d=bbox_3d if bbox_3d is not None else np.array([pos[0], pos[1], pos[2], 50, 50, 50]),
            bbox_2d=bbox_2d,
            confidence=detection['confidence'],
            state=state,
            covariance=covariance,
            appearance_features=appearance_features,
            avg_appearance=embedding.copy() if embedding is not None else None,
            age=1,
            hits=1,
            time_since_update=0,
            depth_mm=depth_mm,
            zone_id=None,
            metadata=meta,
        )
        
        self.tracks.append(track)
        self.next_id += 1
    
    def _compute_iou_2d(self, box1: np.ndarray, box2: np.ndarray) -> float:
        """Compute 2D IoU between two boxes in [x1, y1, x2, y2] format."""
        x1 = max(box1[0], box2[0])
        y1 = max(box1[1], box2[1])
        x2 = min(box1[2], box2[2])
        y2 = min(box1[3], box2[3])
        
        inter_w = max(0.0, x2 - x1)
        inter_h = max(0.0, y2 - y1)
        inter_area = inter_w * inter_h
        
        area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
        area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
        union_area = area1 + area2 - inter_area
        
        if union_area <= 0:
            return 0.0
        return inter_area / union_area
    
    def _deduplicate_tracks(self, iou_threshold: float = 0.70):
        """Merge tracks with high spatial overlap (Gemini audit recommendation).
        
        Addresses: "Multiple track IDs are assigned to the same spatial regions for both
        'box' and 'hand' classes, suggesting issues with NMS or track merging logic."
        
        Strategy: Keep the track with more hits (longer confirmation history).
        """
        if len(self.tracks) < 2:
            return
        
        # Find pairs with high IoU
        tracks_to_remove = set()
        for i in range(len(self.tracks)):
            if i in tracks_to_remove:
                continue
            for j in range(i + 1, len(self.tracks)):
                if j in tracks_to_remove:
                    continue
                
                bbox_i = self.tracks[i].bbox_2d
                bbox_j = self.tracks[j].bbox_2d
                
                if bbox_i is None or bbox_j is None:
                    continue
                    
                iou = self._compute_iou_2d(
                    np.array(bbox_i) if not isinstance(bbox_i, np.ndarray) else bbox_i,
                    np.array(bbox_j) if not isinstance(bbox_j, np.ndarray) else bbox_j,
                )
                
                if iou >= iou_threshold:
                    # Keep track with more hits; if equal, keep older (lower ID)
                    if self.tracks[i].hits > self.tracks[j].hits:
                        tracks_to_remove.add(j)
                    elif self.tracks[j].hits > self.tracks[i].hits:
                        tracks_to_remove.add(i)
                    else:
                        # Equal hits: keep lower ID (older track)
                        tracks_to_remove.add(j)
        
        # Remove duplicate tracks
        if tracks_to_remove:
            self.tracks = [t for idx, t in enumerate(self.tracks) if idx not in tracks_to_remove]
    
    def _compute_iou_3d(
        self,
        pos1: np.ndarray,
        pos2: np.ndarray,
        size1: np.ndarray,
        size2: np.ndarray,
    ) -> float:
        """Compute 3D IoU between two boxes."""
        # Simplified: use center distance + size similarity
        distance = np.linalg.norm(pos1 - pos2)
        max_size = max(np.linalg.norm(size1), np.linalg.norm(size2))
        
        if max_size == 0:
            return 0.0
        
        # Approximate IoU from distance
        iou = max(0.0, 1.0 - distance / max_size)
        return iou
    
    def _cosine_similarity(self, emb1: np.ndarray, emb2: np.ndarray) -> float:
        """Cosine similarity between two embeddings."""
        norm1 = np.linalg.norm(emb1)
        norm2 = np.linalg.norm(emb2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return np.dot(emb1, emb2) / (norm1 * norm2)
    
    def _compute_camera_motion(
        self, pose1: np.ndarray, pose2: np.ndarray
    ) -> np.ndarray:
        """Compute camera translation between two poses."""
        # Extract translation from 4x4 pose matrices
        t1 = pose1[:3, 3]
        t2 = pose2[:3, 3]
        return t2 - t1
    
    def get_statistics(self) -> Dict:
        """Get tracker statistics for monitoring."""
        return {
            'total_tracks': len(self.tracks),
            'confirmed_tracks': sum(1 for t in self.tracks if t.hits >= self.min_hits),
            'active_tracks': sum(1 for t in self.tracks if t.time_since_update == 0),
            'next_id': self.next_id,
        }
