import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional

import numpy as np
import cv2

from orion.managers.model_manager import ModelManager
from orion.perception.labels import LABEL_NORMALIZATION, normalize_label

logger = logging.getLogger(__name__)


def _read_tracks_jsonl(tracks_path: Path) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    with open(tracks_path, "r") as f:
        for line in f:
            if not line.strip():
                continue
            items.append(json.loads(line))
    return items


def _group_by(items: List[Dict[str, Any]], key: str) -> Dict[Any, List[Dict[str, Any]]]:
    groups: Dict[Any, List[Dict[str, Any]]] = {}
    for it in items:
        groups.setdefault(it[key], []).append(it)
    return groups


def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))


def _ensure_int_bbox(b: List[float], w: int, h: int) -> Tuple[int, int, int, int]:
    x1, y1, x2, y2 = [int(round(v)) for v in b]
    x1 = max(0, min(w - 1, x1))
    y1 = max(0, min(h - 1, y1))
    x2 = max(0, min(w - 1, x2))
    y2 = max(0, min(h - 1, y2))
    if x2 <= x1:
        x2 = min(w - 1, x1 + 1)
    if y2 <= y1:
        y2 = min(h - 1, y1 + 1)
    return x1, y1, x2, y2


def _maybe_unrotate_bbox_for_portrait(b: List[float], frame_w: int, frame_h: int) -> List[float]:
    """Undo FrameObserver's 90° CCW rotation for portrait videos.

    FrameObserver rotates portrait frames 90° CCW for detection. That means stored
    bboxes may be in the rotated (landscape) coordinate system, but Phase-2 Re-ID
    crops from the *original* frames. This helper detects that mismatch and maps
    bbox coordinates back into the original portrait frame.
    """
    if not b or len(b) != 4:
        return b

    x1, y1, x2, y2 = map(float, b)
    is_portrait = frame_h > frame_w
    looks_rotated = is_portrait and (max(x1, x2) > frame_w + 2 or max(y1, y2) > frame_h + 2)
    if not looks_rotated:
        return [x1, y1, x2, y2]

    # Inverse mapping of 90° CCW rotation:
    # original -> rotated: x' = y, y' = (W-1) - x
    # rotated  -> original: x = (W-1) - y', y = x'
    orig_w = frame_w
    corners = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
    unrot = []
    for xr, yr in corners:
        xo = (orig_w - 1) - yr
        yo = xr
        unrot.append((xo, yo))
    xs = [p[0] for p in unrot]
    ys = [p[1] for p in unrot]
    return [min(xs), min(ys), max(xs), max(ys)]


def _read_frames_for_ids(video_path: Path, frame_ids: List[int]) -> Dict[int, np.ndarray]:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise FileNotFoundError(f"Cannot open video: {video_path}")
    frames: Dict[int, np.ndarray] = {}
    wanted = set(frame_ids)
    # We assume frame_id is the sampled frame index used earlier
    # We'll decode sequentially for simplicity
    idx = 0
    while wanted and True:
        ok, frame = cap.read()
        if not ok:
            break
        if idx in wanted:
            frames[idx] = frame
            wanted.remove(idx)
        idx += 1
    cap.release()
    return frames


