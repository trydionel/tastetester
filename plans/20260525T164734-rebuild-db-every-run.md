# Rebuild listening.db every run

## Motivation

The flow selects a tiny subset of the full dataset (`.head(10)` on artists,
`.head(50)` on tracks). Changing which rows end up in that subset changes which
genre columns appear, which changes the vector dimension. The existing migration
logic (compare stored dims, drop/recreate vec0 table) is fragile — it failed
when vec0 shadow tables persisted after DROP, requiring a custom cleanup method.
Since the DB is rebuilt from scratch on every successful run anyway, the
simplest and most robust approach is to delete the database file at the start of
`analyze_tracks`.

## Changes

### 1. `etl/flows/analyze_tracks.py`

Add `Path(db_path).unlink(missing_ok=True)` before `ListeningVectorStore` is
used. Also add `from pathlib import Path` at the top.

### 2. `etl/common/vectorstore.py`

Simplify `_ensure_content_table` — always DROP + CREATE unconditionally instead
of checking existing dimensions. Remove `_drop_vec0_table` and `_parse_vec_dim`
(single-use private methods, no longer needed).

### Not changing

- All other DB tables (`track_details`, `vector_registry`) are rebuilt fresh
  inside `_ensure_tables` via `CREATE TABLE IF NOT EXISTS` → `INSERT OR REPLACE`
  — no migration needed.
- `main.py` — unchanged.
- `bin/rerun-flow` — unchanged.
