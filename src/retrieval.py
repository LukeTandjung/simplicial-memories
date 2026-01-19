"""Retrieval pipeline for simplicial knowledge graph.

Implements Section VI of the paper:
1. Vertex Matching - ANN search over embeddings
2. Coface Lookup - Find simplices containing matched vertices
3. Filtration Comparison - Detect knowledge gaps
4. Gap-Driven Inference - Surface holes as implicit queries
"""

import json
import math
import sqlite3
from dataclasses import dataclass

from extraction import EntityExtractor
from simplex_tree import SimplexTree


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


@dataclass
class MatchedVertex:
    vertex_id: int
    content: str
    similarity: float
    meta_data: dict


@dataclass
class Coface:
    vertex_ids: list[int]
    simplex_type: str  # "temporal" or "location"
    meta_data: dict


@dataclass
class RetrievalResult:
    matched_vertices: list[MatchedVertex]
    cofaces: list[Coface]
    knowledge_gaps: list[list[int]]
    context_vertices: dict[int, str]  # vertex_id -> content
    edges: list[tuple[str, str, str]]  # (subject, relation, object)


class KnowledgeRetriever:
    """Retrieves relevant context from the simplicial knowledge graph."""

    def __init__(self, conn: sqlite3.Connection, user_id: int, extractor: EntityExtractor):
        self.conn = conn
        self.user_id = user_id
        self.extractor = extractor
        self.simplex_tree = SimplexTree(conn, user_id)

    def retrieve(self, query: str, top_k: int = 10, similarity_threshold: float = 0.5) -> RetrievalResult:
        """
        Full retrieval pipeline.

        Args:
            query: Natural language query
            top_k: Maximum number of vertices to match
            similarity_threshold: Minimum cosine similarity for vertex matching

        Returns:
            RetrievalResult with matched vertices, cofaces, gaps, and context
        """
        # Step 1: Vertex Matching
        matched_vertices = self.match_vertices(query, top_k, similarity_threshold)

        if not matched_vertices:
            return RetrievalResult(
                matched_vertices=[],
                cofaces=[],
                knowledge_gaps=[],
                context_vertices={},
                edges=[],
            )

        # Step 2: Coface Lookup
        vertex_ids = [v.vertex_id for v in matched_vertices]
        raw_cofaces = self.simplex_tree.locate_cofaces(vertex_ids, include_metadata=True)

        # Convert to Coface objects
        cofaces = [
            Coface(vertex_ids=vids, simplex_type=stype, meta_data=meta)
            for vids, stype, meta in raw_cofaces
        ]

        # Collect all vertices in cofaces
        all_vertex_ids = set()
        for coface in cofaces:
            all_vertex_ids.update(coface.vertex_ids)

        # Step 3: Filtration Comparison (Gap Detection)
        knowledge_gaps = self.detect_gaps([c.vertex_ids for c in cofaces])

        # Step 4: Build context
        context_vertices = self._get_vertex_contents(all_vertex_ids)
        edges = self._get_edges(all_vertex_ids)

        return RetrievalResult(
            matched_vertices=matched_vertices,
            cofaces=cofaces,
            knowledge_gaps=knowledge_gaps,
            context_vertices=context_vertices,
            edges=edges,
        )

    def match_vertices(
        self, query: str, top_k: int = 10, similarity_threshold: float = 0.5
    ) -> list[MatchedVertex]:
        """
        Step 1: Vertex Matching via ANN search.

        Embeds the query and finds similar vertices using brute-force cosine similarity.
        Production systems would use pgvector, Pinecone, FAISS, etc.
        """
        query_embedding = self.extractor.embed(query)

        # Fetch all vertices with embeddings
        rows = self.conn.execute(
            """
            SELECT vertex_id, content, embedding, meta_data
            FROM user_knowledge_vertex
            WHERE user_id = ?
            """,
            (self.user_id,),
        ).fetchall()

        # Compute similarities
        scored = []
        for row in rows:
            embedding = json.loads(row["embedding"])
            similarity = cosine_similarity(query_embedding, embedding)
            if similarity >= similarity_threshold:
                scored.append((row, similarity))

        # Sort by similarity and take top_k
        scored.sort(key=lambda x: x[1], reverse=True)
        top_matches = scored[:top_k]

        return [
            MatchedVertex(
                vertex_id=row["vertex_id"],
                content=row["content"],
                similarity=sim,
                meta_data=json.loads(row["meta_data"]),
            )
            for row, sim in top_matches
        ]

    def detect_gaps(self, cofaces: list[list[int]]) -> list[list[int]]:
        """
        Step 3: Filtration Comparison.

        For each coface, enumerate theoretical faces and check which are missing.
        Missing faces represent knowledge gaps.
        """
        gaps = []
        seen_faces = set()

        for coface in cofaces:
            if len(coface) < 2:
                continue

            theoretical_faces = SimplexTree.enumerate_theoretical_faces(coface)

            for face in theoretical_faces:
                face_tuple = tuple(face)
                if face_tuple in seen_faces:
                    continue
                seen_faces.add(face_tuple)

                # Check if this face exists in the database
                if len(face) > 1:  # Only check faces with 2+ vertices
                    exists = self.simplex_tree.search_simplex(face)
                    if exists is None:
                        gaps.append(face)

        return gaps

    def _get_vertex_contents(self, vertex_ids: set[int]) -> dict[int, str]:
        """Fetch content for a set of vertex IDs."""
        if not vertex_ids:
            return {}

        placeholders = ",".join("?" * len(vertex_ids))
        rows = self.conn.execute(
            f"""
            SELECT vertex_id, content
            FROM user_knowledge_vertex
            WHERE vertex_id IN ({placeholders})
            """,
            tuple(vertex_ids),
        ).fetchall()

        return {row["vertex_id"]: row["content"] for row in rows}

    def _get_edges(self, vertex_ids: set[int]) -> list[tuple[str, str, str]]:
        """Fetch edges between the given vertices."""
        if not vertex_ids:
            return []

        placeholders = ",".join("?" * len(vertex_ids))
        rows = self.conn.execute(
            f"""
            SELECT v1.content as subject, e.content as relation, v2.content as object
            FROM user_knowledge_edge e
            JOIN user_knowledge_vertex v1 ON e.tail_vertex = v1.vertex_id
            JOIN user_knowledge_vertex v2 ON e.head_vertex = v2.vertex_id
            WHERE e.tail_vertex IN ({placeholders})
              AND e.head_vertex IN ({placeholders})
            """,
            tuple(vertex_ids) + tuple(vertex_ids),
        ).fetchall()

        return [(row["subject"], row["relation"], row["object"]) for row in rows]

    def format_context(self, result: RetrievalResult) -> str:
        """Format retrieval result as context string for LLM consumption."""
        lines = []

        if result.matched_vertices:
            lines.append("=== Matched Entities ===")
            for v in result.matched_vertices:
                lines.append(f"  - {v.content} (similarity: {v.similarity:.2f})")

        if result.cofaces:
            lines.append("\n=== Co-occurrence Patterns (Simplices) ===")
            for coface in result.cofaces[:10]:  # Limit to 10
                contents = [result.context_vertices.get(vid, str(vid)) for vid in coface.vertex_ids]

                # Format context based on simplex type
                match coface.simplex_type:
                    case "temporal":
                        start = coface.meta_data.get("window_start", "?")
                        end = coface.meta_data.get("window_end", "?")
                        context = f"from {start} to {end}"
                    case "location":
                        loc = coface.meta_data.get("location", "?")
                        context = f"at {loc}"
                    case _:
                        context = coface.simplex_type

                lines.append(f"  - [{context}] {{{', '.join(contents)}}}")

        if result.edges:
            lines.append("\n=== Known Relationships ===")
            for subj, rel, obj in result.edges[:10]:  # Limit to 10
                lines.append(f"  - ({subj}) --[{rel}]--> ({obj})")

        if result.knowledge_gaps:
            lines.append("\n=== Knowledge Gaps (Unconfirmed Relationships) ===")
            for gap in result.knowledge_gaps[:5]:  # Limit to 5
                contents = [result.context_vertices.get(vid, str(vid)) for vid in gap]
                lines.append(f"  - {{{', '.join(contents)}}} - never directly observed together")

        return "\n".join(lines)


if __name__ == "__main__":
    import argparse
    from pathlib import Path

    from dotenv import load_dotenv

    load_dotenv()

    from database import get_connection

    parser = argparse.ArgumentParser(description="Query the knowledge graph")
    parser.add_argument("query", help="Natural language query")
    parser.add_argument("--db", default="knowledge_graph.db", help="Path to SQLite database")
    parser.add_argument("--top-k", type=int, default=10, help="Number of vertices to match")
    parser.add_argument("--threshold", type=float, default=0.3, help="Similarity threshold")

    args = parser.parse_args()

    conn = get_connection(args.db)
    extractor = EntityExtractor()
    retriever = KnowledgeRetriever(conn, user_id=1, extractor=extractor)

    print(f"Query: {args.query}\n")

    result = retriever.retrieve(args.query, top_k=args.top_k, similarity_threshold=args.threshold)
    print(retriever.format_context(result))

    conn.close()
