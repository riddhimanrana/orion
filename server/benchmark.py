#!/usr/bin/env python3
"""CLI utility for running benchmarks."""
import asyncio
import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

import pytest
from rich.console import Console
from rich.table import Table

console = Console()

def run_benchmarks(args: argparse.Namespace) -> Dict[str, Any]:
    """
    Run benchmarks and return results.
    
    Args:
        args: Command line arguments
        
    Returns:
        Dictionary of benchmark results
    """
    pytest_args = [
        "-v",
        "--benchmark",
        "tests/benchmarks"
    ]
    
    if args.test:
        pytest_args.extend(["-k", args.test])
    
    if args.save:
        # Create benchmark results directory
        results_dir = Path("benchmark_results")
        results_dir.mkdir(exist_ok=True)
        
    # Run benchmarks
    console.print("[yellow]Running benchmarks...[/yellow]")
    pytest.main(pytest_args)
    
    return {}  # TODO: Collect and return actual results

def save_results(results: Dict[str, Any], args: argparse.Namespace) -> None:
    """
    Save benchmark results to file.
    
    Args:
        results: Benchmark results
        args: Command line arguments
    """
    results_dir = Path("benchmark_results")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Add metadata
    results["metadata"] = {
        "timestamp": timestamp,
        "args": vars(args),
        "git_commit": "TODO: Add git commit hash"
    }
    
    # Save as JSON
    output_file = results_dir / f"benchmark_{timestamp}.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
        
    console.print(f"[green]Results saved to: {output_file}[/green]")

def compare_results(file1: str, file2: str) -> None:
    """
    Compare two benchmark result files.
    
    Args:
        file1: First result file
        file2: Second result file
    """
    # Load results
    with open(file1) as f:
        results1 = json.load(f)
    with open(file2) as f:
        results2 = json.load(f)
        
    # Create comparison table
    table = Table(title="Benchmark Comparison")
    table.add_column("Benchmark", justify="left", style="cyan")
    table.add_column(Path(file1).stem, justify="right")
    table.add_column(Path(file2).stem, justify="right")
    table.add_column("Diff %", justify="right")
    
    # TODO: Add actual comparison logic
    console.print(table)

def list_results() -> None:
    """List available benchmark result files."""
    results_dir = Path("benchmark_results")
    if not results_dir.exists():
        console.print("[yellow]No benchmark results found[/yellow]")
        return
        
    # Create results table
    table = Table(title="Benchmark Results")
    table.add_column("Date", justify="left")
    table.add_column("File", justify="left")
    table.add_column("Tests", justify="right")
    
    for result_file in sorted(results_dir.glob("benchmark_*.json")):
        with open(result_file) as f:
            data = json.load(f)
            table.add_row(
                data["metadata"]["timestamp"],
                result_file.name,
                str(len(data.get("results", [])))
            )
            
    console.print(table)

def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run and manage benchmarks"
    )
    
    # Add arguments
    parser.add_argument(
        "--test",
        help="Run specific benchmark test(s)"
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save benchmark results"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available benchmark results"
    )
    parser.add_argument(
        "--compare",
        nargs=2,
        metavar=("FILE1", "FILE2"),
        help="Compare two benchmark result files"
    )
    
    args = parser.parse_args()
    
    if args.list:
        list_results()
        return
        
    if args.compare:
        compare_results(args.compare[0], args.compare[1])
        return
        
    # Run benchmarks
    results = run_benchmarks(args)
    
    if args.save:
        save_results(results, args)

if __name__ == "__main__":
    main()