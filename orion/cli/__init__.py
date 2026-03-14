"""Command-line interface package for Orion.

Keep this module import side-effect free so submodules can be imported without
triggering CLI parsing.
"""


def main() -> int:
    # Lazy import so importing `orion.cli` does not execute parser setup.
    from .main import main as _main

    return _main()


__all__ = ["main"]
