# Simplicial Knowledge Graph

A knowledge graph implementation using simplicial complexes for agent memory, based on the paper "Memory has Many Faces: Simplicial Complexes as Agent Memory Layers".

## Project Structure

```
.
├── paper/                      # Research paper and analysis
│   ├── main.typ                # Paper source (Typst)
│   └── simplex_representation.ipynb  # EDA and pipeline documentation
│
├── src/                        # Implementation
│   ├── database.py             # SQLite connection and initialization
│   ├── extraction.py           # Entity/relationship extraction via LLM
│   ├── pipeline.py             # Extraction pipeline with checkpointing
│   ├── retrieval.py            # Query pipeline (vertex matching, coface lookup, gap detection)
│   ├── simplex_tree.py         # Simplex tree data structure
│   ├── schema.sql              # Database schema
│   ├── search_history.json     # Input data (Google Takeout export)
│   └── pyproject.toml          # Python dependencies
│
├── flake.nix                   # Nix development environment
└── README.md
```

## Setup

```bash
cd src
uv sync
```

Create a `.env` file in `src/` with your API key:
```
DEDALUS_API_KEY=your_key_here
```

## Usage

**Run extraction pipeline:**
```bash
cd src
uv run python pipeline.py search_history.json --window 30 --delay 0.1
```

**Query the knowledge graph:**
```bash
cd src
uv run python retrieval.py "What hotel was I looking at in Jodhpur?" --top-k 10 --threshold 0.3
```

## How It Works

1. **Extraction**: Search history entries are parsed, entities/relationships extracted via LLM, and stored as vertices/edges in SQLite.

2. **Witness Complex Construction**: Entities that co-occur within temporal windows (30 min) or at the same location form simplices, capturing implicit relationships.

3. **Retrieval**: Queries are embedded and matched to vertices. Coface lookup surfaces related entities from the same simplices. Gap detection identifies missing faces (uncertain inferences).

See `paper/simplex_representation.ipynb` for detailed documentation.
