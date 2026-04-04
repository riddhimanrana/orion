import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import math
import numpy as np

from orion.graph.types import SceneGraph, SGNode, SGEdge, VideoSceneGraph

# Temporal smoother import (optional)
try:
    from orion.graph.temporal_smoothing import SceneGraphSmoother
    TEMPORAL_SMOOTHING_AVAILABLE = True
except ImportError:
    TEMPORAL_SMOOTHING_AVAILABLE = False


def _emb_to_mem_map(memory: Dict[str, Any]) -> Dict[str, str]:
    m: Dict[str, str] = {}
    for obj in memory.get("objects", []):
        emb_id = obj.get("prototype_embedding")
        mid = obj.get("memory_id")
        if emb_id and mid:
            m[emb_id] = mid
    return m


def _iou(a: List[float], b: List[float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    aw, ah = max(0.0, ax2 - ax1), max(0.0, ay2 - ay1)
    bw, bh = max(0.0, bx2 - bx1), max(0.0, by2 - by1)
    ua = aw * ah + bw * bh - inter + 1e-8
    return float(inter / ua)


def _centroid(b: List[float]) -> Tuple[float, float]:
    x1, y1, x2, y2 = b
    return (0.5 * (x1 + x2), 0.5 * (y1 + y2))


def _inside(px: float, py: float, b: List[float]) -> bool:
    x1, y1, x2, y2 = b
    return (px >= x1) and (px <= x2) and (py >= y1) and (py <= y2)


def _frame_diag(wh: Tuple[int, int]) -> float:
    w, h = wh
    if not w or not h:
        return 1.0
    return float(math.hypot(w, h))


def _horiz_overlap_ratio(a: List[float], b: List[float]) -> float:
    ax1, _, ax2, _ = a
    bx1, _, bx2, _ = b
    left = max(ax1, bx1)
    right = min(ax2, bx2)
    ov = max(0.0, right - left)
    aw = max(1e-8, ax2 - ax1)
    bw = max(1e-8, bx2 - bx1)
    return float(ov / min(aw, bw))


def build_scene_graphs(
    memory: Dict[str, Any],
    tracks: List[Dict[str, Any]],
    relations: Optional[List[str]] = None,
    near_dist_norm: float = 0.08,
    on_h_overlap: float = 0.3,
    on_vgap_norm: float = 0.02,
    on_subj_overlap_min: float = 0.5,
    on_subj_within_obj: float = 0.0,
    on_small_subject_area: float = 0.05,
    on_small_overlap: float = 0.15,
    on_small_vgap: float = 0.05,
    iou_exclude: float = 0.1,
    held_by_iou: float = 0.3,
    near_small_dist_norm: float = 0.06,
    near_small_area: float = 0.05,
    exclude_on_pairs: Optional[List[Tuple[str, str]]] = None,
    use_pose_for_held: bool = False,
    pose_hand_dist: float = 0.03,
    enable_class_filtering: bool = True,
    # Temporal smoothing parameters (Deep Research v3)
    enable_temporal_smoothing: bool = False,
    temporal_window_size: int = 5,
    temporal_near_threshold: float = 0.4,
    temporal_on_threshold: float = 0.6,
    temporal_held_by_threshold: float = 0.7,
) -> List[Dict[str, Any]]:
    """
    Build per-frame scene graph snapshots with nodes (memory objects) and edges (relations).
    Each graph snapshot has: frame, nodes (list of {memory_id, class, bbox}), edges (list of {relation, subject, object}).
    
    Class filtering rules (when enabled):
    - held_by: subject must be portable (exclude furniture like bed, couch, table, chair, desk)
    - on: subject should be smaller/movable object, or use vertical position (higher object on lower)
    
    Temporal smoothing (when enabled):
    - Uses rolling window to filter flickering edges
    - Relation-specific thresholds control strictness
    """
    if relations is None:
        relations = ["near", "on", "held_by"]
    
    # Class constraints
    FURNITURE_CLASSES = {"bed", "couch", "sofa", "table", "desk", "chair", "bench", "cabinet", "refrigerator"}
    PORTABLE_CLASSES = {"book", "bottle", "cup", "phone", "laptop", "remote", "keyboard", "mouse", "backpack", "handbag", "suitcase"}

    emb_to_mem = _emb_to_mem_map(memory)
    mem_to_class: Dict[str, str] = {}
    for obj in memory.get("objects", []):
        mem_to_class[obj["memory_id"]] = obj.get("class", "object")

    # Group tracks by frame
    by_frame: Dict[int, List[Dict[str, Any]]] = {}
    for r in tracks:
        emb = r.get("embedding_id")
        mem_id = emb_to_mem.get(emb)
        if not mem_id:
            continue
        # Support both bbox and bbox_2d field names
        bbox = r.get("bbox") or r.get("bbox_2d")
        item = {
            "memory_id": mem_id,
            "class": mem_to_class.get(mem_id, r.get("category", "object")),
            "bbox": bbox,
            "frame_width": int(r.get("frame_width", 0)),
            "frame_height": int(r.get("frame_height", 0)),
        }
        by_frame.setdefault(int(r.get("frame_id", 0)), []).append(item)

    graphs: List[Dict[str, Any]] = []
    for frame_id in sorted(by_frame.keys()):
        obs = by_frame[frame_id]
        nodes = []
        edges = []

        for o in obs:
            nodes.append({
                "memory_id": o["memory_id"],
                "class": o["class"],
                "bbox": o["bbox"],
            })

        n = len(obs)
        # Precompute person keypoints map if available (per memory id)
        person_keypoints: Dict[str, List[Tuple[float, float]]] = {}
        for o in obs:
            if o.get("class") == "person":
                kp = o.get("keypoints") or o.get("hand_keypoints") or None
                if kp and isinstance(kp, list):
                    person_keypoints[o["memory_id"]] = kp

        # Infer frame dimensions if missing: estimate from max bbox extent
        # (fallback to typical HD resolution if no bboxes)
        frame_width = None
        frame_height = None
        if obs and obs[0].get("frame_width") and obs[0].get("frame_height"):
            frame_width = obs[0].get("frame_width")
            frame_height = obs[0].get("frame_height")
        else:
            # Estimate from bboxes
            max_x, max_y = 0, 0
            for o in obs:
                if o.get("bbox"):
                    bbox = o["bbox"]
                    max_x = max(max_x, bbox[2])
                    max_y = max(max_y, bbox[3])
            if max_x > 0 and max_y > 0:
                frame_width = int(max_x * 1.1)  # Add 10% margin
                frame_height = int(max_y * 1.1)
            else:
                # Fallback to typical HD resolution
                frame_width = 1280
                frame_height = 720

        for i in range(n):
            A = obs[i]
            for j in range(n):
                if i == j:
                    continue
                B = obs[j]
                if not A.get("bbox") or not B.get("bbox"):
                    continue
                a_b = A["bbox"]
                b_b = B["bbox"]
                wh = (frame_width, frame_height)
                diag = _frame_diag(wh)
                iou_val = _iou(a_b, b_b)

                cxA, cyA = _centroid(a_b)
                cxB, cyB = _centroid(b_b)
                dist = math.hypot(cxA - cxB, cyA - cyB) / max(1e-6, diag)
                bottomA = a_b[3]
                topB = b_b[1]
                h_ov = _horiz_overlap_ratio(a_b, b_b)
                vgap = abs(topB - bottomA) / max(1.0, wh[1])
                # Component-wise overlap and areas for adaptive logic
                ax1, ay1, ax2, ay2 = a_b
                bx1, by1, bx2, by2 = b_b
                aw = max(1e-8, ax2 - ax1)
                ah = max(1e-8, ay2 - ay1)
                bw = max(1e-8, bx2 - bx1)
                bh = max(1e-8, by2 - by1)
                left = max(ax1, bx1)
                right = min(ax2, bx2)
                ov = max(0.0, right - left)
                h_ov_subj = float(ov / max(aw, 1e-8))
                frame_area = max(1.0, float(wh[0] * wh[1]))
                a_area_norm = float((aw * ah) / frame_area)

                # Skip excluded class pairs for 'on'
                pair_excluded = False
                if exclude_on_pairs:
                    a_cls = A.get("class", "object")
                    b_cls = B.get("class", "object")
                    for p in exclude_on_pairs:
                        if (a_cls == p[0] and b_cls == p[1]) or (a_cls == p[1] and b_cls == p[0]):
                            pair_excluded = True

                # Evaluate relations
                if "near" in relations:
                    # Adaptive near: reduce distance for small objects
                    eff_near = near_dist_norm
                    if (a_area_norm <= near_small_area) or ((bw * bh) / max(1.0, float(wh[0] * wh[1])) <= near_small_area):
                        eff_near = min(eff_near, near_small_dist_norm)
                    if (dist <= eff_near) and (iou_val < iou_exclude):
                        edges.append({
                            "relation": "near",
                            "subject": A["memory_id"],
                            "object": B["memory_id"],
                        })
                if "on" in relations:
                    if pair_excluded:
                        # Skip this class pair
                        pass
                    else:
                        # Apply class filtering: prefer smaller/portable as subject, or use vertical ordering
                        subject_ok = True
                        if enable_class_filtering:
                            # If both are furniture or both portable, use vertical position (higher "on" lower)
                            # Otherwise, portable object should be subject
                            a_portable = A["class"] in PORTABLE_CLASSES or A["class"] not in FURNITURE_CLASSES
                            b_portable = B["class"] in PORTABLE_CLASSES or B["class"] not in FURNITURE_CLASSES
                            if not a_portable and b_portable:
                                subject_ok = False  # furniture can't be on portable object
                        # Adaptive thresholds for small subjects
                        eff_h_ov = on_h_overlap
                        eff_vgap = on_vgap_norm
                        eff_subj_ov = on_subj_overlap_min
                        if a_area_norm <= on_small_subject_area:
                            eff_h_ov = min(eff_h_ov, on_small_overlap)
                            eff_vgap = max(eff_vgap, on_small_vgap)
                            eff_subj_ov = min(eff_subj_ov, max(0.3, on_small_overlap))

                        # Subject-within-object check: fraction of subject x-span inside object x-span
                        subj_within_ok = True
                        if on_subj_within_obj > 0:
                            subj_inside = min(ax2, bx2) - max(ax1, bx1)
                            subj_width = ax2 - ax1
                            if subj_width > 0:
                                within_ratio = max(0.0, subj_inside) / subj_width
                                subj_within_ok = (within_ratio >= on_subj_within_obj)

                        if subject_ok and subj_within_ok and (h_ov >= eff_h_ov) and (h_ov_subj >= eff_subj_ov) and (vgap <= eff_vgap) and (cyA <= cyB):
                            edges.append({
                                "relation": "on",
                                "subject": A["memory_id"],
                                "object": B["memory_id"],
                            })
                if "held_by" in relations:
                    if A["class"] != "person" and B["class"] == "person":
                        # Apply class filtering: exclude furniture from being held
                        subject_ok = True
                        if enable_class_filtering and A["class"] in FURNITURE_CLASSES:
                            subject_ok = False
                        
                        if subject_ok:
                            # Pose-aware scoring if available
                            score = 0.0
                            pose_hit = False
                            if use_pose_for_held and B["memory_id"] in person_keypoints:
                                kps = person_keypoints[B["memory_id"]]
                                # normalize keypoints to frame if necessary
                                normalized_kps: List[Tuple[float, float]] = []
                                for p in kps:
                                    try:
                                        px, py = float(p[0]), float(p[1])
                                    except Exception:
                                        continue
                                    # If keypoints look normalized (0-1), scale to pixels
                                    if 0.0 <= px <= 1.0 and 0.0 <= py <= 1.0 and wh[0] and wh[1]:
                                        px *= wh[0]
                                        py *= wh[1]
                                    normalized_kps.append((px, py))
                                # compute min distance to subject centroid
                                if normalized_kps:
                                    min_d = min(math.hypot(px - cxA, py - cyA) for px, py in normalized_kps)
                                    if (min_d / max(1e-6, _frame_diag(wh))) <= pose_hand_dist:
                                        pose_hit = True
                                        score = 1.0
                            # Fallback to IoU/inside check
                            if not pose_hit:
                                if iou_val >= held_by_iou:
                                    score = iou_val
                                elif _inside(cxA, cyA, b_b):
                                    score = 0.5
                            if score > 0.0:
                                edges.append({
                                    "relation": "held_by",
                                    "subject": A["memory_id"],
                                    "object": B["memory_id"],
                                    "score": float(score),
                                })
        # Unique best-person selection for held_by: keep only highest-score person per subject
        held_by_edges = [e for e in edges if e.get("relation") == "held_by"]
        if held_by_edges:
            best_held: Dict[str, Dict[str, Any]] = {}
            for e in held_by_edges:
                subj = e["subject"]
                score = e.get("score", 0.0)
                if subj not in best_held or score > best_held[subj].get("score", 0.0):
                    best_held[subj] = e
            # Remove all held_by edges and add back only best per subject
            edges = [e for e in edges if e.get("relation") != "held_by"]
            for e in best_held.values():
                e.pop("score", None)  # Remove score before final output
                edges.append(e)

        graphs.append({
            "frame": frame_id,
            "nodes": nodes,
            "edges": edges,
        })

    # Apply temporal smoothing if enabled (Deep Research v3)
    if enable_temporal_smoothing and TEMPORAL_SMOOTHING_AVAILABLE:
        try:
            from orion.graph.temporal_smoothing import TemporalSmoothingConfig
            
            smooth_config = TemporalSmoothingConfig(
                window_size=temporal_window_size,
                relation_specific_thresholds={
                    "near": temporal_near_threshold,
                    "on": temporal_on_threshold,
                    "held_by": temporal_held_by_threshold,
                },
            )
            smoother = SceneGraphSmoother(config=smooth_config)
            graphs = smoother.smooth_graphs(graphs)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Temporal smoothing failed: {e}")

    return graphs


def save_scene_graphs(graphs: List[Dict[str, Any]], out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        for g in graphs:
            f.write(json.dumps(g) + "\n")
    return out_path


def build_graph_summary(graphs: List[Dict[str, Any]]) -> Dict[str, Any]:
    total_frames = len(graphs)
    total_nodes = sum(len(g.get("nodes", [])) for g in graphs)
    total_edges = sum(len(g.get("edges", [])) for g in graphs)

    rel_counts: Dict[str, int] = {}
    for g in graphs:
        for e in g.get("edges", []):
            rel = e.get("relation", "unknown")
            rel_counts[rel] = rel_counts.get(rel, 0) + 1

    return {
        "total_frames": total_frames,
        "total_nodes": total_nodes,
        "total_edges": total_edges,
        "relation_counts": rel_counts,
        "avg_nodes_per_frame": round(total_nodes / max(1, total_frames), 2),
        "avg_edges_per_frame": round(total_edges / max(1, total_frames), 2),
    }


def save_graph_summary(summary: Dict[str, Any], out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(summary, f, indent=2)
    return out_path


def build_research_scene_graph(
    memory: Dict[str, Any],
    tracks: List[Dict[str, Any]],
    video_id: str = "video",
    include_cis_edges: bool = False,
    cis_threshold: float = 0.50,
    **kwargs
) -> VideoSceneGraph:
    """
    Build a research-grade Scene Graph using the new schema.
    Wraps the heuristic logic of build_scene_graphs but returns typed objects.
    
    Args:
        memory: Memory dict with clustered objects
        tracks: List of track observations
        video_id: Identifier for the video
        include_cis_edges: Whether to compute Causal Influence Scoring edges
        cis_threshold: Minimum CIS score to include an edge
        **kwargs: Additional arguments for build_scene_graphs
    
    Returns:
        VideoSceneGraph with nodes and edges (spatial + optional causal)
    """
    # Reuse existing logic to get raw dicts
    raw_graphs = build_scene_graphs(memory, tracks, **kwargs)
    
    video_sg = VideoSceneGraph(video_id=video_id)
    
    # Optionally set up CIS scorer
    cis_scorer = None
    if include_cis_edges:
        try:
            from orion.analysis.cis_scorer import CausalInfluenceScorer
            cis_scorer = CausalInfluenceScorer(cis_threshold=cis_threshold)
        except ImportError:
            pass
    
    for g in raw_graphs:
        frame_idx = g.get("frame", 0)
        # Estimate timestamp if not present (assuming 30fps or passed in kwargs)
        timestamp = g.get("timestamp", frame_idx / 30.0) 
        
        sg = SceneGraph(frame_index=frame_idx, timestamp=timestamp)
        
        # Add nodes
        for n in g.get("nodes", []):
            node = SGNode(
                id=n["memory_id"],
                label=n["class"],
                bbox=n.get("bbox"),
                confidence=n.get("confidence", 1.0),
                attributes=n.get("attributes", [])
            )
            sg.nodes.append(node)
            
        # Add spatial edges (near, on, held_by)
        for e in g.get("edges", []):
            edge = SGEdge(
                subject_id=e["subject"],
                predicate=e["relation"],
                object_id=e["object"],
                confidence=e.get("confidence", 1.0)
            )
            sg.edges.append(edge)
        
        # Add CIS edges if enabled
        if cis_scorer and len(sg.nodes) > 1:
            cis_edges = _compute_cis_edges_for_frame(
                sg.nodes, g.get("nodes", []), frame_idx, timestamp, cis_scorer
            )
            sg.edges.extend(cis_edges)
            
        video_sg.graphs.append(sg)
        
    return video_sg


def _compute_cis_edges_for_frame(
    sg_nodes: List[SGNode],
    raw_nodes: List[Dict],
    frame_idx: int,
    timestamp: float,
    cis_scorer,
) -> List[SGEdge]:
    """
    Compute CIS-based causal edges for a single frame.
    
    Creates 'influences', 'grasps', and 'moves_with' edges between entities.
    """
    from dataclasses import dataclass, field
    
    @dataclass
    class _EntityProxy:
        """Lightweight entity proxy for CIS computation.
        
        Must expose `average_embedding` and `object_class` for semantic scoring.
        """
        id: str
        object_class: str
        bbox: List[float]
        state: Optional[List[float]] = None  # [x, y, z, vx, vy, vz]
        bbox_3d: Optional[List[float]] = None
        observations: List = None
        # Embedding for semantic scoring (optional, CIS will use neutral if None)
        average_embedding: Optional[np.ndarray] = None
        depth_mm: Optional[float] = None  # Depth for 3D gating
        
        def __post_init__(self):
            if self.observations is None:
                self.observations = []
    
    # Build entity proxies from raw nodes
    proxies = []
    for raw in raw_nodes:
        # Extract embedding if available (prototype or observation embedding)
        emb = raw.get("average_embedding") or raw.get("embedding")
        if emb is not None and not isinstance(emb, np.ndarray):
            emb = np.array(emb)
        
        # Extract depth from 3D state or bbox_3d
        depth = None
        if raw.get("state_3d") and len(raw.get("state_3d", [])) >= 3:
            depth = raw["state_3d"][2]  # Z component
        elif raw.get("bbox_3d") and len(raw.get("bbox_3d", [])) >= 3:
            depth = raw["bbox_3d"][2]  # Z component
        elif raw.get("depth_mm"):
            depth = raw["depth_mm"]
            
        proxy = _EntityProxy(
            id=raw["memory_id"],
            object_class=raw["class"],
            bbox=raw.get("bbox", [0, 0, 0, 0]),
            state=raw.get("state_3d"),  # [x, y, z, vx, vy, vz] if available
            bbox_3d=raw.get("bbox_3d"),
            average_embedding=emb,
            depth_mm=depth,
        )
        proxies.append(proxy)
    
    if len(proxies) < 2:
        return []
    
    # Compute CIS edges
    cis_edges_raw = cis_scorer.compute_frame_edges(
        entities=proxies,
        frame_id=frame_idx,
        timestamp=timestamp,
    )
    
    # Convert to SGEdge
    sg_edges = []
    for ce in cis_edges_raw:
        edge = SGEdge(
            subject_id=str(ce.agent_id),
            predicate=ce.relation_type,  # "influences", "grasps", "moves_with"
            object_id=str(ce.patient_id),
            confidence=ce.cis_score,
        )
        sg_edges.append(edge)
    
    return sg_edges
