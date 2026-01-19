"""Main pipeline for processing search history into simplicial knowledge graph.

Implements:
1. Parse search history entries
2. Extract entities and relationships via LLM
3. Store vertices and edges
4. Construct witness complexes (temporal and location-based)
"""

import json
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from database import get_connection, init_database
from extraction import (
    EntityExtractor,
    KnowledgeStore,
    extract_notification_topics,
    parse_title,
)
from simplex_tree import SimplexTree


CHECKPOINT_FILE = "checkpoint.json"


def extract_location(entry: dict) -> str | None:
    """Extract normalized location from search history entry."""
    location_infos = entry.get("locationInfos", [])
    if not location_infos:
        return None

    source = location_infos[0].get("source", "")
    match source:
        case str(s) if "Home" in s:
            return "home"
        case str(s) if "Work" in s:
            return "work"
        case _:
            return "other"


def load_checkpoint() -> dict:
    """Load checkpoint from file if it exists."""
    checkpoint_path = Path(CHECKPOINT_FILE)
    if checkpoint_path.exists():
        with open(checkpoint_path, "r") as f:
            return json.load(f)
    return {"processed_indices": [], "entries_with_vertices": []}


def save_checkpoint(processed_indices: list[int], entries_with_vertices: list[tuple[list[int], str]]):
    """Save checkpoint to file."""
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump({
            "processed_indices": processed_indices,
            "entries_with_vertices": entries_with_vertices,
        }, f)


def parse_timestamp(time_str: str) -> datetime:
    """Parse ISO 8601 timestamp from search history."""
    return datetime.fromisoformat(time_str.replace("Z", "+00:00"))


def process_entry(
    entry: dict,
    store: KnowledgeStore,
    extractor: EntityExtractor,
) -> tuple[list[int], str]:
    """
    Process a single search history entry.

    Returns:
        tuple of (vertex_ids, timestamp) for simplex construction
    """
    timestamp = entry["time"]
    activity = parse_title(entry["title"])
    vertex_ids = []

    # Handle notifications specially - topics are in subtitles
    if activity.activity_type == "notification":
        topics = extract_notification_topics(entry.get("subtitles"))
        for topic in topics:
            vid = store.get_or_create_vertex(topic, timestamp)
            vertex_ids.append(vid)
        return vertex_ids, timestamp

    # Skip entries with no content
    if not activity.content:
        return vertex_ids, timestamp

    # Extract entities and relationships via LLM
    extraction = extractor.extract(activity)

    # Create vertices for entities
    entity_to_vertex: dict[str, int] = {}
    for entity in extraction.entities:
        vid = store.get_or_create_vertex(entity, timestamp)
        entity_to_vertex[entity.lower()] = vid
        vertex_ids.append(vid)

    # Create edges for relationships
    for rel in extraction.relationships:
        subj_vid = entity_to_vertex.get(rel.subject.lower())
        obj_vid = entity_to_vertex.get(rel.object.lower())

        if subj_vid and obj_vid:
            store.create_edge(subj_vid, obj_vid, rel.predicate, timestamp)

    return vertex_ids, timestamp


class WitnessComplexBuilder:
    """
    Dynamic witness complex builder that constructs simplices at insertion time.

    Tracks:
    - Current temporal window (inserts simplex when window closes)
    - Location-based vertex sets (updates incrementally)
    """

    def __init__(self, simplex_tree: SimplexTree, window_minutes: int = 30):
        self.simplex_tree = simplex_tree
        self.window_minutes = window_minutes

        # Temporal window state
        self.temporal_vertices: set[int] = set()
        self.window_start: datetime | None = None
        self.window_end: datetime | None = None

        # Location-based state: location -> (vertex_ids, timestamps, simplex_node_id)
        # We store the node_id so we can remove old simplex before inserting updated one
        self.location_vertices: dict[str, set[int]] = defaultdict(set)
        self.location_timestamps: dict[str, list[datetime]] = defaultdict(list)
        self.location_simplex_ids: dict[str, int | None] = {}

    def add_entry(self, vertex_ids: list[int], timestamp: datetime, location: str | None):
        """
        Process a new entry and update witness complexes dynamically.

        - Temporal: If entry is within window, extend it. Otherwise, close current
          window (insert simplex) and start new one.
        - Location: Add vertices to location set and update the location simplex.
        """
        if not vertex_ids:
            return

        # === Temporal witness complex ===
        if self.window_start is None or self.window_end is None:
            # First entry - start new window
            self.temporal_vertices = set(vertex_ids)
            self.window_start = timestamp
            self.window_end = timestamp
        elif timestamp - self.window_end <= timedelta(minutes=self.window_minutes):
            # Within window - extend it
            self.temporal_vertices.update(vertex_ids)
            self.window_end = timestamp
        else:
            # Outside window - close current and start new
            self._flush_temporal_window()
            self.temporal_vertices = set(vertex_ids)
            self.window_start = timestamp
            self.window_end = timestamp

        # === Location witness complex ===
        if location:
            self.location_vertices[location].update(vertex_ids)
            self.location_timestamps[location].append(timestamp)
            self._update_location_simplex(location)

    def _flush_temporal_window(self):
        """Insert current temporal window as simplex if it has 2+ vertices."""
        if len(self.temporal_vertices) >= 2 and self.window_start and self.window_end:
            self.simplex_tree.insert_simplex(
                list(self.temporal_vertices),
                "temporal",
                {
                    "window_start": self.window_start.isoformat(),
                    "window_end": self.window_end.isoformat(),
                    "window_minutes": self.window_minutes,
                },
            )

    def _update_location_simplex(self, location: str):
        """Update the simplex for a location (remove old, insert new)."""
        vertices = self.location_vertices[location]
        if len(vertices) < 2:
            return

        timestamps = self.location_timestamps[location]

        # Remove old simplex if it exists
        old_id = self.location_simplex_ids.get(location)
        if old_id is not None:
            # We need to find and remove the old simplex
            # For now, we'll just insert a new one - duplicates are handled by simplex tree
            pass

        # Insert updated simplex
        node_id = self.simplex_tree.insert_simplex(
            list(vertices),
            "location",
            {
                "location": location,
                "first_seen": min(timestamps).isoformat(),
                "last_seen": max(timestamps).isoformat(),
                "entry_count": len(timestamps),
            },
        )
        self.location_simplex_ids[location] = node_id

    def finalize(self):
        """Flush any remaining state (call at end of processing)."""
        self._flush_temporal_window()


