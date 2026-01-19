"""Main pipeline for processing search history into simplicial knowledge graph.

Implements:
1. Parse search history entries
2. Extract entities and relationships via LLM
3. Store vertices and edges
4. Construct temporal witness complexes (simplices)
"""

import json
import time
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


def build_temporal_windows(
    entries_with_vertices: list[tuple[list[int], datetime]],
    window_minutes: int = 5,
) -> list[tuple[list[int], datetime, datetime]]:
    """
    Group entries into temporal windows for witness complex construction.

    Returns:
        List of (vertex_ids, window_start, window_end) tuples
    """
    if not entries_with_vertices:
        return []

    # Sort by timestamp
    sorted_entries = sorted(entries_with_vertices, key=lambda x: x[1])

    windows = []
    current_vertices = set()
    window_start = sorted_entries[0][1]
    window_end = window_start

    for vertex_ids, timestamp in sorted_entries:
        # Check if this entry falls within the current window
        if timestamp - window_end <= timedelta(minutes=window_minutes):
            current_vertices.update(vertex_ids)
            window_end = timestamp
        else:
            # Save current window if it has 2+ vertices
            if len(current_vertices) >= 2:
                windows.append((list(current_vertices), window_start, window_end))

            # Start new window
            current_vertices = set(vertex_ids)
            window_start = timestamp
            window_end = timestamp

    # Don't forget the last window
    if len(current_vertices) >= 2:
        windows.append((list(current_vertices), window_start, window_end))

    return windows


def run_pipeline(
    search_history_path: str,
    db_path: str = "knowledge_graph.db",
    user_id: int = 1,
    window_minutes: int = 5,
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
        window_minutes: Temporal window size for witness complex
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
        print(f"Checkpoint saved. Resume with: python pipeline.py {search_history_path}")
        conn.close()
        return

    # Final checkpoint save
    save_checkpoint(list(processed_indices), entries_with_vertices)
    print(f"Extracted vertices from {len(entries_with_vertices)} entries")

    # Build temporal windows (convert string timestamps to datetime)
    entries_for_windows = [
        (vids, parse_timestamp(ts)) for vids, ts in entries_with_vertices
    ]
    windows = build_temporal_windows(entries_for_windows, window_minutes)
    print(f"Built {len(windows)} temporal windows")

    # Create simplices for each window
    for vertex_ids, window_start, window_end in windows:
        meta_data = {
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
            "window_minutes": window_minutes,
        }
        simplex_tree.insert_simplex(vertex_ids, "temporal", meta_data)

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
    parser.add_argument("input", nargs="?", default="../search_history.json", help="Path to search_history.json")
    parser.add_argument("--db", default="knowledge_graph.db", help="Path to SQLite database")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of entries to process")
    parser.add_argument("--window", type=int, default=5, help="Temporal window size in minutes")
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
