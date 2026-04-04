"""PVSG dataset loader for evaluation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List


@dataclass
class PVSGBundle:
    root: Path
    split: str
    annotations: List[Dict[str, object]]

    @property
    def video_ids(self) -> List[str]:
        return [str(entry.get("video_id") or entry.get("id") or entry.get("name")) for entry in self.annotations]

    def iter_entries(self) -> Iterable[Dict[str, object]]:
        return iter(self.annotations)


def load_pvsg(root: str | Path, split: str = "test") -> PVSGBundle:
    root = Path(root)
    annotation_path = root / "annotations" / f"{split}.json"
    if not annotation_path.exists():
        raise FileNotFoundError(f"Missing PVSG annotations at {annotation_path}")
    with annotation_path.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)
    if isinstance(payload, dict) and "videos" in payload:
        annotations = payload["videos"]
    elif isinstance(payload, list):
        annotations = payload
    else:
        raise ValueError("Unsupported PVSG annotation format: expected list or {videos: []}")
    return PVSGBundle(root=root, split=split, annotations=annotations)
