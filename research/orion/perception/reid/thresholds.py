import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Any

import numpy as np

from .reid_matcher import compute_track_embeddings, _read_tracks_jsonl

logger = logging.getLogger(__name__)


def otsu_threshold(values: np.ndarray, bins: int = 64) -> float:
    """Compute Otsu threshold for 1D values in [0, 1]."""
    if values.size == 0:
        return 0.75
    values = np.clip(values, 0.0, 1.0)
    hist, bin_edges = np.histogram(values, bins=bins, range=(0.0, 1.0))
    hist = hist.astype(np.float64)
    prob = hist / hist.sum()
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2.0

    omega = np.cumsum(prob)
    mu = np.cumsum(prob * bin_centers)
    mu_t = mu[-1]

    sigma_b_squared = (mu_t * omega - mu) ** 2 / (omega * (1.0 - omega) + 1e-12)
    idx = np.nanargmax(sigma_b_squared)
    t = bin_centers[idx]
    return float(t)


def pairwise_cosine_sims(vecs: List[np.ndarray]) -> np.ndarray:
    if len(vecs) < 2:
        return np.array([], dtype=np.float32)
    X = np.stack(vecs, axis=0).astype(np.float32)
    X /= (np.linalg.norm(X, axis=1, keepdims=True) + 1e-8)
    sims = X @ X.T
    tri = np.triu_indices_from(sims, k=1)
    return sims[tri]


def collect_class_embeddings(
    video_path: Path,
    tracks_path: Path,
) -> Dict[str, List[np.ndarray]]:
    tracks = _read_tracks_jsonl(tracks_path)
    track_embs = compute_track_embeddings(video_path, tracks, max_crops_per_track=4)
    # Group by category
    by_track = {}
    for it in tracks:
        tid = int(it.get("track_id", -1))
        if tid in track_embs:
            by_track.setdefault(tid, it.get("category", "object"))
    class_to_vecs: Dict[str, List[np.ndarray]] = {}
    for tid, cat in by_track.items():
        class_to_vecs.setdefault(cat, []).append(track_embs[tid])
    return class_to_vecs


def tune_thresholds_across(
    episodes: List[Tuple[Path, Path]],
    clamp: Tuple[float, float] = (0.65, 0.9),
) -> Dict[str, float]:
    """
    Auto-tune per-class thresholds using Otsu on pairwise cosine distributions, aggregated across episodes.

    Args:
        episodes: List of (video_path, tracks_path)
        clamp: Min/max clamp for thresholds
    Returns:
        Mapping {class: threshold}
    """
    all_class_sims: Dict[str, List[float]] = {}
    for video_path, tracks_path in episodes:
        logger.info(f"Collecting embeddings: {video_path} | {tracks_path}")
        class_vecs = collect_class_embeddings(video_path, tracks_path)
        for cls, vecs in class_vecs.items():
            sims = pairwise_cosine_sims(vecs)
            if sims.size > 0:
                all_class_sims.setdefault(cls, []).extend(sims.tolist())

    tuned: Dict[str, float] = {}
    for cls, sims in all_class_sims.items():
        vals = np.array(sims, dtype=np.float32)
        t = otsu_threshold(vals)
        t = float(np.clip(t, clamp[0], clamp[1]))
        tuned[cls] = t
        logger.info(f"Class '{cls}': Otsu={t:.3f} (n={len(vals)})")

    return tuned


def save_thresholds(thresholds: Dict[str, float], out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w') as f:
        json.dump({k: float(v) for k, v in thresholds.items()}, f, indent=2)
    return out_path
