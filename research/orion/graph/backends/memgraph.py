"""
Memgraph Graph Backend for Orion
High-performance C++-based graph database for real-time video queries

Stores:
- Entity observations (frame_idx, bbox, zone_id, class, confidence)
- Spatial relationships (NEAR, IN_ZONE, FOLLOWS)
- Temporal relationships (APPEARS_AFTER, COEXISTS_WITH)
- Causal Influence relationships (INFLUENCES, GRASPS, MOVES_WITH)
- Semantic metadata (captions, attributes, VLM descriptions)

Key advantages over SQLite:
- 1000+ TPS on reads/writes (C++ native)
- Graph queries in Cypher (natural for relationships)
- Real-time path finding and pattern matching
- Vector search for semantic similarity (1024-dim V-JEPA2 embeddings)

CIS Edge Types (Stage 4):
- INFLUENCES: Generic causal influence between entities
- GRASPS: Hand-object grasping interaction (high confidence)
- MOVES_WITH: Correlated motion between objects
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import numpy as np

try:
    import mgclient
except ImportError:
    mgclient = None

logger = logging.getLogger(__name__)


@dataclass
class EntityObservation:
    """Single observation of an entity in a frame"""
    entity_id: int
    frame_idx: int
    timestamp: float
    bbox: List[float]  # [x1, y1, x2, y2]
    class_name: str
    confidence: float
    zone_id: Optional[int] = None
    caption: Optional[str] = None


@dataclass
class SpatialRelationship:
    """Spatial relationship between two entities"""
    entity1_id: int
    entity2_id: int
    relationship_type: str  # NEAR, ABOVE, BELOW, LEFT_OF, RIGHT_OF
    confidence: float
    frame_idx: int


class MemgraphBackend:
    """
    High-performance Memgraph backend for video understanding graph
    
    Schema:
    - (Entity {id, class_name, first_seen, last_seen})
    - (Frame {idx, timestamp, zone_id})
    - (Zone {id, type, centroid})
    - (Entity)-[OBSERVED_IN {bbox, confidence, caption}]->(Frame)
    - (Entity)-[NEAR|ABOVE|BELOW {confidence, frame_idx}]->(Entity)
    - (Entity)-[IN_ZONE]->(Zone)
    - (Frame)-[IN_ZONE]->(Zone)
    """
    
    def __init__(self, host: str = "127.0.0.1", port: int = 7687, 
                 username: str = "memgraph", password: str = "memgraph"):
        """
        Initialize Memgraph connection
        
        Args:
            host: Memgraph host (default: localhost)
            port: Memgraph port (default: 7687)
            username: Memgraph username (default: memgraph)
            password: Memgraph password (default: memgraph)
        """
        if mgclient is None:
            raise ImportError(
                "pymgclient not installed. Install with: pip install pymgclient"
            )
        
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.connection = None
        self._connect()
        self._initialize_schema()
    
    def _connect(self):
        """Establish connection to Memgraph"""
        try:
            self.connection = mgclient.connect(
                host=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                lazy=False
            )
            logger.info(f"✓ Connected to Memgraph at {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"Failed to connect to Memgraph: {e}")
            logger.error("Make sure Memgraph is running: docker compose up -d")
            raise
    
    def _initialize_schema(self):
        """Create indexes and constraints for optimal query performance"""
        try:
            cursor = self.connection.cursor()
            
            # Create indexes for fast lookups
            cursor.execute("CREATE INDEX ON :Entity(id);")
            cursor.execute("CREATE INDEX ON :Frame(idx);")
            cursor.execute("CREATE INDEX ON :Zone(id);")
            cursor.execute("CREATE INDEX ON :Entity(class_name);")
            
            # CIS relationship indexes (Stage 4)
            cursor.execute("CREATE INDEX ON :Entity(first_seen);")
            cursor.execute("CREATE INDEX ON :Entity(last_seen);")
            
            self.connection.commit()
            logger.info("✓ Memgraph schema initialized (with CIS indexes)")
        except Exception as e:
            # Indexes may already exist
            logger.debug(f"Schema initialization: {e}")
    
    def add_entity_observation(
        self,
        entity_id: int,
        frame_idx: int,
        timestamp: float,
        bbox: list,
        class_name: str,
        confidence: float,
        zone_id: Optional[int] = None,
        caption: Optional[str] = None,
        crop_path: Optional[str] = None,  # NEW: For query-time captioning
        embedding: Optional[List[float]] = None  # NEW: For vector search
    ):
        """
        Add an entity observation to the graph
        
        Creates/updates:
        - Entity node
        - Frame node
        - OBSERVED_IN relationship
        - Zone relationship (if zone_id provided)
        """
        try:
            cursor = self.connection.cursor()
            
            # Create/update Entity node
            # Note: We only update embedding if provided. 
            # In a real system, we might want to average them or keep a history.
            entity_query = """
            MERGE (e:Entity {id: $entity_id})
            SET e.class_name = $class_name
            """
            
            params = {
                'entity_id': entity_id,
                'class_name': class_name
            }

            if embedding is not None:
                entity_query += ", e.embedding = $embedding"
                params['embedding'] = embedding

            cursor.execute(entity_query, params)
            self.connection.commit()
            
            # Create/update Frame node
            frame_query = """
            MERGE (f:Frame {idx: $frame_idx})
            SET f.timestamp = $timestamp
            """
            cursor.execute(frame_query, {
                'frame_idx': frame_idx,
                'timestamp': timestamp
            })
            self.connection.commit()
            
            # Create OBSERVED_IN relationship with bbox and caption
            obs_props = {
                'entity_id': entity_id,
                'frame_idx': frame_idx,
                'bbox_x1': bbox[0],
                'bbox_y1': bbox[1],
                'bbox_x2': bbox[2],
                'bbox_y2': bbox[3],
                'confidence': confidence
            }
            
            if caption:
                obs_props['caption'] = caption
            
            if crop_path:
                obs_props['crop_path'] = crop_path  # Store for query-time captioning
            
            obs_query = """
            MATCH (e:Entity {id: $entity_id})
            MATCH (f:Frame {idx: $frame_idx})
            MERGE (e)-[r:OBSERVED_IN]->(f)
            SET r.bbox_x1 = $bbox_x1,
                r.bbox_y1 = $bbox_y1,
                r.bbox_x2 = $bbox_x2,
                r.bbox_y2 = $bbox_y2,
                r.confidence = $confidence
            """
            
            if caption:
                obs_query += ", r.caption = $caption"
            
            if crop_path:
                obs_query += ", r.crop_path = $crop_path"
            
            cursor.execute(obs_query, obs_props)
            self.connection.commit()
            
            # Add zone relationship if provided
            if zone_id is not None:
                zone_query = """
                MATCH (e:Entity {id: $entity_id})
                MERGE (z:Zone {id: $zone_id})
                MERGE (e)-[:IN_ZONE]->(z)
                """
                cursor.execute(zone_query, {
                    'zone_id': zone_id,
                    'entity_id': entity_id
                })
                self.connection.commit()
                
        except Exception as e:
            logger.error(f"Failed to add entity observation: {e}")
            raise
    
    def add_spatial_relationship(
        self,
        entity1_id: int,
        entity2_id: int,
        relationship_type: str,
        confidence: float,
        frame_idx: int
    ):
        """
        Add spatial relationship between entities
        
        Examples:
        - (person)-[NEAR {confidence: 0.9}]->(laptop)
        - (book)-[ON_TOP_OF {confidence: 0.85}]->(desk)
        """
        cursor = self.connection.cursor()
        
        cursor.execute(
            f"""
            MATCH (e1:Entity {{id: $entity1_id}})
            MATCH (e2:Entity {{id: $entity2_id}})
            CREATE (e1)-[r:{relationship_type} {{
                confidence: $confidence,
                frame_idx: $frame_idx
            }}]->(e2)
            """,
            {
                "entity1_id": entity1_id,
                "entity2_id": entity2_id,
                "confidence": confidence,
                "frame_idx": frame_idx
            }
        )
        
        self.connection.commit()
    
    def query_entity_by_class(
        self,
        class_name: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Find all entities of a given class
        
        Example: "Find all books in the video"
        """
        cursor = self.connection.cursor()
        
        cursor.execute(
            """
            MATCH (e:Entity {class_name: $class_name})
            MATCH (e)-[r:OBSERVED_IN]->(f:Frame)
            RETURN e.id as entity_id,
                   e.class_name as class_name,
                   e.first_seen as first_seen,
                   e.last_seen as last_seen,
                   collect({
                       frame_idx: f.idx,
                       timestamp: f.timestamp,
                       bbox: r.bbox,
                       confidence: r.confidence,
                       caption: r.caption,
                       crop_path: r.crop_path
                   }) as observations
            LIMIT $limit
            """,
            {"class_name": class_name, "limit": limit}
        )
        
        results = []
        for row in cursor.fetchall():
            results.append({
                "entity_id": row[0],
                "class_name": row[1],
                "first_seen": row[2],
                "last_seen": row[3],
                "observations": row[4]
            })
        
        return results
    
    def query_entity_in_zone(
        self,
        zone_id: int,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Find all entities observed in a specific zone
        
        Example: "What objects were in zone 2?"
        """
        cursor = self.connection.cursor()
        
        cursor.execute(
            """
            MATCH (z:Zone {id: $zone_id})
            MATCH (e:Entity)-[:IN_ZONE]->(z)
            MATCH (e)-[r:OBSERVED_IN]->(f:Frame)
            WHERE f.zone_id = $zone_id
            RETURN e.id as entity_id,
                   e.class_name as class_name,
                   collect({
                       frame_idx: f.idx,
                       bbox: r.bbox,
                       caption: r.caption
                   }) as observations
            LIMIT $limit
            """,
            {"zone_id": zone_id, "limit": limit}
        )
        
        results = []
        for row in cursor.fetchall():
            results.append({
                "entity_id": row[0],
                "class_name": row[1],
                "observations": row[2]
            })
        
        return results
    
    def query_spatial_relationships(
        self,
        entity_id: int
    ) -> List[Dict[str, Any]]:
        """
        Find all spatial relationships for an entity
        
        Example: "What objects are near the laptop?"
        """
        cursor = self.connection.cursor()
        
        cursor.execute(
            """
            MATCH (e1:Entity {id: $entity_id})-[r]->(e2:Entity)
            WHERE type(r) IN ['NEAR', 'ABOVE', 'BELOW', 'LEFT_OF', 'RIGHT_OF']
            RETURN type(r) as relationship,
                   e2.id as related_entity_id,
                   e2.class_name as related_class,
                   r.confidence as confidence,
                   r.frame_idx as frame_idx
            """,
            {"entity_id": entity_id}
        )
        
        results = []
        for row in cursor.fetchall():
            results.append({
                "relationship": row[0],
                "related_entity_id": row[1],
                "related_class": row[2],
                "confidence": row[3],
                "frame_idx": row[4]
            })
        
        return results
    
    def query_temporal_coexistence(
        self,
        entity_id: int,
        time_window: float = 5.0
    ) -> List[Dict[str, Any]]:
        """
        Find entities that appeared at the same time
        
        Example: "What objects appeared with the book?"
        """
        cursor = self.connection.cursor()
        
        cursor.execute(
            """
            MATCH (e1:Entity {id: $entity_id})-[:OBSERVED_IN]->(f1:Frame)
            MATCH (e2:Entity)-[:OBSERVED_IN]->(f2:Frame)
            WHERE e1.id <> e2.id
              AND abs(f1.timestamp - f2.timestamp) <= $time_window
            RETURN DISTINCT e2.id as entity_id,
                            e2.class_name as class_name,
                            count(*) as coexistence_count
            ORDER BY coexistence_count DESC
            """,
            {"entity_id": entity_id, "time_window": time_window}
        )
        
        results = []
        for row in cursor.fetchall():
            results.append({
                "entity_id": row[0],
                "class_name": row[1],
                "coexistence_count": row[2]
            })
        
        return results
    
    def update_caption(
        self,
        entity_id: int,
        frame_idx: int,
        caption: str
    ):
        """
        Update caption for specific observation (lazy-loaded)
        """
        cursor = self.connection.cursor()
        
        cursor.execute(
            """
            MATCH (e:Entity {id: $entity_id})-[r:OBSERVED_IN]->(f:Frame {idx: $frame_idx})
            SET r.caption = $caption
            """,
            {
                "entity_id": entity_id,
                "frame_idx": frame_idx,
                "caption": caption
            }
        )
        
        self.connection.commit()
    
    def get_statistics(self) -> Dict[str, int]:
        """Get graph statistics"""
        cursor = self.connection.cursor()
        
        stats = {}
        
        # Count entities
        cursor.execute("MATCH (e:Entity) RETURN count(e) as count")
        stats["entities"] = cursor.fetchone()[0]
        
        # Count frames
        cursor.execute("MATCH (f:Frame) RETURN count(f) as count")
        stats["frames"] = cursor.fetchone()[0]
        
        # Count zones
        cursor.execute("MATCH (z:Zone) RETURN count(z) as count")
        stats["zones"] = cursor.fetchone()[0]
        
        # Count observations
        cursor.execute("MATCH ()-[r:OBSERVED_IN]->() RETURN count(r) as count")
        stats["observations"] = cursor.fetchone()[0]
        
        # Count spatial relationships
        cursor.execute(
            """
            MATCH ()-[r]->()
            WHERE type(r) IN ['NEAR', 'ABOVE', 'BELOW', 'LEFT_OF', 'RIGHT_OF']
            RETURN count(r) as count
            """
        )
        stats["spatial_relationships"] = cursor.fetchone()[0]
        
        return stats
    
    def clear_all(self):
        """Clear entire graph (use with caution!)"""
        cursor = self.connection.cursor()
        cursor.execute("MATCH (n) DETACH DELETE n")
        self.connection.commit()
        logger.info("✓ Graph cleared")
    
    def close(self):
        """Close connection"""
        if self.connection:
            self.connection.close()
            logger.info("✓ Memgraph connection closed")
    
    def create_vector_index(self, dimension: int = 512, metric: str = "cosine"):
        """
        Create a vector index on Entity embeddings for fast similarity search.
        Requires Memgraph MAGE or vector search support.
        """
        try:
            cursor = self.connection.cursor()
            # Check if index exists or just try to create it.
            # Syntax depends on Memgraph version. Using a generic approach or MAGE.
            # For now, we'll assume standard Memgraph vector index syntax if available,
            # or just rely on the property being there for manual cosine sim if needed.
            
            # Example for Memgraph 2.14+ native vector index:
            # CREATE VECTOR INDEX ON :Entity(embedding) WITH CONFIG {"dimension": 512, "metric": "cosine"}
            
            query = f"""
            CREATE VECTOR INDEX ON :Entity(embedding) 
            WITH CONFIG {{"dimension": {dimension}, "metric": "{metric}"}}
            """
            cursor.execute(query)
            self.connection.commit()
            logger.info(f"✓ Vector index created on Entity(embedding) with dim={dimension}")
        except Exception as e:
            logger.warning(f"Failed to create vector index (might already exist or not supported): {e}")

    def add_observations_batch(
        self,
        observations: List[Dict[str, Any]],
    ) -> int:
        """
        Add multiple entity observations in a single transaction using UNWIND.
        
        This is 10-50x faster than individual add_entity_observation calls.
        
        Args:
            observations: List of dicts with keys:
                - entity_id: int
                - frame_idx: int
                - timestamp: float
                - bbox: [x1, y1, x2, y2]
                - class_name: str
                - confidence: float
                - zone_id: Optional[int]
                - caption: Optional[str]
                - embedding: Optional[List[float]]
                
        Returns:
            Number of observations inserted.
        """
        if not observations:
            return 0
            
        try:
            cursor = self.connection.cursor()
            
            # Prepare data for UNWIND
            obs_data = []
            for obs in observations:
                bbox = obs.get('bbox', [0, 0, 0, 0])
                obs_data.append({
                    'entity_id': obs['entity_id'],
                    'frame_idx': obs['frame_idx'],
                    'timestamp': obs.get('timestamp', 0.0),
                    'class_name': obs['class_name'],
                    'confidence': obs.get('confidence', 0.0),
                    'bbox_x1': bbox[0] if len(bbox) > 0 else 0,
                    'bbox_y1': bbox[1] if len(bbox) > 1 else 0,
                    'bbox_x2': bbox[2] if len(bbox) > 2 else 0,
                    'bbox_y2': bbox[3] if len(bbox) > 3 else 0,
                    'zone_id': obs.get('zone_id'),
                    'caption': obs.get('caption'),
                })
            
            # Batch insert using UNWIND
            batch_query = """
            UNWIND $observations AS obs
            MERGE (e:Entity {id: obs.entity_id})
            SET e.class_name = obs.class_name
            MERGE (f:Frame {idx: obs.frame_idx})
            SET f.timestamp = obs.timestamp
            MERGE (e)-[r:OBSERVED_IN]->(f)
            SET r.bbox_x1 = obs.bbox_x1,
                r.bbox_y1 = obs.bbox_y1,
                r.bbox_x2 = obs.bbox_x2,
                r.bbox_y2 = obs.bbox_y2,
                r.confidence = obs.confidence
            """
            
            cursor.execute(batch_query, {'observations': obs_data})
            self.connection.commit()
            
            logger.debug(f"Batch inserted {len(observations)} observations")
            return len(observations)
            
        except Exception as e:
            logger.error(f"Batch insert failed: {e}")
            raise

    def add_relationships_batch(
        self,
        relationships: List[Dict[str, Any]],
    ) -> int:
        """
        Add multiple spatial relationships in a single transaction.
        
        Args:
            relationships: List of dicts with keys:
                - entity1_id: int
                - entity2_id: int
                - relationship_type: str (NEAR, ABOVE, BELOW, etc.)
                - confidence: float
                - frame_idx: int
                
        Returns:
            Number of relationships inserted.
        """
        if not relationships:
            return 0
            
        try:
            cursor = self.connection.cursor()
            
            # Group by relationship type for efficiency
            by_type: Dict[str, List] = {}
            for rel in relationships:
                rel_type = rel['relationship_type']
                by_type.setdefault(rel_type, []).append(rel)
            
            total = 0
            for rel_type, rels in by_type.items():
                rel_data = [{
                    'e1': r['entity1_id'],
                    'e2': r['entity2_id'],
                    'conf': r['confidence'],
                    'fidx': r['frame_idx']
                } for r in rels]
                
                # Dynamic relationship type
                query = f"""
                UNWIND $rels AS r
                MATCH (e1:Entity {{id: r.e1}})
                MATCH (e2:Entity {{id: r.e2}})
                MERGE (e1)-[rel:{rel_type}]->(e2)
                SET rel.confidence = r.conf,
                    rel.frame_idx = r.fidx
                """
                
                cursor.execute(query, {'rels': rel_data})
                total += len(rels)
            
            self.connection.commit()
            logger.debug(f"Batch inserted {total} relationships")
            return total
            
        except Exception as e:
            logger.error(f"Batch relationship insert failed: {e}")
            raise

    def search_similar_entities(
        self, 
        query_embedding: List[float], 
        limit: int = 5, 
        min_score: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Search for entities with similar embeddings using vector search.
        """
        cursor = self.connection.cursor()
        
        # Using Memgraph's vector search syntax
        # CALL vector_search.search(index_name, query_vector, limit)
        # Or native Cypher if supported.
        
        # We'll try the native Cypher syntax for Memgraph 2.14+
        query = """
        MATCH (e:Entity)
        WHERE e.embedding IS NOT NULL
        WITH e, vector.similarity.cosine(e.embedding, $query_embedding) AS score
        WHERE score >= $min_score
        RETURN e.id as entity_id, 
               e.class_name as class_name, 
               score
        ORDER BY score DESC
        LIMIT $limit
        """
        
        try:
            cursor.execute(query, {
                "query_embedding": query_embedding,
                "min_score": min_score,
                "limit": limit
            })
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    "entity_id": row[0],
                    "class_name": row[1],
                    "score": row[2]
                })
            return results
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []

    # ==========================================================================
    # STAGE 4: CIS (Causal Influence Scoring) EDGE METHODS
    # ==========================================================================

    def add_cis_relationship(
        self,
        agent_id: int,
        patient_id: int,
        relationship_type: str,
        cis_score: float,
        frame_idx: int,
        timestamp: float = 0.0,
        influence_type: str = "generic",
        components: Optional[Dict[str, float]] = None,
    ):
        """
        Add a Causal Influence Scoring (CIS) relationship between two entities.
        
        CIS edges represent causal interactions:
        - INFLUENCES: Generic causal influence
        - GRASPS: Hand-object grasping (high confidence)
        - MOVES_WITH: Correlated motion
        
        Args:
            agent_id: Entity causing the influence (e.g., person/hand)
            patient_id: Entity being influenced (e.g., object)
            relationship_type: INFLUENCES, GRASPS, or MOVES_WITH
            cis_score: Overall CIS score [0, 1]
            frame_idx: Frame where interaction occurred
            timestamp: Frame timestamp in seconds
            influence_type: Detailed interaction type (grasping, touching, etc.)
            components: Optional CIS component breakdown (temporal, spatial, motion, etc.)
        """
        cursor = self.connection.cursor()
        
        props = {
            "agent_id": agent_id,
            "patient_id": patient_id,
            "cis_score": cis_score,
            "frame_idx": frame_idx,
            "timestamp": timestamp,
            "influence_type": influence_type,
        }
        
        # Build property string for optional components
        component_sets = ""
        if components:
            for key, val in components.items():
                props[f"c_{key}"] = val
                component_sets += f", rel.{key} = $c_{key}"
        
        query = f"""
        MATCH (a:Entity {{id: $agent_id}})
        MATCH (p:Entity {{id: $patient_id}})
        MERGE (a)-[rel:{relationship_type}]->(p)
        SET rel.cis_score = $cis_score,
            rel.frame_idx = $frame_idx,
            rel.timestamp = $timestamp,
            rel.influence_type = $influence_type
            {component_sets}
        """
        
        try:
            cursor.execute(query, props)
            self.connection.commit()
        except Exception as e:
            logger.error(f"Failed to add CIS relationship: {e}")
            raise

    def add_cis_relationships_batch(
        self,
        cis_edges: List[Dict[str, Any]],
    ) -> int:
        """
        Add multiple CIS relationships in a single transaction.
        
        High-performance batch insert for CIS edges computed by CausalInfluenceScorer.
        
        Args:
            cis_edges: List of dicts with keys:
                - agent_id: int
                - patient_id: int
                - relationship_type: str (INFLUENCES, GRASPS, MOVES_WITH)
                - cis_score: float [0, 1]
                - frame_idx: int
                - timestamp: float (optional)
                - influence_type: str (optional)
                - components: dict (optional, CIS component breakdown)
                
        Returns:
            Number of CIS edges inserted.
        """
        if not cis_edges:
            return 0
            
        try:
            cursor = self.connection.cursor()
            
            # Group by relationship type for efficiency
            by_type: Dict[str, List] = {}
            for edge in cis_edges:
                rel_type = edge.get('relationship_type', 'INFLUENCES').upper()
                by_type.setdefault(rel_type, []).append(edge)
            
            total = 0
            for rel_type, edges in by_type.items():
                edge_data = []
                for e in edges:
                    components = e.get('components', {})
                    edge_data.append({
                        'agent': e['agent_id'],
                        'patient': e['patient_id'],
                        'score': e['cis_score'],
                        'fidx': e['frame_idx'],
                        'ts': e.get('timestamp', 0.0),
                        'itype': e.get('influence_type', 'generic'),
                        # Flatten components
                        'temporal': components.get('temporal', 0.0),
                        'spatial': components.get('spatial', 0.0),
                        'motion': components.get('motion', 0.0),
                        'semantic': components.get('semantic', 0.0),
                        'hand_bonus': components.get('hand_bonus', 0.0),
                        'distance_3d_mm': components.get('distance_3d_mm', 0.0),
                    })
                
                # Dynamic relationship type with all properties
                query = f"""
                UNWIND $edges AS e
                MATCH (a:Entity {{id: e.agent}})
                MATCH (p:Entity {{id: e.patient}})
                MERGE (a)-[rel:{rel_type}]->(p)
                SET rel.cis_score = e.score,
                    rel.frame_idx = e.fidx,
                    rel.timestamp = e.ts,
                    rel.influence_type = e.itype,
                    rel.temporal = e.temporal,
                    rel.spatial = e.spatial,
                    rel.motion = e.motion,
                    rel.semantic = e.semantic,
                    rel.hand_bonus = e.hand_bonus,
                    rel.distance_3d_mm = e.distance_3d_mm
                """
                
                cursor.execute(query, {'edges': edge_data})
                total += len(edges)
            
            self.connection.commit()
            logger.debug(f"Batch inserted {total} CIS relationships")
            return total
            
        except Exception as e:
            logger.error(f"Batch CIS insert failed: {e}")
            raise

    def query_cis_relationships(
        self,
        entity_id: Optional[int] = None,
        relationship_type: Optional[str] = None,
        min_score: float = 0.5,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Query CIS relationships from the graph.
        
        Args:
            entity_id: Optional entity to filter by (as agent or patient)
            relationship_type: Optional filter (INFLUENCES, GRASPS, MOVES_WITH)
            min_score: Minimum CIS score to include
            limit: Maximum results to return
            
        Returns:
            List of CIS relationship dicts.
        """
        cursor = self.connection.cursor()
        
        # Build query based on filters
        rel_filter = ""
        if relationship_type:
            rel_filter = f":{relationship_type.upper()}"
        
        if entity_id is not None:
            query = f"""
            MATCH (a:Entity)-[r{rel_filter}]->(p:Entity)
            WHERE (a.id = $entity_id OR p.id = $entity_id)
              AND r.cis_score >= $min_score
            RETURN a.id as agent_id,
                   a.class_name as agent_class,
                   type(r) as relationship_type,
                   r.cis_score as cis_score,
                   r.frame_idx as frame_idx,
                   r.influence_type as influence_type,
                   p.id as patient_id,
                   p.class_name as patient_class
            ORDER BY r.cis_score DESC
            LIMIT $limit
            """
            params = {"entity_id": entity_id, "min_score": min_score, "limit": limit}
        else:
            query = f"""
            MATCH (a:Entity)-[r{rel_filter}]->(p:Entity)
            WHERE r.cis_score >= $min_score
            RETURN a.id as agent_id,
                   a.class_name as agent_class,
                   type(r) as relationship_type,
                   r.cis_score as cis_score,
                   r.frame_idx as frame_idx,
                   r.influence_type as influence_type,
                   p.id as patient_id,
                   p.class_name as patient_class
            ORDER BY r.cis_score DESC
            LIMIT $limit
            """
            params = {"min_score": min_score, "limit": limit}
        
        try:
            cursor.execute(query, params)
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    "agent_id": row[0],
                    "agent_class": row[1],
                    "relationship_type": row[2],
                    "cis_score": row[3],
                    "frame_idx": row[4],
                    "influence_type": row[5],
                    "patient_id": row[6],
                    "patient_class": row[7],
                })
            return results
        except Exception as e:
            logger.error(f"CIS query failed: {e}")
            return []

    def get_cis_statistics(self) -> Dict[str, Any]:
        """Get CIS relationship statistics."""
        cursor = self.connection.cursor()
        
        stats = {}
        
        # Count CIS edges by type
        for rel_type in ['INFLUENCES', 'GRASPS', 'MOVES_WITH']:
            try:
                cursor.execute(
                    f"MATCH ()-[r:{rel_type}]->() RETURN count(r) as count"
                )
                stats[f"cis_{rel_type.lower()}"] = cursor.fetchone()[0]
            except:
                stats[f"cis_{rel_type.lower()}"] = 0
        
        # Average CIS score
        try:
            cursor.execute("""
                MATCH ()-[r]->()
                WHERE type(r) IN ['INFLUENCES', 'GRASPS', 'MOVES_WITH']
                  AND r.cis_score IS NOT NULL
                RETURN avg(r.cis_score) as avg_score, 
                       max(r.cis_score) as max_score,
                       count(r) as total
            """)
            row = cursor.fetchone()
            if row:
                stats["avg_cis_score"] = row[0] or 0.0
                stats["max_cis_score"] = row[1] or 0.0
                stats["total_cis_edges"] = row[2] or 0
        except:
            stats["avg_cis_score"] = 0.0
            stats["max_cis_score"] = 0.0
            stats["total_cis_edges"] = 0
        
        return stats

    def add_observations_batch_with_vlm(
        self,
        observations: List[Dict[str, Any]],
    ) -> int:
        """
        Add multiple entity observations with VLM descriptions and embedding IDs.
        
        Extended version of add_observations_batch that includes:
        - vlm_description: FastVLM description of the object
        - embedding_id: V-JEPA2 embedding reference for Re-ID
        - depth_mm: 3D depth for spatial queries
        
        Args:
            observations: List of dicts with extended keys:
                - entity_id, frame_idx, timestamp, bbox, class_name, confidence
                - vlm_description: Optional[str]
                - embedding_id: Optional[str]
                - depth_mm: Optional[float]
                - embedding: Optional[List[float]] (1024-dim V-JEPA2)
                
        Returns:
            Number of observations inserted.
        """
        if not observations:
            return 0
            
        try:
            cursor = self.connection.cursor()
            
            # Prepare data for UNWIND with extended properties
            obs_data = []
            for obs in observations:
                bbox = obs.get('bbox', [0, 0, 0, 0])
                obs_data.append({
                    'entity_id': obs['entity_id'],
                    'frame_idx': obs['frame_idx'],
                    'timestamp': obs.get('timestamp', 0.0),
                    'class_name': obs['class_name'],
                    'confidence': obs.get('confidence', 0.0),
                    'bbox_x1': bbox[0] if len(bbox) > 0 else 0,
                    'bbox_y1': bbox[1] if len(bbox) > 1 else 0,
                    'bbox_x2': bbox[2] if len(bbox) > 2 else 0,
                    'bbox_y2': bbox[3] if len(bbox) > 3 else 0,
                    'zone_id': obs.get('zone_id'),
                    'caption': obs.get('caption'),
                    'vlm_description': obs.get('vlm_description'),
                    'embedding_id': obs.get('embedding_id'),
                    'depth_mm': obs.get('depth_mm'),
                })
            
            # Batch insert with extended properties
            batch_query = """
            UNWIND $observations AS obs
            MERGE (e:Entity {id: obs.entity_id})
            SET e.class_name = obs.class_name
            MERGE (f:Frame {idx: obs.frame_idx})
            SET f.timestamp = obs.timestamp
            MERGE (e)-[r:OBSERVED_IN]->(f)
            SET r.bbox_x1 = obs.bbox_x1,
                r.bbox_y1 = obs.bbox_y1,
                r.bbox_x2 = obs.bbox_x2,
                r.bbox_y2 = obs.bbox_y2,
                r.confidence = obs.confidence,
                r.vlm_description = obs.vlm_description,
                r.embedding_id = obs.embedding_id,
                r.depth_mm = obs.depth_mm
            """
            
            cursor.execute(batch_query, {'observations': obs_data})
            self.connection.commit()
            
            logger.debug(f"Batch inserted {len(observations)} observations (with VLM metadata)")
            return len(observations)
            
        except Exception as e:
            logger.error(f"Batch insert with VLM failed: {e}")
            raise
    # ==========================================================================
    # RAG (Retrieval-Augmented Generation) QUERY METHODS
    # ==========================================================================

    def query_for_rag(
        self,
        query_type: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Unified RAG query interface for LLM-friendly responses.
        
        Query types:
        - "find_object": Find objects by class name or description
        - "spatial_context": Get spatial context around an entity
        - "temporal_journey": Track an entity over time
        - "interactions": Get CIS interactions for an entity
        - "scene_summary": Get summary of a frame range
        
        Returns structured data optimized for LLM context injection.
        """
        handlers = {
            "find_object": self._rag_find_object,
            "spatial_context": self._rag_spatial_context,
            "temporal_journey": self._rag_temporal_journey,
            "interactions": self._rag_interactions,
            "scene_summary": self._rag_scene_summary,
        }
        
        handler = handlers.get(query_type)
        if not handler:
            raise ValueError(f"Unknown RAG query type: {query_type}")
        
        return handler(**kwargs)

    def _rag_find_object(
        self,
        class_name: Optional[str] = None,
        description_keywords: Optional[List[str]] = None,
        frame_range: Optional[Tuple[int, int]] = None,
        limit: int = 10,
        **kwargs
    ) -> Dict[str, Any]:
        """Find objects matching class name or description keywords."""
        cursor = self.connection.cursor()
        
        conditions = []
        params = {"limit": limit}
        
        if class_name:
            conditions.append("e.class_name = $class_name")
            params["class_name"] = class_name.lower()
        
        if frame_range:
            conditions.append("f.idx >= $frame_start AND f.idx <= $frame_end")
            params["frame_start"] = frame_range[0]
            params["frame_end"] = frame_range[1]
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        query = f"""
        MATCH (e:Entity)-[r:OBSERVED_IN]->(f:Frame)
        WHERE {where_clause}
        WITH e, collect({{
            frame: f.idx,
            timestamp: f.timestamp,
            confidence: r.confidence,
            description: r.vlm_description,
            bbox: [r.bbox_x1, r.bbox_y1, r.bbox_x2, r.bbox_y2]
        }}) as observations
        RETURN e.id as entity_id,
               e.class_name as class_name,
               size(observations) as num_observations,
               observations[0].frame as first_seen_frame,
               observations[-1].frame as last_seen_frame,
               observations[0].description as sample_description
        ORDER BY num_observations DESC
        LIMIT $limit
        """
        
        try:
            cursor.execute(query, params)
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    "entity_id": row[0],
                    "class_name": row[1],
                    "num_observations": row[2],
                    "first_seen_frame": row[3],
                    "last_seen_frame": row[4],
                    "sample_description": row[5],
                })
            
            return {
                "query_type": "find_object",
                "results": results,
                "total": len(results),
                "natural_language_summary": self._format_find_object_summary(results, class_name)
            }
        except Exception as e:
            logger.error(f"RAG find_object failed: {e}")
            return {"query_type": "find_object", "results": [], "error": str(e)}

    def _format_find_object_summary(self, results: List[Dict], class_name: Optional[str]) -> str:
        """Format find_object results as natural language for LLM."""
        if not results:
            return f"No {class_name or 'objects'} found in the video."
        
        if class_name:
            summary = f"Found {len(results)} {class_name}(s) in the video:\n"
        else:
            summary = f"Found {len(results)} objects:\n"
        
        for i, r in enumerate(results[:5], 1):
            desc = r.get('sample_description', 'No description')[:100]
            summary += f"  {i}. {r['class_name']} (ID:{r['entity_id']}) - seen {r['num_observations']} times, frames {r['first_seen_frame']}-{r['last_seen_frame']}\n"
            if desc:
                summary += f"     Description: {desc}...\n"
        
        return summary

    def _rag_spatial_context(
        self,
        entity_id: int,
        frame_idx: Optional[int] = None,
        radius_mm: float = 2000.0,
        **kwargs
    ) -> Dict[str, Any]:
        """Get spatial context: what objects are near an entity."""
        cursor = self.connection.cursor()
        
        params = {"entity_id": entity_id}
        frame_filter = ""
        if frame_idx is not None:
            frame_filter = "AND r1.frame_idx = $frame_idx AND r2.frame_idx = $frame_idx"
            params["frame_idx"] = frame_idx
        
        query = f"""
        MATCH (e1:Entity {{id: $entity_id}})-[r1:OBSERVED_IN]->(f:Frame)
        MATCH (e2:Entity)-[r2:OBSERVED_IN]->(f)
        WHERE e1.id <> e2.id {frame_filter}
        OPTIONAL MATCH (e1)-[spatial:NEAR|ABOVE|BELOW]->(e2)
        RETURN e2.id as nearby_id,
               e2.class_name as nearby_class,
               type(spatial) as spatial_relation,
               spatial.confidence as spatial_confidence,
               f.idx as frame_idx
        LIMIT 50
        """
        
        try:
            cursor.execute(query, params)
            
            nearby_objects = {}
            for row in cursor.fetchall():
                eid = row[0]
                if eid not in nearby_objects:
                    nearby_objects[eid] = {
                        "entity_id": eid,
                        "class_name": row[1],
                        "relations": [],
                    }
                if row[2]:  # Has spatial relation
                    nearby_objects[eid]["relations"].append({
                        "type": row[2],
                        "confidence": row[3],
                        "frame_idx": row[4],
                    })
            
            return {
                "query_type": "spatial_context",
                "entity_id": entity_id,
                "nearby_objects": list(nearby_objects.values()),
                "natural_language_summary": self._format_spatial_summary(entity_id, nearby_objects)
            }
        except Exception as e:
            logger.error(f"RAG spatial_context failed: {e}")
            return {"query_type": "spatial_context", "error": str(e)}

    def _format_spatial_summary(self, entity_id: int, nearby_objects: Dict) -> str:
        """Format spatial context as natural language."""
        if not nearby_objects:
            return f"Entity {entity_id} has no nearby objects detected."
        
        summary = f"Entity {entity_id} is near {len(nearby_objects)} objects:\n"
        for obj in list(nearby_objects.values())[:5]:
            relations = obj.get("relations", [])
            if relations:
                rel_str = ", ".join([f"{r['type']} (conf:{r['confidence']:.2f})" for r in relations[:3]])
                summary += f"  - {obj['class_name']} (ID:{obj['entity_id']}): {rel_str}\n"
            else:
                summary += f"  - {obj['class_name']} (ID:{obj['entity_id']}): co-located in frame\n"
        
        return summary

    def _rag_temporal_journey(
        self,
        entity_id: int,
        sample_every_n: int = 10,
        **kwargs
    ) -> Dict[str, Any]:
        """Track an entity's journey through the video."""
        cursor = self.connection.cursor()
        
        query = """
        MATCH (e:Entity {id: $entity_id})-[r:OBSERVED_IN]->(f:Frame)
        WITH e, r, f
        ORDER BY f.idx
        RETURN f.idx as frame_idx,
               f.timestamp as timestamp,
               r.bbox_x1 as x1, r.bbox_y1 as y1,
               r.bbox_x2 as x2, r.bbox_y2 as y2,
               r.vlm_description as description,
               r.confidence as confidence
        """
        
        try:
            cursor.execute(query, {"entity_id": entity_id})
            
            journey = []
            for i, row in enumerate(cursor.fetchall()):
                if i % sample_every_n == 0 or i == 0:  # Sample every N frames + first
                    journey.append({
                        "frame_idx": row[0],
                        "timestamp": row[1],
                        "bbox": [row[2], row[3], row[4], row[5]],
                        "description": row[6],
                        "confidence": row[7],
                    })
            
            return {
                "query_type": "temporal_journey",
                "entity_id": entity_id,
                "journey": journey,
                "total_observations": len(journey) * sample_every_n,
                "natural_language_summary": self._format_journey_summary(entity_id, journey)
            }
        except Exception as e:
            logger.error(f"RAG temporal_journey failed: {e}")
            return {"query_type": "temporal_journey", "error": str(e)}

    def _format_journey_summary(self, entity_id: int, journey: List[Dict]) -> str:
        """Format temporal journey as natural language."""
        if not journey:
            return f"No observations found for entity {entity_id}."
        
        first = journey[0]
        last = journey[-1]
        duration = (last.get("timestamp", 0) or 0) - (first.get("timestamp", 0) or 0)
        
        summary = f"Entity {entity_id} tracked over {len(journey)} key frames ({duration:.1f}s):\n"
        summary += f"  First seen: frame {first['frame_idx']} at {first.get('timestamp', 0):.1f}s\n"
        summary += f"  Last seen: frame {last['frame_idx']} at {last.get('timestamp', 0):.1f}s\n"
        
        if first.get("description"):
            summary += f"  Initial description: {first['description'][:100]}...\n"
        
        return summary

    def _rag_interactions(
        self,
        entity_id: int,
        min_score: float = 0.5,
        limit: int = 20,
        **kwargs
    ) -> Dict[str, Any]:
        """Get CIS interactions involving an entity."""
        cursor = self.connection.cursor()
        
        query = """
        MATCH (a:Entity)-[r]->(p:Entity)
        WHERE type(r) IN ['INFLUENCES', 'GRASPS', 'MOVES_WITH']
          AND (a.id = $entity_id OR p.id = $entity_id)
          AND r.cis_score >= $min_score
        RETURN a.id as agent_id,
               a.class_name as agent_class,
               type(r) as interaction_type,
               r.cis_score as score,
               r.frame_idx as frame_idx,
               r.influence_type as detail,
               p.id as patient_id,
               p.class_name as patient_class
        ORDER BY r.cis_score DESC
        LIMIT $limit
        """
        
        try:
            cursor.execute(query, {"entity_id": entity_id, "min_score": min_score, "limit": limit})
            
            interactions = []
            for row in cursor.fetchall():
                interactions.append({
                    "agent_id": row[0],
                    "agent_class": row[1],
                    "interaction_type": row[2],
                    "score": row[3],
                    "frame_idx": row[4],
                    "detail": row[5],
                    "patient_id": row[6],
                    "patient_class": row[7],
                })
            
            return {
                "query_type": "interactions",
                "entity_id": entity_id,
                "interactions": interactions,
                "natural_language_summary": self._format_interactions_summary(entity_id, interactions)
            }
        except Exception as e:
            logger.error(f"RAG interactions failed: {e}")
            return {"query_type": "interactions", "error": str(e)}

    def _format_interactions_summary(self, entity_id: int, interactions: List[Dict]) -> str:
        """Format interactions as natural language."""
        if not interactions:
            return f"No significant interactions found for entity {entity_id}."
        
        summary = f"Entity {entity_id} has {len(interactions)} interactions:\n"
        for i in interactions[:5]:
            if i["agent_id"] == entity_id:
                summary += f"  - {i['interaction_type']} {i['patient_class']} (ID:{i['patient_id']}) at frame {i['frame_idx']} (score: {i['score']:.2f})\n"
            else:
                summary += f"  - {i['agent_class']} (ID:{i['agent_id']}) {i['interaction_type']} this entity at frame {i['frame_idx']} (score: {i['score']:.2f})\n"
        
        return summary

    def _rag_scene_summary(
        self,
        frame_start: int = 0,
        frame_end: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Get summary of objects and interactions in a frame range."""
        cursor = self.connection.cursor()
        
        params = {"frame_start": frame_start}
        frame_filter = "f.idx >= $frame_start"
        if frame_end is not None:
            frame_filter += " AND f.idx <= $frame_end"
            params["frame_end"] = frame_end
        
        # Get entity counts
        query = f"""
        MATCH (e:Entity)-[r:OBSERVED_IN]->(f:Frame)
        WHERE {frame_filter}
        WITH e.class_name as class, count(distinct e) as entity_count, count(r) as obs_count
        RETURN class, entity_count, obs_count
        ORDER BY obs_count DESC
        LIMIT 20
        """
        
        try:
            cursor.execute(query, params)
            
            class_summary = []
            for row in cursor.fetchall():
                class_summary.append({
                    "class_name": row[0],
                    "entity_count": row[1],
                    "observation_count": row[2],
                })
            
            # Get interaction summary
            interaction_query = f"""
            MATCH (a:Entity)-[r]->(p:Entity)
            WHERE type(r) IN ['INFLUENCES', 'GRASPS', 'MOVES_WITH']
              AND r.frame_idx >= $frame_start
              {"AND r.frame_idx <= $frame_end" if frame_end else ""}
            RETURN type(r) as interaction_type, count(r) as count
            """
            
            cursor.execute(interaction_query, params)
            interaction_summary = {}
            for row in cursor.fetchall():
                interaction_summary[row[0]] = row[1]
            
            return {
                "query_type": "scene_summary",
                "frame_range": [frame_start, frame_end],
                "object_classes": class_summary,
                "interactions": interaction_summary,
                "natural_language_summary": self._format_scene_summary(class_summary, interaction_summary, frame_start, frame_end)
            }
        except Exception as e:
            logger.error(f"RAG scene_summary failed: {e}")
            return {"query_type": "scene_summary", "error": str(e)}

    def _format_scene_summary(self, classes: List[Dict], interactions: Dict, frame_start: int, frame_end: Optional[int]) -> str:
        """Format scene summary as natural language."""
        range_str = f"frames {frame_start}-{frame_end}" if frame_end else f"from frame {frame_start}"
        
        total_entities = sum(c["entity_count"] for c in classes)
        total_obs = sum(c["observation_count"] for c in classes)
        
        summary = f"Scene summary for {range_str}:\n"
        summary += f"  Total: {total_entities} unique entities, {total_obs} observations\n"
        summary += "  Objects by type:\n"
        for c in classes[:7]:
            summary += f"    - {c['class_name']}: {c['entity_count']} entities, {c['observation_count']} sightings\n"
        
        if interactions:
            summary += "  Interactions:\n"
            for itype, count in interactions.items():
                summary += f"    - {itype}: {count}\n"
        
        return summary