"""
Causal Influence Scorer (CIS)
=============================

Computes causal influence scores between entities based on:
1. Temporal proximity
2. Spatial proximity (3D)
3. Motion alignment (3D velocity vectors)
4. Semantic compatibility (embedding + heuristics)
5. Interaction bonuses (Hand-Object with keypoint proximity)

Formula:
    CIS = w_t * T + w_s * S + w_m * M + w_se * Se + H
    
Where:
    T = exp(-|Δt| / τ)                    # Temporal decay
    S = max(0, 1 - (D_3D / D_max)²)       # 3D spatial proximity
    M = max(0, cos(θ_v))                  # 3D velocity alignment
    Se = 0.6*emb_sim + 0.4*type_compat    # Semantic compatibility
    H = hand_bonus if hand interaction    # Discrete bonuses
"""

import numpy as np
import math
from typing import Dict, Optional, Tuple, List, Any, Union
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class CISComponents:
    """Breakdown of CIS score components with debug info."""
    temporal: float
    spatial: float
    motion: float
    semantic: float
    hand_bonus: float
    total: float
    
    # Debug info
    distance_3d_mm: float = 0.0
    velocity_alignment: float = 0.0
    hand_distance_mm: float = float('inf')
    interaction_type: str = "none"


@dataclass
class CISEdge:
    """Represents a causal influence edge between two entities."""
    agent_id: int  # Entity causing the influence (often person/hand)
    patient_id: int  # Entity being influenced (object)
    agent_class: str
    patient_class: str
    cis_score: float
    components: CISComponents
    frame_id: int
    timestamp: float
    
    # Relationship metadata
    relation_type: str = "influences"  # "influences", "grasps", "moves_with"
    confidence: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "agent_id": self.agent_id,
            "patient_id": self.patient_id,
            "agent_class": self.agent_class,
            "patient_class": self.patient_class,
            "cis_score": round(self.cis_score, 4),
            "relation_type": self.relation_type,
            "confidence": round(self.confidence, 4),
            "frame_id": self.frame_id,
            "timestamp": round(self.timestamp, 3),
            "components": {
                "temporal": round(self.components.temporal, 4),
                "spatial": round(self.components.spatial, 4),
                "motion": round(self.components.motion, 4),
                "semantic": round(self.components.semantic, 4),
                "hand_bonus": round(self.components.hand_bonus, 4),
                "distance_3d_mm": round(self.components.distance_3d_mm, 1),
                "velocity_alignment": round(self.components.velocity_alignment, 4),
                "interaction_type": self.components.interaction_type,
            }
        }


