import os

from prefect import flow
from etl.flows import analyze_albums, analyze_artists, analyze_genres, analyze_tracks, construct_listens_history, train_model

@flow
def main():
    df_listens = construct_listens_history()
    df_artists = analyze_artists(df_listens)
    df_albums = analyze_albums(df_listens)
    df_tracks = analyze_tracks(df_listens, df_artists, df_albums)
    df_genres = analyze_genres(df_artists, df_listens)

    bucket_name = os.environ["TASTETESTER_TRAINING_BUCKET"]
    package_uri = os.environ["TASTETESTER_TRAINING_PACKAGE_GCS_URI"]
    endpoint_id = os.environ["TASTETESTER_MODEL_ENDPOINT_ID"]
    if bucket_name is not None:
        train_model(bucket_name, package_uri, endpoint_id)

if __name__ == "__main__":
    main()
