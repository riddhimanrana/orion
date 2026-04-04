"""Canonical label resolution via HDBSCAN clustering on candidate text embeddings.

This module aggregates candidate labels (from open-vocab scoring) across observations
of a track/entity over time and commits a canonical label only when stable.

Algorithm:
1. Collect all candidate labels from observations of an entity.
2. Embed label texts using SentenceTransformer (or CLIP).
3. Cluster embeddings with HDBSCAN to find groups of semantically similar labels.
4. Vote within the largest cluster to select the canonical label.
5. Require minimum persistence + score margin before committing.

This approach handles synonyms (e.g., "water bottle" vs "bottle") and avoids
premature commitment to noisy per-frame labels.
"""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# Lazy imports for heavy deps
_hdbscan = None
_sentence_model = None


def _ensure_hdbscan():
    global _hdbscan
    if _hdbscan is None:
        import hdbscan as hdb
        _hdbscan = hdb
    return _hdbscan


def _ensure_sentence_model(model_name: str = "all-MiniLM-L6-v2"):
    """Load SentenceTransformer for text embedding (cached)."""
    global _sentence_model
    if _sentence_model is None:
        from sentence_transformers import SentenceTransformer
        logger.info(f"Loading SentenceTransformer: {model_name}")
        _sentence_model = SentenceTransformer(model_name)
    return _sentence_model


@dataclass
class CanonicalResult:
    """Result of canonical label resolution."""

    label: str
    confidence: float
    cluster_size: int
    total_candidates: int
    runner_up_label: Optional[str] = None
    runner_up_score: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "label": self.label,
            "confidence": round(self.confidence, 4),
            "cluster_size": self.cluster_size,
            "total_candidates": self.total_candidates,
            "runner_up_label": self.runner_up_label,
            "runner_up_score": round(self.runner_up_score, 4) if self.runner_up_score else None,
        }


