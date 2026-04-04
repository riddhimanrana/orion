#!/usr/bin/env python3
"""
CLI Diagnostics for Super Accurate Mode
========================================

Detailed command-line output showing:
- Frame-by-frame reasoning
- Detection confidence analysis
- Depth estimation quality
- CIS score calculations
- Spatial relationship reasoning
- Tracking decisions
- Quality metrics

Author: Orion Research
Date: November 10, 2025
"""

import numpy as np
from typing import Dict, List, Optional
from dataclasses import dataclass
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box


@dataclass
class DiagnosticInfo:
    """Diagnostic information for a frame"""
    frame_idx: int
    detections: List[Dict]
    depth_stats: Dict
    motion: Optional[str]
    scene_graph: List[Dict]
    timing: Dict
    cis_scores: Optional[Dict] = None
    reasoning: Optional[str] = None


class CLIDiagnostics:
    """
    Comprehensive CLI diagnostics for Super Accurate Mode
    
    Provides detailed frame-by-frame analysis:
    - Detection confidence and reasoning
    - Depth map quality assessment
    - CIS score calculations and explanations
    - Spatial relationship logic
    - Tracking association decisions
    """
    
    def __init__(self, verbose: bool = True, show_every_n: int = 5):
        """
        Initialize CLI diagnostics
        
        Args:
            verbose: Show detailed frame-by-frame output
            show_every_n: Show detailed diagnostics every N frames
        """
        self.console = Console()
        self.verbose = verbose
        self.show_every_n = show_every_n
        
        self.frame_count = 0
        self.total_detections = 0
        self.quality_metrics = {
            'high_conf_detections': 0,  # > 0.7
            'medium_conf_detections': 0,  # 0.5 - 0.7
            'low_conf_detections': 0,  # < 0.5
            'depth_valid_pixels': 0,
            'scene_graphs_generated': 0
        }
    
    def log_frame_start(self, frame_idx: int, is_keyframe: bool = True):
        """Log frame processing start"""
        self.frame_count += 1
        
        if self.verbose and (frame_idx % self.show_every_n == 0):
            marker = "🔑" if is_keyframe else "⚡"
            self.console.print(f"\n{marker} [bold cyan]Frame {frame_idx}[/bold cyan] "
                              f"{'(KEYFRAME - Full Pipeline)' if is_keyframe else '(Tracking Only)'}")
    
    def log_detection_analysis(self, detections: List[Dict], frame_idx: int):
        """Analyze and log detection results"""
        if not detections:
            if self.verbose and (frame_idx % self.show_every_n == 0):
                self.console.print("  [yellow]⚠️  No detections in this frame[/yellow]")
            return
        
        self.total_detections += len(detections)
        
        # Count by confidence
        high_conf = sum(1 for d in detections if d['score'] > 0.7)
        medium_conf = sum(1 for d in detections if 0.5 <= d['score'] <= 0.7)
        low_conf = sum(1 for d in detections if d['score'] < 0.5)
        
        self.quality_metrics['high_conf_detections'] += high_conf
        self.quality_metrics['medium_conf_detections'] += medium_conf
        self.quality_metrics['low_conf_detections'] += low_conf
        
        if self.verbose and (frame_idx % self.show_every_n == 0):
            self.console.print(f"  [green]✓[/green] Detected {len(detections)} objects: "
                              f"{high_conf} high conf, {medium_conf} med, {low_conf} low")
            
            # Show top 3 detections
            top_dets = sorted(detections, key=lambda x: x['score'], reverse=True)[:3]
            for i, det in enumerate(top_dets, 1):
                class_name = det.get('rich_description', det['class'])
                score = det['score']
                depth = det.get('depth', 0.0)
                bbox = det['bbox']
                area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
                
                self.console.print(f"    {i}. [bold]{class_name}[/bold] "
                                 f"conf={score:.3f}, depth={depth:.2f}m, "
                                 f"area={area:.0f}px²")
    
    def log_depth_analysis(self, depth_map: np.ndarray, detections: List[Dict], frame_idx: int):
        """Analyze depth map quality"""
        # Compute depth statistics
        valid_mask = (depth_map > 0.1) & (depth_map < 10.0)
        valid_ratio = np.sum(valid_mask) / depth_map.size
        
        self.quality_metrics['depth_valid_pixels'] += int(np.sum(valid_mask))
        
        if valid_ratio > 0:
            valid_depths = depth_map[valid_mask]
            depth_stats = {
                'mean': float(np.mean(valid_depths)),
                'std': float(np.std(valid_depths)),
                'min': float(np.min(valid_depths)),
                'max': float(np.max(valid_depths)),
                'valid_ratio': float(valid_ratio)
            }
        else:
            depth_stats = {
                'mean': 0.0, 'std': 0.0, 'min': 0.0, 'max': 0.0, 'valid_ratio': 0.0
            }
        
        if self.verbose and (frame_idx % self.show_every_n == 0):
            quality_label = "Excellent" if valid_ratio > 0.9 else "Good" if valid_ratio > 0.7 else "Fair"
            color = "green" if valid_ratio > 0.9 else "yellow" if valid_ratio > 0.7 else "red"
            
            self.console.print(f"  [bold]Depth Map[/bold]: [{color}]{quality_label}[/{color}] "
                              f"({valid_ratio*100:.1f}% valid)")
            self.console.print(f"    Range: {depth_stats['min']:.2f}m - {depth_stats['max']:.2f}m, "
                              f"Mean: {depth_stats['mean']:.2f}m ± {depth_stats['std']:.2f}m")
            
            # Check depth consistency with detections
            if detections:
                det_depths = [d.get('depth', 0.0) for d in detections if d.get('depth', 0.0) > 0]
                if det_depths:
                    self.console.print(f"    Detection depths: {min(det_depths):.2f}m - {max(det_depths):.2f}m")
        
        return depth_stats
    
    def log_scene_graph_reasoning(self, scene_graph: List[Dict], detections: List[Dict], frame_idx: int):
        """Explain scene graph generation reasoning"""
        if not scene_graph:
            if self.verbose and (frame_idx % self.show_every_n == 0) and len(detections) > 1:
                self.console.print("  [yellow]Scene Graph: No spatial relationships detected[/yellow]")
            return
        
        self.quality_metrics['scene_graphs_generated'] += 1
        
        if self.verbose and (frame_idx % self.show_every_n == 0):
            self.console.print(f"  [bold]Scene Graph[/bold]: {len(scene_graph)} relationships")
            
            for rel in scene_graph[:3]:  # Show top 3
                subj_id = rel['subject']
                obj_id = rel['object']
                pred = rel['predicate']
                conf = rel['confidence']
                
                if subj_id < len(detections) and obj_id < len(detections):
                    subj_name = detections[subj_id].get('rich_description', detections[subj_id]['class'])
                    obj_name = detections[obj_id].get('rich_description', detections[obj_id]['class'])
                    
                    self.console.print(f"    • {subj_name} [cyan]{pred}[/cyan] {obj_name} ({conf:.2f})")
                    
                    # Explain reasoning
                    self._explain_spatial_relationship(
                        detections[subj_id], detections[obj_id], pred, conf
                    )
    
    def _explain_spatial_relationship(self, subj: Dict, obj: Dict, pred: str, conf: float):
        """Explain why a spatial relationship was inferred"""
        subj_bbox = subj['bbox']
        obj_bbox = obj['bbox']
        
        subj_depth = subj.get('depth', 0.0)
        obj_depth = obj.get('depth', 0.0)
        
        # Calculate geometric features
        subj_cx = (subj_bbox[0] + subj_bbox[2]) / 2
        obj_cx = (obj_bbox[0] + obj_bbox[2]) / 2
        
        subj_cy = (subj_bbox[1] + subj_bbox[3]) / 2
        obj_cy = (obj_bbox[1] + obj_bbox[3]) / 2
        
        horiz_dist = abs(subj_cx - obj_cx)
        vert_dist = abs(subj_cy - obj_cy)
        depth_diff = abs(subj_depth - obj_depth)
        
        reasoning = []
        
        if pred == "next_to":
            reasoning.append(f"horizontal dist={horiz_dist:.0f}px")
        elif pred == "above" or pred == "below":
            reasoning.append(f"vertical dist={vert_dist:.0f}px")
        elif pred == "in_front_of" or pred == "behind":
            reasoning.append(f"depth diff={depth_diff:.2f}m")
        
        if reasoning:
            self.console.print(f"      → Why: {', '.join(reasoning)}")
    
    def log_cis_analysis(self, cis_scores: Dict[int, float], detections: List[Dict], frame_idx: int):
        """Explain CIS (Causal Influence Score) calculations"""
        if not cis_scores or not self.verbose:
            return
        
        if frame_idx % self.show_every_n == 0:
            self.console.print(f"  [bold magenta]CIS Scores[/bold magenta] (Causal Influence):")
            
            # Sort by CIS score
            sorted_scores = sorted(cis_scores.items(), key=lambda x: x[1], reverse=True)
            
            for obj_id, score in sorted_scores[:3]:  # Top 3
                if obj_id < len(detections):
                    det = detections[obj_id]
                    class_name = det.get('rich_description', det['class'])
                    
                    # Explain what contributes to CIS
                    factors = self._explain_cis_factors(det, score)
                    
                    self.console.print(f"    • {class_name}: [bold]{score:.3f}[/bold]")
                    for factor in factors:
                        self.console.print(f"      → {factor}")
    
    def _explain_cis_factors(self, det: Dict, cis_score: float) -> List[str]:
        """Explain factors contributing to CIS score"""
        factors = []
        
        # Confidence
        conf = det['score']
        if conf > 0.8:
            factors.append(f"High detection confidence ({conf:.2f}) → +boost")
        elif conf < 0.5:
            factors.append(f"Low confidence ({conf:.2f}) → penalty")
        
        # Depth (objects closer tend to be more salient)
        depth = det.get('depth', 5.0)
        if depth < 2.0:
            factors.append(f"Close proximity ({depth:.1f}m) → +attention")
        elif depth > 5.0:
            factors.append(f"Far away ({depth:.1f}m) → lower priority")
        
        # Size (larger objects more influential)
        bbox = det['bbox']
        area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
        if area > 100000:
            factors.append(f"Large object ({area:.0f}px²) → +salience")
        elif area < 10000:
            factors.append(f"Small object ({area:.0f}px²) → less prominent")
        
        # Tracking history
        neighbors = det.get('neighbors', [])
        if len(neighbors) > 2:
            factors.append(f"Tracked across {len(neighbors)} frames → +persistence")
        
        return factors
    
    def log_motion_analysis(self, motion_desc: str, frame_idx: int):
        """Log camera motion analysis"""
        if not motion_desc or not self.verbose:
            return
        
        if frame_idx % self.show_every_n == 0:
            icon = "🎥"
            if "forward" in motion_desc or "backward" in motion_desc:
                icon = "🚶"
            elif "left" in motion_desc or "right" in motion_desc:
                icon = "↔️"
            elif "rotation" in motion_desc:
                icon = "🔄"
            
            self.console.print(f"  {icon} [bold]Camera Motion[/bold]: {motion_desc}")
    
    def log_timing(self, timing: Dict, frame_idx: int):
        """Log frame processing timing"""
        if not self.verbose or frame_idx % self.show_every_n != 0:
            return
        
        total_time = sum(timing.values())
        
        self.console.print(f"  [dim]⏱️  Frame time: {total_time:.1f}ms[/dim]", end="")
        
        # Show slowest component
        if timing:
            slowest = max(timing.items(), key=lambda x: x[1])
            self.console.print(f" [dim](slowest: {slowest[0]} @ {slowest[1]:.1f}ms)[/dim]")
        else:
            self.console.print()
    
    def log_frame_summary(self, diagnostic: DiagnosticInfo):
        """Log complete frame summary (for important frames)"""
        frame_idx = diagnostic.frame_idx
        
        if frame_idx % (self.show_every_n * 2) == 0:  # Every 10 frames
            # Create a summary table
            table = Table(title=f"Frame {frame_idx} Summary", box=box.ROUNDED)
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")
            
            table.add_row("Detections", str(len(diagnostic.detections)))
            table.add_row("Scene Relationships", str(len(diagnostic.scene_graph)))
            
            if diagnostic.depth_stats:
                table.add_row("Depth Quality", f"{diagnostic.depth_stats['valid_ratio']*100:.1f}%")
            
            if diagnostic.timing:
                total_time = sum(diagnostic.timing.values())
                table.add_row("Processing Time", f"{total_time:.1f}ms")
            
            self.console.print(table)
    
    def print_session_summary(self):
        """Print final session summary"""
        self.console.print("\n" + "="*60)
        self.console.print("[bold cyan]📊 SESSION SUMMARY[/bold cyan]")
        self.console.print("="*60)
        
        # Create summary table
        table = Table(box=box.DOUBLE_EDGE)
        table.add_column("Metric", style="cyan", no_wrap=True)
        table.add_column("Value", style="green")
        table.add_column("Notes", style="dim")
        
        table.add_row(
            "Total Frames",
            str(self.frame_count),
            ""
        )
        
        table.add_row(
            "Total Detections",
            str(self.total_detections),
            f"{self.total_detections / max(self.frame_count, 1):.1f} avg/frame"
        )
        
        # Quality breakdown
        high = self.quality_metrics['high_conf_detections']
        med = self.quality_metrics['medium_conf_detections']
        low = self.quality_metrics['low_conf_detections']
        total_dets = high + med + low
        
        if total_dets > 0:
            table.add_row(
                "High Confidence",
                f"{high} ({high/total_dets*100:.1f}%)",
                "score > 0.7"
            )
            table.add_row(
                "Medium Confidence",
                f"{med} ({med/total_dets*100:.1f}%)",
                "score 0.5-0.7"
            )
            table.add_row(
                "Low Confidence",
                f"{low} ({low/total_dets*100:.1f}%)",
                "score < 0.5"
            )
        
        table.add_row(
            "Scene Graphs",
            str(self.quality_metrics['scene_graphs_generated']),
            f"{self.quality_metrics['scene_graphs_generated'] / max(self.frame_count, 1):.1f} avg/frame"
        )
        
        self.console.print(table)
        
        # Quality assessment
        if total_dets > 0:
            quality_score = (high * 1.0 + med * 0.5) / total_dets
            
            if quality_score > 0.8:
                assessment = "[bold green]Excellent[/bold green] - High quality detections"
            elif quality_score > 0.6:
                assessment = "[bold yellow]Good[/bold yellow] - Acceptable quality"
            else:
                assessment = "[bold red]Fair[/bold red] - Consider tuning thresholds"
            
            self.console.print(f"\n[bold]Overall Quality:[/bold] {assessment}")
        
        self.console.print("="*60 + "\n")
