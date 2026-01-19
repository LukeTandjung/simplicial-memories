"""Database connection and initialization for SQLite."""

import json
import sqlite3
from pathlib import Path


def get_connection(db_path: str = "knowledge_graph.db") -> sqlite3.Connection:
    """Get a connection to the SQLite database."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_database(db_path: str = "knowledge_graph.db") -> None:
    """Initialize the database with the schema."""
    schema_path = Path(__file__).parent / "schema.sql"

    with open(schema_path, "r") as f:
        schema_sql = f.read()

    conn = get_connection(db_path)
    conn.executescript(schema_sql)
    conn.commit()
    conn.close()


def json_serialize(obj: dict | list) -> str:
    """Serialize a dict or list to JSON string for SQLite storage."""
    return json.dumps(obj)


def json_deserialize(s: str) -> dict | list:
    """Deserialize a JSON string from SQLite storage."""
    return json.loads(s)
