"""
Visual Embedder
===============

Generates V-JEPA2 embeddings for detected objects (Re-ID backbone).

V-JEPA2 is the canonical Re-ID backbone for Orion v2. It provides 3D-aware
video embeddings that handle viewpoint changes better than 2D encoders.

CLIP is used *separately* for candidate-label scoring (open-vocab), not Re-ID.

Responsibilities:
- Convert cropped regions to V-JEPA2 embeddings
- Normalize embeddings to unit length
- Batch processing for efficiency

Author: Orion Research Team
Date: October 2025 (updated January 2026)
"""

import logging
from typing import List, Optional

import cv2
import numpy as np

from orion.perception.config import EmbeddingConfig
from orion.utils.profiling import profile

logger = logging.getLogger(__name__)


class VisualEmbedder:
    """Generates visual Re-ID embeddings using V-JEPA2.

    V-JEPA2 is the only supported Re-ID embedding backend.
    """

    def __init__(
        self,
        clip_model=None,  # Unused; kept for backward compat signature
        config: Optional[EmbeddingConfig] = None,
    ):
        self.config = config or EmbeddingConfig()
        self.vjepa2 = None
        
        # Resolve device
        import torch
        device = self.config.device
        if device == "auto":
            if torch.cuda.is_available():
                device = "cuda"
            elif getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
                device = "mps"
            else:
                device = "cpu"
        self._device = device
        
        # Always use V-JEPA2
        from orion.backends.vjepa2_backend import VJepa2Embedder
        self.vjepa2 = VJepa2Embedder(
            model_name=self.config.model,
            device=device,
        )
        logger.info(f"VisualEmbedder initialized: V-JEPA2 (device={device}, dim={self.config.embedding_dim})")
    
    @profile("embedder_embed_detections")
    def embed_detections(self, detections: List[dict]) -> List[dict]:
        """
        Add V-JEPA2 embeddings to detections.
        
        Args:
            detections: List of detection dicts from FrameObserver
            
        Returns:
            Same detections with 'embedding' field added
        """
        logger.info("=" * 80)
        logger.info("PHASE 1B: VISUAL EMBEDDING GENERATION (V-JEPA2)")
        logger.info("=" * 80)
        
        logger.info(f"Generating {self.config.embedding_dim}-dim V-JEPA2 embeddings...")
        logger.info(f"  Processing {len(detections)} detections...")
        
        # Optionally cluster detections per frame before embedding extraction
        if self.config.use_cluster_embeddings:
            detections = self._apply_clustering(detections)

        # Process in batches
        batch_size = self.config.batch_size
        total_batches = (len(detections) + batch_size - 1) // batch_size
        for batch_idx in range(total_batches):
            start_idx = batch_idx * batch_size
            end_idx = min(start_idx + batch_size, len(detections))
            batch = detections[start_idx:end_idx]
            embeddings = self._embed_batch(batch)
            for detection, embedding in zip(batch, embeddings):
                detection["embedding"] = embedding
            if (batch_idx + 1) % 5 == 0 or batch_idx == total_batches - 1:
                logger.info(f"  Processed {end_idx}/{len(detections)} detections")
        
        logger.info(f"✓ Generated {len(detections)} V-JEPA2 embeddings")
        logger.info("=" * 80 + "\n")
        
        return detections
    
    @profile("embedder_embed_batch")
    def _embed_batch(self, batch: List[dict]) -> List[np.ndarray]:
        """
        Generate V-JEPA2 embeddings for a batch of detections.
        """
        embeddings: List[np.ndarray] = []
        for detection in batch:
            crop = detection.get("crop")
            if crop is None or crop.size == 0:
                # Fallback: zero embedding
                embeddings.append(np.zeros((self.config.embedding_dim,), dtype=np.float32))
                continue
            # V-JEPA2 expects RGB
            rgb_crop = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
            try:
                embedding_tensor = self.vjepa2.embed_single_image(rgb_crop)
                embedding = embedding_tensor.numpy().flatten().astype(np.float32)
                # Normalize
                norm = np.linalg.norm(embedding)
                if norm > 0:
                    embedding = embedding / norm
                embeddings.append(embedding)
            except Exception as e:
                logger.warning(f"V-JEPA2 embedding failed: {e}")
                embeddings.append(np.zeros((self.config.embedding_dim,), dtype=np.float32))
        return embeddings

    # -------------------------------
    # Clustering logic (IoU-based)
    # -------------------------------
    def _apply_clustering(self, detections: List[dict]) -> List[dict]:
        """Merge overlapping detections per frame to reduce embedding cost."""
        thresh = self.config.cluster_similarity_threshold
        clustered: List[dict] = []
        by_frame: dict[int, List[dict]] = {}
        for det in detections:
            by_frame.setdefault(int(det.get("frame_number", 0)), []).append(det)
        for fidx, frame_dets in by_frame.items():
            clusters: List[List[dict]] = []
            for det in frame_dets:
                bb = det.get("bounding_box") or det.get("bbox") or det.get("bbox_2d")
                if bb is None:
                    clusters.append([det])
                    continue
                x1, y1, x2, y2 = bb.x1, bb.y1, bb.x2, bb.y2
                placed = False
                for cluster in clusters:
                    ob = cluster[0].get("bounding_box") or cluster[0].get("bbox") or cluster[0].get("bbox_2d")
                    if ob is None:
                        continue
                    ox1, oy1, ox2, oy2 = ob.x1, ob.y1, ob.x2, ob.y2
                    inter_x1 = max(x1, ox1)
                    inter_y1 = max(y1, oy1)
                    inter_x2 = min(x2, ox2)
                    inter_y2 = min(y2, oy2)
                    inter = max(0, inter_x2 - inter_x1) * max(0, inter_y2 - inter_y1)
                    area = (x2 - x1) * (y2 - y1)
                    oarea = (ox2 - ox1) * (oy2 - oy1)
                    iou = inter / (area + oarea - inter + 1e-8)
                    if iou >= thresh:
                        cluster.append(det)
                        placed = True
                        break
                if not placed:
                    clusters.append([det])
            # For each cluster create representative detection (first) and mark members
            for cluster in clusters:
                rep = cluster[0]
                rep["cluster_size"] = len(cluster)
                for member in cluster:
                    member["cluster_rep_id"] = id(rep)
                clustered.extend(cluster)
        if clustered:
            avg_size = np.mean([c.get("cluster_size", 1) for c in clustered if "cluster_size" in c])
            logger.info(f"  Clustering reduced duplicates (avg cluster size={avg_size:.2f})")
        return clustered
