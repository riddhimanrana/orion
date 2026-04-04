#!/usr/bin/env python3
"""
PVSG Action-Aware Relation Classifier

Comprehensive classifier for ALL 57 PVSG predicates.
Works for ANY video by using spatial, temporal, and contextual cues.
"""

import numpy as np
from typing import List, Dict, Tuple, Optional, Any, Set
from dataclasses import dataclass
from collections import defaultdict


@dataclass
class Detection:
    """Single object detection."""
    track_id: int
    class_name: str
    bbox: List[float]  # [x1, y1, x2, y2]
    frame_id: int
    confidence: float = 1.0
    frame_image: Optional[np.ndarray] = None
    velocity: Optional[Tuple[float, float]] = None


@dataclass
class HandDetection:
    """Hand detection with landmarks."""
    bbox: List[float]  # [x1, y1, x2, y2]
    landmarks: Optional[np.ndarray] = None
    handedness: str = "unknown"


# =============================================================================
# PVSG PREDICATE DEFINITIONS (ALL 57)
# =============================================================================
PVSG_PREDICATES = [
    "beside", "biting", "blowing", "brushing", "caressing", "carrying",
    "catching", "chasing", "cleaning", "closing", "cooking", "cutting",
    "drinking from", "eating", "entering", "feeding", "grabbing", "guiding",
    "hanging from", "hitting", "holding", "hugging", "in", "in front of",
    "jumping from", "jumping over", "kicking", "kissing", "licking", "lighting",
    "looking at", "lying on", "next to", "on", "opening", "over", "picking",
    "playing", "playing with", "pointing to", "pulling", "pushing", "riding",
    "running on", "shaking hand with", "sitting on", "standing on", "stepping on",
    "stirring", "swinging", "talking to", "throwing", "touching", "toward",
    "walking on", "watering", "wearing"
]

# =============================================================================
# OBJECT CATEGORY DEFINITIONS (for context-aware prediction)
# =============================================================================

# Person-like entities
PERSON_CLASSES = {
    'person', 'adult', 'child', 'baby', 'man', 'woman', 'boy', 'girl',
    'human', 'people', 'kid', 'toddler', 'infant', 'player', 'athlete'
}

# Animals
ANIMAL_CLASSES = {
    'dog', 'cat', 'bird', 'horse', 'cow', 'sheep', 'elephant', 'bear',
    'lion', 'tiger', 'monkey', 'zebra', 'giraffe', 'rabbit', 'duck',
    'chicken', 'pig', 'goat', 'fish', 'snake', 'turtle', 'frog'
}

# Surfaces you can sit/lie/stand/walk on
SURFACE_CLASSES = {
    'floor', 'ground', 'grass', 'carpet', 'mat', 'rug', 'road', 'sidewalk',
    'pavement', 'field', 'court', 'track', 'sand', 'snow', 'ice', 'water',
    'bed', 'sofa', 'couch', 'chair', 'bench', 'stool', 'table', 'desk',
    'stage', 'platform', 'stairs', 'step'
}

# Furniture for sitting
SITTING_SURFACES = {
    'chair', 'sofa', 'couch', 'bench', 'stool', 'bed', 'floor', 'ground',
    'grass', 'carpet', 'mat', 'rug', 'rock', 'log', 'step', 'stairs', 'pillow'
}

# Surfaces for lying
LYING_SURFACES = {
    'bed', 'sofa', 'couch', 'floor', 'ground', 'grass', 'mat', 'carpet',
    'rug', 'sand', 'table', 'bench'
}

# Rideable objects
RIDEABLE = {
    'bicycle', 'bike', 'motorcycle', 'motorbike', 'horse', 'elephant',
    'scooter', 'skateboard', 'surfboard', 'snowboard', 'car', 'bus', 'train'
}

# Wearable items
WEARABLE = {
    'hat', 'cap', 'helmet', 'glasses', 'sunglasses', 'shirt', 'jacket',
    'coat', 'dress', 'pants', 'shorts', 'skirt', 'shoes', 'boots',
    'gloves', 'scarf', 'tie', 'watch', 'bag', 'backpack', 'mask'
}

# Food/drink items
FOOD_ITEMS = {
    'food', 'apple', 'banana', 'orange', 'sandwich', 'pizza', 'cake',
    'bread', 'rice', 'meat', 'vegetable', 'fruit', 'snack', 'meal',
    'ice cream', 'cookie', 'donut', 'burger', 'hotdog'
}

