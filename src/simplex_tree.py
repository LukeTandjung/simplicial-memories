"""Simplex tree operations for user knowledge.

Adapted from paper: "Memory has Many Faces: Simplicial Complexes as Agent Memory Layers"
Original implementation used asyncpg (PostgreSQL), this uses sqlite3.
"""

import json
import sqlite3
from typing import Literal, overload


class SimplexTree:
    """Simplex tree operations for user knowledge."""

    def __init__(self, conn: sqlite3.Connection, user_id: int):
        self.conn = conn
        self.user_id = user_id

    def search_simplex(self, vertex_ids: list[int]) -> int | None:
        """Verify whether a simplex exists. Complexity: O(j log n)"""
        if not vertex_ids:
            return None

        vertex_ids = sorted(vertex_ids)
        current_parent = None

        for vertex_id in vertex_ids:
            if current_parent is None:
                row = self.conn.execute(
                    """
                    SELECT node_id FROM simplex_vertex
                    WHERE user_id = ?
                      AND parent_id IS NULL
                      AND vertex_id = ?
                    """,
                    (self.user_id, vertex_id),
                ).fetchone()
            else:
                row = self.conn.execute(
                    """
                    SELECT node_id FROM simplex_vertex
                    WHERE user_id = ?
                      AND parent_id = ?
                      AND vertex_id = ?
                    """,
                    (self.user_id, current_parent, vertex_id),
                ).fetchone()

            if row is None:
                return None
            current_parent = row["node_id"]

        return current_parent

    def insert_simplex(
        self, vertex_ids: list[int], simplex_type: str, meta_data: dict
    ) -> int:
        """Insert a simplex. Complexity: O(j log n)"""
        if not vertex_ids:
            raise ValueError("Cannot insert empty simplex")

        vertex_ids = sorted(vertex_ids)
        current_parent: int | None = None
        current_depth = 0
        meta_json = json.dumps(meta_data)

        for vertex_id in vertex_ids:
            if current_parent is None:
                row = self.conn.execute(
                    """
                    SELECT node_id FROM simplex_vertex
                    WHERE user_id = ?
                      AND parent_id IS NULL
                      AND vertex_id = ?
                    """,
                    (self.user_id, vertex_id),
                ).fetchone()
            else:
                row = self.conn.execute(
                    """
                    SELECT node_id FROM simplex_vertex
                    WHERE user_id = ?
                      AND parent_id = ?
                      AND vertex_id = ?
                    """,
                    (self.user_id, current_parent, vertex_id),
                ).fetchone()

            if row is not None:
                current_parent = row["node_id"]
            else:
                cursor = self.conn.execute(
                    """
                    INSERT INTO simplex_vertex
                        (user_id, parent_id, vertex_id, depth, type, meta_data)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        self.user_id,
                        current_parent,
                        vertex_id,
                        current_depth + 1,
                        simplex_type,
                        meta_json,
                    ),
                )
                node_id = cursor.lastrowid
                if node_id is None:
                    raise RuntimeError("Failed to insert simplex vertex")
                current_parent = node_id

            current_depth += 1

        self.conn.commit()
        if current_parent is None:
            raise RuntimeError("No simplex vertex created")
        return current_parent

    @overload
    def locate_cofaces(
        self, vertex_ids: list[int], include_metadata: Literal[False] = False,
        max_extra_depth: int | None = None,
    ) -> list[list[int]]: ...

    @overload
    def locate_cofaces(
        self, vertex_ids: list[int], include_metadata: Literal[True],
        max_extra_depth: int | None = None,
    ) -> list[tuple[list[int], str, dict]]: ...

    def locate_cofaces(
        self, vertex_ids: list[int], include_metadata: bool = False,
        max_extra_depth: int | None = 0,
    ) -> list[list[int]] | list[tuple[list[int], str, dict]]:
        """
        Find all simplices containing vertex set. Complexity: O(k T log n)

        Args:
            vertex_ids: Vertices that must be contained in the simplex
            include_metadata: If True, return (vertices, type, meta_data) tuples
            max_extra_depth: Limit subtree traversal depth (default 2, None for unlimited)

        Returns:
            List of vertex ID lists, or list of (vertices, type, meta_data) tuples
        """
        if not vertex_ids:
            return []

        vertex_ids = sorted(vertex_ids)
        last_vertex = vertex_ids[-1]
        min_depth = len(vertex_ids)

        candidates = self.conn.execute(
            """
            SELECT node_id, depth, type, meta_data FROM simplex_vertex
            WHERE user_id = ? AND vertex_id = ? AND depth >= ?
            """,
            (self.user_id, last_vertex, min_depth),
        ).fetchall()

        cofaces = []
        for candidate in candidates:
            path = self._collect_path(candidate["node_id"])
            if self._is_subsequence(vertex_ids, path):
                if include_metadata:
                    cofaces.append((
                        path,
                        candidate["type"],
                        json.loads(candidate["meta_data"]),
                    ))
                    cofaces.extend(self._collect_subtree(
                        candidate["node_id"], path, include_metadata=True,
                        max_extra_depth=max_extra_depth,
                    ))
                else:
                    cofaces.append(path)
                    cofaces.extend(self._collect_subtree(
                        candidate["node_id"], path,
                        max_extra_depth=max_extra_depth,
                    ))

        return cofaces

    def _collect_path(self, node_id: int) -> list[int]:
        """Traverse upward from node to root."""
        vertices = []
        current_id = node_id

        while current_id is not None:
            row = self.conn.execute(
                "SELECT vertex_id, parent_id FROM simplex_vertex WHERE node_id = ?",
                (current_id,),
            ).fetchone()

            if row["vertex_id"] is not None:
                vertices.append(row["vertex_id"])
            current_id = row["parent_id"]

        return list(reversed(vertices))

    def _collect_subtree(
        self,
        root_id: int,
        root_verts: list[int],
        include_metadata: bool = False,
        max_extra_depth: int | None = None,
        current_extra_depth: int = 0,
    ) -> list[list[int]] | list[tuple[list[int], str, dict]]:
        """Collect simplices in subtree, optionally limited by depth."""
        if max_extra_depth is not None and current_extra_depth >= max_extra_depth:
            return []

        children = self.conn.execute(
            "SELECT node_id, vertex_id, type, meta_data FROM simplex_vertex WHERE parent_id = ?",
            (root_id,),
        ).fetchall()

        results: list = []
        for child in children:
            child_verts = root_verts + [child["vertex_id"]]
            if include_metadata:
                results.append((
                    child_verts,
                    child["type"],
                    json.loads(child["meta_data"]),
                ))
                results.extend(self._collect_subtree(
                    child["node_id"], child_verts, include_metadata=True,
                    max_extra_depth=max_extra_depth,
                    current_extra_depth=current_extra_depth + 1,
                ))
            else:
                results.append(child_verts)
                results.extend(self._collect_subtree(
                    child["node_id"], child_verts,
                    max_extra_depth=max_extra_depth,
                    current_extra_depth=current_extra_depth + 1,
                ))

        return results

    def _is_subsequence(self, needle: list[int], haystack: list[int]) -> bool:
        it = iter(haystack)
        return all(v in it for v in needle)

    @staticmethod
    def enumerate_theoretical_faces(vertex_ids: list[int]) -> list[list[int]]:
        """Generate all non-empty subsets. Complexity: O(2^j)"""
        vertex_ids = sorted(vertex_ids)
        n = len(vertex_ids)
        return [
            [vertex_ids[i] for i in range(n) if mask & (1 << i)]
            for mask in range(1, 2**n)
        ]

    def remove_simplex(self, vertex_ids: list[int], remove_cofaces: bool = True) -> bool:
        """Remove a simplex. Complexity: O(j log n) + O(k T log n) if removing cofaces"""
        node_id = self.search_simplex(vertex_ids)
        if node_id is None:
            return False

        if remove_cofaces:
            self.conn.execute(
                """
                WITH RECURSIVE descendants AS (
                    SELECT node_id FROM simplex_vertex WHERE parent_id = ?
                    UNION ALL
                    SELECT sv.node_id FROM simplex_vertex sv
                    JOIN descendants d ON sv.parent_id = d.node_id
                )
                DELETE FROM simplex_vertex
                WHERE node_id IN (SELECT node_id FROM descendants)
                """,
                (node_id,),
            )
        else:
            has_children = self.conn.execute(
                "SELECT EXISTS(SELECT 1 FROM simplex_vertex WHERE parent_id = ?)",
                (node_id,),
            ).fetchone()[0]

            if has_children:
                raise ValueError("Simplex has cofaces")

        self.conn.execute(
            "DELETE FROM simplex_vertex WHERE node_id = ?", (node_id,)
        )
        self.conn.commit()
        return True
