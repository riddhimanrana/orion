"""
RAG Query Module for Orion (Stage 5+6)
=======================================

Natural language queries over video memory stored in Memgraph.

Stage 5: Retrieval (Cypher queries → Evidence)
Stage 6: Reasoning (LLM synthesis → Natural language answers)

Query Types:
1. Entity queries: "What objects are in the video?"
2. Spatial queries: "What was near the laptop?"
3. Temporal queries: "What happened at 25s?"
4. Interaction queries: "What did the person interact with?"
5. Similarity queries: "Find objects similar to the book" (vector search)

Author: Orion Research Team
Date: January 2026
"""

import logging
import os
import time
from typing import Dict, List, Any, Optional, Generator
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)

try:
    from orion.graph.backends.memgraph import MemgraphBackend
    MEMGRAPH_AVAILABLE = True
except ImportError:
    MEMGRAPH_AVAILABLE = False
    MemgraphBackend = None

try:
    from orion.query.reasoning import ReasoningModel, ReasoningConfig
    REASONING_AVAILABLE = True
except ImportError:
    REASONING_AVAILABLE = False
    ReasoningModel = None
    ReasoningConfig = None


@dataclass
class QueryResult:
    """Result of a RAG query"""
    query_type: str
    question: str
    answer: str
    evidence: List[Dict[str, Any]]
    confidence: float = 0.0
    latency_ms: float = 0.0
    cypher_query: Optional[str] = None
    llm_used: bool = False


