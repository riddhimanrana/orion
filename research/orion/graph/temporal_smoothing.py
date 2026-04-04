"""
Temporal Smoothing for Scene Graphs

Implements rolling-window smoothing to filter out flickering edges in scene graphs.
Key insight from deep research: Open-vocab detectors produce noisy per-frame detections
that cause relation edges to appear/disappear rapidly.

Solution: Use temporal voting over N-frame windows to stabilize relations.

Author: Orion Research Team
Date: January 2026
"""

from __future__ import annotations

import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


@dataclass
class TemporalSmoothingConfig:
    """Configuration for temporal smoothing."""
    
    window_size: int = 3
    """Number of frames to consider for temporal voting."""
    
    min_occurrence_ratio: float = 0.5
    """Minimum ratio of frames in window where edge must appear to be kept.
    E.g., 0.5 means edge must appear in at least 50% of frames in window."""
    
    enable_node_smoothing: bool = True
    """Also smooth node presence (filter flickering objects)."""
    
    node_min_occurrence_ratio: float = 0.4
    """Minimum ratio for nodes to persist."""
    
    relation_specific_thresholds: Dict[str, float] = field(default_factory=lambda: {
        "near": 0.4,  # Near relations can flicker more (distance-based)
        "on": 0.6,    # On relations should be more stable
        "held_by": 0.7,  # Held_by should be very stable (action-based)
    })
    """Per-relation minimum occurrence ratios."""


@dataclass
class EdgeKey:
    """Hashable edge identifier."""
    subject_id: str
    predicate: str
    object_id: str
    
    def __hash__(self):
        return hash((self.subject_id, self.predicate, self.object_id))
    
    def __eq__(self, other):
        if not isinstance(other, EdgeKey):
            return False
        return (self.subject_id == other.subject_id and 
                self.predicate == other.predicate and 
                self.object_id == other.object_id)