def compute_observation_embedding(
    video_path: Path,
    observation: Dict[str, Any],
) -> np.ndarray:
    """Compute a DINO embedding for a single track observation.

    This is intended for diagnostics and uses the same crop/un-rotation logic
    as Phase-2 track embedding aggregation.

    Args:
        video_path: Path to source video
        observation: A single JSONL record/observation containing at least
            `frame_id` and (`bbox_2d` or `bbox`).

    Returns:
        L2-normalized embedding vector as np.ndarray (float32)
    """
    frame_id = observation.get("frame_id")
    if frame_id is None:
        frame_id = observation.get("frame_number")
    if frame_id is None:
        raise ValueError("Observation missing frame_id")
    fid = int(frame_id)

    raw_bbox = observation.get("bbox_2d") or observation.get("bbox")
    if raw_bbox is None:
        raise ValueError("Observation missing bbox")
    if isinstance(raw_bbox, dict):
        raw_bbox = [raw_bbox.get("x1"), raw_bbox.get("y1"), raw_bbox.get("x2"), raw_bbox.get("y2")]
    if not isinstance(raw_bbox, (list, tuple)) or len(raw_bbox) != 4:
        raise ValueError("Observation bbox must be length-4")
    raw_bbox_list = [float(v) for v in raw_bbox]

    frames = _read_frames_for_ids(video_path, [fid])
    frame = frames.get(fid)
    if frame is None:
        raise RuntimeError(f"Failed to decode frame {fid} from {video_path}")

    H, W = frame.shape[:2]
    raw_bbox_list = _maybe_unrotate_bbox_for_portrait(raw_bbox_list, frame_w=W, frame_h=H)
    x1, y1, x2, y2 = _ensure_int_bbox(raw_bbox_list, W, H)
    crop = frame[y1:y2, x1:x2]
    if crop.size == 0:
        raise RuntimeError(f"Empty crop for bbox {raw_bbox_list} @ frame {fid}")

    mm = ModelManager.get_instance()
    reid_model = mm.reid_embedder  # V-JEPA2 (3D-aware video encoder)
    
    # V-JEPA2 API
    emb_tensor = reid_model.embed_single_image(crop)
    emb = emb_tensor.numpy().flatten()
    
    return emb.astype(np.float32)


def extract_observation_crop(
    video_path: Path,
    observation: Dict[str, Any],
) -> Tuple[np.ndarray, Tuple[int, int, int, int], int]:
    """Extract the canonical crop used for Phase-2 ReID embedding.

    Returns:
        (crop_bgr, (x1,y1,x2,y2), frame_id)
    """
    frame_id = observation.get("frame_id")
    if frame_id is None:
        frame_id = observation.get("frame_number")
    if frame_id is None:
        raise ValueError("Observation missing frame_id")
    fid = int(frame_id)

    raw_bbox = observation.get("bbox_2d") or observation.get("bbox")
    if raw_bbox is None:
        raise ValueError("Observation missing bbox")
    if isinstance(raw_bbox, dict):
        raw_bbox = [raw_bbox.get("x1"), raw_bbox.get("y1"), raw_bbox.get("x2"), raw_bbox.get("y2")]
    if not isinstance(raw_bbox, (list, tuple)) or len(raw_bbox) != 4:
        raise ValueError("Observation bbox must be length-4")
    raw_bbox_list = [float(v) for v in raw_bbox]

    frames = _read_frames_for_ids(video_path, [fid])
    frame = frames.get(fid)
    if frame is None:
        raise RuntimeError(f"Failed to decode frame {fid} from {video_path}")

    H, W = frame.shape[:2]
    raw_bbox_list = _maybe_unrotate_bbox_for_portrait(raw_bbox_list, frame_w=W, frame_h=H)
    x1, y1, x2, y2 = _ensure_int_bbox(raw_bbox_list, W, H)
    crop = frame[y1:y2, x1:x2]
    if crop.size == 0:
        raise RuntimeError(f"Empty crop for bbox {raw_bbox_list} @ frame {fid}")
    return crop, (x1, y1, x2, y2), fid


