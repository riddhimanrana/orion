"""
Auto-configuration and validation for Orion
============================================

Handles automatic detection, setup, and validation of:
- Neo4j database connections
- Ollama LLM server connections
- Configuration file creation
- Model asset validation
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import httpx
from rich.console import Console
from rich.table import Table
from rich import box

logger = logging.getLogger(__name__)
console = Console()


class ServiceDetector:
    """Detect and validate external services (Neo4j, Ollama, etc.)"""

    def __init__(self):
        # Try to load settings for credentials
        try:
            from orion.settings import OrionSettings
            settings = OrionSettings.load()
            self.memgraph_host = settings.memgraph_host
            self.memgraph_port = settings.memgraph_port
            self.memgraph_user = settings.memgraph_user
            try:
                self.memgraph_password = settings.get_memgraph_password()
            except Exception:
                self.memgraph_password = ""
        except Exception:
            # Fallback to environment variables if settings not available
            self.memgraph_host = os.getenv("ORION_MEMGRAPH_HOST", "127.0.0.1")
            self.memgraph_port = int(os.getenv("ORION_MEMGRAPH_PORT", "7687"))
            self.memgraph_user = os.getenv("ORION_MEMGRAPH_USER", "memgraph")
            self.memgraph_password = os.getenv("ORION_MEMGRAPH_PASSWORD", "")
        
        self.ollama_url = os.getenv("ORION_OLLAMA_BASE_URL", "http://localhost:11434")
        self.timeout = 5

    def detect_memgraph(self) -> Tuple[bool, str]:
        """
        Detect Memgraph availability
        
        Returns:
            (is_available, status_message)
        """
        try:
            from neo4j import GraphDatabase
            
            uri = f"bolt://{self.memgraph_host}:{self.memgraph_port}"
            driver = GraphDatabase.driver(
                uri,
                auth=(self.memgraph_user, self.memgraph_password),
                connection_timeout=self.timeout
            )
            driver.verify_connectivity()
            driver.close()
            return True, f"Connected at {uri}"
        except Exception as e:
            return False, f"Failed: {str(e)}"

    def detect_ollama(self) -> Tuple[bool, str, Optional[str]]:
        """
        Detect Ollama availability and running models
        
        Returns:
            (is_available, status_message, model_name)
        """
        try:
            response = httpx.get(f"{self.ollama_url}/api/tags", timeout=self.timeout)
            if response.status_code == 200:
                data = response.json()
                models = data.get("models", [])
                if models:
                    model_name = models[0]["name"]
                    return True, f"Available with {len(models)} model(s)", model_name
                else:
                    return True, "Available but no models installed", None
            else:
                return False, f"HTTP {response.status_code}", None
        except httpx.TimeoutException:
            return False, "Connection timeout", None
        except Exception as e:
            return False, f"Failed: {str(e)}", None

    def detect_docker(self) -> Tuple[bool, str]:
        """
        Detect Docker availability.
        
        On macOS, also checks for Docker Desktop installation if CLI is not in PATH.
        
        Returns:
            (is_available, status_message)
        """
        import platform
        
        # First, try to run docker --version (standard check)
        try:
            subprocess.run(
                ["docker", "--version"],
                capture_output=True,
                timeout=self.timeout,
                check=True
            )
            return True, "Docker CLI available"
        except FileNotFoundError:
            # Docker CLI not found in PATH, check if it's installed
            pass
        except Exception as e:
            return False, f"Docker error: {str(e)}"
        
        # On macOS, check for Docker Desktop installation
        if platform.system() == "Darwin":
            docker_app_path = Path("/Applications/Docker.app")
            if docker_app_path.exists():
                # Docker Desktop is installed but CLI not in PATH
                return False, (
                    "Docker Desktop installed but CLI not in PATH. "
                    "Run: eval \"$(docker-machine env default)\" or restart your terminal."
                )
        
        return False, "Docker CLI not found in PATH"


class AutoConfiguration:
    """Automatically configure Orion and validate setup"""

    def __init__(self):
        self.detector = ServiceDetector()
        self.settings_path = Path.home() / ".orion" / "config.json"
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)

    def detect_all_services(self) -> Dict[str, Any]:
        """Detect all external services"""
        with console.status("[dim]Detecting services...[/dim]", spinner="dots"):
            results = {
                "memgraph": self.detector.detect_memgraph(),
                "ollama": self.detector.detect_ollama(),
                "docker": self.detector.detect_docker(),
            }
        return results

    def suggest_setup_docker(self) -> Dict[str, str]:
        """
        Suggest Docker commands to start services
        
        Returns:
            Dictionary with docker commands for each service
        """
        return {
            "neo4j": (
                "docker run --name orion-neo4j -d "
                "-p 7687:7687 -p 7474:7474 "
                "-e NEO4J_AUTH=neo4j/orion_secure_password "
                "neo4j:latest"
            ),
            "ollama": (
                "docker run --name orion-ollama -d "
                "-p 11434:11434 "
                "ollama/ollama"
            ),
        }

    def create_env_file(self, neo4j_password: str = "orion_secure_password") -> bool:
        """Create .env file with default credentials"""
        env_path = Path.cwd() / ".env"
        
        env_content = f"""# Orion Configuration
