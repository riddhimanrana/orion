"""Open-vocabulary prompting utilities for Orion.

This module centralizes:
- Stage-1 coarse prompt sets for YOLO-World (high recall, low commitment)
- Prompt groups for *candidate* open-vocab labeling (fine-grained, long-tail)
- A simple scheduler to rotate prompt groups over time

Design goal: avoid setting 100+ prompts on the YOLO-World detector for every frame.
Instead, detect with a small coarse set and accumulate fine-grained candidates over time.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence


# ---------------------------------------------------------------------------
# Stage 1 (dense) prompt set: coarse, stable, low-commitment
# ---------------------------------------------------------------------------

YOLO_WORLD_STAGE1_COARSE_CLASSES: list[str] = [
    # People/body
    "person",
    "face",
    "hand",

    # Broad physical categories
    "container",
    "bottle",
    "cup",
    "bag",
    "box",

    # Household / scene structure
    "furniture",
    "table",
    "chair",
    "door",
    "window",

    # Electronics
    "electronic device",
    "phone",
    "laptop",

    # Text regions
    "text",

    # Background (per Ultralytics YOLO-World guidance)
    "",
]


# ---------------------------------------------------------------------------
# Candidate prompt groups: fine-grained, long-tail, rotated over time
# ---------------------------------------------------------------------------

PROMPT_GROUPS: Dict[str, List[str]] = {
    "electronics": [
        "phone",
        "smartphone",
        "iphone",
        "airpods",
        "airpods case",
        "airpods charging case",
        "wireless earbuds",
        "earbuds case",
        "laptop",
        "charger",
        "charging cable",
        "usb cable",
        "power bank",
        "remote control",
        "keyboard",
        "mouse",
        "tablet",
        "smart watch",
        "watch",
    ],
    "containers": [
        "water bottle",
        "bottle",
        "cup",
        "mug",
        "glass",
        "thermos",
        "food container",
        "tupperware",
        "box",
        "cardboard box",
        "plastic container",
        "backpack",
        "bag",
        "handbag",
        "purse",
        "wallet",
        "keychain",
        "keys",
    ],
    "kitchen": [
        "plate",
        "bowl",
        "fork",
        "spoon",
        "knife",
        "cutting board",
        "pan",
        "pot",
        "kettle",
        "coffee maker",
        "microwave",
        "refrigerator",
    ],
    "office": [
        "book",
        "notebook",
        "paper",
        "pen",
        "pencil",
        "stapler",
        "scissors",
        "tape",
        "lamp",
        "desk",
        "chair",
    ],
    "personal_items": [
        "glasses",
        "sunglasses",
        "hat",
        "shoe",
        "jacket",
        "ring",
    ],
    "architecture": [
        "door",
        "doorway",
        "archway",
        "hallway",
        "staircase",
        "stairs",
        "railing",
        "window",
        "curtain",
        "blinds",
        "wall",
        "floor",
        "ceiling",
        "painting",
        "picture frame",
        "wall art",
        "mirror",
        "rug",
        "ottoman",
        "couch",
    ],
}


@dataclass(frozen=True)
class PromptSchedule:
    """Prompt scheduling parameters for candidate-label rotation."""

    group_names: Sequence[str]
    rotate_every_frames: int = 4

    def pick_group(self, frame_number: int) -> str:
        if not self.group_names:
            raise ValueError("PromptSchedule.group_names cannot be empty")
        idx = (frame_number // max(1, self.rotate_every_frames)) % len(self.group_names)
        return str(self.group_names[idx])


def resolve_prompt_groups(group_names: Sequence[str] | None) -> Dict[str, List[str]]:
    """Resolve a subset of PROMPT_GROUPS.

    Args:
        group_names: names to include. If None/empty, returns all.

    Returns:
        Dict[group_name, prompts]
    """
    if not group_names:
        return dict(PROMPT_GROUPS)
    missing = [g for g in group_names if g not in PROMPT_GROUPS]
    if missing:
        raise ValueError(f"Unknown prompt groups: {missing}. Known: {sorted(PROMPT_GROUPS.keys())}")
    return {g: PROMPT_GROUPS[g] for g in group_names}
