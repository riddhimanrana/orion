"""Overlay API compatibility shim.

The showcase CLI imports :class:`OverlayOptions` and
:func:`render_insight_overlay` from this module.

To keep overlays stable and deterministic, this shim delegates rendering to the
schema-flexible v4 renderer.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from orion.perception.viz_overlay_v4 import OverlayRendererV4, OverlayV4Config


@dataclass
class OverlayOptions:
    """Tunable parameters for insight overlays.

    Most fields are preserved for backward compatibility with older callers.
    The v4 renderer currently uses only output naming and inferred FPS.
    """

    max_relations: int = 4
    message_linger_seconds: float = 1.75
    max_state_messages: int = 5
    gap_frames_for_refind: int = 45
    overlay_basename: str = "video_overlay_insights.mp4"
    frame_offset: int = 0
    use_timestamp_matching: bool = True
    timestamp_offset: float = 0.0


def _infer_target_fps(results_dir: Path) -> Optional[float]:
    """Best-effort overlay FPS inference from run metadata."""
    meta_path = results_dir / "run_metadata.json"
    if not meta_path.exists():
        return None

    try:
        meta = json.loads(meta_path.read_text())
    except Exception:
        return None

    if meta.get("target_fps") is not None:
        try:
            return float(meta["target_fps"])
        except Exception:
            return None

    cfg = meta.get("config")
    if isinstance(cfg, dict) and cfg.get("target_fps") is not None:
        try:
            return float(cfg["target_fps"])
        except Exception:
            return None

    return None


def render_insight_overlay(
    video_path: Path,
    results_dir: Path,
    output_path: Optional[Path] = None,
    options: Optional[OverlayOptions] = None,
) -> Path:
    """Render an overlay video for a results directory."""
    results_dir = Path(results_dir)
    video_path = Path(video_path)
    options = options or OverlayOptions()

    if output_path is None:
        output_path = results_dir / options.overlay_basename
    else:
        output_path = Path(output_path)

    cfg = OverlayV4Config(
        output_fps=_infer_target_fps(results_dir),
        output_filename=output_path.name,
        tracks_filename="tracks.jsonl",
        eval_json_path=None,
    )

    renderer = OverlayRendererV4(video_path=video_path, results_dir=results_dir, config=cfg)
    rendered_path = renderer.render()

    if rendered_path.resolve() != output_path.resolve():
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.move(str(rendered_path), str(output_path))
            rendered_path = output_path
        except Exception:
            shutil.copy2(str(rendered_path), str(output_path))
            rendered_path = output_path

    return rendered_path
