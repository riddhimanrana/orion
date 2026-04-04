"""
3D Perception Engine
====================

Handles depth estimation and 3D lifting of entities.
Includes camera intrinsics utilities for 3D backprojection.
"""

import logging
import numpy as np
from typing import List, Dict, Any, Optional, Tuple

from orion.perception.types import Perception3DResult, EntityState3D, Hand, CameraIntrinsics, VisibilityState
from orion.perception.depth import DepthEstimator

# NOTE: SLAM is intentionally not used by the perception engine.
# The project may still contain SLAM code for future experiments, but the
# default 3D pipeline is depth-only.
SLAM_AVAILABLE = False

logger = logging.getLogger(__name__)


# ============================================================================
# 3D Backprojection Utilities
# ============================================================================

def backproject_point(
    u: float,
    v: float,
    depth_z: float,
    intrinsics: CameraIntrinsics
) -> Tuple[float, float, float]:
    """
    Convert 2D pixel + depth to 3D world coordinates.
    
    Uses pinhole camera model:
        X = (u - cx) * Z / fx
        Y = (v - cy) * Z / fy
        Z = depth
    
    Args:
        u, v: Pixel coordinates (x, y)
        depth_z: Depth value in millimeters
        intrinsics: Camera intrinsics
        
    Returns:
        (X_3d, Y_3d, Z_3d) in millimeters
    """
    X_3d = (u - intrinsics.cx) * depth_z / intrinsics.fx
    Y_3d = (v - intrinsics.cy) * depth_z / intrinsics.fy
    Z_3d = depth_z
    return (X_3d, Y_3d, Z_3d)


def backproject_bbox(
    bbox_2d: Tuple[int, int, int, int],
    depth_map: np.ndarray,
    intrinsics: CameraIntrinsics
) -> Dict[str, Any]:
    """
    Backproject 2D bounding box using depth map to get 3D information.
    
    Args:
        bbox_2d: (x1, y1, x2, y2) in pixels
        depth_map: Depth map (H, W) in millimeters
        intrinsics: Camera intrinsics
        
    Returns:
        Dictionary with centroid_3d, bbox_3d_min/max, depth stats
    """
    x1, y1, x2, y2 = bbox_2d
    x1 = max(0, int(x1))
    y1 = max(0, int(y1))
    x2 = min(depth_map.shape[1] - 1, int(x2))
    y2 = min(depth_map.shape[0] - 1, int(y2))
    
    depth_region = depth_map[y1:y2, x1:x2]
    valid_depths = depth_region[(depth_region > 0) & np.isfinite(depth_region)]
    
    if len(valid_depths) == 0:
        return {
            "centroid_3d": (0.0, 0.0, 0.0),
            "bbox_3d_min": (0.0, 0.0, 0.0),
            "bbox_3d_max": (0.0, 0.0, 0.0),
            "depth_mean": 0.0,
            "depth_variance": 0.0,
        }
    
    depth_mean = float(np.mean(valid_depths))
    depth_variance = float(np.std(valid_depths)) ** 2
    
    center_u = (x1 + x2) / 2.0
    center_v = (y1 + y2) / 2.0
    centroid_3d = backproject_point(center_u, center_v, depth_mean, intrinsics)
    
    corners_3d = []
    for u, v in [(x1, y1), (x2, y1), (x1, y2), (x2, y2)]:
        u_int = int(np.clip(u, 0, depth_map.shape[1] - 1))
        v_int = int(np.clip(v, 0, depth_map.shape[0] - 1))
        corner_depth = depth_map[v_int, u_int]
        d = corner_depth if (corner_depth > 0 and np.isfinite(corner_depth)) else depth_mean
        corners_3d.append(backproject_point(u, v, d, intrinsics))
    
    corners_array = np.array(corners_3d)
    return {
        "centroid_3d": centroid_3d,
        "bbox_3d_min": tuple(corners_array.min(axis=0).tolist()),
        "bbox_3d_max": tuple(corners_array.max(axis=0).tolist()),
        "depth_mean": depth_mean,
        "depth_variance": depth_variance,
    }


