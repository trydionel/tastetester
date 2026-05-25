import pandas as pd
import musicbrainzngs as mb

from prefect import task, flow
from prefect.artifacts import create_link_artifact
from prefect.cache_policies import TASK_SOURCE, INPUTS
from sklearn.preprocessing import MultiLabelBinarizer

from etl.common import root_path
from etl.common.analysis import peak_year
from etl.common.persistence import df_to_parquet, parquet_to_df
from etl.common.audio_features import fetch_genres as mb_fetch_genres

@task()
def extract_artists(df_listens):
  df_artists = df_listens.groupby(by='master_metadata_album_artist_name').agg(
    total_plays=('ts','count'),
    total_playtime_ms=('ms_played','sum'),
    unique_tracks_played=('master_metadata_track_name', 'nunique'),
    unique_albums_played=('master_metadata_album_album_name', 'nunique'),
    years_listened=('ts', lambda ts: ts.dt.year.nunique()),
    most_recent_year=('ts', lambda ts: ts.dt.year.max()),
    peak_year=('ts', peak_year)
  ).reset_index()

  return df_artists

@task(cache_policy=TASK_SOURCE + INPUTS, retries=3, retry_delay_seconds=[2, 5, 15])
def fetch_genres(artist):
  genres = mb_fetch_genres(artist)
  return genres if genres is not None else []

@task
def enrich_with_genres(df_artists):
  df_artist_genres = df_artists.apply(lambda r: fetch_genres(r["master_metadata_album_artist_name"]), axis=1)
  mlb = MultiLabelBinarizer()
  genre_matrix = mlb.fit_transform(df_artist_genres)
  columns = map(lambda genre: f"genre:{genre}", mlb.classes_)
  df_genres = pd.DataFrame(genre_matrix, columns=columns, index=df_artists.index)
  df_out = pd.concat([df_artists[df_artists.columns.difference(['genres'])], df_genres], axis=1)

  return df_out

@flow()
def analyze_artists(listens_parquet_path):
  df_listens = parquet_to_df(listens_parquet_path)
  df_artists = extract_artists(df_listens)
  df_artists_enriched = enrich_with_genres(df_artists)

  parquet_path = str(root_path().joinpath("etl", "artifacts", "artists.parquet"))
  df_to_parquet(df_artists_enriched, parquet_path)
  create_link_artifact(link=parquet_path, key="artists-analysis")

  return parquet_path