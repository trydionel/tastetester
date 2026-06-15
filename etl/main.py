import os

from prefect import flow
from etl.flows import analyze_albums, analyze_artists, analyze_genres, analyze_tracks, construct_listens_history
from etl.common import root_path
from prefect_gcp.cloud_storage import GcsBucket

@flow
def main():
    df_listens = construct_listens_history()
    df_artists = analyze_artists(df_listens)
    df_albums = analyze_albums(df_listens)
    df_tracks = analyze_tracks(df_listens, df_artists, df_albums)
    df_genres = analyze_genres(df_artists, df_listens)

    bucket_name = os.environ["TASTETESTER_TRAINING_BUCKET"]
    bucket = GcsBucket.load(bucket_name)
    bucket.upload_from_folder(root_path().join('etl', 'artifacts'), 'artifacts')

if __name__ == "__main__":
    main()
