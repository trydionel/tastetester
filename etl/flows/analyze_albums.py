import musicbrainzngs as mb
import pandas as pd

from prefect import flow, task
from prefect.artifacts import create_link_artifact
from prefect.cache_policies import TASK_SOURCE, INPUTS

from etl.common import root_path
from etl.common.analysis import peak_year
from etl.common.persistence import df_to_parquet, parquet_to_df

@task
def prep_musicbrainz():
  mb.set_rate_limit()
  mb.set_useragent('trydionel-ds-project', '0.0.1', 'jeff@trydionel.com')

@task
def extract_albums(df_listens):
  df_albums = df_listens[df_listens['master_metadata_album_album_name'] != ''].groupby(by='master_metadata_album_album_name').agg(
    master_metadata_album_artist_name=('master_metadata_album_artist_name', 'first'),
    total_plays=('ts','count'),
    total_playtime_ms=('ms_played','sum'),
    unique_tracks_played=('master_metadata_track_name', lambda track: track.str.lower().nunique()), # FIXME: use levenshtein distance to clean up track names?
    years_listened=('ts', lambda ts: ts.dt.year.nunique()),
    most_recent_year=('ts', lambda ts: ts.dt.year.max()),
    peak_year=('ts', peak_year)
  ).reset_index()

  return df_albums.sort_values(by='total_plays', ascending=False).head(10)

@task(cache_policy=TASK_SOURCE + INPUTS, retries=3, retry_delay_seconds=[2, 5, 15])
def fetch_album_metadata(artist, album):
  res = mb.search_releases(limit=1, artist=artist, release=album)
  albums = res['release-list']

  if len(albums) == 0:
    return None

  if int(albums[0]['ext:score']) < 95:
    return None

  album = albums[0]

  try:
    total_tracks = album['medium-track-count']
  except:
    total_tracks = None

  try:
    release_date = album['release-event-list'][0]['date']
  except:
    release_date = None
  
  try:
    album_type = album['release-group']['type']
  except:
    album_type = None
  
  try:
    record_label = album['label-info-list'][0]['label']['name']
  except:
    record_label = None

  return pd.Series({
    'total_tracks': total_tracks,
    'release_date': release_date,
    'album_type': album_type,
    'record_label': record_label,
  })

@task
def enrich_with_metadata(df_albums):
  df_album_metadata = df_albums.apply(lambda r: fetch_album_metadata(artist=r['master_metadata_album_artist_name'], album=r['master_metadata_album_album_name']), axis=1)

  df_out = pd.concat([df_albums, df_album_metadata], axis=1)
  df_out['percent_tracks_played'] = df_out.apply(lambda r: min(1, r['unique_tracks_played'] / r["total_tracks"]), axis=1)

  return df_out

@flow
def analyze_albums(listens_parquet_path):
  prep_musicbrainz()

  df_listens = parquet_to_df(listens_parquet_path)
  df_albums = extract_albums(df_listens)
  df_artists_enriched = enrich_with_metadata(df_albums)

  parquet_path = str(root_path().joinpath("etl", "artifacts", "albums.parquet"))
  df_to_parquet(df_artists_enriched, parquet_path)
  create_link_artifact(link=parquet_path, key="albums-analysis")

  return parquet_path