# tastetester

A song suggestion engine built from personal listening history.

## Goal

Ingest Spotify streaming history, enrich each track with audio features (via reccobeats), artist genres (via MusicBrainz), and album metadata (via MusicBrainz). Build structured feature vectors — scaled numeric audio features + binary genre profile + album metadata — and store them in a sqlite-vec database for cosine-similarity search. All track metadata is denormalized into a single table so similarity results can be explored without joining back to Parquet files.

## Project structure

```
data/              Raw JSON exports (Spotify, Last.fm, followed artists, liked songs)
etl/
  flows/           Prefect flows: listens → artists/albums/analyze_tracks/genres
  common/          Shared utilities (vector store, persistence, schemas, analysis)
  artifacts/       Outputs: Parquet files, sqlite-vec database
main.py            Pipeline entrypoint — chains all flows
bin/               Utility scripts (sqlite-vec REPL, one-shot rerun)
notebooks/         Exploration and prototyping
plans/             Design documents
```
