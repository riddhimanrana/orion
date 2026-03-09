#!/usr/bin/env python3
"""
Batch evaluation script for SGA.
Runs eval_sga_gdino_single.py on multiple videos and aggregates results.
"""

import os
import sys
import pickle
import random
import subprocess
import argparse
import numpy as np
from pathlib import Path

def get_video_ids(anno_path):
    """Extract all video IDs from the annotation file."""
    if not Path(anno_path).exists():
        print(f"Annotation file not found: {anno_path}")
        return []
        
    with open(anno_path, 'rb') as f:
        ag = pickle.load(f)
    
    video_ids = set()
    for k in ag.keys():
        # Key format: "001YG.mp4/000005.png"
        if '.mp4' in k:
            vid = k.split('.mp4')[0]
            video_ids.add(vid)
    return sorted(list(video_ids))

def parse_results(output_str):
    """Parse R@K metrics from the script output."""
    metrics = {}
    for line in output_str.splitlines():
        line = line.strip()
        if line.startswith("R@10:"):
            metrics['R@10'] = float(line.split(':')[1].strip().replace('%', '')) / 100.0
        elif line.startswith("R@20:"):
            metrics['R@20'] = float(line.split(':')[1].strip().replace('%', '')) / 100.0
        elif line.startswith("R@50:"):
            metrics['R@50'] = float(line.split(':')[1].strip().replace('%', '')) / 100.0
    
    if len(metrics) == 3:
        return metrics
    return None

def main():
    parser = argparse.ArgumentParser(description="Run SGA evaluation on multiple videos")
    parser.add_argument('--count', type=int, default=1000, help='Number of videos to evaluate')
    parser.add_argument('--seed', type=int, default=42, help='Random seed')
    parser.add_argument('--script', type=str, default='scripts/eval_sga_gdino_single.py', help='Path to eval script')
    parser.add_argument('--verbose', action='store_true', help='Print full output for each video')
    args = parser.parse_args()

    random.seed(args.seed)

    # Locate annotations
    possible_anno_paths = [
        'datasets/ActionGenome/annotations/action_genome_v1.0/object_bbox_and_relationship.pkl',
        'datasets/ActionGenome/object_bbox_and_relationship.pkl',
        '../datasets/ActionGenome/object_bbox_and_relationship.pkl',
        '../datasets/ActionGenome/annotations/action_genome_v1.0/object_bbox_and_relationship.pkl'
    ]
    anno_path = next((p for p in possible_anno_paths if Path(p).exists()), None)
    
    if not anno_path:
        print("Error: Could not find Action Genome annotations.")
        sys.exit(1)

    print(f"Loading video list from {anno_path}...")
    all_videos = get_video_ids(anno_path)
    print(f"Found {len(all_videos)} total videos.")

    if not all_videos:
        print("No videos found in annotations.")
        sys.exit(1)

    # Sample videos
    count = min(args.count, len(all_videos))
    videos_to_run = random.sample(all_videos, count)
    print(f"Selected {len(videos_to_run)} videos for evaluation.")

    # Run evaluation
    results = {'R@10': [], 'R@20': [], 'R@50': []}
    
    print("\nStarting batch evaluation...")
    print("-" * 60)

    for i, vid in enumerate(videos_to_run):
        print(f"[{i+1}/{count}] Processing {vid}...", end='', flush=True)
        
        cmd = [sys.executable, args.script, vid]
        
        # Ensure PYTHONPATH includes current directory
        env = os.environ.copy()
        if 'PYTHONPATH' not in env:
            env['PYTHONPATH'] = os.getcwd()
        else:
            env['PYTHONPATH'] = os.getcwd() + os.pathsep + env['PYTHONPATH']

        try:
            # Run the script
            process = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                env=env
            )
            
            if args.verbose:
                print("\n" + process.stdout)
                print(process.stderr)
            
            if process.returncode != 0:
                print(f" Failed (Exit {process.returncode})")
                # print(process.stderr) # Uncomment for debugging
                if not args.verbose:
                    print(process.stderr)
                continue

            # Parse output
            metrics = parse_results(process.stdout)
            
            if metrics:
                for k, v in metrics.items():
                    results[k].append(v)
                print(f" Done. R@10={metrics['R@10']:.2%} R@20={metrics['R@20']:.2%} R@50={metrics['R@50']:.2%}")
            else:
                print(" No valid results (skipped).")
                
        except Exception as e:
            print(f" Error: {e}")

    # Aggregate results
    print("-" * 60)
    print("FINAL AGGREGATED RESULTS")
    print("-" * 60)
    
    if results['R@20']:
        n = len(results['R@20'])
        print(f"Successfully evaluated: {n}/{count} videos")
        
        avg_r10 = np.mean(results['R@10'])
        avg_r20 = np.mean(results['R@20'])
        avg_r50 = np.mean(results['R@50'])
        
        print(f"Average R@10: {avg_r10:.2%}")
        print(f"Average R@20: {avg_r20:.2%}")
        print(f"Average R@50: {avg_r50:.2%}")
        
        # Save to file
        with open('sga_batch_results.txt', 'w') as f:
            f.write(f"Videos Evaluated: {n}\n")
            f.write(f"Average R@10: {avg_r10:.2%}\n")
            f.write(f"Average R@20: {avg_r20:.2%}\n")
            f.write(f"Average R@50: {avg_r50:.2%}\n")
        print("\nResults saved to sga_batch_results.txt")
    else:
        print("No valid results collected.")

if __name__ == "__main__":
    main()