from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


def load_json(path: Path) -> Optional[dict[str, Any]]:
    """Load a JSON file."""
    if not path.exists():
        return None
    with open(path, "r") as f:
        return json.load(f)


def save_json(data: dict[str, Any], path: Path) -> None:
    """Save data to a JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    """Load a JSONL file."""
    if not path.exists():
        return []
    with open(path, "r") as f:
        return [json.loads(line) for line in f if line.strip()]


def save_jsonl(data: list[dict[str, Any]], path: Path) -> None:
    """Save data to a JSONL file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        for item in data:
            f.write(json.dumps(item) + "\n")

def get_perception_run_dims(results_dir: Path) -> Optional[tuple[int, int]]:
    """Reads the processing dimensions from the perception run output."""
    pipeline_output_path = results_dir / "pipeline_output.json"
    if not pipeline_output_path.exists():
        # Fallback for older runs that might have the config in perception_run.json
        pipeline_output_path = results_dir / "perception_run.json"
        if not pipeline_output_path.exists():
            return None
    
    data = load_json(pipeline_output_path)
    if not data:
        return None

    # The config can be at the root level or under a "config" key
    config_data = data.get("config", data)
        
    camera_config = config_data.get("camera", {})
    width = camera_config.get("width")
    height = camera_config.get("height")
    
    if width and height:
        return int(width), int(height)
            
    return None
