"""Orion research toolkit package."""

import os
import warnings

# Suppress fork-related warnings from HuggingFace tokenizers.
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

# Suppress sklearn FutureWarnings about force_all_finite (from HDBSCAN dependency)
warnings.filterwarnings("ignore", message=".*force_all_finite.*", category=FutureWarning)

# Suppress Google API Python version warning (we're aware and will upgrade later)
warnings.filterwarnings("ignore", message=".*Python version.*stop supporting.*", category=FutureWarning)

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("orion-research")
except PackageNotFoundError:  # pragma: no cover
    __version__ = "0.0.0"

# IMPORTANT: keep package import lightweight.
# Avoid importing heavy dependencies (torch, large model wrappers) at import time.

__all__ = [
    "__version__",
    "PerceptionConfig",
    "ObjectClass",
    "BoundingBox",
    "Observation",
    "PerceptionEntity",
    "PerceptionResult",
    "PerceptionEngine",
]


def __getattr__(name: str):
    if name in {
        "PerceptionConfig",
        "ObjectClass",
        "BoundingBox",
        "Observation",
        "PerceptionEntity",
        "PerceptionResult",
    }:
        from orion import perception as _perception

        return getattr(_perception, name)

    if name == "PerceptionEngine":
        from orion.perception.engine import PerceptionEngine as _PerceptionEngine

        return _PerceptionEngine

    raise AttributeError(f"module 'orion' has no attribute {name!r}")


def __dir__():
    return sorted(list(globals().keys()) + __all__)