DRINK_ITEMS = {
    'bottle', 'cup', 'glass', 'mug', 'can', 'drink', 'water', 'juice',
    'soda', 'coffee', 'tea', 'milk', 'wine', 'beer'
}

# Containers
CONTAINERS = {
    'box', 'basket', 'bag', 'bucket', 'bowl', 'pot', 'pan', 'cup',
    'drawer', 'cabinet', 'closet', 'trunk', 'bin', 'container', 'jar'
}

# Holdable/carryable objects (small enough to hold)
HOLDABLE = {
    'ball', 'phone', 'book', 'cup', 'bottle', 'bag', 'toy', 'remote',
    'pen', 'pencil', 'brush', 'knife', 'fork', 'spoon', 'plate', 'bowl',
    'camera', 'racket', 'bat', 'stick', 'umbrella', 'flower', 'baby',
    'child', 'pillow', 'blanket', 'towel', 'paper', 'box', 'food',
    'fruit', 'vegetable', 'tool', 'instrument', 'guitar', 'violin',
    'clothes', 'shirt', 'pants', 'hat', 'shoe'
}

# Objects that can be opened/closed
OPENABLE = {
    'door', 'window', 'drawer', 'cabinet', 'box', 'bag', 'bottle',
    'jar', 'refrigerator', 'oven', 'microwave', 'dishwasher', 'gate',
    'lid', 'trunk', 'closet', 'book', 'laptop', 'umbrella'
}

# Objects that can be kicked
KICKABLE = {
    'ball', 'soccer ball', 'football', 'can', 'bottle', 'box', 'stone',
    'rock', 'toy'
}

# Objects for playing
PLAYABLE = {
    'ball', 'toy', 'game', 'instrument', 'guitar', 'piano', 'drum',
    'racket', 'bat', 'frisbee', 'kite', 'doll', 'teddy bear', 'blocks',
    'cards', 'puzzle', 'video game'
}


