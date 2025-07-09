import streamlit as st
from googleapiclient.discovery import build
import pandas as pd
from io import BytesIO

# Page setup
st.set_page_config(page_title="YouTube Channel Video Exporter", layout="centered")
st.title("📊 YouTube Channel Video Exporter")

st.markdown("Export videos from your YouTube channel in defined **ranges of 50** videos (e.g. 1–50, 51–100).")

# Input form
with st.form(key="form"):
    yt_api_key = st.text_input("🔑 YouTube API Key", type="password")
    channel_id = st.text_input("📡 YouTube Channel ID (e.g. UC_xxx...)")
    total_videos = st.slider("🎬 Total videos to fetch", min_value=50, max_value=500, step=50, value=100)
    submit = st.form_submit_button("📥 Fetch Videos")

# Helper functions
def get_upload_playlist(youtube, channel_id):
    data = youtube.channels().list(part="contentDetails", id=channel_id).execute()
    return data["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

def get_video_ids(youtube, playlist_id, max_videos=100):
    videos = []
    next_token = None
    while len(videos) < max_videos:
        res = youtube.playlistItems().list(
            part="contentDetails,snippet",
            playlistId=playlist_id,
            maxResults=min(50, max_videos - len(videos)),
            pageToken=next_token
        ).execute()
        for item in res["items"]:
            videos.append({
                "video_id": item["contentDetails"]["videoId"],
                "published_at": item["contentDetails"].get("videoPublishedAt") or item["snippet"]["publishedAt"]
            })
        next_token = res.get("nextPageToken")
        if not next_token:
            break
    return videos

def get_video_info(youtube, video_id):
    res = youtube.videos().list(part="snippet,statistics", id=video_id).execute()
    item = res["items"][0]
    return {
        "video_id": video_id,
        "title": item["snippet"]["title"],
        "description": item["snippet"]["description"],
        "tags": ", ".join(item["snippet"].get("tags", [])),
        "views": item["statistics"].get("viewCount", "0"),
        "published_date": item["snippet"]["publishedAt"],
        "url": f"https://www.youtube.com/watch?v={video_id}"
    }

# Initialize session state
if "video_list" not in st.session_state:
    st.session_state.video_list = []

# Fetch data
if submit:
    if not yt_api_key or not channel_id:
        st.error("❌ Please enter both API Key and Channel ID.")
    else:
        try:
            with st.spinner("📡 Fetching video metadata..."):
                youtube = build("youtube", "v3", developerKey=yt_api_key)
                playlist_id = get_upload_playlist(youtube, channel_id)
                video_meta = get_video_ids(youtube, playlist_id, max_videos=total_videos)

                # Sort newest first
                video_meta_sorted = sorted(video_meta, key=lambda x: x["published_at"], reverse=True)
                st.session_state.video_list = video_meta_sorted
                st.success(f"✅ Fetched {len(video_meta_sorted)} videos.")
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")

# Show range selection
if st.session_state.video_list:
    total = len(st.session_state.video_list)
    ranges = [f"{i+1}–{min(i+50, total)}" for i in range(0, total, 50)]

    selected_range = st.selectbox("📦 Select video range to download", ranges)

    # Parse range
    start, end = map(int, selected_range.replace("–", "-").split("-"))
    selected_video_ids = st.session_state.video_list[start-1:end]

    with st.spinner(f"🔍 Fetching video details for {len(selected_video_ids)} videos..."):
        youtube = build("youtube", "v3", developerKey=yt_api_key)
        video_details = [get_video_info(youtube, v["video_id"]) for v in selected_video_ids]

        df = pd.DataFrame(video_details)
        st.write(f"📄 Showing videos {start} to {end}")
        st.dataframe(df)

        # Excel download
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name="Videos")
        output.seek(0)

        st.download_button(
            label=f"⬇️ Download Excel for Videos {start}–{end}",
            data=output,
            file_name=f"youtube_videos_{start}_{end}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