class CanonicalLabeler:
    """Aggregate candidate labels over time and resolve to a single canonical label."""

    def __init__(
        self,
        min_observations: int = 3,
        min_margin: float = 0.15,
        hdbscan_min_cluster_size: int = 2,
        hdbscan_min_samples: int = 1,
        sentence_model_name: str = "all-MiniLM-L6-v2",
    ):
        """
        Args:
            min_observations: Minimum observations before committing a label.
            min_margin: Minimum score margin (0-1) over runner-up to commit.
            hdbscan_min_cluster_size: HDBSCAN min_cluster_size.
            hdbscan_min_samples: HDBSCAN min_samples.
            sentence_model_name: SentenceTransformer model for text embedding.
        """
        self.min_observations = int(min_observations)
        self.min_margin = float(min_margin)
        self.hdbscan_min_cluster_size = int(hdbscan_min_cluster_size)
        self.hdbscan_min_samples = int(hdbscan_min_samples)
        self.sentence_model_name = str(sentence_model_name)
        self._text_emb_cache: Dict[str, np.ndarray] = {}

    def _embed_labels(self, labels: Sequence[str]) -> np.ndarray:
        """Embed label texts using SentenceTransformer."""
        model = _ensure_sentence_model(self.sentence_model_name)
        to_encode: List[str] = []
        for lbl in labels:
            if lbl not in self._text_emb_cache:
                to_encode.append(lbl)
        if to_encode:
            embs = model.encode(to_encode, convert_to_numpy=True, show_progress_bar=False)
            for lbl, emb in zip(to_encode, embs):
                self._text_emb_cache[lbl] = emb / (np.linalg.norm(emb) + 1e-9)
        return np.stack([self._text_emb_cache[lbl] for lbl in labels], axis=0)

    def _cluster_and_vote(
        self,
        labels: List[str],
        scores: List[float],
    ) -> Tuple[Optional[str], float, int, Optional[str], Optional[float]]:
        """Cluster label embeddings and vote within largest cluster."""
        if not labels:
            return None, 0.0, 0, None, None

        unique_labels = list(set(labels))
        if len(unique_labels) == 1:
            # Single label; trivial case
            return unique_labels[0], 1.0, len(labels), None, None

        # Embed unique labels
        embs = self._embed_labels(unique_labels)  # [U, D]

        # Build label -> embedding index
        label_to_idx = {lbl: i for i, lbl in enumerate(unique_labels)}

        # HDBSCAN clustering
        #
        # Note: Some older hdbscan builds do not support metric="cosine".
        # Since we normalize embeddings to unit length, euclidean distance is
        # monotonic with cosine distance:
        #   ||u - v||^2 = 2(1 - cos(u, v))
        # So we can safely fall back to metric="euclidean" when needed.
        hdb = _ensure_hdbscan()
        cluster_kwargs = dict(
            min_cluster_size=max(2, min(self.hdbscan_min_cluster_size, len(unique_labels))),
            min_samples=self.hdbscan_min_samples,
        )
        try:
            clusterer = hdb.HDBSCAN(metric="cosine", **cluster_kwargs)
            cluster_ids = clusterer.fit_predict(embs)  # [U]
        except ValueError as e:
            if "metric" not in str(e).lower():
                raise
            logger.warning(
                "HDBSCAN does not support cosine metric (%s). Falling back to euclidean on normalized embeddings.",
                e,
            )
            clusterer = hdb.HDBSCAN(metric="euclidean", **cluster_kwargs)
            cluster_ids = clusterer.fit_predict(embs)  # [U]

        # Map each candidate occurrence to its cluster
        occurrence_clusters: List[int] = []
        for lbl in labels:
            idx = label_to_idx[lbl]
            occurrence_clusters.append(int(cluster_ids[idx]))

        # Find largest cluster (excluding noise cluster -1)
        cluster_counts = Counter(c for c in occurrence_clusters if c >= 0)
        if not cluster_counts:
            # All noise; fall back to simple vote
            return self._simple_vote(labels, scores)

        largest_cluster = cluster_counts.most_common(1)[0][0]
        cluster_size = cluster_counts[largest_cluster]

        # Vote within largest cluster
        in_cluster_labels: List[str] = []
        in_cluster_scores: List[float] = []
        for lbl, sc, cid in zip(labels, scores, occurrence_clusters):
            if cid == largest_cluster:
                in_cluster_labels.append(lbl)
                in_cluster_scores.append(sc)

        # Aggregate by label (sum of scores)
        label_score_sum: Dict[str, float] = {}
        label_count: Dict[str, int] = {}
        for lbl, sc in zip(in_cluster_labels, in_cluster_scores):
            label_score_sum[lbl] = label_score_sum.get(lbl, 0.0) + sc
            label_count[lbl] = label_count.get(lbl, 0) + 1

        sorted_labels = sorted(label_score_sum.items(), key=lambda x: -x[1])
        best_label, best_score = sorted_labels[0]
        runner_up_label: Optional[str] = None
        runner_up_score_sum: Optional[float] = None
        if len(sorted_labels) > 1:
            runner_up_label, runner_up_score_sum = sorted_labels[1]

        total_cluster_score = float(sum(in_cluster_scores)) + 1e-9
        confidence = float(best_score) / total_cluster_score
        runner_up_confidence = (
            float(runner_up_score_sum) / total_cluster_score
            if runner_up_score_sum is not None
            else None
        )

        return best_label, confidence, cluster_size, runner_up_label, runner_up_confidence

    def _simple_vote(
        self,
        labels: List[str],
        scores: List[float],
    ) -> Tuple[Optional[str], float, int, Optional[str], Optional[float]]:
        """Fallback: simple weighted vote without clustering."""
        if not labels:
            return None, 0.0, 0, None, None
        label_score_sum: Dict[str, float] = {}
        for lbl, sc in zip(labels, scores):
            label_score_sum[lbl] = label_score_sum.get(lbl, 0.0) + sc
        sorted_labels = sorted(label_score_sum.items(), key=lambda x: -x[1])
        best_label, best_score = sorted_labels[0]
        runner_up_label: Optional[str] = None
        runner_up_score_sum: Optional[float] = None
        if len(sorted_labels) > 1:
            runner_up_label, runner_up_score_sum = sorted_labels[1]
        total = float(sum(label_score_sum.values())) + 1e-9
        confidence = float(best_score) / total
        runner_up_confidence = (
            float(runner_up_score_sum) / total
            if runner_up_score_sum is not None
            else None
        )
        return best_label, confidence, len(labels), runner_up_label, runner_up_confidence

    def resolve(
        self,
        observations: Sequence[Any],
        *,
        candidate_key: str = "candidate_labels",
    ) -> Optional[CanonicalResult]:
        """Resolve canonical label from a sequence of observations.

        Args:
            observations: List of Observation objects (or dicts) with candidate_labels.
            candidate_key: Key/attribute name for candidate labels.

        Returns:
            CanonicalResult if stable canonical label found, else None.
        """
        labels: List[str] = []
        scores: List[float] = []

        for obs in observations:
            cands = getattr(obs, candidate_key, None) if hasattr(obs, candidate_key) else obs.get(candidate_key)
            if not cands:
                continue
            for c in cands:
                lbl = c.get("label") if isinstance(c, dict) else getattr(c, "label", None)
                sc = c.get("score", 0.5) if isinstance(c, dict) else getattr(c, "score", 0.5)
                if lbl:
                    labels.append(str(lbl))
                    scores.append(float(sc))

        if len(labels) < self.min_observations:
            logger.debug("Not enough candidates (%d < %d)", len(labels), self.min_observations)
            return None

        best_label, confidence, cluster_size, runner_up_label, runner_up_score = self._cluster_and_vote(labels, scores)

        if best_label is None:
            return None

        # Check margin
        margin = confidence - (runner_up_score if runner_up_score is not None else 0.0)
        if margin < self.min_margin:
            logger.debug(
                "Canonical label margin too small: %s (%.2f) vs %s (%.2f)",
                best_label,
                confidence,
                runner_up_label,
                runner_up_score,
            )
            return None

        return CanonicalResult(
            label=best_label,
            confidence=confidence,
            cluster_size=cluster_size,
            total_candidates=len(labels),
            runner_up_label=runner_up_label,
            runner_up_score=runner_up_score,
        )


# ---------------------------------------------------------------------------
# Convenience: resolve labels for a batch of entities in place
# ---------------------------------------------------------------------------


def canonicalize_entities(
    entities: Sequence[Any],
    labeler: Optional[CanonicalLabeler] = None,
    *,
    canonical_label_attr: str = "canonical_label",
    canonical_confidence_attr: str = "canonical_confidence",
) -> int:
    """Resolve canonical labels for a batch of PerceptionEntity objects.

    Modifies entities in place, setting `canonical_label` and `canonical_confidence`.

    Returns:
        Number of entities that received a canonical label.
    """
    labeler = labeler or CanonicalLabeler()
    count = 0
    for ent in entities:
        obs = getattr(ent, "observations", [])
        result = labeler.resolve(obs)
        if result:
            setattr(ent, canonical_label_attr, result.label)
            setattr(ent, canonical_confidence_attr, result.confidence)
            count += 1
        else:
            setattr(ent, canonical_label_attr, None)
            setattr(ent, canonical_confidence_attr, None)
    logger.info("Canonical labels resolved for %d / %d entities", count, len(entities))
    return count