class CausalInfluenceScorer:
    """
    Enhanced CIS computation with 3D and hand interaction signals.
    
    Formula:
    CIS = w_t * T + w_s * S + w_m * M + w_se * Se + H
    
    With 3D depth gating: if |Z_a - Z_b| > depth_gate_mm, CIS is zeroed
    to prevent foreground-background hallucinations.
    """
    
    def __init__(
        self,
        weight_temporal: float = 0.30,
        weight_spatial: float = 0.44,
        weight_motion: float = 0.21,
        weight_semantic: float = 0.06,
        temporal_decay_tau: float = 4.0,  # seconds
        max_spatial_distance_mm: float = 600.0,  # 600mm = 60cm
        hand_grasping_bonus: float = 0.30,
        hand_touching_bonus: float = 0.15,
        hand_near_bonus: float = 0.05,
        cis_threshold: float = 0.50,
        depth_gate_mm: float = 200.0,  # 3D depth gating threshold (200mm = 20cm)
        enable_depth_gating: bool = True,  # Whether to apply depth gating
        dino_embedder: Any = None,  # Optional DINOv3 embedder for semantic similarity
    ):
        self.weight_temporal = weight_temporal
        self.weight_spatial = weight_spatial
        self.weight_motion = weight_motion
        self.weight_semantic = weight_semantic
        self.temporal_decay_tau = temporal_decay_tau
        self.max_spatial_distance_mm = max_spatial_distance_mm
        self.hand_grasping_bonus = hand_grasping_bonus
        self.hand_touching_bonus = hand_touching_bonus
        self.hand_near_bonus = hand_near_bonus
        self.cis_threshold = cis_threshold
        self.depth_gate_mm = depth_gate_mm
        self.enable_depth_gating = enable_depth_gating
        self.dino_embedder = dino_embedder
        
        # Type compatibility table (heuristic)
        self.type_compatibility = self._build_type_compatibility()
        
        # Cache for visual embeddings (bbox_key -> embedding)
        self._embedding_cache = {}
    
    def calculate_cis(
        self,
        agent_entity: Any, # PerceptionEntity or Track
        patient_entity: Any, # PerceptionEntity or Track
        time_delta: float,
        scene_context: Optional[Dict] = None,
        hand_keypoints: Optional[List[Tuple[float, float, float]]] = None,
    ) -> Tuple[float, CISComponents]:
        """
        Compute CIS between two entities.
        
        Args:
            agent_entity: The influencing entity (often person/hand)
            patient_entity: The influenced entity (object)
            time_delta: Time difference in seconds
            scene_context: Optional scene metadata for context boost
            hand_keypoints: Optional list of 3D hand keypoints [(x,y,z), ...]
        
        Returns:
            (cis_score, components) tuple
        """
        # === 0. DEPTH GATING (early exit) ===
        # If objects are on different depth planes, they cannot causally influence each other
        depth_disparity = self._compute_depth_disparity(agent_entity, patient_entity)
        if self.enable_depth_gating and depth_disparity is not None:
            if depth_disparity > self.depth_gate_mm:
                # Objects are on different depth planes - zero CIS
                return 0.0, CISComponents(
                    temporal=0.0, spatial=0.0, motion=0.0, semantic=0.0,
                    hand_bonus=0.0, total=0.0, distance_3d_mm=depth_disparity,
                    velocity_alignment=0.0, hand_distance_mm=float('inf'),
                    interaction_type="depth_gated"
                )
        
        # === 1. TEMPORAL SCORE ===
        T = self._temporal_score(time_delta)
        
        # === 2. SPATIAL SCORE (3D) ===
        S, dist_3d = self._spatial_score_3d(agent_entity, patient_entity)
        
        # === 3. MOTION SCORE (3D velocity alignment) ===
        M, vel_align = self._motion_score_3d(agent_entity, patient_entity)
        
        # === 4. SEMANTIC SCORE ===
        Se = self._semantic_score(agent_entity, patient_entity)
        
        # === 5. HAND INTERACTION BONUS ===
        H, hand_dist, interaction_type = self._hand_bonus_3d(
            agent_entity, patient_entity, hand_keypoints
        )
        
        # === COMBINE ===
        cis = (
            self.weight_temporal * T +
            self.weight_spatial * S +
            self.weight_motion * M +
            self.weight_semantic * Se +
            H
        )
        
        # Clip to [0, 1]
        cis = max(0.0, min(1.0, cis))
        
        # Apply scene context boost
        if scene_context:
            cis = self._apply_scene_context(cis, agent_entity, patient_entity, scene_context)
        
        components = CISComponents(
            temporal=T,
            spatial=S,
            motion=M,
            semantic=Se,
            hand_bonus=H,
            total=cis,
            distance_3d_mm=dist_3d,
            velocity_alignment=vel_align,
            hand_distance_mm=hand_dist,
            interaction_type=interaction_type,
        )
        
        return cis, components
    
    def _compute_depth_disparity(self, agent: Any, patient: Any) -> Optional[float]:
        """
        Compute absolute depth disparity between two entities.
        
        Used for depth gating: if objects are on different depth planes
        (e.g., foreground vs background), they cannot causally influence each other.
        
        Returns:
            Absolute depth difference in mm, or None if depth not available.
        """
        agent_depth = self._get_depth(agent)
        patient_depth = self._get_depth(patient)
        
        if agent_depth is None or patient_depth is None:
            return None  # Cannot compute, skip depth gating
        
        return abs(agent_depth - patient_depth)
    
    def _get_depth(self, entity: Any) -> Optional[float]:
        """Extract depth (Z coordinate) from entity."""
        # Direct depth attribute
        if hasattr(entity, 'depth_mm') and entity.depth_mm is not None:
            return float(entity.depth_mm)
        
        # From 3D state [x, y, z, ...]
        if hasattr(entity, 'state') and entity.state is not None:
            state = entity.state
            if len(state) >= 3:
                return float(state[2])  # Z component
        
        # From 3D bbox [cx, cy, cz, ...]
        if hasattr(entity, 'bbox_3d') and entity.bbox_3d is not None:
            bbox = entity.bbox_3d
            if len(bbox) >= 3:
                return float(bbox[2])  # Z component
        
        # From centroid_3d_mm
        centroid = self._get_centroid_3d(entity)
        if centroid is not None and len(centroid) >= 3:
            return float(centroid[2])
        
        return None
    
    def _temporal_score(self, time_delta: float) -> float:
        """Exponential temporal decay."""
        score = np.exp(-abs(time_delta) / self.temporal_decay_tau)
        return float(score)
    
    def _spatial_score_3d(self, agent: Any, patient: Any) -> Tuple[float, float]:
        """
        3D Euclidean distance-based scoring with quadratic falloff.
        
        Returns:
            (score, distance_mm) for debugging
        """
        agent_pos = self._get_centroid_3d(agent)
        patient_pos = self._get_centroid_3d(patient)
        
        if agent_pos is None or patient_pos is None:
            return 0.5, float('inf')  # Unknown, return neutral
        
        dist_3d = np.linalg.norm(np.array(agent_pos) - np.array(patient_pos))
        
        # Quadratic falloff: score decreases as distance increases
        # At max_distance, score = 0
        score = max(0.0, 1.0 - (dist_3d / self.max_spatial_distance_mm) ** 2)
        
        # Boost if very close (within 5cm)
        if dist_3d < 50.0:
            score = min(1.0, score * 1.2)
        
        # Extra boost for contact range (within 2cm)
        if dist_3d < 20.0:
            score = min(1.0, score * 1.1)
            
        return float(score), float(dist_3d)

    def _motion_score_3d(self, agent: Any, patient: Any) -> Tuple[float, float]:
        """
        3D velocity alignment using cosine similarity.
        
        High scores indicate objects moving in the same direction
        (e.g., cup being carried by person).
        
        Returns:
            (score, raw_cosine) for debugging
        """
        agent_vel = self._get_velocity_3d(agent)
        patient_vel = self._get_velocity_3d(patient)
        
        if agent_vel is None or patient_vel is None:
            return 0.5, 0.0  # Unknown, neutral score
        
        # Check if either is stationary (near-zero velocity)
        agent_speed = np.linalg.norm(agent_vel)
        patient_speed = np.linalg.norm(patient_vel)
        
        # Minimum speed threshold (5mm/frame ≈ 0.15m/s at 30fps)
        min_speed = 5.0
        
        if agent_speed < min_speed and patient_speed < min_speed:
            # Both stationary - high alignment (they're "moving together" by not moving)
            return 0.8, 0.0
        
        if agent_speed < min_speed or patient_speed < min_speed:
            # One moving, one not - low alignment
            return 0.2, 0.0
        
        # Both moving - compute cosine similarity
        dot = np.dot(agent_vel, patient_vel)
        norm = agent_speed * patient_speed
        
        if norm < 1e-6:
            return 0.5, 0.0
        
        cosine = dot / norm  # Range: [-1, 1]
        
        # Convert to [0, 1] score
        # cos = 1.0 → same direction → score = 1.0
        # cos = 0.0 → perpendicular → score = 0.5
        # cos = -1.0 → opposite → score = 0.0
        score = (cosine + 1.0) / 2.0
        
        # Boost for very similar velocities (both direction AND magnitude)
        speed_ratio = min(agent_speed, patient_speed) / max(agent_speed, patient_speed)
        if cosine > 0.8 and speed_ratio > 0.7:
            # Strong co-movement: moving together at similar speeds
            score = min(1.0, score * 1.15)
        
        return float(score), float(cosine)
    
    def _get_velocity_3d(self, entity: Any) -> Optional[np.ndarray]:
        """
        Extract 3D velocity vector from entity.
        
        Looks for velocity in:
        1. entity.velocity_3d (if available)
        2. entity.state[3:6] (Kalman filter state)
        3. Last observation's velocity field
        """
        # Direct velocity attribute
        if hasattr(entity, 'velocity_3d') and entity.velocity_3d is not None:
            return np.array(entity.velocity_3d)
        
        # Kalman filter state [x, y, z, vx, vy, vz]
        if hasattr(entity, 'state') and entity.state is not None:
            state = entity.state
            if len(state) >= 6:
                return np.array(state[3:6])
        
        # Check last observation
        if hasattr(entity, 'observations') and entity.observations:
            sorted_obs = sorted(entity.observations, key=lambda x: getattr(x, 'timestamp', 0), reverse=True)
            for obs in sorted_obs:
                if hasattr(obs, 'velocity_3d') and obs.velocity_3d is not None:
                    return np.array(obs.velocity_3d)
        
        # Check for Track-style object
        if hasattr(entity, 'velocity') and entity.velocity is not None:
            vel = entity.velocity
            if len(vel) >= 2:
                # 2D velocity - pad with 0 for z
                return np.array([vel[0], vel[1], 0.0])
        
        return None
    
    def _semantic_score(self, agent: Any, patient: Any) -> float:
        """Semantic similarity + type compatibility.
        
        Uses DINOv3 visual embeddings if available, otherwise falls back to
        existing embedding similarity or neutral score.
        """
        # Visual similarity using DINOv3
        emb_sim = 0.5  # Neutral default
        
        if self.dino_embedder is not None:
            # Try to extract visual features using DINOv3
            try:
                agent_visual_emb = self._get_visual_embedding(agent)
                patient_visual_emb = self._get_visual_embedding(patient)
                
                if agent_visual_emb is not None and patient_visual_emb is not None:
                    # Cosine similarity between DINOv3 embeddings
                    dot = np.dot(agent_visual_emb, patient_visual_emb)
                    norm = np.linalg.norm(agent_visual_emb) * np.linalg.norm(patient_visual_emb)
                    if norm > 1e-6:
                        emb_sim = (dot / norm + 1.0) / 2.0  # Normalize to [0, 1]
            except Exception:
                # Fall back to existing embedding logic
                pass
        
        # Fallback to existing embedding similarity if DINOv3 not available or failed
        if emb_sim == 0.5:
            agent_emb = getattr(agent, 'average_embedding', None)
            patient_emb = getattr(patient, 'average_embedding', None)
            
            if agent_emb is not None and patient_emb is not None:
                try:
                    # Ensure numpy arrays
                    if not isinstance(agent_emb, np.ndarray):
                        agent_emb = np.array(agent_emb)
                    if not isinstance(patient_emb, np.ndarray):
                        patient_emb = np.array(patient_emb)
                        
                    # Cosine similarity
                    dot = np.dot(agent_emb, patient_emb)
                    norm = np.linalg.norm(agent_emb) * np.linalg.norm(patient_emb)
                    if norm > 1e-6:
                        emb_sim = (dot / norm + 1.0) / 2.0
                except Exception:
                    # Fall back to neutral on any error
                    emb_sim = 0.5
                
        # Type compatibility
        agent_cls = str(getattr(agent, 'object_class', 'unknown'))
        patient_cls = str(getattr(patient, 'object_class', 'unknown'))
        type_compat = self._check_type_compatibility(agent_cls, patient_cls)
        
        return 0.6 * emb_sim + 0.4 * type_compat

    def _get_visual_embedding(self, entity: Any) -> Optional[np.ndarray]:
        """Extract visual embedding for an entity using DINOv3.
        
        Args:
            entity: Detection object with bbox and frame_image attributes
            
        Returns:
            DINOv3 embedding (normalized) or None if extraction fails
        """
        if self.dino_embedder is None:
            return None
            
        # Check cache first
        bbox = getattr(entity, 'bbox', None)
        frame_id = getattr(entity, 'frame_id', None)
        if bbox is not None and frame_id is not None:
            cache_key = (frame_id, tuple(bbox))
            if cache_key in self._embedding_cache:
                return self._embedding_cache[cache_key]
        
        # Extract crop from frame
        frame_image = getattr(entity, 'frame_image', None)
        if frame_image is None or bbox is None:
            return None
            
        try:
            # Crop bbox region
            x1, y1, x2, y2 = [int(v) for v in bbox]
            crop = frame_image[y1:y2, x1:x2]
            
            if crop.size == 0:
                return None
                
            # Encode with DINOv3
            embedding = self.dino_embedder.encode_image(crop, normalize=True)
            
            # Cache result
            if cache_key is not None:
                self._embedding_cache[cache_key] = embedding
                
            return embedding
        except Exception:
            return None

    def _hand_bonus_3d(
        self,
        agent: Any,
        patient: Any,
        hand_keypoints: Optional[List[Tuple[float, float, float]]] = None,
    ) -> Tuple[float, float, str]:
        """
        Compute hand interaction bonus with 3D keypoint proximity.
        
        Hand interaction hierarchy:
        1. GRASPING: hand keypoint inside object bbox (bonus: 0.30)
        2. TOUCHING: hand keypoint within 50mm of object (bonus: 0.15)
        3. REACHING: hand keypoint within 150mm of object (bonus: 0.05)
        
        Args:
            agent: The agent entity (check if it's a person)
            patient: The patient entity (object being manipulated)
            hand_keypoints: Optional 3D keypoints [(x,y,z), ...] in mm
        
        Returns:
            (bonus, min_hand_distance_mm, interaction_type)
        """
        agent_cls = str(getattr(agent, 'object_class', getattr(agent, 'class_name', ''))).lower()
        patient_cls = str(getattr(patient, 'object_class', getattr(patient, 'class_name', ''))).lower()
        
        # Agent must be person for hand bonus
        if "person" not in agent_cls and "hand" not in agent_cls:
            return 0.0, float('inf'), "none"
        
        # Get patient's 3D position
        patient_pos = self._get_centroid_3d(patient)
        if patient_pos is None:
            # Fallback to simple check
            if "hand" in agent_cls:
                return self.hand_near_bonus, float('inf'), "near_2d"
            return 0.0, float('inf'), "none"
        
        patient_pos = np.array(patient_pos)
        
        # Get patient's 3D bounding box for containment check
        patient_bbox_3d = self._get_bbox_3d(patient)
        
        min_distance = float('inf')
        interaction_type = "none"
        bonus = 0.0
        
        # Try explicit hand keypoints first
        if hand_keypoints and len(hand_keypoints) > 0:
            for kp in hand_keypoints:
                if kp is None:
                    continue
                kp_arr = np.array(kp)
                
                # Check if keypoint is inside object bbox
                if patient_bbox_3d is not None:
                    if self._point_in_bbox_3d(kp_arr, patient_bbox_3d):
                        return self.hand_grasping_bonus, 0.0, "grasping"
                
                # Compute distance to object centroid
                dist = np.linalg.norm(kp_arr - patient_pos)
                min_distance = min(min_distance, dist)
        
        # Fallback: use agent centroid as hand proxy
        if min_distance == float('inf'):
            agent_pos = self._get_centroid_3d(agent)
            if agent_pos is not None:
                # Estimate hand position (offset from person centroid)
                # Hands are typically at the lower-front of person bbox
                agent_bbox_3d = self._get_bbox_3d(agent)
                if agent_bbox_3d is not None:
                    # Use bottom-center of person bbox as hand proxy
                    hand_proxy = np.array([
                        (agent_bbox_3d[0] + agent_bbox_3d[3]) / 2,  # center x
                        agent_bbox_3d[4],  # bottom y (max y)
                        agent_bbox_3d[2],  # front z (min z)
                    ])
                    min_distance = np.linalg.norm(hand_proxy - patient_pos)
                else:
                    min_distance = np.linalg.norm(np.array(agent_pos) - patient_pos)
        
        # Determine interaction type based on distance
        if min_distance < 20.0:  # 2cm - contact
            bonus = self.hand_grasping_bonus
            interaction_type = "grasping"
        elif min_distance < 50.0:  # 5cm - touching
            bonus = self.hand_touching_bonus
            interaction_type = "touching"
        elif min_distance < 150.0:  # 15cm - reaching
            bonus = self.hand_near_bonus
            interaction_type = "reaching"
        
        return bonus, float(min_distance), interaction_type
    
    def _get_bbox_3d(self, entity: Any) -> Optional[np.ndarray]:
        """
        Get 3D bounding box from entity.
        
        Returns:
            [x_min, y_min, z_min, x_max, y_max, z_max] in mm, or None
        """
        # Direct attribute
        if hasattr(entity, 'bbox_3d') and entity.bbox_3d is not None:
            bbox = entity.bbox_3d
            if len(bbox) == 6:
                # Format: [x, y, z, w, h, d] -> convert to [x_min, y_min, z_min, x_max, y_max, z_max]
                x, y, z, w, h, d = bbox
                return np.array([x - w/2, y - h/2, z - d/2, x + w/2, y + h/2, z + d/2])
            return np.array(bbox)
        
        # Check observations
        if hasattr(entity, 'observations') and entity.observations:
            sorted_obs = sorted(entity.observations, key=lambda x: getattr(x, 'timestamp', 0), reverse=True)
            for obs in sorted_obs:
                if hasattr(obs, 'bbox_3d') and obs.bbox_3d is not None:
                    bbox = obs.bbox_3d
                    if len(bbox) == 6:
                        x, y, z, w, h, d = bbox
                        return np.array([x - w/2, y - h/2, z - d/2, x + w/2, y + h/2, z + d/2])
                    return np.array(bbox)
        
        return None
    
    def _point_in_bbox_3d(self, point: np.ndarray, bbox: np.ndarray) -> bool:
        """Check if 3D point is inside 3D bounding box."""
        return (
            bbox[0] <= point[0] <= bbox[3] and
            bbox[1] <= point[1] <= bbox[4] and
            bbox[2] <= point[2] <= bbox[5]
        )

    def _get_centroid_3d(self, entity: Any) -> Optional[Tuple[float, float, float]]:
        """Helper to extract 3D centroid from entity."""
        # Direct attribute on Track
        if hasattr(entity, 'state') and entity.state is not None:
            state = entity.state
            if len(state) >= 3:
                return (float(state[0]), float(state[1]), float(state[2]))
        
        # Direct centroid_3d attribute
        if hasattr(entity, 'centroid_3d') and entity.centroid_3d is not None:
            return tuple(entity.centroid_3d)
        
        # Use the most recent observation with depth
        if hasattr(entity, 'observations') and entity.observations:
            sorted_obs = sorted(entity.observations, key=lambda x: getattr(x, 'timestamp', 0), reverse=True)
            for obs in sorted_obs:
                if hasattr(obs, 'centroid_3d') and obs.centroid_3d is not None:
                    return obs.centroid_3d
        
        # Fallback: use bbox_3d center
        bbox_3d = self._get_bbox_3d(entity)
        if bbox_3d is not None:
            return (
                (bbox_3d[0] + bbox_3d[3]) / 2,
                (bbox_3d[1] + bbox_3d[4]) / 2,
                (bbox_3d[2] + bbox_3d[5]) / 2,
            )
        
        return None

    def _check_type_compatibility(self, class_a: str, class_b: str) -> float:
        pair = tuple(sorted([class_a.lower(), class_b.lower()]))
        return self.type_compatibility.get(pair, 0.5)

    def _build_type_compatibility(self) -> Dict[Tuple[str, str], float]:
        """Build semantic compatibility table for common interactions."""
        return {
            # Hand-object interactions (highest)
            ('cup', 'hand'): 1.0,
            ('cup', 'person'): 0.95,
            ('hand', 'keyboard'): 0.9,
            ('hand', 'mouse'): 0.9,
            ('hand', 'phone'): 0.9,
            ('keyboard', 'person'): 0.85,
            ('mouse', 'person'): 0.85,
            ('phone', 'person'): 0.9,
            ('book', 'hand'): 0.8,
            ('book', 'person'): 0.8,
            ('laptop', 'person'): 0.9,
            ('remote', 'person'): 0.85,
            ('bottle', 'person'): 0.85,
            
            # Furniture-person interactions
            ('chair', 'person'): 0.8,
            ('couch', 'person'): 0.8,
            ('bed', 'person'): 0.75,
            ('desk', 'person'): 0.7,
            ('table', 'person'): 0.7,
            
            # Object-surface relationships
            ('cup', 'table'): 0.7,
            ('cup', 'desk'): 0.7,
            ('laptop', 'desk'): 0.8,
            ('laptop', 'table'): 0.8,
            ('book', 'table'): 0.7,
            ('keyboard', 'desk'): 0.8,
            ('mouse', 'desk'): 0.8,
        }

    def _apply_scene_context(self, cis: float, agent: Any, patient: Any, context: Dict) -> float:
        """Apply scene context boost to CIS score."""
        # Activity-based boost
        if 'activity' in context:
            activity = context['activity'].lower()
            agent_cls = str(getattr(agent, 'object_class', getattr(agent, 'class_name', ''))).lower()
            patient_cls = str(getattr(patient, 'object_class', getattr(patient, 'class_name', ''))).lower()
            
            # Boost if activity matches object pair
            activity_boosts = {
                'cooking': [('person', 'pan'), ('person', 'pot'), ('person', 'knife')],
                'working': [('person', 'laptop'), ('person', 'keyboard'), ('person', 'mouse')],
                'reading': [('person', 'book')],
                'eating': [('person', 'cup'), ('person', 'fork'), ('person', 'spoon')],
            }
            
            for act, pairs in activity_boosts.items():
                if act in activity:
                    for p1, p2 in pairs:
                        if (p1 in agent_cls and p2 in patient_cls) or (p2 in agent_cls and p1 in patient_cls):
                            cis = min(1.0, cis * 1.1)
                            break
        
        return cis

    # ==========================================================================
    # BATCH COMPUTATION & EDGE GENERATION
    # ==========================================================================
    
    def compute_frame_edges(
        self,
        entities: List[Any],
        frame_id: int,
        timestamp: float,
        hand_keypoints_map: Optional[Dict[int, List[Tuple[float, float, float]]]] = None,
    ) -> List[CISEdge]:
        """
        Compute all CIS edges for a single frame.
        
        Args:
            entities: List of entities (tracks) visible in this frame
            frame_id: Current frame index
            timestamp: Frame timestamp in seconds
            hand_keypoints_map: Optional {person_track_id: [keypoints]} for hand detection
        
        Returns:
            List of CISEdge objects for edges above threshold
        """
        edges: List[CISEdge] = []
        
        # Separate persons from objects
        persons = []
        objects = []
        
        for entity in entities:
            cls_name = str(getattr(entity, 'object_class', getattr(entity, 'class_name', ''))).lower()
            entity_id = getattr(entity, 'id', getattr(entity, 'track_id', -1))
            
            if 'person' in cls_name:
                persons.append((entity_id, entity))
            else:
                objects.append((entity_id, entity))
        
        # Compute person→object influences (primary interaction mode)
        for person_id, person in persons:
            # Get hand keypoints for this person if available
            hand_kps = None
            if hand_keypoints_map and person_id in hand_keypoints_map:
                hand_kps = hand_keypoints_map[person_id]
            
            for obj_id, obj in objects:
                cis_score, components = self.calculate_cis(
                    agent_entity=person,
                    patient_entity=obj,
                    time_delta=0.0,  # Same frame
                    hand_keypoints=hand_kps,
                )
                
                if cis_score >= self.cis_threshold:
                    # Determine relation type based on interaction
                    if components.interaction_type == "grasping":
                        relation = "grasps"
                    elif components.motion > 0.7:
                        relation = "moves_with"
                    else:
                        relation = "influences"
                    
                    edge = CISEdge(
                        agent_id=person_id,
                        patient_id=obj_id,
                        agent_class=str(getattr(person, 'object_class', getattr(person, 'class_name', 'person'))),
                        patient_class=str(getattr(obj, 'object_class', getattr(obj, 'class_name', 'object'))),
                        cis_score=cis_score,
                        components=components,
                        frame_id=frame_id,
                        timestamp=timestamp,
                        relation_type=relation,
                        confidence=cis_score,
                    )
                    edges.append(edge)
        
        # Optionally compute object→object co-movement
        for i, (obj_id_a, obj_a) in enumerate(objects):
            for obj_id_b, obj_b in objects[i+1:]:
                # Only check motion alignment for co-movement
                motion_score, _ = self._motion_score_3d(obj_a, obj_b)
                spatial_score, dist = self._spatial_score_3d(obj_a, obj_b)
                
                # High co-movement: objects moving together
                if motion_score > 0.75 and spatial_score > 0.6:
                    # Create bidirectional "moves_with" edge
                    components = CISComponents(
                        temporal=1.0,
                        spatial=spatial_score,
                        motion=motion_score,
                        semantic=0.5,
                        hand_bonus=0.0,
                        total=motion_score * 0.6 + spatial_score * 0.4,
                        distance_3d_mm=dist,
                        velocity_alignment=motion_score,
                        interaction_type="co_movement",
                    )
                    
                    if components.total >= self.cis_threshold:
                        edge = CISEdge(
                            agent_id=obj_id_a,
                            patient_id=obj_id_b,
                            agent_class=str(getattr(obj_a, 'object_class', getattr(obj_a, 'class_name', 'object'))),
                            patient_class=str(getattr(obj_b, 'object_class', getattr(obj_b, 'class_name', 'object'))),
                            cis_score=components.total,
                            components=components,
                            frame_id=frame_id,
                            timestamp=timestamp,
                            relation_type="moves_with",
                            confidence=components.total,
                        )
                        edges.append(edge)
        
        return edges
    
    def compute_temporal_influence(
        self,
        entity_history: Dict[int, List[Any]],  # {entity_id: [observations across frames]}
        window_frames: int = 30,
    ) -> List[CISEdge]:
        """
        Compute temporal causal influence by analyzing state changes.
        
        Detects patterns like:
        - Object A moves → Object B moves shortly after (causation)
        - Person enters frame → Object state changes (interaction)
        
        Args:
            entity_history: Dictionary of entity observations over time
            window_frames: Maximum temporal window to check for causation
        
        Returns:
            List of temporal CIS edges
        """
        edges: List[CISEdge] = []
        
        # Detect state changes per entity
        state_changes: Dict[int, List[Dict]] = {}
        
        for entity_id, observations in entity_history.items():
            changes = self._detect_state_changes(observations)
            if changes:
                state_changes[entity_id] = changes
        
        # Find temporal correlations between state changes
        entity_ids = list(state_changes.keys())
        
        for i, agent_id in enumerate(entity_ids):
            agent_changes = state_changes[agent_id]
            
            for patient_id in entity_ids[i+1:]:
                patient_changes = state_changes[patient_id]
                
                # Check if agent change precedes patient change
                for a_change in agent_changes:
                    for p_change in patient_changes:
                        frame_diff = p_change['frame'] - a_change['frame']
                        
                        # Agent change should precede patient change (causation direction)
                        if 1 <= frame_diff <= window_frames:
                            # Compute temporal CIS
                            time_delta = frame_diff / 30.0  # Assume 30fps
                            T = self._temporal_score(time_delta)
                            
                            # Higher score for closer temporal proximity
                            if T >= 0.5:
                                components = CISComponents(
                                    temporal=T,
                                    spatial=0.5,  # Unknown
                                    motion=0.5,
                                    semantic=0.5,
                                    hand_bonus=0.0,
                                    total=T,
                                    distance_3d_mm=0.0,
                                    velocity_alignment=0.0,
                                    interaction_type="temporal_causation",
                                )
                                
                                edge = CISEdge(
                                    agent_id=agent_id,
                                    patient_id=patient_id,
                                    agent_class=a_change.get('class', 'unknown'),
                                    patient_class=p_change.get('class', 'unknown'),
                                    cis_score=T,
                                    components=components,
                                    frame_id=a_change['frame'],
                                    timestamp=a_change.get('timestamp', 0.0),
                                    relation_type="causes",
                                    confidence=T * 0.8,  # Lower confidence for temporal-only
                                )
                                edges.append(edge)
        
        return edges
    
    def _detect_state_changes(self, observations: List[Any]) -> List[Dict]:
        """
        Detect significant state changes in an entity's observation history.
        
        State changes include:
        - Position change > threshold
        - Velocity change (start/stop moving)
        - Zone change
        """
        changes: List[Dict] = []
        
        if len(observations) < 2:
            return changes
        
        # Sort by timestamp
        sorted_obs = sorted(observations, key=lambda x: getattr(x, 'timestamp', 0))
        
        prev_obs = sorted_obs[0]
        prev_pos = self._get_centroid_3d(prev_obs) if hasattr(prev_obs, 'centroid_3d') or hasattr(prev_obs, 'state') else None
        prev_vel = self._get_velocity_3d(prev_obs)
        
        for obs in sorted_obs[1:]:
            curr_pos = self._get_centroid_3d(obs) if hasattr(obs, 'centroid_3d') or hasattr(obs, 'state') else None
            curr_vel = self._get_velocity_3d(obs)
            
            # Position change detection
            if prev_pos and curr_pos:
                pos_delta = np.linalg.norm(np.array(curr_pos) - np.array(prev_pos))
                if pos_delta > 100.0:  # 10cm movement threshold
                    changes.append({
                        'type': 'position_change',
                        'frame': getattr(obs, 'frame_id', 0),
                        'timestamp': getattr(obs, 'timestamp', 0.0),
                        'class': getattr(obs, 'object_class', getattr(obs, 'class_name', 'unknown')),
                        'delta_mm': pos_delta,
                    })
            
            # Velocity change detection (start/stop moving)
            if prev_vel is not None and curr_vel is not None:
                prev_speed = np.linalg.norm(prev_vel)
                curr_speed = np.linalg.norm(curr_vel)
                
                # Started moving
                if prev_speed < 5.0 and curr_speed > 20.0:
                    changes.append({
                        'type': 'started_moving',
                        'frame': getattr(obs, 'frame_id', 0),
                        'timestamp': getattr(obs, 'timestamp', 0.0),
                        'class': getattr(obs, 'object_class', getattr(obs, 'class_name', 'unknown')),
                        'speed_mm_per_frame': curr_speed,
                    })
                
                # Stopped moving
                elif prev_speed > 20.0 and curr_speed < 5.0:
                    changes.append({
                        'type': 'stopped_moving',
                        'frame': getattr(obs, 'frame_id', 0),
                        'timestamp': getattr(obs, 'timestamp', 0.0),
                        'class': getattr(obs, 'object_class', getattr(obs, 'class_name', 'unknown')),
                    })
            
            prev_obs = obs
            prev_pos = curr_pos
            prev_vel = curr_vel
        
        return changes