def compute_track_embeddings(
    video_path: Path,
    tracks: List[Dict[str, Any]],
    max_crops_per_track: int = 5,
    batch_size: int = 8,
    embedding_backend: str = "vjepa2",
) -> Dict[int, np.ndarray]:
    """
    Compute an average embedding per track by cropping detections from frames.

    Uses batch processing for GPU efficiency when available.

    Args:
        video_path: Path to source video
        tracks: Parsed list of track observations (from tracks.jsonl)
        max_crops_per_track: Cap number of crops per track for speed
        batch_size: Number of crops to process at once (GPU batch)
        embedding_backend: "vjepa2" (default), "clip", "dinov2"

    Returns:
        Dict mapping track_id -> embedding vector (np.ndarray)
    """
    mm = ModelManager.get_instance()
    
    reid_model = None
    if embedding_backend == "vjepa2":
        reid_model = mm.vjepa2
    elif embedding_backend == "clip":
        reid_model = mm.clip
    elif embedding_backend == "dinov2":
        # Check if ModelManager has dinov2, otherwise load it manually or via dino_backend
        if hasattr(mm, "dinov2"):
             reid_model = mm.dinov2
        else:
             # Fallback or error. For now loop in dino_backend if needed, 
             # but ModelManager is preferred. 
             # Assuming ModelManager will be updated or we use separate backend.
             # Actually ModelManager doesn't have dinov2 property in the file I read.
             # I will stick to vjepa2 and clip for now, and map others to error or fallback.
             logger.warning(f"ModelManager does not expose 'dinov2'. Falling back to V-JEPA2")
             reid_model = mm.vjepa2
    else:
        logger.warning(f"Unknown embedding backend '{embedding_backend}'. Defaulting to V-JEPA2")
        reid_model = mm.vjepa2

    by_frame = _group_by(tracks, "frame_id")
    needed_frames = sorted(by_frame.keys())
    frames = _read_frames_for_ids(video_path, needed_frames)

    # Collect per-track embeddings
    per_track_embs: Dict[int, List[np.ndarray]] = {}
    
    # First pass: collect all crops and their metadata
    all_crops: List[np.ndarray] = []
    crop_metadata: List[Tuple[int, int]] = []  # (track_id, crop_index within track)
    crops_per_track: Dict[int, int] = {}  # track_id -> current crop count

    for fid in needed_frames:
        frame = frames.get(fid)
        if frame is None:
            continue
        H, W = frame.shape[:2]
        obs = by_frame[fid]
        
        for det in obs:
            tid = int(det.get("track_id", -1))
            if tid < 0:
                continue
            # Limit samples per track
            current_count = crops_per_track.get(tid, 0)
            if current_count >= max_crops_per_track:
                continue
            raw_bbox = det.get("bbox_2d") or det.get("bbox")
            if not raw_bbox or len(raw_bbox) != 4:
                continue
            raw_bbox = _maybe_unrotate_bbox_for_portrait(list(raw_bbox), frame_w=W, frame_h=H)
            x1, y1, x2, y2 = _ensure_int_bbox(raw_bbox, W, H)
            crop = frame[y1:y2, x1:x2]
            if crop.size == 0:
                continue
            
            all_crops.append(crop)
            crop_metadata.append((tid, current_count))
            crops_per_track[tid] = current_count + 1

    if not all_crops:
        logger.warning("No crops collected for embedding")
        return {}

    logger.info(f"Embedding {len(all_crops)} crops from {len(crops_per_track)} tracks (batch_size={batch_size})")
    
    # Check if model supports batch embedding
    has_batch = hasattr(reid_model, 'embed_batch')

    if has_batch:
        # Use batch embedding when available (it will internally chunk by batch_size)
        try:
            embeddings = reid_model.embed_batch(all_crops, batch_size=batch_size)
            embs = [emb.numpy().flatten() for emb in embeddings]
        except Exception as e:
            logger.warning(f"Batch embedding failed ({e}), falling back to sequential")
            has_batch = False

    if not has_batch:
        # Sequential fallback
        embs = []
        for crop in all_crops:
            emb_tensor = reid_model.embed_single_image(crop)
            embs.append(emb_tensor.numpy().flatten())

    # Group embeddings by track
    for (tid, _), emb in zip(crop_metadata, embs):
        per_track_embs.setdefault(tid, []).append(emb.astype(np.float32))

    # Average per track
    track_proto: Dict[int, np.ndarray] = {}
    for tid, embs in per_track_embs.items():
        if not embs:
            continue
        arr = np.stack(embs, axis=0)
        mean = arr.mean(axis=0)
        # Normalize
        mean = mean / (np.linalg.norm(mean) + 1e-8)
        track_proto[tid] = mean.astype(np.float32)

    return track_proto


