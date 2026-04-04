"""Overlay renderer v3 (FastVLM captions + pseudo-3D boxes).

This is a sibling to `viz_overlay_v2`, keeping the same core goals:
- deterministic, stable, frame_id-based rendering at sampled cadence

Additions:
- pseudo-3D cuboid drawing using depth as a parallax cue
- optional per-frame scene caption overlay (e.g., from FastVLM)
- optional input tracks filename (e.g., tracks_filtered.jsonl)

Run:
python -m orion.perception.viz_overlay_v3 --video ... --results ... --fps 5 \
  --tracks tracks_filtered.jsonl --scene-jsonl vlm_scene.jsonl --output overlay_v3.mp4
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class OverlayV3Config:
    output_fps: float = 5.0
    output_filename: str = "overlay_v3.mp4"
    tracks_filename: str = "tracks.jsonl"
    scene_jsonl_filename: Optional[str] = None
    debug_jsonl_filename: Optional[str] = None


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _read_jsonl(path: Path) -> List[dict]:
    out: List[dict] = []
    with path.open("r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def _get_bbox(rec: dict) -> Optional[List[float]]:
    bb = rec.get("bbox")
    if bb is None:
        bb = rec.get("bbox_2d")
    if bb is None:
        return None
    if isinstance(bb, (list, tuple)) and len(bb) >= 4:
        return [float(bb[0]), float(bb[1]), float(bb[2]), float(bb[3])]
    return None


def _frame_md5_64x64(frame_bgr: np.ndarray) -> str:
    small = cv2.resize(frame_bgr, (64, 64), interpolation=cv2.INTER_AREA)
    return hashlib.md5(small.tobytes()).hexdigest()


class OverlayRendererV3:
    def __init__(self, video_path: Path, results_dir: Path, config: OverlayV3Config):
        self.video_path = video_path
        self.results_dir = results_dir
        self.config = config

        self.tracks_path = self.results_dir / self.config.tracks_filename
        if not self.tracks_path.exists():
            raise FileNotFoundError(f"Tracks file not found: {self.tracks_path}")

        self.scene_map: dict[int, str] = {}
        if self.config.scene_jsonl_filename:
            scene_path = self.results_dir / self.config.scene_jsonl_filename
            if scene_path.exists():
                for o in _read_jsonl(scene_path):
                    fid = o.get("frame_id")
                    cap = o.get("caption")
                    if fid is None or not cap:
                        continue
                    self.scene_map[int(fid)] = str(cap)
            else:
                logger.warning("scene jsonl not found: %s", scene_path)

        tracks = _read_jsonl(self.tracks_path)
        self.by_frame: dict[int, List[dict]] = {}
        for t in tracks:
            fid = t.get("frame_id")
            if fid is None:
                continue
            fid_i = int(fid)
            self.by_frame.setdefault(fid_i, []).append(t)

        self.sorted_frames = sorted(self.by_frame.keys())

    def _draw_label(self, img: np.ndarray, x1: int, y1: int, text: str, color: tuple[int, int, int]):
        font = cv2.FONT_HERSHEY_SIMPLEX
        scale = 0.55
        thickness = 2
        (tw, th), _ = cv2.getTextSize(text, font, scale, thickness)
        y0 = max(0, y1 - th - 8)
        cv2.rectangle(img, (x1, y0), (x1 + tw + 6, y1), color, -1)
        cv2.putText(img, text, (x1 + 3, y1 - 4), font, scale, (0, 0, 0), 1, cv2.LINE_AA)

    def _draw_cuboid(self, img: np.ndarray, bbox: List[float], color: tuple[int, int, int], depth_mm: Optional[float]):
        x1, y1, x2, y2 = [int(v) for v in bbox]
        h, w = img.shape[:2]
        x1 = max(0, min(w - 1, x1))
        x2 = max(0, min(w - 1, x2))
        y1 = max(0, min(h - 1, y1))
        y2 = max(0, min(h - 1, y2))

        if x2 <= x1 or y2 <= y1:
            return

        # Depth-based parallax offset: closer => bigger offset
        if depth_mm is None or depth_mm <= 1:
            base = 14
        else:
            base = int(np.clip(1200.0 / float(depth_mm), 6, 55))

        dx = base
        dy = -base

        x1b = max(0, min(w - 1, x1 + dx))
        x2b = max(0, min(w - 1, x2 + dx))
        y1b = max(0, min(h - 1, y1 + dy))
        y2b = max(0, min(h - 1, y2 + dy))

        # Front face
        cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
        # Back face
        cv2.rectangle(img, (x1b, y1b), (x2b, y2b), color, 2)
        # Connect
        cv2.line(img, (x1, y1), (x1b, y1b), color, 2)
        cv2.line(img, (x2, y1), (x2b, y1b), color, 2)
        cv2.line(img, (x1, y2), (x1b, y2b), color, 2)
        cv2.line(img, (x2, y2), (x2b, y2b), color, 2)

    def render(self) -> Path:
        cap = cv2.VideoCapture(str(self.video_path))
        if not cap.isOpened():
            raise RuntimeError(f"Failed to open video: {self.video_path}")

        src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        # We render at sampling cadence: assume sample interval = round(src_fps / output_fps)
        interval = max(1, int(round(src_fps / self.config.output_fps)))
        render_frame_ids = list(range(0, total_frames, interval))

        out_path = self.results_dir / self.config.output_filename

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(str(out_path), fourcc, self.config.output_fps, (frame_w, frame_h))
        if not writer.isOpened():
            raise RuntimeError("Failed to open VideoWriter (mp4v)")

        debug_f = None
        if self.config.debug_jsonl_filename:
            debug_f = (self.results_dir / self.config.debug_jsonl_filename).open("w")

        # Sequential decode (stable) and write when frame_id matches render schedule
        target_set = set(render_frame_ids)
        decoded_idx = 0
        frames_written = 0
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                if decoded_idx in target_set:
                    dets = self.by_frame.get(decoded_idx, [])

                    # Scene caption
                    caption = self.scene_map.get(decoded_idx)
                    if caption:
                        cv2.rectangle(frame, (0, 0), (frame_w, 42), (0, 0, 0), -1)
                        cv2.putText(frame, caption[:120], (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2, cv2.LINE_AA)

                    for d in dets:
                        bbox = _get_bbox(d)
                        if bbox is None:
                            continue
                        label = d.get("class_name") or d.get("category") or "unknown"
                        conf = float(d.get("confidence", 0.0) or 0.0)
                        depth_mm = d.get("depth_mm")
                        try:
                            depth_mm_f = float(depth_mm) if depth_mm is not None else None
                        except Exception:
                            depth_mm_f = None

                        # Color: deterministic per track
                        tid = _safe_int(d.get("track_id", d.get("id")), 0)
                        color = ((37 * tid) % 255, (17 * tid) % 255, (97 * tid) % 255)

                        self._draw_cuboid(frame, bbox, color, depth_mm_f)

                        z_text = ""
                        if depth_mm_f is not None and depth_mm_f > 0:
                            z_text = f" Z{depth_mm_f/1000.0:.2f}m"
                        text = f"{label} {conf:.2f}{z_text}"
                        self._draw_label(frame, int(bbox[0]), int(bbox[1]), text, color)

                    writer.write(frame)
                    frames_written += 1

                    if debug_f is not None:
                        debug_f.write(
                            json.dumps(
                                {
                                    "frame_id": decoded_idx,
                                    "decoded_pos_msec": cap.get(cv2.CAP_PROP_POS_MSEC),
                                    "decoded_pos_frames": cap.get(cv2.CAP_PROP_POS_FRAMES),
                                    "frame_md5_64x64": _frame_md5_64x64(frame),
                                    "num_dets": len(dets),
                                }
                            )
                            + "\n"
                        )

                decoded_idx += 1

        finally:
            cap.release()
            writer.release()
            if debug_f is not None:
                debug_f.close()

        logger.info("✓ Wrote %d frames to %s", frames_written, out_path)
        return out_path


def main() -> None:
    ap = argparse.ArgumentParser(description="Overlay renderer v3 (3D cues + FastVLM captions)")
    ap.add_argument("--video", type=str, required=True)
    ap.add_argument("--results", type=str, required=True)
    ap.add_argument("--fps", type=float, default=5.0)
    ap.add_argument("--tracks", type=str, default="tracks.jsonl")
    ap.add_argument("--scene-jsonl", type=str, default=None)
    ap.add_argument("--output", type=str, default="overlay_v3.mp4")
    ap.add_argument("--debug-jsonl", type=str, default=None)
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    cfg = OverlayV3Config(
        output_fps=float(args.fps),
        output_filename=str(args.output),
        tracks_filename=str(args.tracks),
        scene_jsonl_filename=str(args.scene_jsonl) if args.scene_jsonl else None,
        debug_jsonl_filename=str(args.debug_jsonl) if args.debug_jsonl else None,
    )

    renderer = OverlayRendererV3(Path(args.video), Path(args.results), cfg)
    out = renderer.render()
    print(f"Output saved to: {out}")


if __name__ == "__main__":
    main()
