# Track Details Table — Denormalized metadata store

## Motivation

The enriched `tracks.parquet` has ~50 columns (audio features, behavioral stats,
23 genre booleans, album metadata), but the SQLite DB only exposes 5 behavioral
scalars and a 3-field metadata JSON next to each vector. Getting full metadata
requires joining back to parquet files. A single `track_details` table gives
one-JOIN access to everything after similarity search.

## Proposed schema

```sql
CREATE TABLE track_details (
  spotify_track_uri TEXT PRIMARY KEY,
  -- Identity
  track_name TEXT,
  artist_name TEXT,
  album_name TEXT,
  -- Behavioral
  total_plays INTEGER,
  total_playtime_ms INTEGER,
  years_listened INTEGER,
  most_recent_year INTEGER,
  peak_year REAL,
  -- Audio features (from reccobeats)
  danceability REAL, energy REAL, tempo REAL, acousticness REAL,
  valence REAL, instrumentalness REAL, liveness REAL,
  speechiness REAL, loudness REAL,
  -- Artist genres (collapsed from 23+ binary columns into a JSON array)
  genres TEXT,
  -- Album metadata
  total_tracks INTEGER,
  release_date_year INTEGER
);
```

## Query pattern

```sql
SELECT td.*, v.distance
FROM track_content_vectors v
JOIN track_details td ON v.entity_key = td.spotify_track_uri
WHERE v.vector MATCH ?
ORDER BY v.distance LIMIT 10;
```

## Changes

| File | Change |
|---|---|
| `etl/common/vector_schemas.py` | Add `TRACK_DETAILS_COLS` dict: DB column → DataFrame column |
| `etl/common/vectorstore.py` | Add `store_track_details(df)` method: collapse genre booleans to JSON, select/rename, bulk insert |
| `etl/flows/analyze_tracks.py` | Add `store_track_details` task; replace `store_track_behavior` call with it; remove old task |
| `AGENTS.md` | Update embedding store docs: `track_details` replaces `track_behavior` |

## Non-goals

- `main.py` — flow ordering stays the same
- Existing parquet outputs — still written
- `track_content_vectors` — untouched
- Artist, album, genre flows — untouched
- `track_behavior` table — removed in the same pass (not kept as transition)
