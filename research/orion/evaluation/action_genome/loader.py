"""Action Genome dataset loader (SGA evaluation)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

from orion.vsgg.datasets import ActionGenomeSceneGraphDataset, VideoSceneGraphSample


@dataclass
class ActionGenomeBundle:
    root: str
    split: str
    samples: List[VideoSceneGraphSample]

    def iter_samples(self) -> Iterable[VideoSceneGraphSample]:
        return iter(self.samples)


def load_action_genome(root: str, split: str = "test", max_videos: int | None = None) -> ActionGenomeBundle:
    dataset = ActionGenomeSceneGraphDataset(
        root,
        split=split,
        group_by_video=True,
        min_frames_per_video=2,
        max_videos=max_videos,
    )
    return ActionGenomeBundle(root=root, split=split, samples=dataset.samples)
