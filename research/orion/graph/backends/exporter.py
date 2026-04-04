from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from orion.graph import load_tracks
from orion.perception.spatial_zones import ZoneManager

try:
    from orion.graph.backends.memgraph import MemgraphBackend
except ImportError as exc:  # pragma: no cover - only hit when pymgclient missing
    MemgraphBackend = None  # type: ignore
    MEMGRAPH_IMPORT_ERROR = exc
else:
    MEMGRAPH_IMPORT_ERROR = None


@dataclass
class MemgraphExportResult:
    observations_written: int
    relations_written: int
    entities_indexed: int
    output_host: str
    output_port: int
    scene_graph_edges: int
    cis_edges_written: int = 0  # Stage 4: CIS edges


def _require_backend() -> None:
    if MemgraphBackend is None:
        raise RuntimeError(
            "Memgraph backend unavailable. Install pymgclient to enable graph export."
        ) from MEMGRAPH_IMPORT_ERROR


def _memory_indices(memory_path: Path) -> Dict[str, Dict]:
    data = json.loads(memory_path.read_text())
    entries: Dict[str, Dict] = {}
    for obj in data.get("objects", []):
        mem_id = obj.get("memory_id")
        if not mem_id:
            continue
        entries[mem_id] = obj
    return entries


def _memory_id_to_int(mem_id: str) -> int:
    digits = "".join(ch for ch in mem_id if ch.isdigit())
    if digits:
        return int(digits)
    return abs(hash(mem_id)) % (2 ** 31)


def export_results_to_memgraph(
    results_dir: Path,
    video_path: Optional[Path] = None,
    host: str = "127.0.0.1",
    port: int = 7687,
    username: str = "memgraph",
    password: str = "memgraph",
    *,
    clear_existing: bool = False,
) -> MemgraphExportResult:
    """Push tracks + scene graph outputs into a running Memgraph instance."""

    _require_backend()
    tracks_path = results_dir / "tracks.jsonl"
    memory_path = results_dir / "memory.json"
    graph_path = results_dir / "scene_graph.jsonl"

    if not tracks_path.exists():
        raise FileNotFoundError(f"tracks.jsonl missing in {results_dir}")
    if not memory_path.exists():
        raise FileNotFoundError(f"memory.json missing in {results_dir}")
    if not graph_path.exists():
        raise FileNotFoundError(f"scene_graph.jsonl missing in {results_dir}")

    zone_manager = ZoneManager()
    memory_index = _memory_indices(memory_path)
    embed_to_mem: Dict[str, str] = {}
    track_to_mem: Dict[int, str] = {}
    for mem_id, payload in memory_index.items():
        emb = payload.get("prototype_embedding")
        if emb:
            embed_to_mem[emb] = mem_id
        for segment in payload.get("appearance_history", []):
            tid = segment.get("track_id")
            if tid is not None:
                track_to_mem[int(tid)] = mem_id

    mg = MemgraphBackend(host=host, port=port, username=username, password=password)
    if clear_existing:
        mg.clear_all()

    observations_written = 0
    entity_ids: Dict[str, int] = {}

    for det in load_tracks(tracks_path):
        embedding_id = det.get("embedding_id")
        track_id = int(det.get("track_id", -1))
        mem_id = None
        if embedding_id and embedding_id in embed_to_mem:
            mem_id = embed_to_mem[embedding_id]
        elif track_id in track_to_mem:
            mem_id = track_to_mem[track_id]
        if not mem_id or mem_id not in memory_index:
            continue
        entity_ids.setdefault(mem_id, _memory_id_to_int(mem_id))
        mem_payload = memory_index[mem_id]
        class_name = mem_payload.get("class", det.get("category", "object"))
        zone_id = mem_payload.get("zone_id")
        if zone_id is None:
            zone_id = zone_manager.assign_zone_from_class(class_name)
            mem_payload["zone_id"] = zone_id
        caption = mem_payload.get("description") or mem_payload.get("best_caption")
        embedding = mem_payload.get("embedding_vector") or mem_payload.get("prototype_embedding_vector")
        embedding_payload = None
        if isinstance(embedding, list):
            embedding_payload = embedding
        bbox = det.get("bbox") or [0, 0, 0, 0]
        try:
            mg.add_entity_observation(
                entity_id=entity_ids[mem_id],
                frame_idx=int(det.get("frame_id", 0)),
                timestamp=float(det.get("timestamp", 0.0)),
                bbox=bbox,
                class_name=class_name,
                confidence=float(det.get("confidence", 0.0)),
                zone_id=zone_id,
                caption=caption,
                embedding=embedding_payload,
            )
            observations_written += 1
        except Exception as exc:  # pragma: no cover - network failure
            raise RuntimeError(f"Failed to write observation for {mem_id}: {exc}")

    relations_written = 0
    scene_graph_edges = 0
    with open(graph_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            graph = json.loads(line)
            edges = graph.get("edges", [])
            scene_graph_edges += len(edges)
            for edge in edges:
                subj = edge.get("subject")
                obj = edge.get("object")
                rel_type = edge.get("relation", "NEAR").upper()
                if not subj or not obj:
                    continue
                subj_id = entity_ids.get(subj)
                obj_id = entity_ids.get(obj)
                if subj_id is None or obj_id is None:
                    continue
                try:
                    mg.add_spatial_relationship(
                        entity1_id=subj_id,
                        entity2_id=obj_id,
                        relationship_type=rel_type,
                        confidence=float(edge.get("confidence", 0.9)),
                        frame_idx=int(graph.get("frame", graph.get("frame_id", 0))),
                    )
                    relations_written += 1
                except Exception as exc:  # pragma: no cover - network failure
                    raise RuntimeError(f"Failed to write relation {subj}->{obj}: {exc}")

    # Stage 4: Export CIS edges if present
    cis_edges_written = 0
    cis_path = results_dir / "cis_edges.jsonl"
    if cis_path.exists():
        try:
            cis_edges = []
            with open(cis_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    edge = json.loads(line)
                    # Map to entity IDs
                    agent_id = entity_ids.get(str(edge.get('agent_id')))
                    patient_id = entity_ids.get(str(edge.get('patient_id')))
                    if agent_id is None or patient_id is None:
                        # Try numeric lookup
                        agent_id = edge.get('agent_id')
                        patient_id = edge.get('patient_id')
                    if agent_id is not None and patient_id is not None:
                        cis_edges.append({
                            'agent_id': int(agent_id),
                            'patient_id': int(patient_id),
                            'relationship_type': edge.get('relation_type', 'INFLUENCES').upper(),
                            'cis_score': float(edge.get('cis_score', 0.5)),
                            'frame_idx': int(edge.get('frame_id', 0)),
                            'timestamp': float(edge.get('timestamp', 0.0)),
                            'influence_type': edge.get('components', {}).get('interaction_type', 'generic'),
                            'components': edge.get('components', {}),
                        })
            
            if cis_edges and hasattr(mg, 'add_cis_relationships_batch'):
                cis_edges_written = mg.add_cis_relationships_batch(cis_edges)
        except Exception as exc:
            # CIS export is optional; don't fail the whole export
            pass

    mg.close()

    return MemgraphExportResult(
        observations_written=observations_written,
        relations_written=relations_written,
        entities_indexed=len(entity_ids),
        output_host=host,
        output_port=port,
        scene_graph_edges=scene_graph_edges,
        cis_edges_written=cis_edges_written,
    )
