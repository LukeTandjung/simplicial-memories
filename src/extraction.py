"""Entity extraction and knowledge graph construction pipeline.

Uses DedalusLabs SDK for embeddings and LLM-based triple extraction.
"""

import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime

from dedalus_labs import Dedalus
from pydantic import BaseModel

from database import json_serialize


# --- Pydantic models for structured LLM output ---


class Relationship(BaseModel):
    subject: str
    predicate: str  # e.g., "located_in", "is_a", "related_to"
    object: str


class ExtractionResult(BaseModel):
    entities: list[str]
    relationships: list[Relationship]


# --- Activity parsing ---


@dataclass
class ParsedActivity:
    activity_type: str  # searched, visited, viewed, notification, unknown
    content: str  # the search query, URL, place name, or topic
    raw_title: str


def parse_title(title: str) -> ParsedActivity:
    """Parse the title field to extract activity type and content."""
    match title:
        case str(s) if s.startswith("Searched for "):
            return ParsedActivity("searched", s[13:], title)
        case str(s) if s.startswith("Visited "):
            return ParsedActivity("visited", s[8:], title)
        case str(s) if s.startswith("Viewed "):
            return ParsedActivity("viewed", s[7:], title)
        case "1 notification":
            return ParsedActivity("notification", "", title)
        case "Used Search" | "Ran internet speed test":
            return ParsedActivity("unknown", "", title)
        case _:
            return ParsedActivity("unknown", title, title)


def extract_notification_topics(subtitles: list[dict] | None) -> list[str]:
    """Extract topics from notification subtitles."""
    if not subtitles:
        return []

    topics = []
    for subtitle in subtitles:
        name = subtitle.get("name", "")
        if name and name != "Including topics:":
            topics.append(name)
    return topics


# --- LLM-based extraction ---


EXTRACTION_PROMPT = """Extract entities and relationships from this search activity.

Activity type: {activity_type}
Content: {content}

Rules:
- Extract concrete entities (people, places, organizations, products, concepts)
- For search queries, extract the main topics/concepts being searched
- For URLs, extract the domain and any identifiable entities from the path
- For place names, extract the place and any location hierarchy (city, country)
- Relationships should capture semantic connections between extracted entities
- Common relationship types: located_in, is_a, related_to, part_of, about

Examples:

Activity: searched "best restaurants jodhpur"
Entities: ["restaurants", "jodhpur"]
Relationships: [("restaurants", "located_in", "jodhpur")]

Activity: visited "Jules & Jim Hotel, Marais | Official site"
Entities: ["Jules & Jim Hotel", "Marais", "hotel"]
Relationships: [("Jules & Jim Hotel", "is_a", "hotel"), ("Jules & Jim Hotel", "located_in", "Marais")]

Activity: viewed "Indana Palace Jodhpur"
Entities: ["Indana Palace", "Jodhpur"]
Relationships: [("Indana Palace", "located_in", "Jodhpur")]

Now extract from the given activity. Return only entities and relationships that are clearly present."""


class EntityExtractor:
    """Extract entities and relationships using DedalusLabs SDK."""

    def __init__(self):
        api_key = os.environ.get("DEDALUS_API_KEY")
        if not api_key:
            raise RuntimeError("DEDALUS_API_KEY environment variable not set")
        self.client = Dedalus(api_key=api_key)
        self.embedding_model = "openai/text-embedding-3-small"
        self.extraction_model = "openai/gpt-4o-mini"

    def extract(self, activity: ParsedActivity) -> ExtractionResult:
        """Extract entities and relationships from a parsed activity."""
        if not activity.content:
            return ExtractionResult(entities=[], relationships=[])

        prompt = EXTRACTION_PROMPT.format(
            activity_type=activity.activity_type,
            content=activity.content,
        )

        result = self.client.chat.completions.parse(
            model=self.extraction_model,
            messages=[{"role": "user", "content": prompt}],
            response_format=ExtractionResult,
        )

        return result.choices[0].message.parsed

    def embed(self, text: str) -> list[float]:
        """Generate embedding for text using DedalusLabs."""
        response = self.client.embeddings.create(
            model=self.embedding_model,
            input=text,
        )
        return response.data[0].embedding

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        if not texts:
            return []

        response = self.client.embeddings.create(
            model=self.embedding_model,
            input=texts,
        )
        return [item.embedding for item in response.data]


