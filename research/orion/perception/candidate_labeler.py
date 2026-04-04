"""Open-vocabulary candidate labeling.

This module attaches *non-committal* candidate labels to detections.

Implementation choice (intentional): use CLIP for candidate scoring.
- YOLO-World is used for *detection* with a small coarse prompt set.
- CLIP provides fast text-image similarity for fine-grained candidate hypotheses.

This avoids the failure mode observed when setting 100+ prompts on YOLO-World
("prompt collapse" + noisy labels + poor recall/precision).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

from orion.perception.open_vocab import PromptSchedule, resolve_prompt_groups

logger = logging.getLogger(__name__)


@dataclass
class CandidateLabel:
    label: str
    score: float
    source: str = "clip"

    def to_dict(self) -> Dict[str, Any]:
        return {"label": self.label, "score": float(self.score), "source": self.source}


class OpenVocabCandidateLabeler:
    """Attach top-k open-vocab candidate labels to detections."""

    def __init__(
        self,
        clip_embedder: Any,
        prompt_schedule: PromptSchedule,
        prompt_groups: Optional[Dict[str, List[str]]] = None,
        top_k: int = 5,
        text_template: str = "a photo of {label}",
    ):
        self.clip = clip_embedder
        self.schedule = prompt_schedule
        self.prompt_groups = prompt_groups or resolve_prompt_groups(list(prompt_schedule.group_names))
        self.top_k = int(top_k)
        self.text_template = str(text_template)

        # Cache: prompt -> embedding vector
        self._text_emb_cache: Dict[str, np.ndarray] = {}

    def _embed_prompts(self, prompts: Sequence[str]) -> np.ndarray:
        """Return stacked text embeddings for prompts."""
        texts: List[str] = []
        for p in prompts:
            p = str(p).strip()
            if not p:
                continue
            if p not in self._text_emb_cache:
                texts.append(p)

        if texts:
            # Batch encode new prompts
            new_embs = self.clip.encode_texts([self.text_template.format(label=t) for t in texts], normalize=True)
            for t, e in zip(texts, new_embs):
                self._text_emb_cache[t] = e

        return np.stack([self._text_emb_cache[str(p).strip()] for p in prompts if str(p).strip()], axis=0)

    def score_crops(
        self,
        crops: Sequence[np.ndarray],
        prompts: Sequence[str],
        top_k: Optional[int] = None,
    ) -> List[List[CandidateLabel]]:
        """Score each crop against prompts using CLIP similarity."""
        if not crops:
            return []
        clean_prompts = [p.strip() for p in prompts if str(p).strip()]
        if not clean_prompts:
            return [[] for _ in crops]

        text_embs = self._embed_prompts(clean_prompts)  # [P, D]

        # Batch encode images
        img_embs = self.clip.encode_images(list(crops), normalize=True)  # [N, D]

        # Similarity = dot for normalized embeddings
        sims = img_embs @ text_embs.T  # [N, P]

        k = int(top_k or self.top_k)
        k = max(1, min(k, sims.shape[1]))

        results: List[List[CandidateLabel]] = []
        for i in range(sims.shape[0]):
            row = sims[i]
            # argpartition for speed
            idxs = np.argpartition(-row, kth=k - 1)[:k]
            idxs = idxs[np.argsort(-row[idxs])]
            results.append([
                CandidateLabel(label=clean_prompts[j], score=float(row[j]), source="clip")
                for j in idxs
            ])
        return results

    def attach_candidates(
        self,
        detections: List[Dict[str, Any]],
        frame_number: int,
        *,
        crop_key: str = "crop",
        output_key: str = "candidate_labels",
        group_override: Optional[str] = None,
    ) -> None:
        """Mutates detection dicts in-place to add candidate labels."""
        if not detections:
            return

        group_name = group_override or self.schedule.pick_group(int(frame_number))
        prompts = self.prompt_groups.get(group_name)
        if not prompts:
            logger.debug("No prompts for group %s", group_name)
            return

        crops: List[np.ndarray] = []
        valid_indices: List[int] = []
        for i, det in enumerate(detections):
            crop = det.get(crop_key)
            if isinstance(crop, np.ndarray) and crop.size > 0:
                crops.append(crop)
                valid_indices.append(i)

        if not crops:
            return

        scored = self.score_crops(crops=crops, prompts=prompts)
        for det_idx, cand_list in zip(valid_indices, scored):
            detections[det_idx][output_key] = [c.to_dict() for c in cand_list]
            detections[det_idx]["candidate_group"] = group_name
