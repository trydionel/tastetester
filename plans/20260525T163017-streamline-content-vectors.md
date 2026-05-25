# Streamline Content Vectors — remove metadata & album features

## Rationale

1. **Metadata in `metadata_json` is redundant** now that `track_details` exists. Every query that returns similar tracks joins against `track_details` to get full metadata anyway. Storing it with the vec0 entry wastes space per vector row and complicates the store method.

2. **`total_tracks` and `release_date_year` are hard to enrich** when a user recommends a brand-new track. The audio-features API (reccobeats) returns the 9 core features; album metadata requires a separate MusicBrainz lookup that isn't wired up yet. Better to omit them from the similarity vector and add them back later if they prove valuable.

## Changes

### 1. `etl/common/vector_schemas.py`

- Remove `"total_tracks"`, `"release_date_year"` from `CONTENT_FEATURES["numeric"]`
- Remove `CONTENT_FEATURES["metadata"]` key

### 2. `etl/common/vectorstore.py`

| Method | Change |
|---|---|
| `_ensure_content_table` | Remove `metadata_json TEXT` from vec0 CREATE (table dropped & recreated by dim change anyway) |
| `store_content_vectors` | Remove `metadata_cols` parameter; drop the metadata-loop logic; simplify INSERT to `(entity_key, vector)` |
| `similar_to_vector` | Drop `metadata_json` from SELECT; remove `"metadata"` from returned dict |
| `build_track_vector` | Remove `DEFAULTS` FIXME dict (only held the two album fields); remaining features come from audio-features API |

### 3. `etl/flows/analyze_tracks.py`

- Remove `metadata_cols=sc["metadata"]` from `store.store_content_vectors()` call

### 4. `AGENTS.md`

- Update "35 dims" → "33 dims"
- Remove `metadata_json` reference from vec0 table description

## Not changing

- `TRACK_DETAILS_COLS` — `total_tracks` and `release_date_year` stay here; useful for display after similarity
- `app/recommender.py` — already uses `store.get_track_details()`, not `match['metadata']`
- `enrich_tracks_with_context` — still writes album fields to the enriched DataFrame (consumed by `track_details`)
- `store_track_details` task — unchanged

## Side effect

vec0 table drops and recreates (33 dims vs current 35). Existing vectors are rebuilt on next `bin/rerun-flow`. `track_details` table is untouched.