class SceneGraphSmoother:
    """
    Temporal smoother for scene graph relations.
    
    Maintains a sliding window of recent frame graphs and outputs
    smoothed graphs where only persistent relations are kept.
    """
    
    def __init__(self, config: TemporalSmoothingConfig = None):
        self.config = config or TemporalSmoothingConfig()
        
        # Sliding window of recent graphs
        self._graph_window: deque = deque(maxlen=self.config.window_size)
        
        # Edge occurrence counts in current window
        self._edge_counts: Dict[EdgeKey, int] = defaultdict(int)
        
        # Node occurrence counts
        self._node_counts: Dict[str, int] = defaultdict(int)
        
        # Statistics
        self._total_input_edges = 0
        self._total_output_edges = 0
        self._frames_processed = 0
        
        logger.info(f"SceneGraphSmoother initialized: window={self.config.window_size}, "
                    f"min_ratio={self.config.min_occurrence_ratio}")
    
    def process_frame(self, frame_graph: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single frame's scene graph and return smoothed version.
        
        Args:
            frame_graph: Dict with 'frame', 'nodes', 'edges' keys
            
        Returns:
            Smoothed scene graph with filtered edges
        """
        self._frames_processed += 1
        
        # Extract nodes and edges from current frame
        frame_id = frame_graph.get("frame", self._frames_processed)
        nodes = frame_graph.get("nodes", [])
        edges = frame_graph.get("edges", [])
        
        self._total_input_edges += len(edges)
        
        # Build edge set for current frame
        current_edges: Set[EdgeKey] = set()
        for edge in edges:
            key = EdgeKey(
                subject_id=edge.get("subject", edge.get("subject_id", "")),
                predicate=edge.get("relation", edge.get("predicate", "")),
                object_id=edge.get("object", edge.get("object_id", ""))
            )
            current_edges.add(key)
        
        # Build node set for current frame
        current_nodes: Set[str] = set()
        for node in nodes:
            node_id = node.get("memory_id", node.get("id", ""))
            current_nodes.add(node_id)
        
        # Update window: remove oldest frame's contributions
        if len(self._graph_window) == self.config.window_size:
            oldest = self._graph_window[0]
            for edge_key in oldest["edges"]:
                self._edge_counts[edge_key] -= 1
                if self._edge_counts[edge_key] <= 0:
                    del self._edge_counts[edge_key]
            for node_id in oldest["nodes"]:
                self._node_counts[node_id] -= 1
                if self._node_counts[node_id] <= 0:
                    del self._node_counts[node_id]
        
        # Add current frame's contributions
        self._graph_window.append({
            "frame": frame_id,
            "edges": current_edges,
            "nodes": current_nodes,
        })
        
        for edge_key in current_edges:
            self._edge_counts[edge_key] += 1
        for node_id in current_nodes:
            self._node_counts[node_id] += 1
        
        # Filter edges by temporal voting
        window_len = len(self._graph_window)
        smoothed_edges = []
        
        for edge in edges:
            key = EdgeKey(
                subject_id=edge.get("subject", edge.get("subject_id", "")),
                predicate=edge.get("relation", edge.get("predicate", "")),
                object_id=edge.get("object", edge.get("object_id", ""))
            )
            
            occurrence_count = self._edge_counts.get(key, 0)
            occurrence_ratio = occurrence_count / window_len
            
            # Use relation-specific threshold if available
            relation = key.predicate
            threshold = self.config.relation_specific_thresholds.get(
                relation, self.config.min_occurrence_ratio
            )
            
            if occurrence_ratio >= threshold:
                # Add temporal confidence to edge
                smoothed_edge = dict(edge)
                smoothed_edge["temporal_confidence"] = occurrence_ratio
                smoothed_edge["window_occurrences"] = occurrence_count
                smoothed_edges.append(smoothed_edge)
        
        # Filter nodes if enabled
        smoothed_nodes = nodes
        if self.config.enable_node_smoothing:
            smoothed_nodes = []
            for node in nodes:
                node_id = node.get("memory_id", node.get("id", ""))
                occurrence_count = self._node_counts.get(node_id, 0)
                occurrence_ratio = occurrence_count / window_len
                
                if occurrence_ratio >= self.config.node_min_occurrence_ratio:
                    smoothed_node = dict(node)
                    smoothed_node["temporal_confidence"] = occurrence_ratio
                    smoothed_nodes.append(smoothed_node)
        
        self._total_output_edges += len(smoothed_edges)
        
        return {
            "frame": frame_id,
            "nodes": smoothed_nodes,
            "edges": smoothed_edges,
            "smoothing_metadata": {
                "window_size": window_len,
                "input_edges": len(edges),
                "output_edges": len(smoothed_edges),
                "filtered_edges": len(edges) - len(smoothed_edges),
            }
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get smoothing statistics."""
        return {
            "frames_processed": self._frames_processed,
            "total_input_edges": self._total_input_edges,
            "total_output_edges": self._total_output_edges,
            "edge_reduction_ratio": 1.0 - (self._total_output_edges / max(1, self._total_input_edges)),
            "current_window_size": len(self._graph_window),
            "unique_edges_in_window": len(self._edge_counts),
            "unique_nodes_in_window": len(self._node_counts),
        }
    
    def reset(self):
        """Reset smoother state."""
        self._graph_window.clear()
        self._edge_counts.clear()
        self._node_counts.clear()
        self._total_input_edges = 0
        self._total_output_edges = 0
        self._frames_processed = 0
    
    def smooth_graphs(self, graphs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Apply temporal smoothing to a sequence of scene graphs.
        
        Convenience method that processes all graphs and returns smoothed versions.
        
        Args:
            graphs: List of frame-level scene graphs
            
        Returns:
            List of smoothed scene graphs
        """
        self.reset()  # Start fresh for new sequence
        
        smoothed = []
        for graph in graphs:
            smoothed.append(self.process_frame(graph))
        
        stats = self.get_stats()
        logger.info(f"Scene graph smoothing complete: "
                    f"{stats['total_input_edges']} → {stats['total_output_edges']} edges "
                    f"({stats['edge_reduction_ratio']:.1%} reduction)")
        
        return smoothed


def smooth_scene_graph_sequence(
    graphs: List[Dict[str, Any]],
    config: TemporalSmoothingConfig = None,
) -> List[Dict[str, Any]]:
    """
    Apply temporal smoothing to a sequence of scene graphs.
    
    Args:
        graphs: List of frame-level scene graphs
        config: Smoothing configuration
        
    Returns:
        List of smoothed scene graphs
    """
    smoother = SceneGraphSmoother(config)
    
    smoothed = []
    for graph in graphs:
        smoothed.append(smoother.process_frame(graph))
    
    stats = smoother.get_stats()
    logger.info(f"Scene graph smoothing complete: "
                f"{stats['total_input_edges']} → {stats['total_output_edges']} edges "
                f"({stats['edge_reduction_ratio']:.1%} reduction)")
    
    return smoothed
