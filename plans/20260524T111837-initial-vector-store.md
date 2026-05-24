# Embedding Store — Implementation Plan

## Goal

Build a vector embedding store so that a **new song suggestion** can be enriched via third-party APIs, converted to a rich content vector, and compared via cosine similarity against known tracks.

The track content vector collapses **audio features + artist genre profile + album metadata** into one comparison surface. Behavioral data (play counts, listening span) lives in a regular SQLite table for lookup and ranking — no need to vectorize it.

Vectors are built from existing structured data — **no text models or LLMs**.

---

## Key design decisions

### Content only is a vector — behavioral is a regular table

| Data | Storage | Why |
|---|---|---|
| **content vector** | sqlite-vec vec0 table | Cosine similarity search for matching new songs to known tracks |
| **behavioral** | regular SQLite table with scalar columns | Lookup for ranking/filtering results (`ORDER BY total_plays DESC`, `WHERE total_plays > 10`) |

A new song suggestion has no behavioral history. If combined into one vector, half the dimensions would be empty, biasing results toward low-play-count noise. Separating them means content handles similarity, behavioral handles ranking — independently and with the right tools for each.

### Collapse artist/album onto the track

Artist genre tags and album metadata are joined onto the track DataFrame during `analyze_tracks`, producing a single enriched content vector per track. `analyze_tracks` runs after `analyze_artists` and `analyze_albums` to consume their parquet outputs.

---

## New dependency

```
uv add sqlite-vec
```

---

## SQLite database

**Path:** `etl/artifacts/listening.db` (gitignored via existing `etl/artifacts/*` rule).

### Schema

```sql
-- vec0 virtual table for ANN content similarity
CREATE VIRTUAL TABLE track_content_vectors USING vec0(
  entity_key TEXT PRIMARY KEY,        -- spotify_track_uri
  metadata_json TEXT,                  -- track name, artist, album for display
  vector FLOAT[?]                      -- 10 audio + N genre:* + 2 album
);

-- regular table for behavioral data (not a vector)
CREATE TABLE track_behavior (
  spotify_track_uri TEXT PRIMARY KEY,
  track_name TEXT,
  artist_name TEXT,
  album_name TEXT,
  total_plays INTEGER,
  total_playtime_ms INTEGER,
  years_listened INTEGER,
  most_recent_year INTEGER,
  peak_year REAL
);

-- Scaler and column metadata for the content vector
CREATE TABLE vector_registry (
  subspace TEXT PRIMARY KEY,           -- "track_content"
  dimensions INTEGER NOT NULL,
  feature_columns TEXT NOT NULL,       -- JSON array of column names
  scaler BLOB,                         -- pickle of sklearn StandardScaler
  model_version TEXT DEFAULT 'v1',
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

### Design notes

- Only one vec0 table — `track_content_vectors`. Everything else is a regular table.
- sqlite-vec virtual tables don't efficiently filter by text column, but since there's only one vec0 table, that's fine.
- `vector_registry` stores the fitted `StandardScaler` as a pickle BLOB. `feature_columns` detects schema drift (e.g., a new `genre:*` column) to trigger a refit.
- Behavioral fields are stored as plain scalars — you can `WHERE total_plays > 0` or `ORDER BY peak_year DESC` in any combination.

---

## Feature vector

### Track content vector (~12 + *N* dims)

Audio features from reccobeats + artist genre profile from MusicBrainz + album metadata.

| Feature | Source column | Origin | Type |
|---|---|---|---|
| danceability | `danceability` | reccobeats | scaled |
| energy | `energy` | reccobeats | scaled |
| tempo | `tempo` | reccobeats | scaled |
| acousticness | `acousticness` | reccobeats | scaled |
| valence | `valence` | reccobeats | scaled |
| instrumentalness | `instrumentalness` | reccobeats | scaled |
| liveness | `liveness` | reccobeats | scaled |
| speechiness | `speechiness` | reccobeats | scaled |
| loudness | `loudness` | reccobeats | scaled |
| duration_ms | `duration_ms` | reccobeats | scaled |
| genre:* | one per `genre:*` column | MusicBrainz (via artist) | binary (0/1) |
| total_tracks | `total_tracks` | MusicBrainz (via album) | scaled (nullable → fill mean) |
| release_date_year | `release_date` (parse year) | MusicBrainz (via album) | scaled (nullable → drop row) |

---

## Flow dependency changes

**Current** (tracks parallel to artists/albums):

```
construct_listens_history ─┬─ analyze_artists
                           ├─ analyze_albums
                           ├─ analyze_tracks
                           └── analyze_genres
