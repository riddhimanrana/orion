"""
Data Path Configuration
=======================

Standardized path accessors for episodes, results, and model assets.

Usage:
    from orion.config.data_paths import episodes_dir, results_dir, models_dir
    from orion.config.data_paths import load_episode_meta, save_results
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional


# ============================================================================
# Path Constants
# ============================================================================

# Project root (orion-research/)
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Data directories
EPISODES_DIR = PROJECT_ROOT / "data" / "examples" / "episodes"
RESULTS_DIR = PROJECT_ROOT / "results"
MODELS_DIR = PROJECT_ROOT / "models"

# Convenience accessors
episodes_dir = EPISODES_DIR
results_dir = RESULTS_DIR
models_dir = MODELS_DIR


# ============================================================================
# Episode Management
# ============================================================================

def get_episode_dir(episode_id: str) -> Path:
    """Get episode directory path."""
    return EPISODES_DIR / episode_id


def get_results_dir(episode_id: str) -> Path:
    """Get results directory path for an episode."""
    return RESULTS_DIR / episode_id


def load_episode_meta(episode_id: str) -> Dict[str, Any]:
    """
    Load episode metadata from meta.json.
    
    Args:
        episode_id: Episode identifier
        
    Returns:
        Dictionary containing episode metadata
        
    Raises:
        FileNotFoundError: If meta.json doesn't exist
        json.JSONDecodeError: If meta.json is invalid
    """
    meta_path = get_episode_dir(episode_id) / "meta.json"
    
    if not meta_path.exists():
        raise FileNotFoundError(
            f"Episode metadata not found: {meta_path}\n"
            f"Expected structure: data/examples/episodes/{episode_id}/meta.json"
        )
    
    with open(meta_path, 'r') as f:
        meta = json.load(f)
    
    return meta


def load_episode_gt(episode_id: str) -> Optional[Dict[str, Any]]:
    """
    Load episode ground truth from gt.json if available.
    
    Args:
        episode_id: Episode identifier
        
    Returns:
        Dictionary containing ground truth, or None if not available
    """
    gt_path = get_episode_dir(episode_id) / "gt.json"
    
    if not gt_path.exists():
        return None
    
    with open(gt_path, 'r') as f:
        gt = json.load(f)
    
    return gt


def get_episode_video_path(episode_id: str) -> Optional[Path]:
    """
    Get path to episode video file.
    
    Args:
        episode_id: Episode identifier
        
    Returns:
        Path to video file, or None if not found
    """
    episode_dir = get_episode_dir(episode_id)
    
    # Check common video filenames
    for filename in ["video.mp4", "video.mov", "recording.mp4", "recording.mov"]:
        video_path = episode_dir / filename
        if video_path.exists():
            return video_path
    
    return None


def get_episode_frames_dir(episode_id: str) -> Optional[Path]:
    """
    Get path to episode frames directory.
    
    Args:
        episode_id: Episode identifier
        
    Returns:
        Path to frames directory, or None if not found
    """
    frames_dir = get_episode_dir(episode_id) / "frames"
    
    if frames_dir.exists() and frames_dir.is_dir():
        return frames_dir
    
    return None


# ============================================================================
# Results Management
# ============================================================================

def ensure_results_dir(episode_id: str) -> Path:
    """
    Ensure results directory exists for an episode.
    
    Args:
        episode_id: Episode identifier
        
    Returns:
        Path to results directory
    """
    results_dir = get_results_dir(episode_id)
    results_dir.mkdir(parents=True, exist_ok=True)
    return results_dir


def get_results_path(episode_id: str, filename: str) -> Path:
    """
    Get path to a specific results file.
    
    Args:
        episode_id: Episode identifier
        filename: Results filename (e.g., 'tracks.jsonl', 'memory.json')
        
    Returns:
        Path to results file
    """
    return get_results_dir(episode_id) / filename


def save_results_json(episode_id: str, filename: str, data: Dict[str, Any]) -> Path:
    """
    Save results data as JSON.
    
    Args:
        episode_id: Episode identifier
        filename: Output filename
        data: Data to save
        
    Returns:
        Path to saved file
    """
    results_dir = ensure_results_dir(episode_id)
    output_path = results_dir / filename
    
    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2)
    
    return output_path


def save_results_jsonl(episode_id: str, filename: str, data: list) -> Path:
    """
    Save results data as line-delimited JSON.
    
    Args:
        episode_id: Episode identifier
        filename: Output filename (should end in .jsonl)
        data: List of objects to save (can be dicts or objects with to_dict())
        
    Returns:
        Path to saved file
    """
    results_dir = ensure_results_dir(episode_id)
    output_path = results_dir / filename
    
    with open(output_path, 'w') as f:
        for item in data:
            # Handle objects with to_dict() method (e.g., Track dataclass)
            if hasattr(item, 'to_dict'):
                item = item.to_dict()
            f.write(json.dumps(item) + '\n')
    
    return output_path


# ============================================================================
# Validation
# ============================================================================

def validate_episode_structure(episode_id: str) -> Dict[str, bool]:
    """
    Validate episode directory structure.
    
    Args:
        episode_id: Episode identifier
        
    Returns:
        Dictionary with validation results
    """
    episode_dir = get_episode_dir(episode_id)
    
    checks = {
        "episode_dir_exists": episode_dir.exists(),
        "meta_json_exists": (episode_dir / "meta.json").exists(),
        "gt_json_exists": (episode_dir / "gt.json").exists(),
        "video_exists": get_episode_video_path(episode_id) is not None,
        "frames_dir_exists": get_episode_frames_dir(episode_id) is not None,
    }
    
    return checks


def list_episodes() -> list[str]:
    """
    List all available episodes.
    
    Returns:
        List of episode IDs
    """
    if not EPISODES_DIR.exists():
        return []
    
    episodes = []
    for item in EPISODES_DIR.iterdir():
        if item.is_dir() and (item / "meta.json").exists():
            episodes.append(item.name)
    
    return sorted(episodes)


def list_results() -> list[str]:
    """
    List all episodes with results.
    
    Returns:
        List of episode IDs with results
    """
    if not RESULTS_DIR.exists():
        return []
    
    results = []
    for item in RESULTS_DIR.iterdir():
        if item.is_dir():
            results.append(item.name)
    
    return sorted(results)