def run_pipeline(
    search_history_path: str,
    db_path: str = "knowledge_graph.db",
    user_id: int = 1,
    window_minutes: int = 30,
    limit: int | None = None,
    delay: float = 0.1,
    resume: bool = True,
):
    """
    Run the full pipeline to process search history into knowledge graph.

    Args:
        search_history_path: Path to search_history.json
        db_path: Path to SQLite database
        user_id: User ID for multi-tenant support
        window_minutes: Temporal window size for witness complex (default 30)
        limit: Optional limit on number of entries to process
        delay: Delay between API calls in seconds (rate limiting)
        resume: Whether to resume from checkpoint
    """
    # Initialize database
    init_database(db_path)
    conn = get_connection(db_path)

    # Initialize components
    extractor = EntityExtractor()
    store = KnowledgeStore(conn, user_id, extractor)
    simplex_tree = SimplexTree(conn, user_id)

    # Dynamic witness complex builder - constructs simplices at insertion time
    witness_builder = WitnessComplexBuilder(simplex_tree, window_minutes)

    # Load search history
    with open(search_history_path, "r") as f:
        data = json.load(f)

    if limit:
        data = data[:limit]

    # Load checkpoint if resuming
    checkpoint = load_checkpoint() if resume else {"processed_indices": [], "entries_with_vertices": []}
    processed_indices = set(checkpoint["processed_indices"])
    entries_with_vertices: list[tuple[list[int], str]] = checkpoint["entries_with_vertices"]

    if processed_indices:
        print(f"Resuming from checkpoint: {len(processed_indices)} entries already processed")

    total = len(data)
    remaining = total - len(processed_indices)
    print(f"Processing {remaining} entries (of {total} total)...")

    try:
        for i, entry in enumerate(data):
            if i in processed_indices:
                continue

            vertex_ids, timestamp = process_entry(entry, store, extractor)

            if vertex_ids:
                entries_with_vertices.append((vertex_ids, timestamp))

                # Dynamic simplex construction at insertion time
                location = extract_location(entry)
                witness_builder.add_entry(
                    vertex_ids,
                    parse_timestamp(timestamp),
                    location,
                )

            processed_indices.add(i)

            # Progress update and checkpoint every 10 entries
            if len(processed_indices) % 10 == 0:
                save_checkpoint(list(processed_indices), entries_with_vertices)
                print(f"  Processed {len(processed_indices)}/{total} entries (checkpointed)")

            # Rate limiting
            time.sleep(delay)

    except KeyboardInterrupt:
        print("\nInterrupted! Saving checkpoint...")
        save_checkpoint(list(processed_indices), entries_with_vertices)
        witness_builder.finalize()  # Flush remaining temporal window
        print(f"Checkpoint saved. Resume with: python pipeline.py {search_history_path}")
        conn.close()
        return

    # Final checkpoint save
    save_checkpoint(list(processed_indices), entries_with_vertices)

    # Flush any remaining temporal window
    witness_builder.finalize()

    print(f"Extracted vertices from {len(entries_with_vertices)} entries")
    print("Pipeline complete!")

    # Print summary stats
    vertex_count = conn.execute(
        "SELECT COUNT(*) FROM user_knowledge_vertex WHERE user_id = ?",
        (user_id,),
    ).fetchone()[0]

    edge_count = conn.execute(
        "SELECT COUNT(*) FROM user_knowledge_edge WHERE user_id = ?",
        (user_id,),
    ).fetchone()[0]

    simplex_count = conn.execute(
        "SELECT COUNT(*) FROM simplex_vertex WHERE user_id = ?",
        (user_id,),
    ).fetchone()[0]

    print(f"\nSummary:")
    print(f"  Vertices: {vertex_count}")
    print(f"  Edges: {edge_count}")
    print(f"  Simplex nodes: {simplex_count}")

    conn.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Process search history into knowledge graph")
    parser.add_argument("input", nargs="?", default="search_history.json", help="Path to search_history.json")
    parser.add_argument("--db", default="knowledge_graph.db", help="Path to SQLite database")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of entries to process")
    parser.add_argument("--window", type=int, default=30, help="Temporal window size in minutes")
    parser.add_argument("--delay", type=float, default=0.1, help="Delay between API calls in seconds")
    parser.add_argument("--no-resume", action="store_true", help="Start fresh, ignore checkpoint")

    args = parser.parse_args()
    run_pipeline(
        args.input,
        args.db,
        limit=args.limit,
        window_minutes=args.window,
        delay=args.delay,
        resume=not args.no_resume,
    )
