# app.py
import streamlit as st
from googleapiclient.discovery import build

st.set_page_config(page_title="YouTube Video Info", layout="centered")

st.title("🎥 YouTube Video Info Viewer")

# Input fields
api_key = st.text_input("🔑 Enter your YouTube API Key", type="password")
video_id = st.text_input("🎬 Enter a YouTube Video ID (e.g., eCjRD9qzk1o)")

if st.button("Fetch Info"):
    if not api_key or not video_id:
        st.error("Please enter both API Key and Video ID")
    else:
        try:
            youtube = build("youtube", "v3", developerKey=api_key)
            resp = youtube.videos().list(part="snippet,statistics", id=video_id).execute()
            if not resp["items"]:
                st.error("Invalid or private video ID.")
            else:
                item = resp["items"][0]
                st.success("✅ Video Details:")
                st.subheader("📺 Title")
                st.write(item["snippet"]["title"])

                st.subheader("📝 Description")
                st.code(item["snippet"]["description"])

                tags = item["snippet"].get("tags", [])
                st.subheader("🏷️ Tags")
                st.write(", ".join(tags) if tags else "No tags")

                views = item["statistics"].get("viewCount", "0")
                st.subheader("👁️ Views")
                st.write(views)
        except Exception as e:
            st.error(f"Error: {str(e)}")
