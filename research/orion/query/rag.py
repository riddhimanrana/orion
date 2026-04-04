"""
RAG Query Module for Orion
===========================

Natural language queries over video memory stored in Memgraph.

This module provides:
1. Entity queries: "Where did the book appear?"
2. Spatial queries: "What was near the laptop?"
3. Temporal queries: "What happened between frames 100-200?"
4. Interaction queries: "What did the person interact with?"

Author: Orion Research Team
Date: January 2026
"""

import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

try:
    from orion.graph.backends.memgraph import MemgraphBackend
    MEMGRAPH_AVAILABLE = True
except ImportError:
    MEMGRAPH_AVAILABLE = False
    MemgraphBackend = None


@dataclass
class QueryResult:
    """Result of a RAG query"""
    query_type: str
    question: str
    answer: str
    evidence: List[Dict[str, Any]]
    confidence: float = 0.0


class OrionRAG:
    """
    RAG (Retrieval-Augmented Generation) query interface for Orion.
    
    Queries the Memgraph graph database to answer natural language
    questions about video content.
    
    Example usage:
        rag = OrionRAG(host="127.0.0.1", port=7687)
        result = rag.query("What objects did the person interact with?")
        print(result.answer)
    """
    
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 7687,
        username: str = "memgraph",
        password: str = "memgraph",
    ):
        """Initialize RAG with Memgraph connection."""
        if not MEMGRAPH_AVAILABLE:
            raise ImportError("Memgraph backend not available. Install pymgclient.")
        
        self.backend = MemgraphBackend(
            host=host,
            port=port,
            username=username,
            password=password,
        )
        logger.info(f"RAG connected to Memgraph at {host}:{port}")
    
    def query(self, question: str) -> QueryResult:
        """
        Answer a natural language question about the video.
        
        Supported question types:
        - "What objects are in the video?"
        - "Where did X appear?"
        - "What was near X?"
        - "What did the person interact with?"
        - "What happened at time T?"
        
        Args:
            question: Natural language question
            
        Returns:
            QueryResult with answer and evidence
        """
        question_lower = question.lower()
        
        # Route to appropriate query handler
        if "what objects" in question_lower or "list objects" in question_lower:
            return self._query_all_objects(question)
        
        elif "where" in question_lower and "appear" in question_lower:
            return self._query_object_location(question)
        
        elif "near" in question_lower:
            return self._query_spatial_near(question)
        
        elif "interact" in question_lower or "held" in question_lower:
            return self._query_interactions(question)
        
        elif "time" in question_lower or "frame" in question_lower:
            return self._query_temporal(question)
        
        else:
            # Default: try to find mentioned object
            return self._query_object_info(question)
    
    def _query_all_objects(self, question: str) -> QueryResult:
        """List all objects detected in the video."""
        cursor = self.backend.connection.cursor()
        
        cursor.execute("""
            MATCH (e:Entity)-[r:OBSERVED_IN]->(f:Frame)
            WITH e.class_name AS class, count(r) AS observations, 
                 min(f.timestamp) AS first_seen, max(f.timestamp) AS last_seen
            RETURN class, observations, first_seen, last_seen
            ORDER BY observations DESC
        """)
        
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
        )
    
    def _query_object_location(self, question: str) -> QueryResult:
        """Query where a specific object appeared."""
        # Extract object name from question
        obj_name = self._extract_object_name(question)
        
        cursor = self.backend.connection.cursor()
        cursor.execute("""
            MATCH (e:Entity {class_name: $class_name})-[r:OBSERVED_IN]->(f:Frame)
            WITH e, f, r ORDER BY f.timestamp
            RETURN e.id, collect({
                frame: f.idx,
                time: f.timestamp,
                bbox: [r.bbox_x1, r.bbox_y1, r.bbox_x2, r.bbox_y2]
            }) AS appearances
            LIMIT 1
        """, {"class_name": obj_name})
        
        results = cursor.fetchall()
        
        if not results:
            return QueryResult(
                query_type="object_location",
                question=question,
                answer=f"No '{obj_name}' found in the video.",
                evidence=[],
                confidence=0.0,
            )
        
        appearances = results[0][1]
        evidence = appearances[:10]  # Limit to 10 appearances
        
        first = appearances[0]
        last = appearances[-1]
        
        answer = f"The {obj_name} appears {len(appearances)} times, from {first['time']:.1f}s to {last['time']:.1f}s."
        
        return QueryResult(
            query_type="object_location",
            question=question,
            answer=answer,
            evidence=evidence,
            confidence=1.0 if results else 0.0,
        )
    
    def _query_spatial_near(self, question: str) -> QueryResult:
        """Query objects near a specific entity."""
        obj_name = self._extract_object_name(question)
        
        cursor = self.backend.connection.cursor()
        cursor.execute("""
            MATCH (e1:Entity {class_name: $class_name})-[r:NEAR]->(e2:Entity)
            WITH e2.class_name AS nearby, count(r) AS times, avg(r.confidence) AS avg_conf
            RETURN nearby, times, avg_conf
            ORDER BY times DESC
            LIMIT 10
        """, {"class_name": obj_name})
        
        results = cursor.fetchall()
        
        evidence = [{"nearby": row[0], "count": row[1], "avg_confidence": row[2]} for row in results]
        
        if not results:
            # Try reverse direction
            cursor.execute("""
                MATCH (e1:Entity)-[r:NEAR]->(e2:Entity {class_name: $class_name})
                WITH e1.class_name AS nearby, count(r) AS times, avg(r.confidence) AS avg_conf
                RETURN nearby, times, avg_conf
                ORDER BY times DESC
                LIMIT 10
            """, {"class_name": obj_name})
            results = cursor.fetchall()
            evidence = [{"nearby": row[0], "count": row[1], "avg_confidence": row[2]} for row in results]
        
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
        )
    
    def _query_interactions(self, question: str) -> QueryResult:
        """Query interaction relationships (HELD_BY, etc.)."""
        cursor = self.backend.connection.cursor()
        
        cursor.execute("""
            MATCH (obj:Entity)-[r:HELD_BY]->(agent:Entity)
            WITH obj.class_name AS object, agent.class_name AS holder, 
                 count(r) AS times, avg(r.confidence) AS avg_conf
            RETURN object, holder, times, avg_conf
            ORDER BY times DESC
        """)
        
        results = cursor.fetchall()
        
        evidence = [
            {"object": row[0], "holder": row[1], "count": row[2], "confidence": row[3]}
            for row in results
        ]
        
        if not results:
            answer = "No interactions (held objects) detected."
        else:
            interactions = [f"{row[0]} held by {row[1]} ({row[2]} times)" for row in results]
            answer = "Interactions: " + "; ".join(interactions)
        
        return QueryResult(
            query_type="interactions",
            question=question,
            answer=answer,
            evidence=evidence,
            confidence=1.0 if results else 0.0,
        )
    
    def _query_temporal(self, question: str) -> QueryResult:
        """Query what happened at a specific time or frame range."""
        # Extract time/frame from question
        import re
        
        # Try to extract time in seconds
        time_match = re.search(r'(\d+(?:\.\d+)?)\s*s(?:ec)?', question)
        frame_match = re.search(r'frame[s]?\s*(\d+)', question)
        
        cursor = self.backend.connection.cursor()
        
        if time_match:
            target_time = float(time_match.group(1))
            cursor.execute("""
                MATCH (e:Entity)-[r:OBSERVED_IN]->(f:Frame)
                WHERE abs(f.timestamp - $target_time) < 2.0
                RETURN e.class_name AS class, f.idx AS frame, f.timestamp AS time
                ORDER BY f.timestamp
            """, {"target_time": target_time})
        elif frame_match:
            target_frame = int(frame_match.group(1))
            cursor.execute("""
                MATCH (e:Entity)-[r:OBSERVED_IN]->(f:Frame)
                WHERE abs(f.idx - $target_frame) < 20
                RETURN e.class_name AS class, f.idx AS frame, f.timestamp AS time
                ORDER BY f.idx
            """, {"target_frame": target_frame})
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
        )
    
    def _query_object_info(self, question: str) -> QueryResult:
        """General query about a specific object."""
        obj_name = self._extract_object_name(question)
        
        cursor = self.backend.connection.cursor()
        cursor.execute("""
            MATCH (e:Entity {class_name: $class_name})-[r:OBSERVED_IN]->(f:Frame)
            WITH e, count(r) AS obs_count, 
                 min(f.timestamp) AS first, max(f.timestamp) AS last
            OPTIONAL MATCH (e)-[held:HELD_BY]->(holder:Entity)
            RETURN e.id, e.class_name, obs_count, first, last, 
                   collect(DISTINCT holder.class_name) AS holders
        """, {"class_name": obj_name})
        
        results = cursor.fetchall()
        
        if not results:
            return QueryResult(
                query_type="object_info",
                question=question,
                answer=f"No information found about '{obj_name}'.",
                evidence=[],
                confidence=0.0,
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
        )
    
    def _extract_object_name(self, question: str) -> str:
        """Extract object name from question."""
        # Common objects to look for
        objects = [
            "laptop", "keyboard", "mouse", "book", "person", "bed", "sink",
            "remote", "cell phone", "phone", "suitcase", "tv", "monitor",
            "chair", "desk", "couch", "refrigerator", "door", "bottle",
            "cup", "backpack", "handbag", "clock"
        ]
        
        question_lower = question.lower()
        for obj in objects:
            if obj in question_lower:
                return obj
        
        # Default to extracting the quoted word or last noun
        import re
        quoted = re.search(r'"([^"]+)"', question)
        if quoted:
            return quoted.group(1)
        
        return "person"  # Default fallback
    
    def close(self):
        """Close Memgraph connection."""
        if self.backend:
            self.backend.close()


def main():
    """Test RAG queries."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test Orion RAG queries")
    parser.add_argument("--host", default="127.0.0.1", help="Memgraph host")
    parser.add_argument("--port", type=int, default=7687, help="Memgraph port")
    parser.add_argument("--question", "-q", help="Question to ask")
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO)
    
    rag = OrionRAG(host=args.host, port=args.port)
    
    if args.question:
        result = rag.query(args.question)
        print(f"\nQ: {result.question}")
        print(f"A: {result.answer}")
        print(f"Confidence: {result.confidence:.2f}")
        print(f"Evidence: {len(result.evidence)} items")
    else:
        # Interactive mode
        print("Orion RAG Query Interface")
        print("=" * 50)
        print("Example questions:")
        print("  - What objects are in the video?")
        print("  - Where did the book appear?")
        print("  - What was near the laptop?")
        print("  - What did the person interact with?")
        print("  - What happened at 25s?")
        print("=" * 50)
        
        while True:
            try:
                question = input("\nQ: ").strip()
                if not question or question.lower() in ("exit", "quit", "q"):
                    break
                
                result = rag.query(question)
                print(f"A: {result.answer}")
                
            except KeyboardInterrupt:
                break
    
    rag.close()


if __name__ == "__main__":
    main()
