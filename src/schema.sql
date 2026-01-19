-- SQLite schema for simplicial complex knowledge graph
-- Adapted from paper: "Memory has Many Faces: Simplicial Complexes as Agent Memory Layers"
-- Note: SQLite uses B-tree indexes (O(log n)) instead of HASH indexes (O(1))

CREATE TABLE IF NOT EXISTS user_knowledge_vertex (
    vertex_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    embedding TEXT NOT NULL,  -- JSON array of floats
    content TEXT NOT NULL,
    meta_data TEXT DEFAULT '{}'  -- JSON object
);

CREATE TABLE IF NOT EXISTS user_knowledge_edge (
    edge_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    tail_vertex INTEGER REFERENCES user_knowledge_vertex(vertex_id),
    head_vertex INTEGER REFERENCES user_knowledge_vertex(vertex_id),
    content TEXT,  -- relationship label
    meta_data TEXT DEFAULT '{}'  -- JSON object
);

CREATE TABLE IF NOT EXISTS simplex_vertex (
    node_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    parent_id INTEGER REFERENCES simplex_vertex(node_id),
    vertex_id INTEGER REFERENCES user_knowledge_vertex(vertex_id),
    depth INTEGER NOT NULL,
    type TEXT,
    meta_data TEXT DEFAULT '{}'  -- JSON object
);

-- Indexes for efficient operations (B-tree, O(log n))

-- Unique constraint for non-root nodes
CREATE UNIQUE INDEX IF NOT EXISTS idx_simplex_unique
    ON simplex_vertex (user_id, parent_id, vertex_id)
    WHERE parent_id IS NOT NULL;

-- Unique constraint for root nodes
CREATE UNIQUE INDEX IF NOT EXISTS idx_simplex_root_unique
    ON simplex_vertex (user_id, vertex_id)
    WHERE parent_id IS NULL;

-- Child lookup
CREATE INDEX IF NOT EXISTS idx_children
    ON simplex_vertex (parent_id);

-- Vertex depth lookup for coface operations
CREATE INDEX IF NOT EXISTS idx_vertex_depth
    ON simplex_vertex (user_id, vertex_id, depth);

-- Parent traversal
CREATE INDEX IF NOT EXISTS idx_parent
    ON simplex_vertex (parent_id);

-- Content lookup for canonicalization
CREATE INDEX IF NOT EXISTS idx_vertex_content
    ON user_knowledge_vertex (user_id, content);

-- Edge lookup
CREATE INDEX IF NOT EXISTS idx_edge_vertices
    ON user_knowledge_edge (user_id, tail_vertex, head_vertex);
