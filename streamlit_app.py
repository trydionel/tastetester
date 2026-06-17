import streamlit as st
from app.recommender import Recommender

st.title("Taste tester")

spotify_url = st.text_input("Enter a track URL to analyze")
track_uri = spotify_url.split("/")[-1].split("?")[0]

if not track_uri:
    st.stop()

st.iframe(f"https://open.spotify.com/embed/track/{track_uri}")

try:
    with st.spinner("Analyzing track..."):
        recommender = Recommender()
        analysis = recommender.analyze(track_uri)
    
    st.subheader("Analysis")
    st.write(f"Expected number of plays for {analysis.details['artists'][0]['name']} - {analysis.details['trackTitle']}: {analysis.expected_plays:.2f} ({analysis.percentile:.2f} percentile)")
    
    st.subheader("Most similar listening history")
    for match in analysis.matches:
        st.write(f"{match['artist_name']} - {match['track_name']} ({match['total_plays']} listens, {match['distance']:.2f} distance)")
except Exception as e:
    st.error(f"Error analyzing track {track_uri}: {e}")