# --- Vertex and Edge management ---


class KnowledgeStore:
    """Manages vertex and edge storage with canonicalization."""

    def __init__(self, conn: sqlite3.Connection, user_id: int, extractor: EntityExtractor):
        self.conn = conn
        self.user_id = user_id
        self.extractor = extractor
        self._vertex_cache: dict[str, int] = {}  # content -> vertex_id
        self._load_vertex_cache()

    def _load_vertex_cache(self):
        """Load existing vertices into cache for canonicalization."""
        rows = self.conn.execute(
            "SELECT vertex_id, content FROM user_knowledge_vertex WHERE user_id = ?",
            (self.user_id,),
        ).fetchall()
        for row in rows:
            self._vertex_cache[row["content"].lower()] = row["vertex_id"]

    def get_or_create_vertex(self, content: str, timestamp: str) -> int:
        """Get existing vertex or create new one (canonicalization)."""
        canonical = content.lower().strip()

        if canonical in self._vertex_cache:
            vertex_id = self._vertex_cache[canonical]
            self._update_vertex_metadata(vertex_id, timestamp)
            return vertex_id

        # Create new vertex
        embedding = self.extractor.embed(content)
        meta_data = {
            "first_seen": timestamp,
            "last_seen": timestamp,
            "frequency": 1,
        }

        cursor = self.conn.execute(
            """
            INSERT INTO user_knowledge_vertex (user_id, embedding, content, meta_data)
            VALUES (?, ?, ?, ?)
            """,
            (self.user_id, json_serialize(embedding), content, json_serialize(meta_data)),
        )
        vertex_id = cursor.lastrowid
        if vertex_id is None:
            raise RuntimeError("Failed to insert vertex")
        self._vertex_cache[canonical] = vertex_id
        self.conn.commit()

        return vertex_id

    def _update_vertex_metadata(self, vertex_id: int, timestamp: str):
        """Update vertex metadata with new occurrence."""
        row = self.conn.execute(
            "SELECT meta_data FROM user_knowledge_vertex WHERE vertex_id = ?",
            (vertex_id,),
        ).fetchone()

        meta_data = json.loads(row["meta_data"])
        meta_data["frequency"] = meta_data.get("frequency", 0) + 1
        meta_data["last_seen"] = timestamp

        self.conn.execute(
            "UPDATE user_knowledge_vertex SET meta_data = ? WHERE vertex_id = ?",
            (json_serialize(meta_data), vertex_id),
        )
        self.conn.commit()

    def create_edge(
        self,
        tail_vertex: int,
        head_vertex: int,
        relationship: str,
        timestamp: str,
    ) -> int:
        """Create an edge between two vertices."""
        # Check if edge already exists
        existing = self.conn.execute(
            """
            SELECT edge_id FROM user_knowledge_edge
            WHERE user_id = ? AND tail_vertex = ? AND head_vertex = ? AND content = ?
            """,
            (self.user_id, tail_vertex, head_vertex, relationship),
        ).fetchone()

        if existing:
            return existing["edge_id"]

        meta_data = {"created_at": timestamp}
        cursor = self.conn.execute(
            """
            INSERT INTO user_knowledge_edge (user_id, tail_vertex, head_vertex, content, meta_data)
            VALUES (?, ?, ?, ?, ?)
            """,
            (self.user_id, tail_vertex, head_vertex, relationship, json_serialize(meta_data)),
        )
        self.conn.commit()
        edge_id = cursor.lastrowid
        if edge_id is None:
            raise RuntimeError("Failed to insert edge")
        return edge_id