# ============================================================================
# 3D Perception Engine
# ============================================================================

class Perception3DEngine:
    def __init__(
        self,
        enable_depth: bool = True,
        enable_hands: bool = False,
        enable_occlusion: bool = False,
        enable_slam: bool = False,
        depth_model_size: str = "small",
        camera_intrinsics: Optional[CameraIntrinsics] = None,
    ):
        self.enable_depth = enable_depth
        self.enable_hands = enable_hands
        self.enable_occlusion = enable_occlusion
        self.enable_slam = enable_slam
        self.depth_model_size = depth_model_size
        self.camera_intrinsics = camera_intrinsics
        
        self.depth_estimator = None
        if enable_depth:
            try:
                # Use "depth_anything_3" as per depth.py implementation
                self.depth_estimator = DepthEstimator(
                    model_name="depth_anything_3",
                    model_size=self.depth_model_size,
                )
                logger.info("Perception3DEngine: DepthEstimator initialized")
            except Exception as e:
                logger.error(f"Failed to initialize DepthEstimator: {e}")
        
        self.slam_engine = None
        if enable_slam:
            logger.warning("Perception3DEngine: SLAM requested but is disabled/deprecated in this build")

    def update_camera_intrinsics(self, intrinsics: CameraIntrinsics):
        """Update the camera intrinsics used for 3D calculations."""
        self.camera_intrinsics = intrinsics
        logger.info(f"Perception3DEngine: Camera intrinsics updated to {intrinsics.width}x{intrinsics.height}")

    def process_frame(
        self,
        frame: np.ndarray,
        detections: List[Dict],
        frame_number: int,
        timestamp: float
    ) -> Perception3DResult:
        
        depth_map = None
        if self.depth_estimator:
            depth_map, _ = self.depth_estimator.estimate(frame)
            
        camera_pose = None
            
        # Lift detections to 3D
        entities_3d = []
        if depth_map is not None:
            h, w = frame.shape[:2] # Use frame dimensions
            
            # Use provided intrinsics or estimate from frame dimensions
            if self.camera_intrinsics:
                intrinsics = self.camera_intrinsics
                if intrinsics.width != w or intrinsics.height != h:
                    logger.warning(f"Intrinsics dimensions ({intrinsics.width}x{intrinsics.height}) mismatch frame dimensions ({w}x{h}). Using frame dimensions for estimation.")
                    intrinsics = CameraIntrinsics.auto_estimate(w, h)
            else:
                intrinsics = CameraIntrinsics.auto_estimate(w, h)
            
            for det in detections:
                bbox = det.get('bbox') # (x1, y1, x2, y2)
                if bbox:
                    x1, y1, x2, y2 = [int(c) for c in bbox]
                    cx, cy = int((x1 + x2) / 2), int((y1 + y2) / 2)
                    
                    # Clamp to image bounds
                    cx = max(0, min(w - 1, cx))
                    cy = max(0, min(h - 1, cy))
                    
                    # Sample depth at centroid
                    z = float(depth_map[cy, cx])
                    
                    # Backproject
                    centroid_3d = backproject_point(float(cx), float(cy), z, intrinsics)
                    
                    entity_3d = EntityState3D(
                        entity_id=det.get('entity_id', 'unknown'),
                        frame_number=frame_number,
                        timestamp=timestamp,
                        class_label=det.get('class', 'unknown'),
                        class_confidence=det.get('confidence', 0.0),
                        bbox_2d_px=(x1, y1, x2, y2),
                        centroid_2d_px=(float(cx), float(cy)),
                        centroid_3d_mm=centroid_3d,
                        depth_mean_mm=z,
                        visibility_state=VisibilityState.FULLY_VISIBLE
                    )
                    entities_3d.append(entity_3d)

        return Perception3DResult(
            frame_number=frame_number,
            timestamp=timestamp,
            entities=entities_3d,
            hands=[],
            depth_map=depth_map,
            camera_pose=camera_pose
        )