# Generated automatically by 'orion setup'

# Neo4j Configuration
ORION_NEO4J_URI=neo4j://localhost:7687
ORION_NEO4J_USER=neo4j
ORION_NEO4J_PASSWORD={neo4j_password}

# Ollama Configuration
ORION_OLLAMA_BASE_URL=http://localhost:11434

# Optional: Custom model specifications
# ORION_YOLO_MODEL=yolo11x
# ORION_EMBEDDING_DIM=512
"""
        
        try:
            if not env_path.exists():
                with open(env_path, "w") as f:
                    f.write(env_content)
                console.print(f"[green]✓[/green] Created {env_path}")
                return True
            else:
                console.print(f"[yellow]⚠[/yellow] {env_path} already exists (not overwriting)")
                return False
        except Exception as e:
            console.print(f"[red]✗[/red] Failed to create .env: {e}")
            return False

    def validate_setup(self) -> bool:
        """
        Comprehensive setup validation
        
        Returns:
            True if all critical services are available
        """
        results = self.detect_all_services()
        
        table = Table(title="Service Status", box=box.ROUNDED)
        table.add_column("Service", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Details", style="yellow")
        
        neo4j_ok, neo4j_msg = results["neo4j"]
        table.add_row(
            "Neo4j",
            "[green]✓[/green]" if neo4j_ok else "[red]✗[/red]",
            neo4j_msg
        )
        
        ollama_ok, ollama_msg, ollama_model = results["ollama"]
        table.add_row(
            "Ollama",
            "[green]✓[/green]" if ollama_ok else "[red]✗[/red]",
            ollama_msg
        )
        
        docker_ok, docker_msg = results["docker"]
        table.add_row(
            "Docker",
            "[green]✓[/green]" if docker_ok else "[yellow]⚠[/yellow]",
            docker_msg
        )
        
        console.print(table)
        
        return neo4j_ok and ollama_ok

    def auto_setup_with_docker(self) -> bool:
        """
        Automatically start Neo4j and Ollama with Docker
        
        Returns:
            True if setup successful
        """
        docker_ok, _ = self.detector.detect_docker()
        if not docker_ok:
            console.print("[red]Docker not available. Please install Docker first.[/red]")
            return False
        
        console.print("\n[bold cyan]Starting services with Docker...[/bold cyan]\n")
        
        commands = self.suggest_setup_docker()
        
        # Start Neo4j
        console.print("[bold]Starting Neo4j...[/bold]")
        try:
            subprocess.run(
                commands["neo4j"],
                shell=True,
                check=False,
                capture_output=True
            )
            console.print("[green]✓ Neo4j container started[/green]")
            console.print("[dim]Waiting for Neo4j to be ready...[/dim]")
            time.sleep(5)
        except Exception as e:
            console.print(f"[red]✗ Failed to start Neo4j: {e}[/red]")
            return False
        
        # Start Ollama
        console.print("\n[bold]Starting Ollama...[/bold]")
        try:
            subprocess.run(
                commands["ollama"],
                shell=True,
                check=False,
                capture_output=True
            )
            console.print("[green]✓ Ollama container started[/green]")
            console.print("[dim]Waiting for Ollama to be ready...[/dim]")
            time.sleep(3)
        except Exception as e:
            console.print(f"[red]✗ Failed to start Ollama: {e}[/red]")
            return False
        
        # Verify connectivity
        console.print("\n[bold]Verifying connectivity...[/bold]")
        neo4j_ok, neo4j_msg = self.detector.detect_neo4j()
        ollama_ok, ollama_msg, _ = self.detector.detect_ollama()
        
        if neo4j_ok:
            console.print(f"[green]✓ Neo4j: {neo4j_msg}[/green]")
        else:
            console.print(f"[red]✗ Neo4j: {neo4j_msg}[/red]")
        
        if ollama_ok:
            console.print(f"[green]✓ Ollama: {ollama_msg}[/green]")
        else:
            console.print(f"[red]✗ Ollama: {ollama_msg}[/red]")
        
        return neo4j_ok and ollama_ok


def setup_command(args) -> int:
    """
    Execute 'orion setup' command
    
    Auto-configures and validates Orion installation
    """
    console.print("\n[bold cyan]🔧 Orion Auto-Configuration Setup[/bold cyan]\n")
    
    config = AutoConfiguration()
    
    # Step 1: Detect existing services
    console.print("[bold]Step 1: Detecting existing services...[/bold]\n")
    results = config.detect_all_services()
    
    neo4j_ok, neo4j_msg = results["neo4j"]
    ollama_ok, ollama_msg, _ = results["ollama"]
    docker_ok, docker_msg = results["docker"]
    
    # Show current status
    table = Table(title="Current Service Status", box=box.ROUNDED)
    table.add_column("Service", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Details", style="yellow")
    
    table.add_row(
        "Neo4j",
        "[green]✓ Running[/green]" if neo4j_ok else "[red]✗ Not available[/red]",
        neo4j_msg
    )
    table.add_row(
        "Ollama",
        "[green]✓ Running[/green]" if ollama_ok else "[red]✗ Not available[/red]",
        ollama_msg
    )
    table.add_row(
        "Docker",
        "[green]✓ Available[/green]" if docker_ok else "[yellow]⚠ Not available[/yellow]",
        docker_msg
    )
    
    console.print(table)
    
    # Step 2: Create .env file
    console.print("\n[bold]Step 2: Creating configuration file...[/bold]\n")
    config.create_env_file()
    
    # Step 3: Auto-start services if needed and Docker available
    if not (neo4j_ok and ollama_ok):
        if docker_ok and not args.no_docker:
            console.print("\n[bold]Step 3: Starting services with Docker...[/bold]\n")
            if config.auto_setup_with_docker():
                console.print("\n[green]✓ All services started successfully![/green]")
            else:
                console.print("\n[yellow]⚠ Some services failed to start[/yellow]")
                return 1
        else:
            console.print("\n[bold yellow]Step 3: Manual service startup required[/bold yellow]\n")
            commands = config.suggest_setup_docker()
            
            console.print("[bold]To start Neo4j:[/bold]")
            console.print(f"[dim]{commands['neo4j']}[/dim]\n")
            
            console.print("[bold]To start Ollama:[/bold]")
            console.print(f"[dim]{commands['ollama']}[/dim]\n")
            
            console.print("After starting services, run: [cyan]orion setup[/cyan]")
            return 1
    else:
        console.print("\n[bold]Step 3: Services already running[/bold]\n")
    
    # Step 4: Final validation
    console.print("[bold]Step 4: Final validation...[/bold]\n")
    if config.validate_setup():
        console.print("\n[bold green]✓ Setup complete! Orion is ready to use.[/bold green]")
        console.print("\nNext steps:")
        console.print("  1. Run: [cyan]orion status[/cyan] (check everything)")
        console.print("  2. Analyze video: [cyan]orion analyze video.mp4[/cyan]")
        console.print("  3. Try Q&A mode: [cyan]orion qa[/cyan]")
        return 0
    else:
        console.print("\n[bold red]✗ Setup incomplete. Please check the errors above.[/bold red]")
        return 1


def status_command(args) -> int:
    """
    Execute 'orion status' command
    
    Comprehensive system status check
    """
    console.print("\n[bold cyan]Orion System Status[/bold cyan]\n")
    
    config = AutoConfiguration()
    results = config.detect_all_services()
    
    neo4j_ok, neo4j_msg = results["neo4j"]
    ollama_ok, ollama_msg, ollama_model = results["ollama"]
    docker_ok, docker_msg = results["docker"]
    
    # Services status table
    table = Table(title="Service Status", box=box.ROUNDED)
    table.add_column("Service", style="cyan", no_wrap=True)
    table.add_column("Status", style="green", justify="center")
    table.add_column("Details", style="yellow")
    
    table.add_row(
        "Neo4j",
        "[green]✓[/green]" if neo4j_ok else "[red]✗[/red]",
        neo4j_msg
    )
    table.add_row(
        "Ollama",
        "[green]✓[/green]" if ollama_ok else "[red]✗[/red]",
        ollama_msg
    )
    if ollama_model:
        table.add_row(
            "  Default Model",
            "[green]✓[/green]",
            ollama_model
        )
    table.add_row(
        "Docker",
        "[green]✓[/green]" if docker_ok else "[yellow]⚠[/yellow]",
        docker_msg
    )
    
    console.print(table)
    
    # Configuration table
    console.print("\n[bold cyan]Configuration[/bold cyan]")
    config_table = Table(title="Active Configuration", box=box.ROUNDED)
    config_table.add_column("Setting", style="cyan")
    config_table.add_column("Value", style="green")
    
    config_table.add_row("Neo4j URI", config.detector.neo4j_uri)
    config_table.add_row("Neo4j User", config.detector.neo4j_user)
    config_table.add_row("Ollama URL", config.detector.ollama_url)
    
    # Check for config.json
    from orion.settings import OrionSettings
    config_json_path = OrionSettings.config_path()
    config_exists = config_json_path.exists()
    config_table.add_row(
        "Config File", 
        f"[green]✓ {config_json_path}[/green]" if config_exists else "[yellow]⚠ Missing[/yellow]"
    )
    
    console.print(config_table)
    
    # Overall health
    console.print()
    if neo4j_ok and ollama_ok:
        console.print("[bold green]✓ System is healthy and ready to use[/bold green]")
        return 0
    else:
        missing = []
        if not neo4j_ok:
            missing.append("Neo4j")
        if not ollama_ok:
            missing.append("Ollama")
        
        console.print(f"[bold yellow]⚠ Missing services: {', '.join(missing)}[/bold yellow]")
        console.print("\nRun: [cyan]orion setup[/cyan] to auto-configure")
        return 1