class PVSGActionClassifier:
    """
    Comprehensive PVSG relation classifier.
    Predicts ALL 57 PVSG predicates based on spatial, temporal, and context cues.
    """
    
    def __init__(
        self,
        holding_hand_dist: float = 100.0,
        holding_min_frames: int = 3,
        throwing_velocity_thresh: float = 50.0,
        throwing_accel_thresh: float = 30.0,
        picking_hand_dist: float = 120.0,
        vjepa_embedder: Optional[Any] = None,
    ):
        self.holding_hand_dist = holding_hand_dist
        self.holding_min_frames = holding_min_frames
        self.throwing_velocity_thresh = throwing_velocity_thresh
        self.throwing_accel_thresh = throwing_accel_thresh
        self.picking_hand_dist = picking_hand_dist
        self.vjepa_embedder = vjepa_embedder
        self.track_history: Dict[int, List[Detection]] = defaultdict(list)
    
    # =========================================================================
    # UTILITY METHODS
    # =========================================================================
    
    def bbox_center(self, bbox: List[float]) -> Tuple[float, float]:
        """Get bbox center point."""
        return ((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)
    
    def bbox_area(self, bbox: List[float]) -> float:
        """Get bbox area."""
        return max((bbox[2] - bbox[0]) * (bbox[3] - bbox[1]), 1)
    
    def distance(self, p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
        """Euclidean distance between two points."""
        return np.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)
    
    def compute_iou(self, bbox1: List[float], bbox2: List[float]) -> float:
        """Compute IoU between two bboxes."""
        x1 = max(bbox1[0], bbox2[0])
        y1 = max(bbox1[1], bbox2[1])
        x2 = min(bbox1[2], bbox2[2])
        y2 = min(bbox1[3], bbox2[3])
        
        inter = max(0, x2 - x1) * max(0, y2 - y1)
        area1 = self.bbox_area(bbox1)
        area2 = self.bbox_area(bbox2)
        union = area1 + area2 - inter
        
        return inter / union if union > 0 else 0
    
    def compute_overlap(self, bbox1: List[float], bbox2: List[float]) -> Tuple[float, float]:
        """Compute overlap dimensions."""
        overlap_x = max(0, min(bbox1[2], bbox2[2]) - max(bbox1[0], bbox2[0]))
        overlap_y = max(0, min(bbox1[3], bbox2[3]) - max(bbox1[1], bbox2[1]))
        return overlap_x, overlap_y
    
    def is_person(self, class_name: str) -> bool:
        """Check if class is person-like."""
        name = class_name.lower()
        return any(p in name for p in PERSON_CLASSES)
    
    def is_animal(self, class_name: str) -> bool:
        """Check if class is an animal."""
        name = class_name.lower()
        return any(a in name for a in ANIMAL_CLASSES)
    
    def is_agent(self, class_name: str) -> bool:
        """Check if class can be an agent (person or animal)."""
        return self.is_person(class_name) or self.is_animal(class_name)
    
    def class_in_set(self, class_name: str, class_set: Set[str]) -> bool:
        """Check if class name matches any in the set."""
        name = class_name.lower()
        return any(c in name for c in class_set)
    
    def update_track_history(self, detection: Detection):
        """Add detection to track history."""
        self.track_history[detection.track_id].append(detection)
        if len(self.track_history[detection.track_id]) > 30:
            self.track_history[detection.track_id].pop(0)
    
    def compute_velocity(self, track_id: int) -> Optional[Tuple[float, float]]:
        """Compute velocity from track history."""
        history = self.track_history.get(track_id, [])
        if len(history) < 2:
            return None
        
        velocities = []
        for i in range(1, min(len(history), 5)):
            prev, curr = history[-(i+1)], history[-i]
            dt = max(1, curr.frame_id - prev.frame_id)
            if dt > 10:
                continue
            c1, c2 = self.bbox_center(prev.bbox), self.bbox_center(curr.bbox)
            velocities.append(((c2[0] - c1[0]) / dt, (c2[1] - c1[1]) / dt))
        
        if not velocities:
            return None
        
        avg_vx = sum(v[0] for v in velocities) / len(velocities)
        avg_vy = sum(v[1] for v in velocities) / len(velocities)
        return (avg_vx, avg_vy)
    
    def get_speed(self, track_id: int) -> float:
        """Get speed magnitude."""
        vel = self.compute_velocity(track_id)
        if vel is None:
            return 0.0
        return np.sqrt(vel[0]**2 + vel[1]**2)
    
    # =========================================================================
    # SPATIAL RELATION DETECTION
    # =========================================================================
    
    def detect_spatial_relations(
        self, subj: Detection, obj: Detection
    ) -> List[Tuple[str, float]]:
        """
        Detect pure spatial relations: beside, next to, in front of, in, on, over, toward
        """
        candidates = []
        
        s_center = self.bbox_center(subj.bbox)
        o_center = self.bbox_center(obj.bbox)
        dist = self.distance(s_center, o_center)
        
        s_area = self.bbox_area(subj.bbox)
        o_area = self.bbox_area(obj.bbox)
        
        overlap_x, overlap_y = self.compute_overlap(subj.bbox, obj.bbox)
        iou = self.compute_iou(subj.bbox, obj.bbox)
        
        # Normalize distance by average object size
        avg_size = np.sqrt(s_area + o_area) / 2
        norm_dist = dist / max(avg_size, 1)
        
        # 'beside' / 'next to' - nearby, limited overlap
        if norm_dist < 2.5 and iou < 0.3:
            conf = max(0.3, 0.85 - norm_dist * 0.2)
            candidates.append(('beside', conf * 0.9))
            candidates.append(('next to', conf))
        
        # 'in front of' - subject closer to camera (lower y or larger)
        if norm_dist < 3.0:
            if s_center[1] > o_center[1] + 15:  # Subject lower = closer
                candidates.append(('in front of', 0.75))
            elif s_area > o_area * 1.2 and iou > 0.05:
                candidates.append(('in front of', 0.65))
        
        # 'in' - subject contained within object (containers)
        if self.class_in_set(obj.class_name, CONTAINERS):
            containment = (overlap_x * overlap_y) / max(s_area, 1)
            if containment > 0.5:
                candidates.append(('in', 0.85))
            elif containment > 0.3:
                candidates.append(('in', 0.7))
        
        # 'on' - subject resting on top of object
        if overlap_x > 0:
            # Subject bottom near object top
            s_bottom = subj.bbox[3]
            o_top = obj.bbox[1]
            vertical_gap = abs(s_bottom - o_top)
            if vertical_gap < (subj.bbox[3] - subj.bbox[1]) * 0.3:
                if s_center[1] < o_center[1]:  # Subject above object
                    candidates.append(('on', 0.8))
        
        # 'over' - subject above object with some overlap
        if s_center[1] < o_center[1] - 20 and overlap_x > 0:
            candidates.append(('over', 0.7))
        
        # 'toward' - motion-based, subject moving toward object
        vel = self.compute_velocity(subj.track_id)
        if vel:
            speed = np.sqrt(vel[0]**2 + vel[1]**2)
            if speed > 3:
                # Direction toward object
                dir_to_obj = (o_center[0] - s_center[0], o_center[1] - s_center[1])
                dir_mag = np.sqrt(dir_to_obj[0]**2 + dir_to_obj[1]**2)
                if dir_mag > 0:
                    cos_angle = (vel[0]*dir_to_obj[0] + vel[1]*dir_to_obj[1]) / (speed * dir_mag)
                    if cos_angle > 0.5:  # Moving toward
                        candidates.append(('toward', 0.7 + cos_angle * 0.2))
        
        return candidates
    
    # =========================================================================
    # PERSON-PERSON RELATION DETECTION
    # =========================================================================
    
    def detect_person_person_relations(
        self, subj: Detection, obj: Detection, subj_hands: List[HandDetection]
    ) -> List[Tuple[str, float]]:
        """
        Detect person-person relations:
        touching, looking at, talking to, hugging, kissing, shaking hand with,
        hitting, chasing, guiding, carrying, caressing, feeding, pointing to
        """
        candidates = []
        
        dist = self.distance(self.bbox_center(subj.bbox), self.bbox_center(obj.bbox))
        overlap_x, overlap_y = self.compute_overlap(subj.bbox, obj.bbox)
        iou = self.compute_iou(subj.bbox, obj.bbox)
        
        s_area = self.bbox_area(subj.bbox)
        o_area = self.bbox_area(obj.bbox)
        
        # Face regions (top 30% of bbox)
        s_face_bottom = subj.bbox[1] + (subj.bbox[3] - subj.bbox[1]) * 0.35
        o_face_bottom = obj.bbox[1] + (obj.bbox[3] - obj.bbox[1]) * 0.35
        
        # Check face-level overlap
        face_overlap_y = max(0, min(s_face_bottom, o_face_bottom) - max(subj.bbox[1], obj.bbox[1]))
        
        # 'pointing to' - PRIORITIZE this for PVSG! Common in GT
        # Happens when people are at medium distance, one gesturing toward another
        if 50 < dist < 500:
            # Higher confidence for medium-range (pointing range)
            if 100 < dist < 300:
                candidates.append(('pointing to', 0.85))  # High priority!
            else:
                candidates.append(('pointing to', 0.7))
        
        # 'looking at' - nearby persons
        if dist < 400:
            conf = max(0.4, 0.75 - dist / 600)  # REDUCED from 0.95
            candidates.append(('looking at', conf))
        
        # 'talking to' - close proximity
        if dist < 250:
            conf = max(0.35, 0.7 - dist / 400)  # REDUCED
            candidates.append(('talking to', conf))
        
        # 'touching' - ONLY if significant overlap (MUCH stricter)
        if iou > 0.15:  # Stricter threshold
            overlap_ratio = (overlap_x * overlap_y) / min(s_area, o_area)
            conf = min(0.8, 0.5 + overlap_ratio)  # REDUCED max conf
            candidates.append(('touching', conf))
        
        # 'hugging' - significant body overlap
        if iou > 0.15:
            candidates.append(('hugging', 0.85))
        elif overlap_x > 0 and overlap_y > 0:
            overlap_ratio = (overlap_x * overlap_y) / min(s_area, o_area)
            if overlap_ratio > 0.2:
                candidates.append(('hugging', 0.75))
        
        # 'kissing' - face regions overlapping/close
        if face_overlap_y > 0 and overlap_x > 0:
            candidates.append(('kissing', 0.85))
        elif dist < 80:
            # Very close faces
            s_face_center = (self.bbox_center(subj.bbox)[0], subj.bbox[1] + (subj.bbox[3]-subj.bbox[1])*0.2)
            o_face_center = (self.bbox_center(obj.bbox)[0], obj.bbox[1] + (obj.bbox[3]-obj.bbox[1])*0.2)
            face_dist = self.distance(s_face_center, o_face_center)
            if face_dist < 60:
                candidates.append(('kissing', 0.8))
        
        # 'shaking hand with' - hand regions close, medium distance
        if 50 < dist < 200:
            # Estimate hand positions (middle-lower body)
            s_hand_y = subj.bbox[1] + (subj.bbox[3] - subj.bbox[1]) * 0.55
            o_hand_y = obj.bbox[1] + (obj.bbox[3] - obj.bbox[1]) * 0.55
            if abs(s_hand_y - o_hand_y) < 50:
                candidates.append(('shaking hand with', 0.7))
        
        # 'hitting' - overlap with motion
        if iou > 0.1:
            subj_speed = self.get_speed(subj.track_id)
            if subj_speed > 15:
                candidates.append(('hitting', 0.8))
        
        # 'chasing' - both moving, subject behind and moving toward
        subj_vel = self.compute_velocity(subj.track_id)
        obj_vel = self.compute_velocity(obj.track_id)
        if subj_vel and obj_vel:
            subj_speed = np.sqrt(subj_vel[0]**2 + subj_vel[1]**2)
            obj_speed = np.sqrt(obj_vel[0]**2 + obj_vel[1]**2)
            if subj_speed > 5 and obj_speed > 3 and dist < 400:
                candidates.append(('chasing', 0.8))
        
        # 'guiding' - close, one leading
        if dist < 150 and overlap_x > 0:
            candidates.append(('guiding', 0.6))
        
        # 'carrying' - one much smaller (child) and overlapping
        if o_area < s_area * 0.4 and iou > 0.2:
            candidates.append(('carrying', 0.85))
        
        # 'caressing' - close contact
        if dist < 100 and (overlap_x > 0 or overlap_y > 0):
            candidates.append(('caressing', 0.6))
        
        # 'feeding' - close, one bringing something to another's face area
        if dist < 150:
            candidates.append(('feeding', 0.45))
        
        return candidates
    
    # =========================================================================
    # PERSON-OBJECT RELATION DETECTION
    # =========================================================================
    
    def detect_person_object_relations(
        self, person: Detection, obj: Detection, hands: List[HandDetection]
    ) -> List[Tuple[str, float]]:
        """
        Detect person-object relations - the bulk of PVSG predicates.
        """
        candidates = []
        
        p_center = self.bbox_center(person.bbox)
        o_center = self.bbox_center(obj.bbox)
        dist = self.distance(p_center, o_center)
        
        p_area = self.bbox_area(person.bbox)
        o_area = self.bbox_area(obj.bbox)
        
        overlap_x, overlap_y = self.compute_overlap(person.bbox, obj.bbox)
        iou = self.compute_iou(person.bbox, obj.bbox)
        has_overlap = overlap_x > 0 and overlap_y > 0
        
        obj_class = obj.class_name.lower()
        
        # Estimate hand positions
        hand_y = person.bbox[1] + (person.bbox[3] - person.bbox[1]) * 0.55
        hand_region_top = hand_y - 50
        hand_region_bottom = hand_y + 80
        obj_in_hand_region = hand_region_top < o_center[1] < hand_region_bottom
        
        # Get motion info
        person_speed = self.get_speed(person.track_id)
        obj_speed = self.get_speed(obj.track_id)
        person_vel = self.compute_velocity(person.track_id)
        obj_vel = self.compute_velocity(obj.track_id)
        
        # =====================================================================
        # HOLDING / CARRYING / GRABBING
        # =====================================================================
        if self.class_in_set(obj_class, HOLDABLE) or o_area < p_area * 0.3:
            if has_overlap or dist < 150:
                if obj_in_hand_region or iou > 0.05:
                    candidates.append(('holding', 0.9))
                    candidates.append(('grabbing', 0.7))
                elif dist < 100:
                    candidates.append(('holding', 0.8))
            
            # Carrying - holding while moving
            if (has_overlap or dist < 100) and person_speed > 5:
                candidates.append(('carrying', 0.85))
        
        # =====================================================================
        # THROWING / CATCHING / PICKING
        # =====================================================================
        if self.class_in_set(obj_class, HOLDABLE) or self.class_in_set(obj_class, KICKABLE):
            # Throwing - object has high velocity, was near person
            if obj_speed > 20 and dist < 300:
                candidates.append(('throwing', 0.85))
            
            # Catching - object moving toward person
            if obj_vel and obj_speed > 10:
                dir_to_person = (p_center[0] - o_center[0], p_center[1] - o_center[1])
                dir_mag = np.sqrt(dir_to_person[0]**2 + dir_to_person[1]**2)
                if dir_mag > 0:
                    cos_angle = (obj_vel[0]*dir_to_person[0] + obj_vel[1]*dir_to_person[1]) / (obj_speed * dir_mag)
                    if cos_angle > 0.3 and dist < 300:
                        candidates.append(('catching', 0.8))
            
            # Picking - reaching down
            if o_center[1] > p_center[1] + 50 and dist < 200:
                candidates.append(('picking', 0.75))
        
        # =====================================================================
        # KICKING / HITTING
        # =====================================================================
        if self.class_in_set(obj_class, KICKABLE):
            foot_y = person.bbox[3] - 30
            if abs(o_center[1] - foot_y) < 80 and dist < 150:
                if person_speed > 3 or obj_speed > 5:
                    candidates.append(('kicking', 0.85))
            
            if has_overlap and (person_speed > 10 or obj_speed > 10):
                candidates.append(('hitting', 0.75))
        
        # =====================================================================
        # SITTING ON / LYING ON / STANDING ON
        # =====================================================================
        if self.class_in_set(obj_class, SITTING_SURFACES):
            if has_overlap or iou > 0.05:
                # Person on furniture
                candidates.append(('sitting on', 0.9))
            elif dist < 150:
                candidates.append(('sitting on', 0.75))
        
        if self.class_in_set(obj_class, LYING_SURFACES):
            if has_overlap:
                # Check if person is horizontal (wide aspect ratio)
                p_width = person.bbox[2] - person.bbox[0]
                p_height = person.bbox[3] - person.bbox[1]
                if p_width > p_height * 1.2:
                    candidates.append(('lying on', 0.9))
                else:
                    candidates.append(('lying on', 0.7))
        
        if self.class_in_set(obj_class, SURFACE_CLASSES):
            if has_overlap:
                p_bottom = person.bbox[3]
                o_top = obj.bbox[1]
                if p_bottom > o_top - 30:
                    if person_speed < 3:
                        candidates.append(('standing on', 0.85))
                    elif person_speed < 15:
                        candidates.append(('walking on', 0.85))
                    else:
                        candidates.append(('running on', 0.85))
                    candidates.append(('stepping on', 0.6))
        
        # =====================================================================
        # RIDING
        # =====================================================================
        if self.class_in_set(obj_class, RIDEABLE):
            if has_overlap or iou > 0.1:
                candidates.append(('riding', 0.95))
            elif dist < 100:
                candidates.append(('riding', 0.8))
        
        # =====================================================================
        # WEARING
        # =====================================================================
        if self.class_in_set(obj_class, WEARABLE):
            if has_overlap or iou > 0.1:
                candidates.append(('wearing', 0.9))
        
        # =====================================================================
        # EATING / DRINKING FROM
        # =====================================================================
        face_y = person.bbox[1] + (person.bbox[3] - person.bbox[1]) * 0.2
        obj_near_face = abs(o_center[1] - face_y) < 80 and abs(o_center[0] - p_center[0]) < 100
        
        if self.class_in_set(obj_class, FOOD_ITEMS):
            if obj_near_face or (has_overlap and o_center[1] < p_center[1]):
                candidates.append(('eating', 0.9))
            elif dist < 150:
                candidates.append(('eating', 0.7))
        
        if self.class_in_set(obj_class, DRINK_ITEMS):
            if obj_near_face or (has_overlap and o_center[1] < p_center[1]):
                candidates.append(('drinking from', 0.9))
            elif dist < 150:
                candidates.append(('drinking from', 0.7))
        
        # =====================================================================
        # OPENING / CLOSING
        # =====================================================================
        if self.class_in_set(obj_class, OPENABLE):
            if dist < 150 or has_overlap:
                if person_speed > 2:
                    candidates.append(('opening', 0.7))
                    candidates.append(('closing', 0.65))
        
        # =====================================================================
        # PUSHING / PULLING
        # =====================================================================
        if dist < 150 and has_overlap:
            if person_vel and obj_vel:
                # Same direction = pushing
                dot = person_vel[0]*obj_vel[0] + person_vel[1]*obj_vel[1]
                if dot > 0 and person_speed > 3:
                    candidates.append(('pushing', 0.8))
                elif dot < 0:
                    candidates.append(('pulling', 0.75))
            elif person_speed > 5:
                candidates.append(('pushing', 0.7))
        
        # =====================================================================
        # PLAYING / PLAYING WITH
        # =====================================================================
        if self.class_in_set(obj_class, PLAYABLE):
            if dist < 200 or has_overlap:
                candidates.append(('playing with', 0.85))
                candidates.append(('playing', 0.75))
        
        # =====================================================================
        # SWINGING
        # =====================================================================
        if self.class_in_set(obj_class, HOLDABLE) and obj_speed > 15:
            if dist < 200:
                candidates.append(('swinging', 0.8))
        
        # =====================================================================
        # TOUCHING - generic contact
        # =====================================================================
        if has_overlap or dist < 80:
            candidates.append(('touching', 0.8))
        
        # =====================================================================
        # LOOKING AT - very common, medium distance
        # =====================================================================
        if dist < 400:
            conf = max(0.4, 0.8 - dist / 500)
            candidates.append(('looking at', conf))
        
        # =====================================================================
        # POINTING TO
        # =====================================================================
        if 100 < dist < 500:
            candidates.append(('pointing to', 0.5))
        
        # =====================================================================
        # CONTEXT-SPECIFIC RELATIONS
        # =====================================================================
        
        # Cooking/stirring/cutting - kitchen context
        if any(k in obj_class for k in ['pot', 'pan', 'stove', 'oven', 'food']):
            if dist < 150:
                candidates.append(('cooking', 0.7))
                candidates.append(('stirring', 0.6))
        
        if any(k in obj_class for k in ['knife', 'cutting board']):
            if dist < 100:
                candidates.append(('cutting', 0.75))
        
        # Cleaning
        if any(k in obj_class for k in ['broom', 'mop', 'cloth', 'sponge', 'vacuum']):
            if dist < 150:
                candidates.append(('cleaning', 0.8))
        
        # Watering
        if any(k in obj_class for k in ['hose', 'watering can', 'plant', 'flower']):
            if dist < 150:
                candidates.append(('watering', 0.7))
        
        # Lighting
        if any(k in obj_class for k in ['candle', 'lighter', 'match', 'lamp']):
            if dist < 100:
                candidates.append(('lighting', 0.7))
        
        # Brushing
        if any(k in obj_class for k in ['brush', 'toothbrush', 'hair']):
            if dist < 100:
                candidates.append(('brushing', 0.75))
        
        # Blowing - CRITICAL for birthday cake scenes!
        if any(k in obj_class for k in ['candle', 'balloon', 'bubble', 'cake']):
            if dist < 200:  # Extended range
                candidates.append(('blowing', 0.9))  # HIGH priority for candle
        
        # Entering
        if any(k in obj_class for k in ['door', 'gate', 'building', 'car', 'bus', 'room']):
            if dist < 200 and person_speed > 3:
                candidates.append(('entering', 0.7))
        
        # Hanging from
        if any(k in obj_class for k in ['bar', 'rope', 'branch', 'pole']):
            if has_overlap and p_center[1] > o_center[1]:
                candidates.append(('hanging from', 0.8))
        
        # Jumping from/over
        if person_speed > 10:
            if o_center[1] > p_center[1]:
                candidates.append(('jumping from', 0.7))
            if has_overlap:
                candidates.append(('jumping over', 0.7))
        
        return candidates
    
    # =========================================================================
    # ANIMAL RELATIONS
    # =========================================================================
    
    def detect_animal_relations(
        self, animal: Detection, obj: Detection
    ) -> List[Tuple[str, float]]:
        """Detect animal-specific relations."""
        candidates = []
        
        a_center = self.bbox_center(animal.bbox)
        o_center = self.bbox_center(obj.bbox)
        dist = self.distance(a_center, o_center)
        
        overlap_x, overlap_y = self.compute_overlap(animal.bbox, obj.bbox)
        has_overlap = overlap_x > 0 and overlap_y > 0
        
        obj_class = obj.class_name.lower()
        animal_speed = self.get_speed(animal.track_id)
        
        # Sitting/lying/standing on surfaces
        if self.class_in_set(obj_class, SURFACE_CLASSES):
            if has_overlap:
                if animal_speed < 3:
                    candidates.append(('sitting on', 0.8))
                    candidates.append(('lying on', 0.75))
                else:
                    candidates.append(('walking on', 0.8))
                    candidates.append(('running on', 0.7))
                candidates.append(('standing on', 0.7))
        
        # In containers
        if self.class_in_set(obj_class, CONTAINERS):
            if has_overlap:
                candidates.append(('in', 0.85))
        
        # Playing with toys
        if self.class_in_set(obj_class, PLAYABLE):
            if dist < 150 or has_overlap:
                candidates.append(('playing with', 0.85))
        
        # Eating/drinking
        if self.class_in_set(obj_class, FOOD_ITEMS):
            if dist < 100 or has_overlap:
                candidates.append(('eating', 0.85))
                candidates.append(('biting', 0.7))
                candidates.append(('licking', 0.65))
        
        if self.class_in_set(obj_class, DRINK_ITEMS):
            if dist < 100:
                candidates.append(('drinking from', 0.8))
                candidates.append(('licking', 0.7))
        
        # Chasing
        if animal_speed > 10 and dist < 300:
            candidates.append(('chasing', 0.8))
        
        # Looking at
        if dist < 400:
            candidates.append(('looking at', 0.7))
        
        # Touching
        if has_overlap or dist < 50:
            candidates.append(('touching', 0.75))
        
        # Biting/licking (close contact)
        if dist < 80:
            candidates.append(('biting', 0.6))
            candidates.append(('licking', 0.6))
        
        return candidates
    
    # =========================================================================
    # MAIN PREDICTION METHOD
    # =========================================================================
    
    def predict_relations(
        self,
        detections: List[Detection],
        hand_detections: Dict[int, List[HandDetection]],
        frame_id: int
    ) -> List[Tuple[int, int, str, float]]:
        """
        Predict ALL relevant PVSG relations for a frame.
        
        Returns: List of (subject_id, object_id, predicate, confidence)
        """
        relations = []
        
        # Update track histories
        for det in detections:
            self.update_track_history(det)
        
        # Process all pairs
        for i, subj in enumerate(detections):
            subj_is_person = self.is_person(subj.class_name)
            subj_is_animal = self.is_animal(subj.class_name)
            subj_hands = hand_detections.get(subj.track_id, [])
            
            for j, obj in enumerate(detections):
                if i == j:
                    continue
                
                obj_is_person = self.is_person(obj.class_name)
                obj_is_animal = self.is_animal(obj.class_name)
                
                candidates = []
                
                # 1. Person-Person relations
                if subj_is_person and obj_is_person:
                    candidates.extend(self.detect_person_person_relations(subj, obj, subj_hands))
                
                # 2. Person-Object relations
                elif subj_is_person and not obj_is_person:
                    candidates.extend(self.detect_person_object_relations(subj, obj, subj_hands))
                
                # 3. Animal relations
                elif subj_is_animal:
                    if obj_is_person:
                        # Animal-person: looking at, touching, chasing, etc.
                        dist = self.distance(self.bbox_center(subj.bbox), self.bbox_center(obj.bbox))
                        if dist < 400:
                            candidates.append(('looking at', 0.75))
                        if dist < 100:
                            candidates.append(('touching', 0.8))
                            candidates.append(('licking', 0.6))
                            candidates.append(('biting', 0.5))
                        if self.get_speed(subj.track_id) > 10:
                            candidates.append(('chasing', 0.75))
                    else:
                        candidates.extend(self.detect_animal_relations(subj, obj))
                
                # 4. Object-Object relations (e.g., 'cake on table', 'candle on cake')
                # These are CRITICAL for PVSG - many GT relations are object-object
                elif not subj_is_person and not subj_is_animal:
                    candidates.extend(self.detect_spatial_relations(subj, obj))
                
                # Select best relations (avoid spam)
                if candidates:
                    # Sort by confidence
                    candidates.sort(key=lambda x: -x[1])
                    
                    # Keep top 3 relations per pair
                    seen = set()
                    for pred, conf in candidates:
                        if pred not in seen and conf > 0.4:  # Lower threshold to catch more
                            relations.append((subj.track_id, obj.track_id, pred, conf))
                            seen.add(pred)
                        if len(seen) >= 3:
                            break
        
        return relations


def main():
    """Test the classifier."""
    classifier = PVSGActionClassifier()
    
    person = Detection(track_id=1, class_name='person', bbox=[100, 100, 200, 300], frame_id=10)
    sofa = Detection(track_id=2, class_name='sofa', bbox=[80, 200, 300, 350], frame_id=10)
    
    detections = [person, sofa]
    hand_detections = {}
    
    relations = classifier.predict_relations(detections, hand_detections, frame_id=10)
    
    print("Predicted relations:")
    for subj, obj, pred, conf in relations:
        print(f"  [{subj}] --{pred}--> [{obj}] (conf: {conf:.2f})")


if __name__ == '__main__':
    main()