```

**New** (tracks joins artist and album parquet outputs):

```
construct_listens_history ─┬─ analyze_artists ─┐
                           ├─ analyze_albums ──┤
                           │                   ├── analyze_tracks
                           │                   │   (enrich content vec + store behavioral)
                           └── analyze_genres  │
                                                └ data flows unchanged
```

---

## New shared module: `etl/common/vectorstore.py`

```python
LISTENING_DB = "etl/artifacts/listening.db"

class ListeningVectorStore:
    def __init__(self, db_path=LISTENING_DB):
        """Open sqlite-vec connection. check_same_thread=False."""

    def ensure_tables(self):
        """CREATE VIRTUAL TABLE IF NOT EXISTS track_content_vectors.
           CREATE TABLE IF NOT EXISTS track_behavior.
           CREATE TABLE IF NOT EXISTS vector_registry."""

    def store_content_vectors(self, df, feature_cols, entity_key_col,
                              binary_cols=None, metadata_cols=None):
        """
        1. Load scaler from registry (or fit+store if first run / schema drifted).
        2. Scale numeric feature_cols; leave binary_cols as-is (already 0/1).
        3. Build metadata JSON from metadata_cols.
        4. Batch insert into track_content_vectors.
        """

    def store_behavioral_data(self, df, col_mapping):
        """Bulk insert/replace into track_behavior table.
           col_mapping = {db_column: df_column, ...}"""

    # scaler helpers
    def _load_scaler(self) -> StandardScaler | None: ...
    def _save_scaler(self, scaler, dimensions, feature_columns): ...

    # query helpers
    def similar_to_vector(self, vector, limit=10):
        """SELECT entity_key, metadata_json FROM track_content_vectors
           ORDER BY vector_distance_cosine(vector, ?) LIMIT ?"""
    def get_behavior(self, uri):
        """SELECT * FROM track_behavior WHERE spotify_track_uri = ?"""

    def close(self): ...
    def __enter__(self): return self
    def __exit__(self, *args): self.close()
```

No need for `similar_to(entity_key)` since the song-suggestion pipeline compares against an external vector, not one already in the DB.

---

## New shared module: `etl/common/vector_schemas.py`

```python
CONTENT_FEATURES = {
    "numeric": [
        "danceability", "energy", "tempo", "acousticness", "valence",
        "instrumentalness", "liveness", "speechiness", "loudness",
        "duration_ms", "total_tracks", "release_date_year",
    ],
    "binary_prefix": "genre:",       # gathered dynamically from df columns
    "entity_key": "spotify_track_uri",
    "metadata": [
        "master_metadata_track_name",
        "master_metadata_album_artist_name",
        "master_metadata_album_album_name",
    ],
}

BEHAVIORAL_COLS = {
    "total_plays": "total_plays",
    "total_playtime_ms": "total_playtime_ms",
    "years_listened": "years_listened",
    "most_recent_year": "most_recent_year",
    "peak_year": "peak_year",
}
```

---

## Integration into `analyze_tracks` — where the work happens

The flow gets two new capabilities:
1. Accept `artists_parquet_path` and `albums_parquet_path` parameters
2. After existing enrichment, join artist genres + album metadata, then build vectors + insert

```python
@task
def enrich_tracks_with_context(df_tracks, artists_path, albums_path):
    """Join artist genre profile and album metadata onto each track row."""
    df_artists = parquet_to_df(artists_path)
    df_albums = parquet_to_df(albums_path)

    genre_cols = [c for c in df_artists.columns if c.startswith("genre:")]
    df_tracks = df_tracks.merge(
        df_artists[["master_metadata_album_artist_name"] + genre_cols],
        on="master_metadata_album_artist_name", how="left"
    )
    for col in genre_cols:
        if col in df_tracks.columns:
            df_tracks[col] = df_tracks[col].fillna(0)

    df_albums_ctx = df_albums[["master_metadata_album_album_name",
                                "total_tracks", "release_date"]].copy()
    df_albums_ctx["release_date_year"] = pd.to_datetime(
        df_albums_ctx["release_date"], errors="coerce"
    ).dt.year
    df_tracks = df_tracks.merge(
        df_albums_ctx.drop(columns=["release_date"]),
        on="master_metadata_album_album_name", how="left"
    )
    df_tracks["total_tracks"] = df_tracks["total_tracks"].fillna(
        df_tracks["total_tracks"].mean()
    )

    return df_tracks

