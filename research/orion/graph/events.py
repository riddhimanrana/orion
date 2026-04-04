import json
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional

import math


def load_tracks(tracks_path: Path) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    with open(tracks_path, "r") as f:
        for line in f:
            if line.strip():
                items.append(json.loads(line))
    return items


def load_memory(memory_path: Path) -> Dict[str, Any]:
    return json.loads(memory_path.read_text())


def _sorted_segments(obj: Dict[str, Any]) -> List[Dict[str, Any]]:
    segs = obj.get("appearance_history", [])
    segs = sorted(segs, key=lambda s: (s.get("first_frame", 0), s.get("last_frame", 0)))
    return segs


def build_events(memory: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Build lifecycle events (appeared, disappeared, reappeared, merged) using memory.json.

    Returns a list of event dicts suitable for writing to events.jsonl.
    """
    events: List[Dict[str, Any]] = []

    objects = memory.get("objects", [])
    for obj in objects:
        mem_id = obj.get("memory_id")
        segs = _sorted_segments(obj)
        if not segs:
            continue

        # Appeared at first segment start
        first = segs[0]
        events.append({
            "type": "appeared",
            "memory_id": mem_id,
            "frame": int(first.get("first_frame", 0)),
            "track_id": int(first.get("track_id")) if "track_id" in first else None,
            "details": f"First detection of {obj.get('class', 'object')}"
        })

        # For each segment, disappear at its end unless another starts right away
        for i, seg in enumerate(segs):
            last_frame = int(seg.get("last_frame", seg.get("first_frame", 0)))
            cur_tid = int(seg.get("track_id")) if "track_id" in seg else None
            # If there's a next segment, create reappeared and merged if track changed
            if i + 1 < len(segs):
                nxt = segs[i + 1]
                next_first = int(nxt.get("first_frame", 0))
                next_tid = int(nxt.get("track_id")) if "track_id" in nxt else None
                # Disappeared at end of current segment
                events.append({
                    "type": "disappeared",
                    "memory_id": mem_id,
                    "frame": last_frame,
                    "track_id": cur_tid,
                    "reason": "occluded",
                })
                # Reappeared at start of next segment
                gap = max(0, next_first - last_frame)
                events.append({
                    "type": "reappeared",
                    "memory_id": mem_id,
                    "frame": next_first,
                    "track_id": next_tid,
                    "gap_frames": gap,
                })
                # If track changed, note a merge of duplicate tracks
                if next_tid is not None and cur_tid is not None and next_tid != cur_tid:
                    events.append({
                        "type": "merged",
                        "memory_id": mem_id,
                        "frame": next_first,
                        "merged_tracks": [cur_tid, next_tid],
                        "details": "Duplicate tracks merged via re-ID",
                    })
            else:
                # Last segment: disappeared at its end due to end-of-episode
                events.append({
                    "type": "disappeared",
                    "memory_id": mem_id,
                    "frame": last_frame,
                    "track_id": cur_tid,
                    "reason": "end",
                })

    return events


# ==========================
# Advanced heuristics (Phase 3+)
# ==========================

def _emb_to_mem_map(memory: Dict[str, Any]) -> Dict[str, str]:
    m: Dict[str, str] = {}
    for obj in memory.get("objects", []):
        emb_id = obj.get("prototype_embedding")
        mid = obj.get("memory_id")
        if emb_id and mid:
            m[emb_id] = mid
    return m


def _per_frame_memory_observations(tracks: List[Dict[str, Any]], memory: Dict[str, Any]) -> Dict[int, List[Dict[str, Any]]]:
    emb_to_mem = _emb_to_mem_map(memory)
    by_frame: Dict[int, List[Dict[str, Any]]] = {}
    for r in tracks:
        emb = r.get("embedding_id")
        mem_id = emb_to_mem.get(emb)
        if not mem_id:
            continue
        item = {
            "memory_id": mem_id,
            "track_id": int(r.get("track_id", -1)),
            "category": r.get("category", "object"),
            "bbox": r.get("bbox"),
            "frame_id": int(r.get("frame_id", 0)),
            "frame_width": int(r.get("frame_width", 0)),
            "frame_height": int(r.get("frame_height", 0)),
        }
        by_frame.setdefault(item["frame_id"], []).append(item)
    return by_frame


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


def build_state_events(
    memory: Dict[str, Any],
    tracks: List[Dict[str, Any]],
    iou_threshold: float = 0.3,
    debounce_window: int = 1,
) -> List[Dict[str, Any]]:
    """
    Infer simple state changes like held_by_person per memory, using spatial overlap.
    Emits state_change events on transitions. Debounces with a min consecutive frame window.
    """
    events: List[Dict[str, Any]] = []
    by_frame = _per_frame_memory_observations(tracks, memory)

    # Track debounced state per memory_id
    state: Dict[str, Dict[str, Any]] = {}

    for frame_id in sorted(by_frame.keys()):
        obs = by_frame[frame_id]
        persons = [o for o in obs if o.get("category") == "person"]
        others = [o for o in obs if o.get("category") != "person"]

        for o in others:
            held = False
            for p in persons:
                if p.get("bbox") and o.get("bbox"):
                    iou = _iou(p["bbox"], o["bbox"])
                    if iou >= iou_threshold:
                        held = True
                        break
                    cx, cy = _centroid(o["bbox"])
                    if _inside(cx, cy, p["bbox"]):
                        held = True
                        break
            s = state.setdefault(o["memory_id"], {"confirmed": False, "pending": None, "count": 0})
            if held == s["confirmed"]:
                s["pending"], s["count"] = None, 0
            else:
                if s["pending"] is None or s["pending"] != held:
                    s["pending"], s["count"] = held, 1
                else:
                    s["count"] += 1
                if s["count"] >= max(1, debounce_window):
                    events.append({
                        "type": "state_change",
                        "memory_id": o["memory_id"],
                        "frame": frame_id,
                        "state": "held_by_person",
                        "value": held,
                    })
                    s["confirmed"], s["pending"], s["count"] = held, None, 0

    return events


def _cosine(a: List[float], b: List[float]) -> float:
    import numpy as np
    va = np.asarray(a, dtype=np.float32)
    vb = np.asarray(b, dtype=np.float32)
    n = np.linalg.norm(va) * np.linalg.norm(vb) + 1e-8
    return float(np.dot(va, vb) / n)


def build_split_events(
    memory: Dict[str, Any],
    tracks: List[Dict[str, Any]],
    split_sim_threshold: float = 0.9,
    max_gap_frames: int = 1800,
    spatial_dist_norm: float = 0.1,
) -> List[Dict[str, Any]]:
    """
    Detect likely 'split' cases where the same object became multiple memories.
    Heuristics: same class, high embedding similarity, temporal adjacency/overlap,
    and spatial proximity of end→start bboxes.
    """
    events: List[Dict[str, Any]] = []
    objs = memory.get("objects", [])
    emb_map = memory.get("embeddings", {})

    # Build quick lookup of first/last frames and representative bboxes from tracks
    by_frame = _per_frame_memory_observations(tracks, memory)
    # For each memory, capture bbox at first and last visible frames
    first_bbox: Dict[str, Tuple[int, List[float], Tuple[int, int]]] = {}
    last_bbox: Dict[str, Tuple[int, List[float], Tuple[int, int]]] = {}

    for frame_id in sorted(by_frame.keys()):
        for o in by_frame[frame_id]:
            mid = o["memory_id"]
            bbox = o.get("bbox")
            if bbox is None:
                continue
            wh = (o.get("frame_width", 0), o.get("frame_height", 0))
            if mid not in first_bbox:
                first_bbox[mid] = (frame_id, bbox, wh)
            last_bbox[mid] = (frame_id, bbox, wh)

    def norm_dist(b1: List[float], wh1: Tuple[int, int], b2: List[float], wh2: Tuple[int, int]) -> float:
        c1 = _centroid(b1)
        c2 = _centroid(b2)
        # Use average diagonal for normalization
        d1 = math.hypot(wh1[0], wh1[1]) if wh1[0] and wh1[1] else 1.0
        d2 = math.hypot(wh2[0], wh2[1]) if wh2[0] and wh2[1] else 1.0
        d = math.hypot(c1[0] - c2[0], c1[1] - c2[1])
        return float(d / ((d1 + d2) * 0.5))

    # Pairwise checks
    for i in range(len(objs)):
        oi = objs[i]
        for j in range(i + 1, len(objs)):
            oj = objs[j]
            if oi.get("class") != oj.get("class"):
                continue
            ei = oi.get("prototype_embedding")
            ej = oj.get("prototype_embedding")
            if ei not in emb_map or ej not in emb_map:
                continue
            sim = _cosine(emb_map[ei], emb_map[ej])
            if sim < split_sim_threshold:
                continue

            # Temporal relation
            fi, li = int(oi.get("first_seen_frame", 0)), int(oi.get("last_seen_frame", 0))
            fj, lj = int(oj.get("first_seen_frame", 0)), int(oj.get("last_seen_frame", 0))

            gap = max(0, min(abs(fj - li), abs(fi - lj)))
            if gap > max_gap_frames:
                continue

            # Spatial proximity at boundary: use last of early to first of late
            # Decide which appears later
            first_i = first_bbox.get(oi["memory_id"])  # (frame, bbox, wh)
            last_i = last_bbox.get(oi["memory_id"])    # (frame, bbox, wh)
            first_j = first_bbox.get(oj["memory_id"])  # (frame, bbox, wh)
            last_j = last_bbox.get(oj["memory_id"])    # (frame, bbox, wh)

            if not first_i or not last_i or not first_j or not last_j:
                continue

            # Determine edge pair
            if fi <= fj:
                # i earlier, compare last_i to first_j
                _, b1, wh1 = last_i
                _, b2, wh2 = first_j
                when = fj
                merged_tracks = []
            else:
                _, b1, wh1 = last_j
                _, b2, wh2 = first_i
                when = fi
                merged_tracks = []

            nd = norm_dist(b1, wh1, b2, wh2)
            if nd <= spatial_dist_norm or _iou(b1, b2) > 0.0:
                events.append({
                    "type": "split",
                    "frame": when,
                    "memory_ids": [oi["memory_id"], oj["memory_id"]],
                    "class": oi.get("class"),
                    "similarity": round(sim, 3),
                    "gap_frames": gap,
                    "details": "Likely single object split into multiple memories (candidate merge)",
                })

    return events


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


def build_relation_events(
    memory: Dict[str, Any],
    tracks: List[Dict[str, Any]],
    relations: Optional[List[str]] = None,
    near_dist_norm: float = 0.08,
    on_h_overlap: float = 0.3,
    on_vgap_norm: float = 0.02,
    iou_exclude: float = 0.1,
    debounce_window: int = 1,
) -> List[Dict[str, Any]]:
    """
    Build debounced relation change events: 'near' and 'on' between memory pairs in the same frame.
    Emits events with type 'relation_change' and fields: relation, subject, object, value.
    """
    if relations is None:
        relations = ["near", "on"]

    events: List[Dict[str, Any]] = []
    by_frame = _per_frame_memory_observations(tracks, memory)

    # Debounce state per (relation, A, B)
    state: Dict[Tuple[str, str, str], Dict[str, Any]] = {}

    for frame_id in sorted(by_frame.keys()):
        obs = by_frame[frame_id]
        n = len(obs)
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
                wh = (A.get("frame_width", 0), A.get("frame_height", 0))
                diag = _frame_diag(wh)
                iou = _iou(a_b, b_b)

                # Compute primitive measures
                cxA, cyA = _centroid(a_b)
                cxB, cyB = _centroid(b_b)
                dist = math.hypot(cxA - cxB, cyA - cyB) / max(1e-6, diag)
                bottomA = a_b[3]
                topB = b_b[1]
                h_ov = _horiz_overlap_ratio(a_b, b_b)
                vgap = abs(topB - bottomA) / max(1.0, wh[1])

                # Eval each relation
                flags: Dict[str, bool] = {}
                if "near" in relations:
                    flags["near"] = (dist <= near_dist_norm) and (iou < iou_exclude)
                if "on" in relations:
                    # A on B if A is directly above B with sufficient horizontal overlap and tiny vertical gap/penetration
                    flags["on"] = (h_ov >= on_h_overlap) and (vgap <= on_vgap_norm) and (cyA <= cyB)

                for rel, val in flags.items():
                    key = (rel, A["memory_id"], B["memory_id"])
                    s = state.setdefault(key, {"confirmed": False, "pending": None, "count": 0})
                    if val == s["confirmed"]:
                        s["pending"], s["count"] = None, 0
                    else:
                        if s["pending"] is None or s["pending"] != val:
                            s["pending"], s["count"] = val, 1
                        else:
                            s["count"] += 1
                        if s["count"] >= max(1, debounce_window):
                            events.append({
                                "type": "relation_change",
                                "relation": rel,
                                "subject": A["memory_id"],
                                "object": B["memory_id"],
                                "frame": frame_id,
                                "value": val,
                            })
                            s["confirmed"], s["pending"], s["count"] = val, None, 0

    return events


def build_merge_suggestions(
    memory: Dict[str, Any],
    tracks: List[Dict[str, Any]],
    split_sim_threshold: float = 0.85,
    max_gap_frames: int = 2400,
    spatial_dist_norm: float = 0.2,
    top_k: int = 20,
) -> List[Dict[str, Any]]:
    """
    Produce ranked merge suggestions from potential splits. Score combines similarity, temporal proximity, and spatial proximity.
    """
    # Recompute candidates similarly to build_split_events, but with lenient thresholds and a score
    objs = memory.get("objects", [])
    emb_map = memory.get("embeddings", {})
    by_frame = _per_frame_memory_observations(tracks, memory)
    first_bbox: Dict[str, Tuple[int, List[float], Tuple[int, int]]] = {}
    last_bbox: Dict[str, Tuple[int, List[float], Tuple[int, int]]] = {}

    for frame_id in sorted(by_frame.keys()):
        for o in by_frame[frame_id]:
            mid = o["memory_id"]
            bbox = o.get("bbox")
            if bbox is None:
                continue
            wh = (o.get("frame_width", 0), o.get("frame_height", 0))
            if mid not in first_bbox:
                first_bbox[mid] = (frame_id, bbox, wh)
            last_bbox[mid] = (frame_id, bbox, wh)

    def norm_dist(b1: List[float], wh1: Tuple[int, int], b2: List[float], wh2: Tuple[int, int]) -> float:
        c1 = _centroid(b1)
        c2 = _centroid(b2)
        d1 = _frame_diag(wh1)
        d2 = _frame_diag(wh2)
        d = math.hypot(c1[0] - c2[0], c1[1] - c2[1])
        return float(d / ((d1 + d2) * 0.5))

    suggestions: List[Dict[str, Any]] = []
    for i in range(len(objs)):
        oi = objs[i]
        for j in range(i + 1, len(objs)):
            oj = objs[j]
            if oi.get("class") != oj.get("class"):
                continue
            ei = oi.get("prototype_embedding")
            ej = oj.get("prototype_embedding")
            if ei not in emb_map or ej not in emb_map:
                continue
            sim = _cosine(emb_map[ei], emb_map[ej])
            if sim < split_sim_threshold:
                continue

            fi, li = int(oi.get("first_seen_frame", 0)), int(oi.get("last_seen_frame", 0))
            fj, lj = int(oj.get("first_seen_frame", 0)), int(oj.get("last_seen_frame", 0))
            gap = max(0, min(abs(fj - li), abs(fi - lj)))
            if gap > max_gap_frames:
                continue

            bi = last_bbox.get(oi["memory_id"]) or first_bbox.get(oi["memory_id"])  # fallback
            bj = first_bbox.get(oj["memory_id"]) or last_bbox.get(oj["memory_id"])  # fallback
            if not bi or not bj:
                continue
            _, b1, wh1 = bi
            _, b2, wh2 = bj
            nd = norm_dist(b1, wh1, b2, wh2)

            # Score: 0..1 higher is better
            gap_score = 1.0 - min(1.0, gap / float(max_gap_frames))
            dist_score = 1.0 - min(1.0, nd / float(spatial_dist_norm))
            score = 0.6 * sim + 0.2 * gap_score + 0.2 * max(0.0, dist_score)

            suggestions.append({
                "memory_ids": [oi["memory_id"], oj["memory_id"]],
                "class": oi.get("class"),
                "similarity": round(sim, 4),
                "gap_frames": gap,
                "distance": round(nd, 4),
                "score": round(score, 4),
            })

    suggestions.sort(key=lambda s: s["score"], reverse=True)
    return suggestions[:top_k]


def save_merge_suggestions(suggestions: List[Dict[str, Any]], out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump({"suggestions": suggestions}, f, indent=2)
    return out_path


def save_events_jsonl(events: List[Dict[str, Any]], out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        for ev in events:
            f.write(json.dumps(ev) + "\n")
    return out_path