class OrionRAG:
    """
    RAG (Retrieval-Augmented Generation) query interface for Orion.
    
    Combines:
    - Stage 5: Memgraph retrieval (Cypher queries)
    - Stage 6: LLM reasoning (Ollama synthesis)
    
    Example usage:
        rag = OrionRAG(host="127.0.0.1", port=7687)
        
        # Simple query (retrieval only)
        result = rag.query("What objects are in the video?")
        
        # With LLM synthesis (Stage 6)
        result = rag.query("What did the person interact with?", use_llm=True)
        
        # Streaming response
        for token in rag.stream_query("Describe the interactions"):
            print(token, end="")
    """
    
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 7687,
        username: str = "memgraph",
        password: str = "memgraph",
        enable_llm: bool = True,
        llm_model: str = "qwen2.5:14b-instruct-q8_0",
        ollama_url: str = "http://localhost:11434",
    ):
        """
        Initialize RAG with Memgraph and optional LLM.
        
        Args:
            host: Memgraph host
            port: Memgraph port
            username: Memgraph username
            password: Memgraph password
            enable_llm: Enable Stage 6 LLM reasoning
            llm_model: Ollama model for reasoning
            ollama_url: Ollama API URL
        """
        if not MEMGRAPH_AVAILABLE:
            raise ImportError("Memgraph backend not available. Install pymgclient.")
        
        self.backend = MemgraphBackend(
            host=host,
            port=port,
            username=username,
            password=password,
        )
        logger.info(f"RAG connected to Memgraph at {host}:{port}")
        
        # Allow runtime overrides without needing to thread params everywhere.
        # Useful for Lambda where we may prefer a smaller model.
        env_url = os.environ.get("ORION_OLLAMA_URL")
        if env_url:
            ollama_url = str(env_url)
        env_model = os.environ.get("ORION_OLLAMA_MODEL")
        if env_model:
            llm_model = str(env_model)

        # Initialize LLM reasoning (Stage 6)
        self.reasoning_model = None
        self.llm_enabled = False
        
        if enable_llm and REASONING_AVAILABLE:
            try:
                config = ReasoningConfig(model=llm_model, base_url=ollama_url)
                self.reasoning_model = ReasoningModel(config=config)
                if self.reasoning_model.validate_model():
                    self.llm_enabled = True
                    logger.info(f"✓ Stage 6 LLM enabled: {llm_model}")
                else:
                    logger.warning("LLM model validation failed, using template answers")
            except Exception as e:
                logger.warning(f"Failed to initialize LLM: {e}")
        elif enable_llm:
            logger.warning("Reasoning module not available, using template answers")
    
    def query(
        self,
        question: str,
        use_llm: Optional[bool] = None,
        episode_id: Optional[str] = None,
        use_neural_cypher: bool = True,
    ) -> QueryResult:
        """
        Answer a natural language question about the video.
        
        Neural Cypher RAG: Uses the LLM to dynamically generate Cypher queries
        instead of hardcoded string matching. Falls back to template queries
        if LLM is disabled or generation fails.
        
        Args:
            question: Natural language question
            use_llm: Force LLM synthesis on/off (default: auto based on initialization)
            episode_id: Filter by episode (for multi-episode support)
            use_neural_cypher: Use LLM-generated Cypher (default: True)
            
        Returns:
            QueryResult with answer and evidence
        """
        start_time = time.time()
        
        # Determine if we should use LLM
        should_use_llm = use_llm if use_llm is not None else self.llm_enabled
        
        # NEURAL CYPHER RAG: Let LLM generate the query if enabled
        if use_neural_cypher and should_use_llm and self.reasoning_model:
            result = self._query_neural_cypher(question)
            if result.evidence:  # Neural cypher succeeded
                # Synthesize natural language answer from evidence
                try:
                    llm_answer = self.reasoning_model.synthesize_answer(
                        question=question,
                        evidence=result.evidence,
                    )
                    result.answer = llm_answer
                    result.llm_used = True
                except Exception as e:
                    logger.warning(f"LLM synthesis failed: {e}")
                result.latency_ms = (time.time() - start_time) * 1000
                return result
            # If neural cypher returned no evidence, fall through to template queries
            logger.debug("Neural Cypher returned no results, trying template queries")
        
        # FALLBACK: Template-based routing for specific query patterns
        question_lower = question.lower()
        
        # Route to appropriate retrieval handler
        if "what objects" in question_lower or "list objects" in question_lower:
            result = self._query_all_objects(question)
        
        elif "where" in question_lower and "appear" in question_lower:
            result = self._query_object_location(question)
        
        elif "near" in question_lower:
            result = self._query_spatial_near(question)
        
        elif "interact" in question_lower or "held" in question_lower or "holding" in question_lower:
            result = self._query_interactions(question)
        
        elif "time" in question_lower or "frame" in question_lower or "when" in question_lower:
            result = self._query_temporal(question)
        
        elif "similar" in question_lower or "like" in question_lower:
            result = self._query_similar_objects(question)
        
        else:
            # Default: try to find mentioned object
            result = self._query_object_info(question)
        
        # Apply LLM synthesis if enabled
        if should_use_llm and self.reasoning_model and result.evidence:
            try:
                llm_answer = self.reasoning_model.synthesize_answer(
                    question=question,
                    evidence=result.evidence,
                )
                result.answer = llm_answer
                result.llm_used = True
            except Exception as e:
                logger.warning(f"LLM synthesis failed, using template: {e}")
        
        result.latency_ms = (time.time() - start_time) * 1000
        return result
    
    def _query_neural_cypher(self, question: str) -> QueryResult:
        """
        Generate and execute a Cypher query using the LLM.
        
        This is the core of Neural Cypher RAG - the LLM translates
        natural language directly into graph queries.
        """
        # Generate Cypher with enhanced schema hint
        schema_hint = """
Schema (Memgraph):
- (Entity {id: INT, class_name: STRING, first_seen: FLOAT, last_seen: FLOAT, embedding: LIST})
  Objects detected in video (person, laptop, book, chair, etc.)

- (Frame {idx: INT, timestamp: FLOAT})
  Video frames with timestamps in seconds

- (Entity)-[OBSERVED_IN {bbox_x1, bbox_y1, bbox_x2, bbox_y2, confidence}]->(Frame)
  When/where an entity was seen

- (Entity)-[NEAR {confidence: FLOAT, frame_idx: INT}]->(Entity)
  Two objects were spatially close in a frame

- (Entity)-[HELD_BY {confidence: FLOAT, frame_idx: INT}]->(Entity)
  Object was held/interacted with by another entity (usually person)

Common Patterns:
- Find all objects: MATCH (e:Entity) RETURN DISTINCT e.class_name
- Object timeline: MATCH (e:Entity)-[:OBSERVED_IN]->(f:Frame) RETURN e.class_name, f.timestamp ORDER BY f.timestamp
- Spatial relations: MATCH (e1)-[r:NEAR]-(e2) RETURN e1.class_name, e2.class_name, r.confidence
- Interactions: MATCH (obj)-[r:HELD_BY]->(agent) RETURN obj.class_name, agent.class_name
"""
        
        def _looks_like_sql(q: str) -> bool:
            u = (q or "").upper()
            return any(tok in u for tok in ("SELECT ", " FROM ", "INSERT ", "UPDATE ", "DELETE "))

        def _exec(cypher: str) -> QueryResult:
            # Execute the generated query
            cursor = self.backend.connection.cursor()
            cursor.execute(cypher)
            results = cursor.fetchall()

            # Convert results to evidence dicts
            evidence: List[Dict[str, Any]] = []
            if results:
                # Try to get column names
                try:
                    col_names = [desc[0] for desc in cursor.description] if cursor.description else None
                except Exception:
                    col_names = None

                for row in results[:20]:  # Limit to 20 results
                    if col_names:
                        evidence.append(dict(zip(col_names, row)))
                    else:
                        evidence.append({f"col_{i}": v for i, v in enumerate(row)})

            return QueryResult(
                query_type="neural_cypher",
                question=question,
                answer="",  # Will be filled by LLM synthesis
                evidence=evidence,
                confidence=1.0 if evidence else 0.0,
                cypher_query=cypher,
            )

        try:
            cypher = self.reasoning_model.generate_cypher(question, schema_hint)
            
            if not cypher or len(cypher) < 10 or _looks_like_sql(cypher):
                logger.warning(f"Invalid Cypher generated: {cypher}")
                return QueryResult(
                    query_type="neural_cypher",
                    question=question,
                    answer="",
                    evidence=[],
                    confidence=0.0,
                    cypher_query=cypher,
                )

            try:
                return _exec(cypher)
            except Exception as e:
                # One-shot retry: ask the model to correct the Cypher using the parse/runtime error.
                logger.warning(f"Neural Cypher execution failed: {e}")
                retry_prompt = (
                    f"{question}\n\n"
                    f"The previous Cypher failed in Memgraph with this error:\n{e}\n\n"
                    "Please output a corrected Cypher query only (no markdown, no explanation)."
                )
                cypher2 = self.reasoning_model.generate_cypher(retry_prompt, schema_hint)
                if not cypher2 or len(cypher2) < 10 or _looks_like_sql(cypher2):
                    return QueryResult(
                        query_type="neural_cypher",
                        question=question,
                        answer="",
                        evidence=[],
                        confidence=0.0,
                        cypher_query=cypher2,
                    )
                return _exec(cypher2)
            
        except Exception as e:
            logger.warning(f"Neural Cypher execution failed: {e}")
            return QueryResult(
                query_type="neural_cypher",
                question=question,
                answer="",
                evidence=[],
                confidence=0.0,
            )
    
    def stream_query(
        self,
        question: str,
        episode_id: Optional[str] = None,
    ) -> Generator[str, None, None]:
        """
        Stream answer tokens for real-time display.
        
        Yields:
            Answer tokens as they're generated
        """
        if not self.reasoning_model:
            # Fall back to non-streaming
            result = self.query(question, use_llm=False, episode_id=episode_id)
            yield result.answer
            return
        
        # Get evidence first
        question_lower = question.lower()
        
        if "what objects" in question_lower or "list objects" in question_lower:
            result = self._query_all_objects(question)
        elif "interact" in question_lower or "held" in question_lower:
            result = self._query_interactions(question)
        elif "near" in question_lower:
            result = self._query_spatial_near(question)
        else:
            result = self._query_object_info(question)
        
        # Stream LLM response
        for token in self.reasoning_model.stream_answer(question, result.evidence):
            yield token
    
    def _query_all_objects(self, question: str) -> QueryResult:
        """List all objects detected in the video."""
        cursor = self.backend.connection.cursor()
        
        cypher = """
            MATCH (e:Entity)-[r:OBSERVED_IN]->(f:Frame)
            WITH e.class_name AS class, count(r) AS observations, 
                 min(f.timestamp) AS first_seen, max(f.timestamp) AS last_seen
            RETURN class, observations, first_seen, last_seen
            ORDER BY observations DESC
        """
        
        cursor.execute(cypher)
        results = cursor.fetchall()
        
        evidence = []
        object_list = []
        for row in results:
            evidence.append({
                "class": row[0],
                "observations": row[1],
                "first_seen": f"{row[2]:.1f}s" if row[2] else "N/A",
                "last_seen": f"{row[3]:.1f}s" if row[3] else "N/A",
            })
            object_list.append(f"{row[0]} ({row[1]} observations)")
        
        answer = f"Found {len(results)} object types: " + ", ".join(object_list)
        
        return QueryResult(
            query_type="all_objects",
            question=question,
            answer=answer,
            evidence=evidence,
            confidence=1.0,
            cypher_query=cypher,
        )
    
    def _query_object_location(self, question: str) -> QueryResult:
        """Query where a specific object appeared."""
        obj_name = self._extract_object_name(question)
        
        cypher = """
            MATCH (e:Entity {class_name: $class_name})-[r:OBSERVED_IN]->(f:Frame)
            WITH e, f, r ORDER BY f.timestamp
            RETURN e.id, collect({
                frame: f.idx,
                time: f.timestamp,
                bbox: [r.bbox_x1, r.bbox_y1, r.bbox_x2, r.bbox_y2]
            }) AS appearances
            LIMIT 1
        """
        
        cursor = self.backend.connection.cursor()
        cursor.execute(cypher, {"class_name": obj_name})
        results = cursor.fetchall()
        
        if not results:
            return QueryResult(
                query_type="object_location",
                question=question,
                answer=f"No '{obj_name}' found in the video.",
                evidence=[],
                confidence=0.0,
                cypher_query=cypher,
            )
        
        appearances = results[0][1]
        evidence = appearances[:10]  # Limit for display
        
        first = appearances[0]
        last = appearances[-1]
        
        answer = f"The {obj_name} appears {len(appearances)} times, from {first['time']:.1f}s to {last['time']:.1f}s."
        
        return QueryResult(
            query_type="object_location",
            question=question,
            answer=answer,
            evidence=evidence,
            confidence=1.0,
            cypher_query=cypher,
        )
    
    def _query_spatial_near(self, question: str) -> QueryResult:
        """Query objects near a specific entity."""
        obj_name = self._extract_object_name(question)
        
        # Try both directions for NEAR relationship
        cypher = """
            MATCH (e1:Entity {class_name: $class_name})-[r:NEAR]-(e2:Entity)
            WITH e2.class_name AS nearby, count(r) AS times, avg(r.confidence) AS avg_conf
            RETURN nearby, times, avg_conf
            ORDER BY times DESC
            LIMIT 10
        """
        
        cursor = self.backend.connection.cursor()
        cursor.execute(cypher, {"class_name": obj_name})
        results = cursor.fetchall()
        
        evidence = [
            {"nearby": row[0], "count": row[1], "avg_confidence": row[2]}
            for row in results
        ]
        
        if not results:
            answer = f"No spatial relationships found for '{obj_name}'."
        else:
            nearby_list = [row[0] for row in results]
            answer = f"Objects near {obj_name}: " + ", ".join(nearby_list)
        
        return QueryResult(
            query_type="spatial_near",
            question=question,
            answer=answer,
            evidence=evidence,
            confidence=1.0 if results else 0.0,
            cypher_query=cypher,
        )
    
    def _query_interactions(self, question: str) -> QueryResult:
        """Query interaction relationships (HELD_BY, etc.)."""
        cypher = """
            MATCH (obj:Entity)-[r:HELD_BY]->(agent:Entity)
            WITH obj.class_name AS object, agent.class_name AS holder, 
                 count(r) AS times, avg(r.confidence) AS avg_conf
            RETURN object, holder, times, avg_conf
            ORDER BY times DESC
        """
        
        cursor = self.backend.connection.cursor()
        cursor.execute(cypher)
        results = cursor.fetchall()
        
        evidence = [
            {"object": row[0], "holder": row[1], "count": row[2], "confidence": row[3]}
            for row in results
        ]
        
        if not results:
            answer = "No interactions (held objects) detected in this video."
        else:
            interactions = [f"{row[0]} held by {row[1]} ({row[2]} times)" for row in results]
            answer = "Interactions: " + "; ".join(interactions)
        
        return QueryResult(
            query_type="interactions",
            question=question,
            answer=answer,
            evidence=evidence,
            confidence=1.0 if results else 0.0,
            cypher_query=cypher,
        )
    
    def _query_temporal(self, question: str) -> QueryResult:
        """Query what happened at a specific time or frame range."""
        import re
        
        # Try to extract time in seconds
        time_match = re.search(r'(\d+(?:\.\d+)?)\s*s(?:ec)?', question)
        frame_match = re.search(r'frame[s]?\s*(\d+)', question)
        
        cursor = self.backend.connection.cursor()
        
        if time_match:
            target_time = float(time_match.group(1))
            cypher = """
                MATCH (e:Entity)-[r:OBSERVED_IN]->(f:Frame)
                WHERE abs(f.timestamp - $target_time) < 2.0
                RETURN e.class_name AS class, f.idx AS frame, f.timestamp AS time
                ORDER BY f.timestamp
            """
            cursor.execute(cypher, {"target_time": target_time})
            
        elif frame_match:
            target_frame = int(frame_match.group(1))
            cypher = """
                MATCH (e:Entity)-[r:OBSERVED_IN]->(f:Frame)
                WHERE abs(f.idx - $target_frame) < 20
                RETURN e.class_name AS class, f.idx AS frame, f.timestamp AS time
                ORDER BY f.idx
            """
            cursor.execute(cypher, {"target_frame": target_frame})
            
        else:
            return QueryResult(
                query_type="temporal",
                question=question,
                answer="Could not parse time/frame from question. Use format like '25s' or 'frame 500'.",
                evidence=[],
                confidence=0.0,
            )
        
        results = cursor.fetchall()
        evidence = [{"class": row[0], "frame": row[1], "time": row[2]} for row in results]
        
        if not results:
            answer = "No objects found at that time."
        else:
            objects = list(set(row[0] for row in results))
            answer = f"At that time, detected: " + ", ".join(objects)
        
        return QueryResult(
            query_type="temporal",
            question=question,
            answer=answer,
            evidence=evidence,
            confidence=1.0 if results else 0.0,
            cypher_query=cypher if 'cypher' in locals() else None,
        )
    
    def _query_similar_objects(self, question: str) -> QueryResult:
        """
        Find objects similar to a reference using vector embeddings.
        
        Uses V-JEPA2 embeddings stored in Entity nodes.
        """
        obj_name = self._extract_object_name(question)
        
        # Get reference embedding
        cursor = self.backend.connection.cursor()
        
        ref_cypher = """
            MATCH (e:Entity {class_name: $class_name})
            WHERE e.embedding IS NOT NULL
            RETURN e.id, e.class_name, e.embedding
            LIMIT 1
        """
        cursor.execute(ref_cypher, {"class_name": obj_name})
        ref_result = cursor.fetchall()
        
        if not ref_result or not ref_result[0][2]:
            return QueryResult(
                query_type="similarity",
                question=question,
                answer=f"No embedding found for '{obj_name}'. Cannot perform similarity search.",
                evidence=[],
                confidence=0.0,
            )
        
        ref_embedding = np.array(ref_result[0][2])
        
        # Get all other embeddings
        all_cypher = """
            MATCH (e:Entity)
            WHERE e.embedding IS NOT NULL AND e.class_name <> $class_name
            RETURN e.id, e.class_name, e.embedding
        """
        cursor.execute(all_cypher, {"class_name": obj_name})
        all_results = cursor.fetchall()
        
        if not all_results:
            return QueryResult(
                query_type="similarity",
                question=question,
                answer=f"No other objects with embeddings found to compare with '{obj_name}'.",
                evidence=[],
                confidence=0.0,
            )
        
        # Compute cosine similarities
        similarities = []
        for row in all_results:
            emb = np.array(row[2])
            if len(emb) == len(ref_embedding):
                sim = np.dot(ref_embedding, emb) / (np.linalg.norm(ref_embedding) * np.linalg.norm(emb) + 1e-8)
                similarities.append({
                    "id": row[0],
                    "class": row[1],
                    "similarity": float(sim),
                })
        
        # Sort by similarity
        similarities.sort(key=lambda x: x["similarity"], reverse=True)
        evidence = similarities[:5]  # Top 5 similar
        
        if evidence:
            top_matches = [f"{e['class']} ({e['similarity']:.2f})" for e in evidence]
            answer = f"Objects most similar to {obj_name}: " + ", ".join(top_matches)
        else:
            answer = f"Could not compute similarities for '{obj_name}'."
        
        return QueryResult(
            query_type="similarity",
            question=question,
            answer=answer,
            evidence=evidence,
            confidence=evidence[0]["similarity"] if evidence else 0.0,
        )
    
    def _query_object_info(self, question: str) -> QueryResult:
        """General query about a specific object."""
        obj_name = self._extract_object_name(question)
        
        cypher = """
            MATCH (e:Entity {class_name: $class_name})-[r:OBSERVED_IN]->(f:Frame)
            WITH e, count(r) AS obs_count, 
                 min(f.timestamp) AS first, max(f.timestamp) AS last
            OPTIONAL MATCH (e)-[held:HELD_BY]->(holder:Entity)
            RETURN e.id, e.class_name, obs_count, first, last, 
                   collect(DISTINCT holder.class_name) AS holders
        """
        
        cursor = self.backend.connection.cursor()
        cursor.execute(cypher, {"class_name": obj_name})
        results = cursor.fetchall()
        
        if not results:
            return QueryResult(
                query_type="object_info",
                question=question,
                answer=f"No information found about '{obj_name}'.",
                evidence=[],
                confidence=0.0,
                cypher_query=cypher,
            )
        
        row = results[0]
        evidence = [{
            "id": row[0],
            "class": row[1],
            "observations": row[2],
            "first_seen": row[3],
            "last_seen": row[4],
            "held_by": row[5],
        }]
        
        parts = [f"The {row[1]} was detected {row[2]} times"]
        if row[3] and row[4]:
            parts.append(f"from {row[3]:.1f}s to {row[4]:.1f}s")
        if row[5] and row[5][0]:
            parts.append(f"and was held by {', '.join(row[5])}")
        
        answer = ", ".join(parts) + "."
        
        return QueryResult(
            query_type="object_info",
            question=question,
            answer=answer,
            evidence=evidence,
            confidence=1.0,
            cypher_query=cypher,
        )
    
    def _extract_object_name(self, question: str) -> str:
        """Extract object name from question."""
        # Common COCO objects to look for
        objects = [
            "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck",
            "boat", "traffic light", "fire hydrant", "stop sign", "parking meter", "bench",
            "bird", "cat", "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe",
            "backpack", "umbrella", "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard",
            "sports ball", "kite", "baseball bat", "baseball glove", "skateboard", "surfboard",
            "tennis racket", "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl",
            "banana", "apple", "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza",
            "donut", "cake", "chair", "couch", "potted plant", "bed", "dining table", "toilet",
            "tv", "laptop", "mouse", "remote", "keyboard", "cell phone", "microwave", "oven",
            "toaster", "sink", "refrigerator", "book", "clock", "vase", "scissors", "teddy bear",
            "hair drier", "toothbrush", "monitor", "desk", "door", "window",
        ]
        
        question_lower = question.lower()
        for obj in objects:
            if obj in question_lower:
                return obj
        
        # Check for quoted terms
        import re
        quoted = re.search(r'"([^"]+)"', question)
        if quoted:
            return quoted.group(1)
        
        return "person"  # Default fallback
    
    def get_stats(self) -> Dict[str, Any]:
        """Get RAG system statistics."""
        cursor = self.backend.connection.cursor()
        
        # Count entities and relationships
        cursor.execute("MATCH (e:Entity) RETURN count(e) AS cnt")
        entity_count = cursor.fetchall()[0][0]
        
        cursor.execute("MATCH (f:Frame) RETURN count(f) AS cnt")
        frame_count = cursor.fetchall()[0][0]
        
        cursor.execute("MATCH ()-[r:OBSERVED_IN]->() RETURN count(r) AS cnt")
        obs_count = cursor.fetchall()[0][0]
        
        cursor.execute("MATCH ()-[r:NEAR]->() RETURN count(r) AS cnt")
        near_count = cursor.fetchall()[0][0]
        
        cursor.execute("MATCH ()-[r:HELD_BY]->() RETURN count(r) AS cnt")
        held_count = cursor.fetchall()[0][0]
        
        return {
            "entities": entity_count,
            "frames": frame_count,
            "observations": obs_count,
            "near_relationships": near_count,
            "held_by_relationships": held_count,
            "llm_enabled": self.llm_enabled,
            "llm_model": self.reasoning_model.config.model if self.reasoning_model else None,
        }
    
    def close(self):
        """Close connections."""
        if self.backend:
            self.backend.close()
        if self.reasoning_model:
            self.reasoning_model.clear_history()


