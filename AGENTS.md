# tastetester — agent guide

## Commands

```sh
PREFECT_API_URL=http://127.0.0.1:4200/api uv run python -m etl.main
# Or with a local prefect server:
#   uv run prefect server start --host 127.0.0.1 &; PREFECT_API_URL=... uv run python main.py

uv run python -c "..."         # one-off snippet in the venv
uv add <package>               # add a dependency
uv sync                        # sync env with lockfile
```

No tests, no CI, no linter/formatter config exist.

## Architecture

- **Entrypoint**: `main.py` — a Prefect `@flow` that chains downstream flows.
- **All flows** (`etl/flows/`) read/write Parquet files in `etl/artifacts/` (gitignored). They accept/return file paths, not DataFrames.
- **Flow dependency order**: `construct_listens_history` → `analyze_artists` + `analyze_albums` (parallel) → `analyze_tracks` → `analyze_genres`.
- **`analyze_tracks`** now also accepts `artists_parquet_path` and `albums_parquet_path`. It enriches each track with artist genre columns and album metadata before building content vectors.
- **Last.fm data** is loaded but not yet merged into listens (line 71 of `construct_listens_history.py`). `enrich_with_spotify_ids` is a no-op stub.
- The pipeline requires a Prefect API server. Run `uv run prefect server start --host 127.0.0.1` in a separate terminal, then set `PREFECT_API_URL`.

## Embedding store

At the end of `analyze_tracks`, two things are written to `etl/artifacts/listening.db`:

| Table | Type | Contents |
|---|---|---|
| `track_content_vectors` | sqlite-vec vec0 | Content vectors (audio features + artist genre profile). 32 dims currently. |
| `track_details` | regular SQLite | Denormalized row per track: identity, behavioral stats, audio features, genres (JSON array), album metadata. Supersedes former `track_behavior` table. |

### Query examples

```python
import sqlite3, sqlite_vec

conn = sqlite3.connect("etl/artifacts/listening.db")
conn.enable_load_extension(True)
sqlite_vec.load(conn)

# Find tracks similar to a given track, joined with full metadata
vec = conn.execute(
    "SELECT vector FROM track_content_vectors WHERE entity_key = ?",
    ("spotify:track:...",),
).fetchone()[0]

conn.execute("""
    SELECT td.*, v.distance
    FROM track_content_vectors v
    JOIN track_details td ON v.entity_key = td.spotify_track_uri
    WHERE v.vector MATCH ?
    ORDER BY v.distance
    LIMIT 10
""", (vec,)).fetchall()

# Look up all metadata for a single track
conn.execute(
    "SELECT * FROM track_details WHERE spotify_track_uri = ?",
    ("spotify:track:...",),
).fetchone()
```

`etl/common/vectorstore.py` wraps this in a `ListeningVectorStore` class with `similar_to_vector()`, `get_track_details()`, etc.

## Shared utilities

- `etl/common/__init__.py` — `root_path()` resolves the repo root. Use for any file path.
- `etl/common/persistence.py` — `df_to_parquet(df, path)` and `parquet_to_df(path)` are Prefect tasks.
- `etl/common/analysis.py` — `peak_year(ts)` computes weighted-average peak year.
- `etl/common/vector_schemas.py` — `CONTENT_FEATURES`, `PREDICTION_FEATURES`, `BEHAVIORAL_COLS`, and `TRACK_DETAILS_COLS` constants. `PREDICTION_FEATURES` (11 audio features) is the whitelist used by both training (`models/play_count/trainer/task.py`) and prediction (`app/recommender.py`).
- `etl/common/vectorstore.py` — `ListeningVectorStore` class for building/querying the embedding store.

## Data sources

Raw JSON (gitignored per `.gitignore`):
- `data/spotify/*.json` — Spotify streaming history exports
- `data/lastfm/*.json` — Last.fm recent tracks export (single file)

`SPOTIFY_TOKEN` in `.env` is declared but not yet consumed in code.

## External APIs

| API | Used in | Notes |
|---|---|---|
| MusicBrainz (musicbrainzngs) | `analyze_artists`, `analyze_albums` | Rate-limited. Tasks have `retries=3, retry_delay_seconds=[2,5,15]`. |
| reccobeats.com/v1/audio-features | `analyze_tracks` | 1 call/s rate limit. Batched to ≤40 track IDs. No auth key. |

## Notable quirks

- Directory is `etl/common/` (not `etl/commons/` — earlier refs in git may use the old name).
- The Docker Compose stack is for running a Prefect server/worker. Flows can also run with a local server (see Commands section).
- Prefect 3.x (not 2.x). Uses `@flow` / `@task` decorators and `prefect.artifacts.create_link_artifact`.
- `enrich_with_genres` (artists) calls `fetch_genres` inside a `df.apply()` — each row is a separate task invocation. Known performance bottleneck.
- `analyze_tracks` uses `np.array_split` in 40-track batches because the reccobeats API has a 40-ID limit.
- FIXMEs exist for: using only top-10 artists during dev, track-name dedup via levenshtein distance.
- No `tool.ruff`, `tool.pytest`, or `tool.mypy` sections in `pyproject.toml`.
- `sqlite-vec` (v0.1.9) added as a dependency. The `vectorstore.py` uses `vec0` virtual tables and the `MATCH` operator for ANN queries.
- `store_track_content_vectors` and `store_track_details` tasks use `cache_policy=NO_CACHE` because they hold an unpicklable SQLite connection.
- At training time, `train_model.py` writes `etl/artifacts/prediction_features.json` — the exact column list used by the model (11 audio features + genre columns). The recommender loads this file so both sides agree on feature order. Falls back to `PREDICTION_FEATURES` only if file is missing.