def cluster_tracks(
    track_embeddings: Dict[int, np.ndarray],
    tracks: List[Dict[str, Any]],
    cosine_threshold: float = 0.75,
    class_thresholds: Optional[Dict[str, float]] = None,
) -> Tuple[Dict[str, Dict[str, Any]], Dict[int, str], Dict[str, np.ndarray]]:
    """
    Cluster per-track embeddings into persistent memory objects.

    Args:
        track_embeddings: track_id -> embedding vector
        tracks: original observations for metadata aggregation
        cosine_threshold: similarity threshold for merging into same memory

    Returns:
        memory_objects: memory_id -> object dict (without embeddings map)
        track_to_memory: track_id -> memory_id
        embeddings_map: emb_id -> prototype embedding (np.ndarray)
    """
    # Aggregate per-track stats
    by_track = _group_by(tracks, "track_id")
    track_meta: Dict[int, Dict[str, Any]] = {}
    for tid_str, obs in by_track.items():
        tid = int(tid_str)
        # Get raw labels
        raw_cats = [o.get("class_name", o.get("label", "object")) for o in obs]
        raw_category = max(set(raw_cats), key=raw_cats.count) if raw_cats else "object"
        
        # Apply label normalization for clustering
        normalized_category = normalize_label(raw_category)
        
        frames = [int(o.get("frame_id", 0)) for o in obs]
        track_meta[tid] = {
            "category": normalized_category,  # Use normalized for clustering
            "raw_category": raw_category,     # Keep original for reference
            "first": min(frames) if frames else 0,
            "last": max(frames) if frames else 0,
            "count": len(obs),
        }

    # Greedy clustering per normalized category
    memory_objects: Dict[str, Dict[str, Any]] = {}
    embeddings_map: Dict[str, np.ndarray] = {}
    track_to_memory: Dict[int, str] = {}

    mem_counter = 1
    emb_counter = 1

    # Group track ids by normalized category
    cat_to_tids: Dict[str, List[int]] = {}
    for tid, meta in track_meta.items():
        if tid in track_embeddings:
            cat_to_tids.setdefault(meta["category"], []).append(tid)

    for category, tids in cat_to_tids.items():
        # Select threshold for this category
        cat_thresh = cosine_threshold
        if class_thresholds and category in class_thresholds:
            cat_thresh = float(class_thresholds[category])
        clusters: List[Tuple[str, np.ndarray, List[int]]] = []  # (mem_id, proto, members)
        for tid in sorted(tids):
            emb = track_embeddings[tid]
            assigned = False
            # Find best cluster
            best_idx = -1
            best_sim = -1.0
            for idx, (_, proto, _) in enumerate(clusters):
                sim = _cosine_sim(emb, proto)
                if sim > best_sim:
                    best_sim = sim
                    best_idx = idx
            if best_idx >= 0 and best_sim >= cat_thresh:
                # Merge into existing cluster and update prototype (running mean)
                mem_id, proto, members = clusters[best_idx]
                members.append(tid)
                new_proto = proto * (len(members) - 1) / len(members) + emb / len(members)
                new_proto = new_proto / (np.linalg.norm(new_proto) + 1e-8)
                clusters[best_idx] = (mem_id, new_proto.astype(np.float32), members)
                track_to_memory[tid] = mem_id # Assign memory id to track
                assigned = True
            if not assigned:
                mem_id = f"mem_{mem_counter:03d}"
                mem_counter += 1
                clusters.append((mem_id, emb, [tid]))
                track_to_memory[tid] = mem_id # Assign new memory id

        # Finalize clusters into memory objects
        for mem_id, proto, members in clusters:
            emb_id = f"emb_{emb_counter:03d}"
            emb_counter += 1
            embeddings_map[emb_id] = proto.astype(np.float32)
            # Aggregate metadata
            first = min(track_meta[tid]["first"] for tid in members)
            last = max(track_meta[tid]["last"] for tid in members)
            total_obs = sum(track_meta[tid]["count"] for tid in members)
            
            # Determine the most common category among the member tracks
            member_categories = [track_meta[tid]["category"] for tid in members]
            final_category = max(set(member_categories), key=member_categories.count) if member_categories else "object"

            appearance_history = []
            for tid in members:
                appearance_history.append({
                    "track_id": tid,
                    "first_frame": track_meta[tid]["first"],
                    "last_frame": track_meta[tid]["last"],
                    "observations": track_meta[tid]["count"],
                })
                

            # Collect unique raw labels from member tracks
            raw_labels = list(set(track_meta[tid]["raw_category"] for tid in members))

            memory_objects[mem_id] = {
                "memory_id": mem_id,
                "class": final_category,  # Normalized canonical label
                "raw_labels": raw_labels,  # Original labels before normalization
                "first_seen_frame": first,
                "last_seen_frame": last,
                "total_observations": total_obs,
                "prototype_embedding": emb_id,
                "appearance_history": appearance_history,
                "current_state": "visible",
            }

    return memory_objects, track_to_memory, embeddings_map