@task
def store_track_content_vectors(df_tracks_enriched, store):
    schema = CONTENT_FEATURES
    genre_cols = [c for c in df_tracks_enriched.columns
                  if c.startswith(schema["binary_prefix"])]
    store.store_content_vectors(
        df_tracks_enriched,
        feature_cols=schema["numeric"] + genre_cols,
        binary_cols=genre_cols,
        entity_key_col=schema["entity_key"],
        metadata_cols=schema["metadata"],
    )

@task
def store_track_behavior(df_tracks, store):
    store.store_behavioral_data(df_tracks, BEHAVIORAL_COLS)

@flow
def analyze_tracks(listens_parquet_path,
                   artists_parquet_path=None,
                   albums_parquet_path=None,
                   db_path=LISTENING_DB):
    df_listens = parquet_to_df(listens_parquet_path)
    df_tracks = extract_tracks(df_listens)
    df_tracks_enriched = enrich_with_audio_features(df_tracks)

    if artists_parquet_path and albums_parquet_path:
        df_tracks_enriched = enrich_tracks_with_context(
            df_tracks_enriched, artists_parquet_path, albums_parquet_path
        )

    parquet_path = str(root_path().joinpath("etl", "artifacts", "tracks.parquet"))
    df_to_parquet(df_tracks_enriched, parquet_path)

    with ListeningVectorStore(db_path) as store:
        store_track_content_vectors(df_tracks_enriched, store)
        store_track_behavior(df_tracks, store)

    return parquet_path
```

Notice: behavioral data is written from `df_tracks` (before enrichment), because we want behavior data for all tracks — even those whose artist or album wasn't in the top-10 enrichment set.

---

## Integration into `main.py`

```python
@flow
def main():
    df_listens = construct_listens_history()
    df_artists = analyze_artists(df_listens)
    df_albums = analyze_albums(df_listens)
    # Tracks now runs after artists + albums complete
    df_tracks = analyze_tracks(df_listens, df_artists, df_albums)
    df_genres = analyze_genres(df_artists, df_listens)
```

---

## Song suggestion flow (not implemented, but the store supports it)

```python
store = ListeningVectorStore()

# 1. Enrich suggestion via third-party APIs → audio features + artist genre tags
# 2. Build content vector using same feature columns + loaded scaler
content_vec = build_track_content_vector(audio_features, genre_tags, store.load_scaler())

# 3. Find nearest neighbors in track content space
results = store.similar_to_vector(content_vec, limit=20)

# 4. Re-rank by behavioral popularity
#    (simple example: multiply similarity by log(total_plays + 1))
for row in results:
    beh = store.get_behavior(row["entity_key"])
    row["score"] = row["_distance"] * math.log(beh["total_plays"] + 1)
```

---

## Not changing

- `etl/flows/construct_listens_history.py` — untouched.
- `etl/flows/analyze_artists.py` — still produces `artists.parquet` as before.
- `etl/flows/analyze_albums.py` — still produces `albums.parquet` as before.
- `etl/flows/analyze_genres.py` — still produces `genres.parquet` as before.
- Existing parquet outputs — still written; the vector store is additive.

---

## Implementation order

1. `uv add sqlite-vec` and verify it loads.
2. Create `etl/common/vector_schemas.py`.
3. Create `etl/common/vectorstore.py`.
4. Modify `etl/flows/analyze_tracks.py`:
   - Add `enrich_tracks_with_context` task.
   - Add `store_track_content_vectors` task.
   - Add `store_track_behavior` task.
   - Update `analyze_tracks` flow signature and body.
5. Update `main.py` to pass artist/album paths and ensure ordering.
6. Run `uv run python main.py` and verify the DB is populated.
