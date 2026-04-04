"""CLI utility functions for runtime, services, and system checks."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)

from ..managers import AssetManager

console = Console()


def select_backend(requested: Optional[str] = None) -> str:
    """Select the best available backend (torch or mlx)."""
    import platform
    try:
        import torch
        if platform.system() == "Darwin" and platform.processor() == "arm":
            return "mps"
        elif torch.cuda.is_available():
            return "cuda"
        return "cpu"
    except ImportError:
        return "cpu"


def prepare_runtime(requested: Optional[str]) -> Tuple[str, AssetManager]:
    """Prepare runtime with enhanced progress display."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("[cyan]Selecting runtime backend...", total=3)

        backend = select_backend(requested)
        progress.update(task, advance=1, description=f"[cyan]Selected: {backend}")

        manager = AssetManager()
        progress.update(task, advance=1, description="[yellow]Checking assets...")

        if manager.assets_ready(backend):
            progress.update(
                task, advance=1, description=f"[green]✓ Runtime '{backend}' ready", completed=3
            )
            return backend, manager

        progress.update(task, description=f"[yellow]Downloading models for '{backend}'...")
        try:
            manager.ensure_runtime_assets(backend)
            progress.update(
                task, advance=1, description="[green]✓ Models synchronized", completed=3
            )
        except Exception as exc:
            progress.stop()
            console.print(f"[red]✗ Failed to download models: {exc}[/red]")
            sys.exit(1)

    return backend, manager


def run_command(cmd: str, description: str) -> Optional[str]:
    """Run a shell command with progress display."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task(f"[cyan]{description}...", total=None)
        try:
            result = subprocess.run(
                cmd, shell=True, check=True, capture_output=True, text=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            console.print(f"[red]✗ {description} failed: {e.stderr}[/red]")
            return None
        except FileNotFoundError:
            console.print(f"[red]✗ Command not found: {cmd.split()[0]}[/red]")
            return None


def is_docker_daemon_running() -> bool:
    """Check if the Docker daemon is running."""
    console.print("[dim]Checking Docker daemon status...[/dim]")
    return run_command("docker info", "Checking Docker status") is not None


def is_container_running(container_name: str) -> bool:
    """Check if a Docker container is running."""
    output = run_command(
        f"docker ps -q -f name={container_name}",
        f"Checking for container: {container_name}",
    )
    return output is not None and output != ""


def prompt_user(question: str, default: bool = True) -> bool:
    """Prompt the user for a yes/no answer."""
    from rich.prompt import Confirm

    return Confirm.ask(question, default=default)
