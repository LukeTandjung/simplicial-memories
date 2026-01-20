# Implementation TODOs

## 1. Missing `embedding` column on `user_knowledge_edge`

**File:** `src/schema.sql:13-20`

Paper schema includes `embedding FLOAT[]` on edges for edge-based semantic search. Current implementation omits this to save time on embedding generation.

**Action:** Add when/if edge-based retrieval becomes necessary.

---

## 2. Incomplete location simplex update

**File:** `src/pipeline.py:200-205`

```python
if old_id is not None:
    # We need to find and remove the old simplex
    # For now, we'll just insert a new one
    pass  # <-- Does nothing
```

This creates duplicate location simplices as users accumulate searches at the same location. The simplex tree's uniqueness constraints only prevent exact duplicates at the node level.

**Action:** Implement proper removal of old location simplex before inserting updated version, or deduplicate at query time.

---

## 3. `construct_from_witness` architecture

**Paper:** Has `construct_from_witness` as a method on `SimplexTree` class.

**Implementation:** Uses separate `WitnessComplexBuilder` class in `pipeline.py`.

This works but deviates from paper architecture. The paper's version operates on existing `meta_data` in the database; the implementation tracks state in memory during pipeline execution.

**Action:** Document this architectural difference or refactor if needed.

---

## 4. Brute-force vector search

**File:** `src/retrieval.py:128-135`

Fetches all vertices and computes cosine similarity in Python. Fine for 1,410 entries, won't scale to 55k+.

**Action:** Consider sqlite-vec, FAISS, or similar ANN index for production use.
