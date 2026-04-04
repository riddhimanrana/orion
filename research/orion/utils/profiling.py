import time
import logging
from functools import wraps
from collections import defaultdict
import json
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

class Profiler:
    """
    Simple profiler to track execution time of different components.
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Profiler, cls).__new__(cls)
            cls._instance.timings = defaultdict(list)
            cls._instance.counts = defaultdict(int)
            cls._instance.enabled = True
        return cls._instance

    def reset(self):
        self.timings = defaultdict(list)
        self.counts = defaultdict(int)

    def start(self, name: str):
        if not self.enabled:
            return
        # We'll use a stack-based approach or just simple start/stop if we assume no overlapping same-name calls in same thread
        # For simplicity in this context, let's return a context manager
        return TimerContext(name, self)

    def add_timing(self, name: str, duration: float):
        self.timings[name].append(duration)
        self.counts[name] += 1

    def get_stats(self) -> Dict:
        stats = {}
        for name, times in self.timings.items():
            stats[name] = {
                "count": self.counts[name],
                "total_time": sum(times),
                "avg_time": sum(times) / len(times) if times else 0,
                "min_time": min(times) if times else 0,
                "max_time": max(times) if times else 0
            }
        return stats

    def save_stats(self, filepath: Path):
        stats = self.get_stats()
        with open(filepath, 'w') as f:
            json.dump(stats, f, indent=2)
        logger.info(f"Profiling stats saved to {filepath}")

class TimerContext:
    def __init__(self, name: str, profiler: Profiler):
        self.name = name
        self.profiler = profiler
        self.start_time = 0

    def __enter__(self):
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.perf_counter() - self.start_time
        self.profiler.add_timing(self.name, duration)

def profile(name: Optional[str] = None):
    """Decorator to profile a function."""
    def decorator(func):
        metric_name = name or func.__name__
        @wraps(func)
        def wrapper(*args, **kwargs):
            profiler = Profiler()
            with profiler.start(metric_name):
                return func(*args, **kwargs)
        return wrapper
    return decorator
