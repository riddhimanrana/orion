"""Minimal GraphBuilder for Neo4j integration with perception results."""
import logging
from typing import Optional

logger = logging.getLogger('orion.graph')


class GraphBuilder:
    """Build knowledge graph from perception results in Neo4j."""
    
    def __init__(self, neo4j_uri: str, neo4j_user: str, neo4j_password: str):
        """Initialize graph builder with Neo4j connection."""
        self.neo4j_uri = neo4j_uri
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password
        self.driver = None
        
        try:
            from neo4j import GraphDatabase
            self.driver = GraphDatabase.driver(
                neo4j_uri,
                auth=(neo4j_user, neo4j_password)
            )
            logger.info(f"✓ Connected to Neo4j at {neo4j_uri}")
        except ImportError:
            logger.warning("Neo4j driver not installed. Install: pip install neo4j")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
    
    def close(self):
        """Close Neo4j connection."""
        if self.driver:
            self.driver.close()
    
    def clear_database(self):
        """Clear all nodes and relationships."""
        if not self.driver:
            return
        
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
            logger.info("✓ Database cleared")
    
    def build_from_perception(self, perception_result):
        """Build graph from PerceptionResult."""
        if not self.driver:
            logger.warning("No Neo4j connection available")
            return
        
        with self.driver.session() as session:
            # Create video node
            session.run(
                """
                CREATE (v:Video {
                    path: $path,
                    duration: $duration,
                    frames: $frames,
                    fps: $fps
                })
                """,
                path=perception_result.video_path,
                duration=perception_result.duration_seconds,
                frames=perception_result.total_frames,
                fps=perception_result.fps
            )
            
            # Create entity nodes
            for entity in perception_result.entities:
                cls = entity.object_class.value if hasattr(entity.object_class, 'value') else str(entity.object_class)
                
                session.run(
                    """
                    CREATE (e:Entity {
                        id: $id,
                        class: $class_name,
                        observation_count: $obs_count,
                        first_frame: $first_frame,
                        last_frame: $last_frame,
                        description: $description
                    })
                    """,
                    id=entity.entity_id,
                    class_name=cls,
                    obs_count=len(entity.observations),
                    first_frame=entity.first_seen_frame,
                    last_frame=entity.last_seen_frame,
                    description=entity.description or ""
                )
                
                # Link entity to video
                session.run(
                    """
                    MATCH (v:Video {path: $video_path})
                    MATCH (e:Entity {id: $entity_id})
                    CREATE (e)-[:APPEARS_IN]->(v)
                    """,
                    video_path=perception_result.video_path,
                    entity_id=entity.entity_id
                )
            
            logger.info(f"✓ Created {len(perception_result.entities)} entity nodes")
    
    def query(self, cypher: str, params: Optional[dict] = None):
        """Execute Cypher query and return results."""
        if not self.driver:
            return []
        
        with self.driver.session() as session:
            result = session.run(cypher, params or {})
            return [dict(record) for record in result]

