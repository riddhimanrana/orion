"""Rich overlay renderer v4 (YOLO + Re-ID + FastVLM + Gemini QA panel).

Goals:
- deterministic, stable, frame_id-based rendering at sampled cadence
- schema-flexible: supports both showcase `tracks.jsonl` (bbox_2d/class_name/track_id)
  and PerceptionEngine `tracks.jsonl` (bounding_box/object_class/temp_id/entity_id)
- optional QA panel sourced from `scripts/eval_v3_architecture.py` JSON output

Run:
  python -m orion.perception.viz_overlay_v4 --video data/examples/test.mp4 \
    --results results/engine_test --eval-json results/lambda_orion_20260108/lambda_eval_v3_test_20260108.json

Notes:
- This renders at the detection sampling cadence (default: inferred from tracks/video).
- If a detection contains FastVLM fields (vlm_*), they are displayed and color-coded.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class OverlayV4Config:
    # Video timing
    output_fps: Optional[float] = None  # None => infer from video/sample interval

    # Output
    output_filename: str = "overlay_v4.mp4"
    tracks_filename: str = "tracks.jsonl"

    # Panels
    show_frame_info: bool = True
    show_scene_caption: bool = True

    # Detection label verbosity
    show_candidate_labels: bool = True
    show_scene_filter: bool = True
    show_semantic_verifier: bool = True

    # QA panel (optional)
    eval_json_path: Optional[Path] = None
    qa_seconds_per_item: float = 6.0
    qa_only_wrong: bool = False
    qa_max_lines: int = 8


def _read_jsonl(path: Path) -> List[dict]:
    out: List[dict] = []
    with path.open("r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def _safe_int(v: Any, default: int = -1) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _get_frame_id(rec: dict) -> Optional[int]:
    for k in ("frame_id", "frame_number", "frame"):
        v = rec.get(k)
        if v is None:
            continue
        try:
            return int(v)
        except Exception:
            continue
    return None


def _get_bbox(rec: dict) -> Optional[List[float]]:
    bb = rec.get("bbox_2d")
    if bb is None:
        bb = rec.get("bbox")
    if bb is not None:
        if isinstance(bb, (list, tuple)) and len(bb) >= 4:
            return [float(bb[0]), float(bb[1]), float(bb[2]), float(bb[3])]

    bb2 = rec.get("bounding_box")
    if isinstance(bb2, dict):
        keys = ("x1", "y1", "x2", "y2")
        if all(k in bb2 for k in keys):
            return [float(bb2["x1"]), float(bb2["y1"]), float(bb2["x2"]), float(bb2["y2"])]
    if isinstance(bb2, (list, tuple)) and len(bb2) >= 4:
        return [float(bb2[0]), float(bb2[1]), float(bb2[2]), float(bb2[3])]

    return None


def _get_label(rec: dict) -> str:
    for k in ("class_name", "object_class", "label", "category"):
        v = rec.get(k)
        if v:
            return str(v)
    return "unknown"


_TEMP_ID_RE = re.compile(r"(\d+)")


def _get_track_id(rec: dict) -> int:
    tid = rec.get("track_id")
    if tid is not None:
        return _safe_int(tid, -1)

    # PerceptionEngine schema: temp_id is a string (often contains a numeric suffix)
    temp_id = rec.get("temp_id")
    if temp_id:
        m = _TEMP_ID_RE.search(str(temp_id))
        if m:
            return _safe_int(m.group(1), -1)

    return -1


def _wrap_text(text: str, max_chars: int) -> List[str]:
    """Very small, deterministic word-wrap."""
    if not text:
        return []
    words = text.split()
    lines: List[str] = []
    cur: List[str] = []
    cur_len = 0
    for w in words:
        extra = (1 if cur else 0) + len(w)
        if cur and cur_len + extra > max_chars:
            lines.append(" ".join(cur))
            cur = [w]
            cur_len = len(w)
        else:
            cur.append(w)
            cur_len += extra
    if cur:
        lines.append(" ".join(cur))
    return lines


def _color_for_id(seed: int) -> Tuple[int, int, int]:
    # Deterministic BGR for OpenCV
    return ((37 * seed) % 255, (17 * seed) % 255, (97 * seed) % 255)


def _unrotate_if_needed(
    bbox: List[float],
    frame_w: int,
    frame_h: int,
) -> List[float]:
    """Undo 90° CCW rotation for portrait videos when bboxes look rotated."""
    x1, y1, x2, y2 = bbox
    is_portrait = frame_h > frame_w

    # Heuristic: bbox coords exceed the portrait frame bounds => likely in rotated landscape space.
    looks_rotated = is_portrait and (max(x1, x2) > frame_w + 2 or max(y1, y2) > frame_h + 2)
    if not looks_rotated:
        return bbox

    # Inverse mapping of 90° CCW rotation:
    # original -> rotated: x' = y, y' = (W-1) - x
    # rotated  -> original: x = (W-1) - y', y = x'
    orig_w = frame_w
    corners = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
    unrot: List[Tuple[float, float]] = []
    for xr, yr in corners:
        xo = (orig_w - 1) - yr
        yo = xr
        unrot.append((xo, yo))
    xs = [p[0] for p in unrot]
    ys = [p[1] for p in unrot]
    return [min(xs), min(ys), max(xs), max(ys)]


def _load_run_metadata(results_dir: Path) -> Dict[str, Any]:
    p = results_dir / "run_metadata.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}


def _load_track_to_memory(results_dir: Path) -> Dict[int, str]:
    """Optional mapping for showcase pipeline (Phase 2 memory.json)."""
    memory_path = results_dir / "memory.json"
    if not memory_path.exists():
        return {}
    try:
        data = json.loads(memory_path.read_text())
        track_to_mem: Dict[int, str] = {}
        for obj in data.get("objects", []):
            mem_id = obj.get("memory_id")
            if not mem_id:
                continue
            for seg in obj.get("appearance_history", []):
                tid = seg.get("track_id")
                if tid is None:
                    continue
                try:
                    track_to_mem[int(tid)] = str(mem_id)
                except Exception:
                    continue
        return track_to_mem
    except Exception:
        return {}


def _load_eval_items(eval_json_path: Path, only_wrong: bool) -> List[dict]:
    try:
        payload = json.loads(eval_json_path.read_text())
    except Exception as e:
        logger.warning("Failed to read eval json: %s", e)
        return []

    items = payload.get("results")
    if not isinstance(items, list):
        return []

    out: List[dict] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        verdict = str(it.get("gemini_verdict", "")).upper().strip()
        if only_wrong and verdict == "CORRECT":
            continue
        out.append(it)
    return out


class OverlayRendererV4:
    def __init__(self, video_path: Path, results_dir: Path, config: OverlayV4Config):
        self.video_path = Path(video_path)
        self.results_dir = Path(results_dir)
        self.config = config

        self.tracks_path = self.results_dir / self.config.tracks_filename
        if not self.tracks_path.exists():
            raise FileNotFoundError(f"Tracks file not found: {self.tracks_path}")

        self.meta = _load_run_metadata(self.results_dir)
        self.scene_caption: str = ""
        # PerceptionEngine schema
        if isinstance(self.meta.get("scene_caption"), str):
            self.scene_caption = str(self.meta.get("scene_caption") or "")
        # Showcase schema
        if not self.scene_caption and isinstance(self.meta.get("detector"), dict):
            self.scene_caption = str(self.meta.get("detector", {}).get("scene_caption") or "")

        # Track->memory mapping (optional)
        self.track_to_memory = _load_track_to_memory(self.results_dir)

        # Eval items (optional)
        self.eval_items: List[dict] = []
        if self.config.eval_json_path is not None:
            self.eval_items = _load_eval_items(self.config.eval_json_path, self.config.qa_only_wrong)

        tracks = _read_jsonl(self.tracks_path)
        self.by_frame: Dict[int, List[dict]] = {}
        for t in tracks:
            fid = _get_frame_id(t)
            if fid is None:
                continue
            self.by_frame.setdefault(int(fid), []).append(t)

        self.sorted_frames = sorted(self.by_frame.keys())
        if not self.sorted_frames:
            raise RuntimeError("No frame-indexed tracks found in tracks.jsonl")

    def _draw_text_panel(
        self,
        frame: np.ndarray,
        lines: List[str],
        origin: Tuple[int, int],
        width: int,
        bg_alpha: float = 0.6,
        font_scale: float = 0.52,
        line_height: int = 18,
        pad: int = 10,
    ) -> None:
        if not lines:
            return

        h, w = frame.shape[:2]
        x0, y0 = origin
        panel_w = min(width, w - x0 - 1)
        panel_h = min(h - y0 - 1, pad * 2 + line_height * len(lines) + 6)

        overlay = frame.copy()
        cv2.rectangle(overlay, (x0, y0), (x0 + panel_w, y0 + panel_h), (0, 0, 0), -1)
        cv2.addWeighted(overlay, bg_alpha, frame, 1.0 - bg_alpha, 0, frame)

        y = y0 + pad + 14
        for ln in lines:
            cv2.putText(
                frame,
                ln,
                (x0 + pad, y),
                cv2.FONT_HERSHEY_SIMPLEX,
                font_scale,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )
            y += line_height

    def _qa_lines(self, out_idx: int, fps: float) -> List[str]:
        if not self.eval_items:
            return []

        frames_per = max(1, int(round(self.config.qa_seconds_per_item * fps)))
        idx = (out_idx // frames_per) % len(self.eval_items)
        it = self.eval_items[idx]

        q = str(it.get("question", "")).strip()
        ans = str(it.get("orion_answer", "")).strip()
        verdict = str(it.get("gemini_verdict", "")).upper().strip()
        notes = str(it.get("gemini_notes", "")).strip()

        # Keep within panel budget
        lines: List[str] = []
        lines.append(f"QA {idx+1}/{len(self.eval_items)} | Gemini: {verdict}")
        for ln in _wrap_text(f"Q: {q}", 62)[:2]:
            lines.append(ln)
        for ln in _wrap_text(f"Orion: {ans}", 62)[:3]:
            lines.append(ln)
        for ln in _wrap_text(f"Gemini notes: {notes}", 62)[:3]:
            lines.append(ln)

        return lines[: self.config.qa_max_lines]

    def _draw_detection(self, frame: np.ndarray, det: dict, frame_w: int, frame_h: int) -> None:
        bbox = _get_bbox(det)
        if bbox is None:
            return

        bbox = _unrotate_if_needed(bbox, frame_w=frame_w, frame_h=frame_h)
        x1, y1, x2, y2 = [int(v) for v in bbox]

        # Clamp
        x1 = max(0, min(frame_w - 1, x1))
        x2 = max(0, min(frame_w - 1, x2))
        y1 = max(0, min(frame_h - 1, y1))
        y2 = max(0, min(frame_h - 1, y2))
        if x2 <= x1 or y2 <= y1:
            return

        label = _get_label(det)
        conf = _safe_float(det.get("confidence"), 0.0)
        raw_yolo = det.get("raw_yolo_class")

        tid = _get_track_id(det)
        ent = det.get("entity_id")
        mem_id = self.track_to_memory.get(tid) if tid >= 0 else None

        # Semantic verifier status (FastVLM)
        vlm_is_valid = det.get("vlm_is_valid")
        try:
            vlm_is_valid_b = bool(vlm_is_valid) if vlm_is_valid is not None else None
        except Exception:
            vlm_is_valid_b = None

        base_color = _color_for_id(tid if tid >= 0 else (abs(hash(label)) % 997))

        # Scene filter signal (legacy / v2)
        scene_reason = det.get("scene_filter_reason") or det.get("scene_filter_reason_v2")

        if vlm_is_valid_b is True:
            color = (60, 220, 60)
            thickness = 3
        elif vlm_is_valid_b is False:
            color = (40, 40, 220)
            thickness = 3
        else:
            s_reason = str(scene_reason or "")
            if s_reason and ("does_not" in s_reason or "blacklisted" in s_reason or "below_threshold" in s_reason):
                color = (0, 165, 255)
                thickness = 3
            else:
                color = base_color
                thickness = 2

        cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)

        # Label line 1
        parts = [label, f"{conf:.2f}"]
        if tid >= 0:
            parts.append(f"T{tid}")
        if ent:
            parts.append(f"E{str(ent)[-4:]}")
        if mem_id:
            parts.append(f"M{str(mem_id)[-4:]}")
        line1 = " | ".join(parts)

        # Label line 2 (semantic + filters)
        line2_parts: List[str] = []
        if raw_yolo and str(raw_yolo) != label:
            line2_parts.append(f"yolo:{raw_yolo}")

        if self.config.show_scene_filter and scene_reason:
            sim = det.get("scene_similarity")
            if sim is None:
                sim = det.get("scene_similarity_v2")
            if sim is not None:
                line2_parts.append(f"scene:{scene_reason} {float(sim):.2f}")
            else:
                line2_parts.append(f"scene:{scene_reason}")

        if self.config.show_semantic_verifier and det.get("vlm_similarity") is not None:
            vs = _safe_float(det.get("vlm_similarity"), 0.0)
            vtag = "✓" if vlm_is_valid_b is True else "✗" if vlm_is_valid_b is False else "?"
            line2_parts.append(f"fastvlm:{vtag} {vs:.2f}")

        if self.config.show_candidate_labels and det.get("candidate_labels"):
            cands = det.get("candidate_labels")
            if isinstance(cands, list) and cands:
                top = cands[:2]
                cand_strs = []
                for c in top:
                    if isinstance(c, dict) and c.get("label"):
                        sc = c.get("score")
                        if sc is None:
                            cand_strs.append(str(c["label"]))
                        else:
                            try:
                                cand_strs.append(f"{c['label']}({float(sc):.2f})")
                            except Exception:
                                cand_strs.append(str(c["label"]))
                if cand_strs:
                    line2_parts.append("cands:" + ",".join(cand_strs))

        line2 = " | ".join(line2_parts)[:110]

        # Draw label background
        font = cv2.FONT_HERSHEY_SIMPLEX
        scale = 0.52
        t1 = 2
        (w1, h1), b1 = cv2.getTextSize(line1, font, scale, t1)
        (w2, h2), b2 = cv2.getTextSize(line2, font, 0.46, 1) if line2 else ((0, 0), 0)
        pad = 6
        box_w = max(w1, w2) + pad * 2
        box_h = h1 + b1 + (h2 + b2 if line2 else 0) + pad * 3

        y0 = y1 - box_h - 4
        if y0 < 0:
            y0 = y2 + 4
        x0 = x1

        overlay = frame.copy()
        cv2.rectangle(overlay, (x0, y0), (x0 + box_w, y0 + box_h), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)

        y_text = y0 + pad + h1
        cv2.putText(frame, line1, (x0 + pad, y_text), font, scale, (255, 255, 255), t1, cv2.LINE_AA)
        if line2:
            y_text2 = y_text + pad + h2
            cv2.putText(frame, line2, (x0 + pad, y_text2), font, 0.46, (220, 220, 220), 1, cv2.LINE_AA)

    def render(self) -> Path:
        cap = cv2.VideoCapture(str(self.video_path))
        if not cap.isOpened():
            raise RuntimeError(f"Failed to open video: {self.video_path}")

        src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        # Infer sample interval from track frame ids
        diffs = [b - a for a, b in zip(self.sorted_frames, self.sorted_frames[1:]) if b > a]
        if diffs:
            # Most common diff
            vals, counts = np.unique(np.array(diffs, dtype=np.int32), return_counts=True)
            sample_interval = int(vals[int(np.argmax(counts))])
            sample_interval = max(1, sample_interval)
        else:
            sample_interval = 1

        sampled_frame_ids = list(range(0, total_frames, sample_interval))
        sampled_set = set(sampled_frame_ids)

        # Output fps: either configured, or computed from interval
        if self.config.output_fps is None or self.config.output_fps <= 0:
            out_fps = max(1.0, float(src_fps) / float(sample_interval))
        else:
            out_fps = float(self.config.output_fps)

        out_path = self.results_dir / self.config.output_filename

        codecs = ["avc1", "mp4v", "XVID"]
        writer = None
        for codec in codecs:
            fourcc = cv2.VideoWriter_fourcc(*codec)
            writer = cv2.VideoWriter(str(out_path), fourcc, out_fps, (frame_w, frame_h))
            if writer.isOpened():
                logger.info("Using codec=%s, output_fps=%.2f", codec, out_fps)
                break
            writer.release()
            writer = None
        if writer is None:
            raise RuntimeError("Failed to create video writer")

        try:
            decoded_idx = 0
            written = 0
            sampled_count = len(sampled_frame_ids)

            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                if decoded_idx in sampled_set:
                    dets = self.by_frame.get(decoded_idx, [])

                    # Header bar
                    if self.config.show_scene_caption and self.scene_caption:
                        cv2.rectangle(frame, (0, 0), (frame_w, 44), (0, 0, 0), -1)
                        cv2.putText(
                            frame,
                            (self.scene_caption[:120] + ("…" if len(self.scene_caption) > 120 else "")),
                            (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.62,
                            (255, 255, 255),
                            2,
                            cv2.LINE_AA,
                        )

                    for d in dets:
                        self._draw_detection(frame, d, frame_w=frame_w, frame_h=frame_h)

                    if self.config.show_frame_info:
                        ts = None
                        if dets and dets[0].get("timestamp") is not None:
                            ts = _safe_float(dets[0].get("timestamp"), 0.0)
                        if ts is None:
                            ts = float(decoded_idx) / float(src_fps)
                        info_lines = [
                            f"frame={decoded_idx}/{total_frames}  t={ts:.2f}s  dets={len(dets)}",
                        ]
                        # Surface embedding backend if present
                        emb_backend = None
                        try:
                            emb_backend = self.meta.get("metrics", {}).get("embedding_backend")
                        except Exception:
                            emb_backend = None
                        if not emb_backend and isinstance(self.meta.get("metrics"), dict):
                            emb_backend = self.meta["metrics"].get("embedding_backend")
                        if emb_backend:
                            info_lines.append(f"Re-ID embeddings: {emb_backend}")

                        self._draw_text_panel(frame, info_lines, origin=(10, 52), width=460, bg_alpha=0.45)

                    qa_lines = self._qa_lines(written, fps=out_fps)
                    if qa_lines:
                        # Right-side QA panel
                        self._draw_text_panel(
                            frame,
                            qa_lines,
                            origin=(max(10, frame_w - 560), 52),
                            width=550,
                            bg_alpha=0.62,
                            font_scale=0.50,
                            line_height=18,
                            pad=10,
                        )

                    writer.write(frame)
                    written += 1
                    if written % 60 == 0:
                        logger.info("Rendered %d/%d frames", written, sampled_count)

                    if written >= sampled_count:
                        break

                decoded_idx += 1

        finally:
            cap.release()
            writer.release()

        logger.info("✓ Wrote overlay: %s", out_path)
        return out_path


def main() -> None:
    ap = argparse.ArgumentParser(description="Overlay renderer v4 (semantic + QA panel)")
    ap.add_argument("--video", type=str, required=True)
    ap.add_argument("--results", type=str, required=True)
    ap.add_argument("--tracks", type=str, default="tracks.jsonl")
    ap.add_argument("--output", type=str, default="overlay_v4.mp4")
    ap.add_argument("--fps", type=float, default=0.0, help="Output FPS. 0 => infer from tracks/video")

    ap.add_argument("--eval-json", type=str, default=None, help="Eval JSON from scripts/eval_v3_architecture.py")
    ap.add_argument("--qa-seconds", type=float, default=6.0)
    ap.add_argument("--qa-only-wrong", action="store_true")

    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    cfg = OverlayV4Config(
        output_fps=(args.fps if args.fps and args.fps > 0 else None),
        output_filename=str(args.output),
        tracks_filename=str(args.tracks),
        eval_json_path=(Path(args.eval_json) if args.eval_json else None),
        qa_seconds_per_item=float(args.qa_seconds),
        qa_only_wrong=bool(args.qa_only_wrong),
    )

    renderer = OverlayRendererV4(Path(args.video), Path(args.results), cfg)
    out = renderer.render()
    print(f"Output saved to: {out}")


if __name__ == "__main__":
    main()
