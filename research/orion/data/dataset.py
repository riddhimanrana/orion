from abc import ABC, abstractmethod
from typing import Iterator, Dict, Any, List
from pathlib import Path
import json

class Dataset(ABC):
    """Base class for video datasets."""
    
    @abstractmethod
    def __len__(self) -> int:
        pass
    
    @abstractmethod
    def __getitem__(self, idx: int) -> Dict[str, Any]:
        """Returns a dict with 'video_path', 'video_id', and optional 'ground_truth'."""
        pass
    
    @abstractmethod
    def get_video_paths(self) -> List[Path]:
        pass

class JsonDataset(Dataset):
    """
    Generic dataset where video metadata is stored in a JSON file.
    Expected format:
    [
        {"video_id": "vid1", "path": "path/to/vid1.mp4", ...},
        ...
    ]
    """
    def __init__(self, json_path: str, data_root: str):
        self.json_path = Path(json_path)
        self.data_root = Path(data_root)
        
        with open(self.json_path, 'r') as f:
            self.data = json.load(f)
            
    def __len__(self) -> int:
        return len(self.data)
    
    def __getitem__(self, idx: int) -> Dict[str, Any]:
        item = self.data[idx]
        video_path = self.data_root / item["path"]
        return {
            "video_id": item.get("video_id", video_path.stem),
            "video_path": str(video_path),
            "ground_truth": item.get("ground_truth")
        }

    def get_video_paths(self) -> List[Path]:
        return [self.data_root / item["path"] for item in self.data]

class ActionGenomeDataset(Dataset):
    """
    Placeholder for Action Genome dataset loader.
    """
    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir)
        # TODO: Implement specific logic for Action Genome structure
        self.videos = list(self.root_dir.glob("*.mp4"))
        
    def __len__(self) -> int:
        return len(self.videos)
        
    def __getitem__(self, idx: int) -> Dict[str, Any]:
        video_path = self.videos[idx]
        return {
            "video_id": video_path.stem,
            "video_path": str(video_path),
            "ground_truth": None # Load annotations if available
        }
        
    def get_video_paths(self) -> List[Path]:
        return self.videos
