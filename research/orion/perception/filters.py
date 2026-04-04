"""
Semantic Filtering Module for Orion v2

Uses FastVLM + Sentence Transformers to validate detections by:
1. Generating a VLM description of each object crop
2. Comparing the description to the detected label using sentence embeddings
3. Filtering out false positives where description doesn't match label

Author: Orion Research Team
Date: January 2026
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Sequence, Tuple, Dict, Any

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# Lazy imports for heavy dependencies
_sentence_transformer = None
_fastvlm = None


def get_sentence_transformer():
    """Lazy-load sentence transformer model."""
    global _sentence_transformer
    if _sentence_transformer is None:
        try:
            from sentence_transformers import SentenceTransformer
            logger.info("Loading all-mpnet-base-v2 sentence transformer...")
            _sentence_transformer = SentenceTransformer('sentence-transformers/all-mpnet-base-v2')
            logger.info("✓ Sentence transformer loaded (768-dim embeddings)")
        except ImportError:
            raise ImportError("sentence-transformers required. Install with: pip install sentence-transformers")
    return _sentence_transformer


def get_fastvlm(device: str = "cuda"):
    """Lazy-load FastVLM model."""
    global _fastvlm
    if _fastvlm is None:
        from orion.backends.torch_fastvlm import FastVLMTorchWrapper
        logger.info(f"Loading FastVLM on {device}...")
        _fastvlm = FastVLMTorchWrapper(device=device)
        logger.info("✓ FastVLM loaded")
    return _fastvlm


@dataclass
class FilterResult:
    """Result of semantic filtering for a single detection."""
    track_id: int
    label: str
    description: str
    similarity: float
    is_valid: bool
    confidence: float = 0.0
    reason: str = ""


@dataclass
class SemanticFilterConfig:
    """Configuration for semantic filtering."""
    
    # Similarity thresholds
    similarity_threshold: float = 0.25
    """Minimum cosine similarity between label and VLM description to keep detection."""
    
    # VLM settings
    description_prompt: str = "Describe this object in one sentence. Be specific about what it is."
    """Prompt for VLM to generate object description."""
    
    max_tokens: int = 50
    """Maximum tokens for VLM response."""
    
    temperature: float = 0.1
    """VLM temperature (lower = more deterministic)."""
    
    # Batch settings
    batch_size: int = 16
    """Number of crops to process in parallel for sentence embeddings."""
    
    # Scene context
    use_scene_context: bool = True
    """Whether to also compare description to scene context."""
    
    scene_similarity_weight: float = 0.3
    """Weight of scene similarity in final score (label similarity = 1 - this)."""
    
    # Device
    device: str = "cuda"
    """Device for VLM inference."""


class SemanticFilter:
    """
    Semantic filter for validating object detections using VLM + embeddings.
    
    Pipeline:
    1. For each object crop, generate a VLM description
    2. Embed both the detection label and the description
    3. Compute cosine similarity
    4. Filter out detections where similarity is too low (likely false positives)
    
    Example:
        filter = SemanticFilter()
        results = filter.filter_tracks(tracks, crops)
        valid_tracks = [t for t, r in zip(tracks, results) if r.is_valid]
    """
    
    def __init__(
        self,
        config: Optional[SemanticFilterConfig] = None,
        *,
        vlm_model: Optional[Any] = None,
        sentence_model: Optional[Any] = None,
    ):
        """Initialize semantic filter.
        
        Args:
            config: Filter configuration. Uses defaults if None.
            vlm_model: Optional pre-loaded VLM wrapper instance (e.g., ModelManager.fastvlm).
                If provided, the filter will not load its own FastVLM instance.
            sentence_model: Optional pre-loaded SentenceTransformer instance.
        """
        self.config = config or SemanticFilterConfig()
        self._sentence_model = sentence_model
        self._vlm = vlm_model
        self._label_embeddings_cache: Dict[str, np.ndarray] = {}
        self._scene_embeddings_cache: Dict[str, np.ndarray] = {}
    
    @property
    def sentence_model(self):
        """Lazy-load sentence transformer."""
        if self._sentence_model is None:
            self._sentence_model = get_sentence_transformer()
        return self._sentence_model
    
    @property
    def vlm(self):
        """Lazy-load VLM."""
        if self._vlm is None:
            self._vlm = get_fastvlm(self.config.device)
        return self._vlm

    def rerank_candidate_labels(
        self,
        description: str,
        candidates: Sequence[Dict[str, Any]],
        *,
        blend: float = 0.6,
        top_k: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Re-rank candidate labels using a VLM-generated description.

        This is intended to make open-vocab hypotheses more robust by using
        FastVLM as a semantic verifier.

        Args:
            description: VLM description of the crop.
            candidates: Existing candidate labels [{label, score, source}, ...]
            blend: Blend factor for combining original candidate score and VLM text similarity.
                new_score = (1-blend)*orig_score + blend*vlm_similarity
            top_k: Optional cap on number of candidates returned.

        Returns:
            New list of candidates (sorted by blended score desc), with extra fields:
            - score_orig
            - score_vlm
            - score (blended)
            - source updated to include '+fastvlm'
        """
        if not candidates:
            return []
        if not isinstance(description, str) or not description.strip():
            # Nothing to rerank against.
            return list(candidates)

        # Embed description once.
        desc_emb = self.embed_text(description)

        reranked: List[Dict[str, Any]] = []
        for c in candidates:
            try:
                label = str(c.get("label", "")).strip()
            except Exception:
                label = ""
            if not label:
                continue
            orig_score = float(c.get("score", 0.0) or 0.0)
            label_emb = self.get_label_embedding(label)
            sim = self.cosine_similarity(desc_emb, label_emb)
            blended = (1.0 - float(blend)) * orig_score + float(blend) * sim
            out = dict(c)
            out["score_orig"] = orig_score
            out["score_vlm"] = sim
            out["score"] = float(blended)
            src = str(out.get("source", "candidate"))
            if "fastvlm" not in src:
                out["source"] = src + "+fastvlm"
            reranked.append(out)

        reranked.sort(key=lambda x: float(x.get("score", 0.0) or 0.0), reverse=True)
        if top_k is not None and top_k > 0:
            reranked = reranked[: int(top_k)]
        return reranked
    
    def embed_text(self, text: str) -> np.ndarray:
        """Embed a single text string."""
        return self.sentence_model.encode(text, convert_to_numpy=True)
    
    def embed_texts_batch(self, texts: Sequence[str]) -> np.ndarray:
        """Embed multiple texts in a batch."""
        return self.sentence_model.encode(texts, convert_to_numpy=True, batch_size=self.config.batch_size)
    
    def get_label_embedding(self, label: str) -> np.ndarray:
        """Get embedding for a label (cached for efficiency)."""
        if label not in self._label_embeddings_cache:
            # Expand label to more descriptive text for better matching
            expanded = f"A {label}, which is a type of object"
            self._label_embeddings_cache[label] = self.embed_text(expanded)
        return self._label_embeddings_cache[label]
    
    def cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Compute cosine similarity between two vectors."""
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))
    
    def generate_description(self, crop: Image.Image) -> str:
        """Generate VLM description for a single crop."""
        try:
            response = self.vlm.generate_description(
                crop,
                self.config.description_prompt,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
            )
            # Clean up response (remove prompt echo if present)
            if self.config.description_prompt in response:
                response = response.split(self.config.description_prompt)[-1].strip()
            return response.strip()
        except Exception as e:
            logger.warning(f"VLM generation failed: {e}")
            return ""
    
    def generate_descriptions_batch(
        self, 
        crops: Sequence[Image.Image],
        show_progress: bool = True,
    ) -> List[str]:
        """Generate VLM descriptions for multiple crops.
        
        Note: FastVLM doesn't support true batching, so we iterate.
        But we can still be efficient by pre-loading the model once.
        """
        descriptions = []
        total = len(crops)
        
        for i, crop in enumerate(crops):
            if show_progress and (i + 1) % 10 == 0:
                logger.info(f"  VLM processing: {i + 1}/{total}")
            desc = self.generate_description(crop)
            descriptions.append(desc)
        
        return descriptions
    
    def filter_single(
        self,
        crop: Image.Image,
        label: str,
        track_id: int,
        confidence: float = 0.0,
        scene_context: Optional[str] = None,
    ) -> FilterResult:
        """Filter a single detection.
        
        Args:
            crop: Object crop image.
            label: Detected label (e.g., "chair").
            track_id: Track ID for reference.
            confidence: Detection confidence score.
            scene_context: Optional scene description for context validation.
            
        Returns:
            FilterResult with validity decision.
        """
        # Generate VLM description
        description = self.generate_description(crop)
        
        if not description:
            # VLM failed, keep detection (high recall)
            return FilterResult(
                track_id=track_id,
                label=label,
                description="[VLM failed]",
                similarity=0.5,  # Neutral
                is_valid=True,
                confidence=confidence,
                reason="VLM generation failed, keeping by default",
            )
        
        # Embed description
        desc_embedding = self.embed_text(description)
        
        # Get label embedding (cached)
        label_embedding = self.get_label_embedding(label)
        
        # Compute similarity
        label_similarity = self.cosine_similarity(desc_embedding, label_embedding)
        
        # Optionally factor in scene context
        final_similarity = label_similarity
        if self.config.use_scene_context and scene_context:
            scene_embedding = self._scene_embeddings_cache.get(scene_context)
            if scene_embedding is None:
                scene_embedding = self.embed_text(scene_context)
                self._scene_embeddings_cache[scene_context] = scene_embedding
            scene_similarity = self.cosine_similarity(desc_embedding, scene_embedding)
            final_similarity = (
                (1 - self.config.scene_similarity_weight) * label_similarity +
                self.config.scene_similarity_weight * scene_similarity
            )
        
        # Decision
        is_valid = final_similarity >= self.config.similarity_threshold
        
        reason = ""
        if not is_valid:
            reason = f"Low similarity ({final_similarity:.2f} < {self.config.similarity_threshold}): '{label}' ≠ '{description[:50]}...'"
        
        return FilterResult(
            track_id=track_id,
            label=label,
            description=description,
            similarity=final_similarity,
            is_valid=is_valid,
            confidence=confidence,
            reason=reason,
        )
    
    def filter_batch(
        self,
        crops: Sequence[Image.Image],
        labels: Sequence[str],
        track_ids: Sequence[int],
        confidences: Optional[Sequence[float]] = None,
        scene_context: Optional[str] = None,
        show_progress: bool = True,
    ) -> List[FilterResult]:
        """Filter multiple detections efficiently.
        
        This is optimized for batch processing:
        1. Generate all VLM descriptions (sequential, VLM can't batch)
        2. Embed all descriptions in one batch (parallel)
        3. Compute all similarities (vectorized)
        
        Args:
            crops: List of object crop images.
            labels: List of detected labels.
            track_ids: List of track IDs.
            confidences: Optional list of detection confidences.
            scene_context: Optional scene description for context validation.
            show_progress: Whether to log progress.
            
        Returns:
            List of FilterResults.
        """
        n = len(crops)
        if n == 0:
            return []
        
        if confidences is None:
            confidences = [0.0] * n
        
        logger.info(f"Semantic filtering {n} tracks...")
        
        # Step 1: Generate all descriptions (VLM is sequential)
        logger.info("  Step 1: Generating VLM descriptions...")
        descriptions = self.generate_descriptions_batch(crops, show_progress)
        
        # Step 2: Batch embed all descriptions
        logger.info("  Step 2: Embedding descriptions...")
        valid_indices = [i for i, d in enumerate(descriptions) if d]
        valid_descriptions = [descriptions[i] for i in valid_indices]
        
        if valid_descriptions:
            desc_embeddings = self.embed_texts_batch(valid_descriptions)
        else:
            desc_embeddings = np.array([])
        
        # Pre-compute unique label embeddings
        unique_labels = set(labels)
        for label in unique_labels:
            _ = self.get_label_embedding(label)  # Populate cache
        
        # Optional: scene embedding
        scene_embedding = None
        if self.config.use_scene_context and scene_context:
            scene_embedding = self.embed_text(scene_context)
        
        # Step 3: Compute similarities and build results
        logger.info("  Step 3: Computing similarities...")
        results = []
        desc_idx = 0
        
        for i in range(n):
            track_id = track_ids[i]
            label = labels[i]
            confidence = confidences[i]
            description = descriptions[i]
            
            if not description:
                # VLM failed
                results.append(FilterResult(
                    track_id=track_id,
                    label=label,
                    description="[VLM failed]",
                    similarity=0.5,
                    is_valid=True,
                    confidence=confidence,
                    reason="VLM generation failed, keeping by default",
                ))
                continue
            
            # Get embeddings
            desc_emb = desc_embeddings[desc_idx]
            desc_idx += 1
            label_emb = self.get_label_embedding(label)
            
            # Compute similarity
            label_similarity = self.cosine_similarity(desc_emb, label_emb)
            
            final_similarity = label_similarity
            if scene_embedding is not None:
                scene_sim = self.cosine_similarity(desc_emb, scene_embedding)
                final_similarity = (
                    (1 - self.config.scene_similarity_weight) * label_similarity +
                    self.config.scene_similarity_weight * scene_sim
                )
            
            is_valid = final_similarity >= self.config.similarity_threshold
            
            reason = ""
            if not is_valid:
                reason = f"Low similarity ({final_similarity:.2f}): '{label}' ≠ '{description[:40]}...'"
            
            results.append(FilterResult(
                track_id=track_id,
                label=label,
                description=description,
                similarity=final_similarity,
                is_valid=is_valid,
                confidence=confidence,
                reason=reason,
            ))
        
        # Summary
        valid_count = sum(1 for r in results if r.is_valid)
        invalid_count = n - valid_count
        logger.info(f"  ✓ Filtering complete: {valid_count} valid, {invalid_count} rejected")
        
        return results


    def validate_with_scene_context(
        self,
        label: str,
        description: str,
        scene_caption: str,
        label_similarity: float,
    ) -> Tuple[bool, float, str]:
        """Validate a detection using both object description and scene context.
        
        This provides two-level validation:
        1. Does the VLM description match the detected label?
        2. Does the label make sense in the current scene?
        
        Args:
            label: Detected object label.
            description: VLM description of the object crop.
            scene_caption: Scene-level caption for context.
            label_similarity: Pre-computed similarity between description and label.
            
        Returns:
            Tuple of (is_valid, combined_score, reason).
        """
        # Check 1: Label vs Description (already computed)
        desc_valid = label_similarity >= self.config.similarity_threshold
        
        # Check 2: Label vs Scene Context
        if scene_caption:
            scene_embedding = self.embed_text(scene_caption)
            label_embedding = self.get_label_embedding(label)
            scene_similarity = self.cosine_similarity(label_embedding, scene_embedding)
            
            # Combined score with weighting
            combined = (
                (1 - self.config.scene_similarity_weight) * label_similarity +
                self.config.scene_similarity_weight * scene_similarity
            )
            
            # Heuristic: if label is totally out of context, flag it
            context_valid = scene_similarity >= 0.15
        else:
            combined = label_similarity
            scene_similarity = 0.0
            context_valid = True
        
        # Final decision
        is_valid = desc_valid and context_valid
        
        reason = ""
        if not desc_valid:
            reason = f"Description mismatch ({label_similarity:.2f}): '{label}' vs VLM"
        elif not context_valid:
            reason = f"Context mismatch ({scene_similarity:.2f}): '{label}' not in scene"
        
        return is_valid, combined, reason


def create_semantic_filter(
    device: str = "cuda",
    similarity_threshold: float = 0.25,
    use_scene_context: bool = True,
) -> SemanticFilter:
    """Factory function to create a configured semantic filter.
    
    Args:
        device: Device for VLM inference.
        similarity_threshold: Minimum similarity to keep detection.
        use_scene_context: Whether to factor in scene context.
        
    Returns:
        Configured SemanticFilter instance.
    """
    config = SemanticFilterConfig(
        device=device,
        similarity_threshold=similarity_threshold,
        use_scene_context=use_scene_context,
    )
    return SemanticFilter(config)


__all__ = [
    "SemanticFilter",
    "SemanticFilterConfig", 
    "FilterResult",
    "create_semantic_filter",
]
