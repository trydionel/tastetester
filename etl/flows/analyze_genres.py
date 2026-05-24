import numpy as np
import pandas as pd

from prefect import flow, task
from prefect.artifacts import create_link_artifact

from etl.common import root_path
from etl.common.analysis import peak_year
from etl.common.persistence import df_to_parquet, parquet_to_df

@task
def join_artists_to_listens(df_artists, df_listens):
  return pd.merge(left=df_listens, right=df_artists, on="master_metadata_album_artist_name")

@task
def extract_genres(df_listens_with_artists):
  id_vars = filter(lambda c: not c.startswith('genre:'), df_listens_with_artists.columns.values)
  df_listens_long_genres = df_listens_with_artists.melt(id_vars=id_vars, value_name='has_genre', var_name='genre')
  df_listens_long_genres = df_listens_long_genres[df_listens_long_genres['has_genre'] == 1]
  df_listens_long_genres['genre'] = df_listens_long_genres['genre'].str.replace('genre:', '')

  df_analysis = df_listens_long_genres.groupby('genre').agg(
    total_plays=('ts','count'),
    total_playtime_ms=('ms_played','sum'),
    unique_albums_played=('master_metadata_album_album_name', 'nunique'),
    years_listened=('ts', lambda ts: ts.dt.year.nunique()),
    most_recent_year=('ts', lambda ts: ts.dt.year.max()),
    peak_year=('ts', peak_year)
  ).reset_index()

  return df_analysis

@flow
def analyze_genres(artists_parquet_path, listens_parquet_path):
  df_artists = parquet_to_df(artists_parquet_path)
  df_listens = parquet_to_df(listens_parquet_path)

  df_listens_with_artists = join_artists_to_listens(df_artists, df_listens)
  df_genres = extract_genres(df_listens_with_artists)

  parquet_path = str(root_path().joinpath("etl", "artifacts", "genres.parquet"))
  df_to_parquet(df_genres, parquet_path)
  create_link_artifact(link=parquet_path, key="genres-analysis")

  return parquet_path