def build_memory_from_tracks(
    episode_id: str,
    video_path: Path,
    tracks_path: Path,
    results_dir: Path,
    cosine_threshold: float = 0.75,
    max_crops_per_track: int = 5,
    reid_batch_size: int = 8,
    class_thresholds: Optional[Dict[str, float]] = None,
    embedding_backend: str = "vjepa2",
) -> Path:
    """
    Phase 2: Build memory.json and update tracks with embedding ids.

    Returns:
        Path to saved memory.json
    """
    logger.info(f"[Phase 2] Building memory from tracks (backend={embedding_backend})...")
    tracks = _read_tracks_jsonl(tracks_path)

    logger.info(f"Computing per-track embeddings ({embedding_backend})...")
    track_embs = compute_track_embeddings(
        video_path,
        tracks,
        max_crops_per_track=max_crops_per_track,
        batch_size=reid_batch_size,
        embedding_backend=embedding_backend,
    )
    logger.info(f"✓ Got embeddings for {len(track_embs)} tracks")

    # Cluster tracks into memory objects
    logger.info("Clustering tracks into persistent objects (cosine)…")
    memory_objects, track_to_memory, embeddings_map = cluster_tracks(
        track_embs, tracks, cosine_threshold, class_thresholds
    )
    logger.info(f"✓ Built {len(memory_objects)} memory objects")

    # Save memory.json
    memory = {
        "objects": list(memory_objects.values()),
        "embeddings": {k: v.tolist() for k, v in embeddings_map.items()},
        "statistics": {
            "total_objects": len(memory_objects),
            "active_objects": sum(1 for o in memory_objects.values() if o.get("current_state") == "visible"),
        },
    }
    results_dir.mkdir(parents=True, exist_ok=True)
    memory_path = results_dir / "memory.json"
    with open(memory_path, "w") as f:
        json.dump(memory, f, indent=2)
    logger.info(f"✓ Saved memory.json → {memory_path}")

    # Update tracks.jsonl with embedding_id (prototype of assigned memory)
    updated_tracks_path = update_tracks_with_embeddings(tracks_path, memory_objects)
    logger.info(f"✓ Updated tracks with embedding_id → {updated_tracks_path}")

    # Also save a simple cluster mapping
    clusters = {mem_id: [h["track_id"] for h in obj["appearance_history"]] for mem_id, obj in memory_objects.items()}
    with open(results_dir / "reid_clusters.json", "w") as f:
        json.dump(clusters, f, indent=2)
    logger.info(f"✓ Saved reid_clusters.json → {results_dir / 'reid_clusters.json'}")

    return memory_path


def update_tracks_with_embeddings(tracks_path: Path, memory_objects: Dict[str, Dict[str, Any]]) -> Path:
    """
    Overwrite tracks.jsonl inserting embedding_id per observation based on memory mapping.
    Creates a backup file alongside.
    """
    # Build track_id -> emb_id mapping
    track_to_emb: Dict[int, str] = {}
    for obj in memory_objects.values():
        emb_id = obj.get("prototype_embedding")
        for h in obj.get("appearance_history", []):
            track_to_emb[int(h["track_id"])] = emb_id

    # Backup
    orig_path = tracks_path.with_suffix(".orig.jsonl")
    if not orig_path.exists():
        orig_path.write_bytes(tracks_path.read_bytes())

    # Write updated
    tmp_path = tracks_path.with_suffix(".tmp.jsonl")
    with open(orig_path, "r") as fin, open(tmp_path, "w") as fout:
        for line in fin:
            if not line.strip():
                continue
            item = json.loads(line)
            tid = int(item.get("track_id", -1))
            emb_id = track_to_emb.get(tid)
            if emb_id is not None:
                item["embedding_id"] = emb_id
            fout.write(json.dumps(item) + "\n")

    # Replace
    tmp_path.replace(tracks_path)
    return tracks_path