def main():
    """Interactive RAG query interface."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Orion RAG Query Interface")
    parser.add_argument("--host", default="127.0.0.1", help="Memgraph host")
    parser.add_argument("--port", type=int, default=7687, help="Memgraph port")
    parser.add_argument("--question", "-q", help="Single question to ask")
    parser.add_argument("--no-llm", action="store_true", help="Disable LLM synthesis")
    parser.add_argument("--model", default="qwen2.5:14b-instruct-q8_0", help="LLM model")
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    
    print("Initializing Orion RAG...")
    rag = OrionRAG(
        host=args.host,
        port=args.port,
        enable_llm=not args.no_llm,
        llm_model=args.model,
    )
    
    # Show stats
    stats = rag.get_stats()
    print(f"\n📊 Database Stats:")
    print(f"   Entities: {stats['entities']}")
    print(f"   Frames: {stats['frames']}")
    print(f"   Observations: {stats['observations']}")
    print(f"   Spatial (NEAR): {stats['near_relationships']}")
    print(f"   Interactions (HELD_BY): {stats['held_by_relationships']}")
    print(f"   LLM Enabled: {stats['llm_enabled']}")
    if stats['llm_model']:
        print(f"   LLM Model: {stats['llm_model']}")
    
    if args.question:
        # Single question mode
        result = rag.query(args.question)
        print(f"\n❓ Q: {result.question}")
        print(f"💡 A: {result.answer}")
        print(f"📈 Confidence: {result.confidence:.2f}")
        print(f"⏱️  Latency: {result.latency_ms:.0f}ms")
        print(f"🔍 Evidence: {len(result.evidence)} items")
        if result.llm_used:
            print(f"🤖 LLM: Yes")
    else:
        # Interactive mode
        print("\n" + "=" * 60)
        print("Orion RAG Query Interface (Stage 5+6)")
        print("=" * 60)
        print("Example questions:")
        print("  - What objects are in the video?")
        print("  - Where did the book appear?")
        print("  - What was near the laptop?")
        print("  - What did the person interact with?")
        print("  - What happened at 25s?")
        print("  - Find objects similar to the person")
        print("Type 'exit' or 'quit' to exit, 'stats' for database stats")
        print("=" * 60)
        
        while True:
            try:
                question = input("\n❓ Q: ").strip()
                if not question:
                    continue
                if question.lower() in ("exit", "quit", "q"):
                    break
                if question.lower() == "stats":
                    stats = rag.get_stats()
                    for k, v in stats.items():
                        print(f"   {k}: {v}")
                    continue
                if question.lower() == "clear":
                    if rag.reasoning_model:
                        rag.reasoning_model.clear_history()
                    print("   Conversation history cleared")
                    continue
                
                # Stream response if LLM is enabled
                if rag.llm_enabled:
                    print("💡 A: ", end="", flush=True)
                    for token in rag.stream_query(question):
                        print(token, end="", flush=True)
                    print()
                else:
                    result = rag.query(question)
                    print(f"💡 A: {result.answer}")
                
            except KeyboardInterrupt:
                print("\n")
                break
            except Exception as e:
                print(f"❌ Error: {e}")
    
    rag.close()
    print("\n👋 Goodbye!")


if __name__ == "__main__":
    main()
