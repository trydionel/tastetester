from pathlib import Path

import numpy as np
import pandas as pd

from ratelimit import limits
from prefect import flow, task
from prefect.artifacts import create_link_artifact
from prefect.cache_policies import TASK_SOURCE, INPUTS, NO_CACHE

from etl.common import root_path
from etl.common.analysis import peak_year
from etl.common.persistence import df_to_parquet, parquet_to_df
from etl.common.vector_schemas import CONTENT_FEATURES, TRACK_DETAILS_COLS
from etl.common.vectorstore import ListeningVectorStore
from etl.common.audio_features import fetch_audio_features

@task
def extract_tracks(df_listens):
  df_tracks = df_listens.groupby(by='spotify_track_uri').agg(
    master_metadata_album_artist_name=('master_metadata_album_artist_name', 'first'),
    master_metadata_album_album_name=('master_metadata_album_album_name', 'first'),
    master_metadata_track_name=('master_metadata_track_name', 'first'),
    total_plays=('ts','count'),
    total_playtime_ms=('ms_played','sum'),
    unique_tracks_played=('master_metadata_track_name', lambda track: track.str.lower().nunique()), # FIXME: use levenshtein distance to clean up track names?
    years_listened=('ts', lambda ts: ts.dt.year.nunique()),
    most_recent_year=('ts', lambda ts: ts.dt.year.max()),
    peak_year=('ts', peak_year)
  ).reset_index()

  return df_tracks

@limits(calls=1, period=1)
def get_audio_features(ids):
  return fetch_audio_features(ids)

@task(cache_policy=TASK_SOURCE + INPUTS, retries=3, retry_delay_seconds=[2, 5, 15])
def enrich_tracks(track_ids):
  features = get_audio_features(track_ids)
  metadata = features['content']

  return pd.DataFrame.from_dict(metadata)

@task
def enrich_with_audio_features(df_tracks):
  chunks = np.array_split(df_tracks, np.ceil(len(df_tracks) / 40)) # split into batches of <=40 tracks
  df_track_metadata_chunks = map(lambda chunk: enrich_tracks(chunk['spotify_track_uri'].map(lambda t: t.split(':')[-1]).to_numpy()), chunks)
  df_track_metadata = pd.concat(df_track_metadata_chunks)
  df_track_metadata['spotify_track_uri'] = df_track_metadata['href'].apply(lambda href: f"spotify:track:{href.split("/")[-1]}")

  return pd.merge(left=df_tracks, right=df_track_metadata, left_on='spotify_track_uri', right_on='spotify_track_uri', how='left')

@task
def enrich_tracks_with_context(df_tracks, artists_parquet_path, albums_parquet_path):
  df_artists = parquet_to_df(artists_parquet_path)
  df_albums = parquet_to_df(albums_parquet_path)

  genre_cols = [c for c in df_artists.columns if c.startswith("genre:")]
  if genre_cols:
    df_tracks = df_tracks.merge(
      df_artists[["master_metadata_album_artist_name"] + genre_cols],
      on="master_metadata_album_artist_name", how="left"
    )
    for col in genre_cols:
      if col in df_tracks.columns:
        df_tracks[col] = df_tracks[col].fillna(0)

  if "total_tracks" in df_albums.columns and "release_date" in df_albums.columns:
    df_albums_ctx = df_albums[["master_metadata_album_album_name",
                                "total_tracks", "release_date"]].copy()
    df_albums_ctx["release_date_year"] = pd.to_datetime(
      df_albums_ctx["release_date"], errors="coerce"
    ).dt.year
    df_tracks = df_tracks.merge(
      df_albums_ctx.drop(columns=["release_date"]),
      on="master_metadata_album_album_name", how="left"
    )
    mean_tracks = df_tracks["total_tracks"].mean()
    df_tracks["total_tracks"] = df_tracks["total_tracks"].fillna(mean_tracks)
    df_tracks["release_date_year"] = df_tracks["release_date_year"].fillna(
      df_tracks["release_date_year"].median()
    )

  return df_tracks


@task(cache_policy=NO_CACHE)
def store_track_content_vectors(df_tracks_enriched, store):
  sc = CONTENT_FEATURES
  genre_cols = [c for c in df_tracks_enriched.columns if c.startswith(sc["binary_prefix"])]
  store.store_content_vectors(
    df_tracks_enriched,
    feature_cols=sc["numeric"] + genre_cols,
    binary_cols=genre_cols if genre_cols else None,
    entity_key_col=sc["entity_key"],
  )


@task(cache_policy=NO_CACHE)
def store_track_details(df_tracks_enriched, store):
  store.store_track_details(
    df_tracks_enriched, TRACK_DETAILS_COLS, CONTENT_FEATURES["entity_key"],
  )


@flow
def analyze_tracks(listens_parquet_path,
                   artists_parquet_path=None,
                   albums_parquet_path=None,
                   db_path="etl/artifacts/listening.db"):
  df_listens = parquet_to_df(listens_parquet_path)
  df_tracks = extract_tracks(df_listens)
  df_tracks_enriched = enrich_with_audio_features(df_tracks)

  if artists_parquet_path and albums_parquet_path:
    df_tracks_enriched = enrich_tracks_with_context(
      df_tracks_enriched, artists_parquet_path, albums_parquet_path
    )

  parquet_path = str(root_path().joinpath("etl", "artifacts", "tracks.parquet"))
  df_to_parquet(df_tracks_enriched, parquet_path)
  create_link_artifact(link=parquet_path, key="tracks-analysis")

  Path(db_path).unlink(missing_ok=True)
  with ListeningVectorStore(db_path) as store:
    store_track_content_vectors(df_tracks_enriched, store)
    store_track_details(df_tracks_enriched, store)

  return parquet_path