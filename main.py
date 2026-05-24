from prefect import flow
from etl.flows import analyze_albums, analyze_artists, analyze_genres, analyze_tracks, construct_listens_history

@flow
def main():
    df_listens = construct_listens_history()
    df_artists = analyze_artists(df_listens)
    df_albums = analyze_albums(df_listens)
    df_tracks = analyze_tracks(df_listens, df_artists, df_albums)
    df_genres = analyze_genres(df_artists, df_listens)


if __name__ == "__main__":
    main()
