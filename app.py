import streamlit as st
from googleapiclient.discovery import build
import pandas as pd
from io import BytesIO

# Page config
st.set_page_config(page_title="YouTube Channel Video Exporter", layout="centered")
st.title("📊 YouTube Channel Video Exporter")

st.markdown("Export videos from your YouTube channel in batches of 50.")

# Inputs
with st.form(key="form"):
    yt_api_key = st.text_input("🔑 YouTube API Key", type="password")
    channel_id = st.text_input("📡 YouTube Channel ID (e.g. UC_x5XG1OV2P6uZZ5FSM9Ttw)")
    total_videos = st.slider("🎬 Total videos to fetch (max 500)", min_value=50, max_value=500, step=50, value=100)
    submit = st.form_submit_button("📥 Fetch Videos")

# Functions
def get_upload_playlist(youtube, channel_id):
    data = youtube.channels().list(part="contentDetails", id=channel_id).execute()
    return data["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

def get_video_ids_and_dates(youtube, playlist_id, max_videos=100):
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

# State store
if "video_data_all" not in st.session_state:
    st.session_state.video_data_all = []

if submit:
    if not yt_api_key or not channel_id:
        st.error("❌ Please enter both API Key and Channel ID.")
    else:
        try:
            with st.spinner("📡 Fetching videos..."):
                youtube = build("youtube", "v3", developerKey=yt_api_key)
                playlist_id = get_upload_playlist(youtube, channel_id)
                video_meta = get_video_ids_and_dates(youtube, playlist_id, max_videos=total_videos)

                # Sort by published date (newest first)
                video_meta_sorted = sorted(video_meta, key=lambda x: x["published_at"], reverse=True)
                selected_video_ids = [v["video_id"] for v in video_meta_sorted]

                # Fetch details
                st.session_state.video_data_all = []
                for vid in selected_video_ids:
                    info = get_video_info(youtube, vid)
                    st.session_state.video_data_all.append(info)

                st.success(f"✅ Fetched {len(st.session_state.video_data_all)} videos.")
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")

# If videos exist, show paginated output
if st.session_state.video_data_all:
    per_page = 50
    total_pages = (len(st.session_state.video_data_all) + per_page - 1) // per_page
    page = st.number_input("📄 Select Page", min_value=1, max_value=total_pages, value=1, step=1)

    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    df = pd.DataFrame(st.session_state.video_data_all[start_idx:end_idx])

    st.write(f"Showing videos {start_idx + 1} to {min(end_idx, len(st.session_state.video_data_all))} of {len(st.session_state.video_data_all)}")
    st.dataframe(df)

    # Excel export
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name=f"Page {page}")
    output.seek(0)

    st.download_button(
        label=f"⬇️ Download Excel (Page {page})",
        data=output,
        file_name=f"youtube_page_{page}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
