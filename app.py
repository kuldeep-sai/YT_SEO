import streamlit as st
from googleapiclient.discovery import build
import pandas as pd
from io import BytesIO

# Page setup
st.set_page_config(page_title="YouTube Channel Video Export", layout="centered")
st.title("📺 Export All YouTube Channel Videos to Excel")

st.markdown("Enter your credentials below to fetch all videos from a channel and download them as an Excel file.")

# Input form
with st.form("input_form"):
    yt_api_key = st.text_input("🔑 YouTube API Key", type="password")
    channel_id = st.text_input("📡 YouTube Channel ID (e.g. UC_x5XG1OV2P6uZZ5FSM9Ttw)")
    submitted = st.form_submit_button("📥 Fetch & Export")

# YouTube API helpers
def get_upload_playlist(youtube, channel_id):
    response = youtube.channels().list(
        part="contentDetails",
        id=channel_id
    ).execute()
    return response["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

def get_all_video_ids(youtube, playlist_id):
    video_ids = []
    next_page_token = None
    while True:
        response = youtube.playlistItems().list(
            part="contentDetails",
            playlistId=playlist_id,
            maxResults=50,
            pageToken=next_page_token
        ).execute()
        for item in response["items"]:
            video_ids.append(item["contentDetails"]["videoId"])
        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            break
    return video_ids

def get_video_metadata(youtube, video_id):
    response = youtube.videos().list(
        part="snippet,statistics",
        id=video_id
    ).execute()
    item = response["items"][0]
    return {
        "Video ID": video_id,
        "Title": item["snippet"]["title"],
        "Description": item["snippet"]["description"],
        "Tags": ", ".join(item["snippet"].get("tags", [])),
        "Views": item["statistics"].get("viewCount", "0"),
        "Video URL": f"https://www.youtube.com/watch?v={video_id}"
    }

# On form submit
if submitted:
    if not yt_api_key or not channel_id:
        st.error("Please provide both API key and channel ID.")
    else:
        try:
            st.info("🔍 Connecting to YouTube API...")
            youtube = build("youtube", "v3", developerKey=yt_api_key)

            st.info("📥 Getting upload playlist...")
            uploads_playlist = get_upload_playlist(youtube, channel_id)

            st.info("📦 Fetching all video IDs...")
            video_ids = get_all_video_ids(youtube, uploads_playlist)

            st.success(f"✅ Found {len(video_ids)} videos.")

            st.info("⏳ Fetching metadata for each video...")
            data = []
            for idx, vid in enumerate(video_ids):
                metadata = get_video_metadata(youtube, vid)
                data.append(metadata)
                st.progress((idx + 1) / len(video_ids))

            # Create DataFrame
            df = pd.DataFrame(data)

            # Convert to Excel
            # Convert to Excel
output = BytesIO()
with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
    df.to_excel(writer, index=False, sheet_name='YouTube Videos')
output.seek(0)


            # Download button
            st.download_button(
                label="📥 Download Excel File",
                data=output,
                file_name="youtube_channel_videos.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

            st.success("🎉 Download ready!")

        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
