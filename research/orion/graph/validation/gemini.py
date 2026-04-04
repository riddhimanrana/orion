from __future__ import annotations

"""Helpers for validating scene graph relations with Gemini Vision."""

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class GeminiSampleResult:
    frame: int
    overall_quality: str
    verdict_counts: Dict[str, int]


class GeminiValidationError(RuntimeError):
    """Raised when Gemini validation cannot be executed."""


def _load_gemini_model(api_key: str, model_name: str):
    try:
        from orion.utils.gemini_client import get_gemini_model
    except Exception as exc:  # pragma: no cover
        raise GeminiValidationError(
            "Gemini client helpers are unavailable; ensure Orion is importable."
        ) from exc

    try:
        return get_gemini_model(model_name, api_key=api_key)
    except Exception as exc:  # pragma: no cover - dependency missing at runtime
        raise GeminiValidationError(
            "google-genai is not installed. Install it via 'pip install google-genai'."
        ) from exc


def _read_env_file(env_path: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    if not env_path.exists():
        return values
    with env_path.open("r") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def load_dotenv(default_path: Optional[Path] = None) -> None:
    """Load environment variables from a .env file if present."""

    if default_path is None:
        default_path = Path(__file__).resolve().parents[3] / ".env"
    env_values = _read_env_file(default_path)
    for key, value in env_values.items():
        os.environ.setdefault(key, value)


def _clean_response_text(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 2:
            text = "\n".join(lines[1:-1]).strip()
    return text


def _validate_single_sample(model, frame_txt: Path, frame_jpg: Path) -> Dict[str, Any]:
    import json as _json

    prompt = (
        "You are validating spatial relations detected in a video frame.\n\n"
        "For each relation listed in the detection report, respond with a JSON matching this schema:\n"
        "{\n  \"frame\": <frame_number>,\n  \"validations\": [\n    {\n      \"relation\": str,\n      \"subject\": str,\n      \"object\": str,\n      \"verdict\": \"CORRECT|INCORRECT|AMBIGUOUS\",\n      \"reason\": str\n    }\n  ],\n  \"missing_relations\": [str],\n  \"overall_quality\": \"HIGH|MEDIUM|LOW\",\n  \"notes\": str\n}\n"
        "Analyze carefully before responding."
    )

    report_contents = frame_txt.read_text()
    with frame_jpg.open("rb") as img_handle:
        img_data = img_handle.read()

    response = model.generate_content([prompt, {"mime_type": "image/jpeg", "data": img_data}, report_contents])
    text = _clean_response_text(response.text or "{}").strip()
    if not text:
        raise GeminiValidationError(f"Empty response for sample {frame_txt.name}")
    return _json.loads(text)


def _summarize_feedback(samples: List[Dict[str, Any]]) -> Dict[str, int]:
    counts = {"CORRECT": 0, "INCORRECT": 0, "AMBIGUOUS": 0}
    for sample in samples:
        for validation in sample.get("validations", []):
            verdict = validation.get("verdict", "").upper()
            if verdict in counts:
                counts[verdict] += 1
    return counts


def validate_directory(
    sample_dir: Path,
    output_path: Path,
    *,
    max_samples: Optional[int] = None,
    model_name: str = "gemini-2.0-flash",
    api_key: Optional[str] = None,
    sleep_seconds: float = 1.0,
) -> Dict[str, Any]:
    """Validate a directory of frame_{id}.txt/jpg pairs with Gemini."""

    if not sample_dir.exists():
        raise FileNotFoundError(f"Sample directory not found: {sample_dir}")

    load_dotenv()
    api_key = api_key or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise GeminiValidationError("GOOGLE_API_KEY is not set; cannot contact Gemini")

    model = _load_gemini_model(api_key, model_name)

    txt_files = sorted(sample_dir.glob("frame_*.txt"))
    if max_samples:
        txt_files = txt_files[:max_samples]
    if not txt_files:
        raise GeminiValidationError("No frame_*.txt files found in sample directory")

    all_feedback: List[Dict[str, Any]] = []
    for idx, txt_file in enumerate(txt_files, 1):
        jpg_file = txt_file.with_suffix(".jpg")
        if not jpg_file.exists():
            raise GeminiValidationError(f"Missing paired JPG for {txt_file}")
        result = _validate_single_sample(model, txt_file, jpg_file)
        all_feedback.append(result)
        if idx < len(txt_files):
            time.sleep(max(0.0, sleep_seconds))

    summary_counts = _summarize_feedback(all_feedback)
    payload = {
        "total_samples": len(all_feedback),
        "validated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "samples": all_feedback,
        "verdict_counts": summary_counts,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w") as handle:
        json.dump(payload, handle, indent=2)

    return payload