import streamlit as st
from googleapiclient.discovery import build
import pandas as pd
from io import BytesIO

# Page setup
st.set_page_config(page_title="YouTube Channel to Excel", layout="centered")
st.title("📊 YouTube Channel Video Exporter")

st.markdown("🔽 Enter your API credentials and get the latest 50 videos as an Excel file.")

# Inputs
with st.form(key="form"):
    yt_api_key = st.text_input("🔑 YouTube API Key", type="password")
    channel_id = st.text_input("📡 YouTube Channel ID (e.g. UC_x5XG1OV2P6uZZ5FSM9Ttw)")
    submit = st.form_submit_button("📥 Fetch Videos & Download Excel")

# YouTube API functions
def get_upload_playlist(youtube, channel_id):
    data = youtube.channels().list(
        part="contentDetails",
        id=channel_id
    ).execute()
    return data["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

def get_video_ids(youtube, playlist_id, max_videos=50):
    videos = []
    next_token = None
    while len(videos) < max_videos:
        res = youtube.playlistItems().list(
            part="contentDetails",
            playlistId=playlist_id,
            maxResults=min(50, max_videos - len(videos)),
            pageToken=next_token
        ).execute()
        for item in res["items"]:
            videos.append(item["contentDetails"]["videoId"])
        next_token = res.get("nextPageToken")
        if not next_token:
            break
    return videos

def get_video_info(youtube, video_id):
    res = youtube.videos().list(
        part="snippet,statistics",
        id=video_id
    ).execute()
    item = res["items"][0]
    return {
        "video_id": video_id,
        "title": item["snippet"]["title"],
        "description": item["snippet"]["description"],
        "tags": ", ".join(item["snippet"].get("tags", [])),
        "views": item["statistics"].get("viewCount", "0"),
        "url": f"https://www.youtube.com/watch?v={video_id}"
    }

# On form submission
if submit:
    if not yt_api_key or not channel_id:
        st.error("❌ Please enter both API Key and Channel ID.")
    else:
        try:
            with st.spinner("📡 Fetching videos..."):
                youtube = build("youtube", "v3", developerKey=yt_api_key)
                playlist_id = get_upload_playlist(youtube, channel_id)
                video_ids = get_video_ids(youtube, playlist_id, max_videos=50)

                videos_data = []
                for vid in video_ids:
                    info = get_video_info(youtube, vid)
                    videos_data.append(info)

                df = pd.DataFrame(videos_data)

                # Create in-memory Excel file
                output = BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False, sheet_name="YouTube Videos")
                    writer.save()
                output.seek(0)

                st.success("✅ Fetched and ready to download!")

                # Show preview
                st.dataframe(df.head())

                # Download button
                st.download_button(
                    label="📥 Download Excel",
                    data=output,
                    file_name="youtube_channel_videos.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
