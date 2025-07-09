import streamlit as st
from googleapiclient.discovery import build
import pandas as pd
from io import BytesIO

# Page config
st.set_page_config(page_title="YouTube Channel Video Exporter", layout="centered")
st.title("📊 YouTube Channel Video Exporter")

st.markdown("Export videos from your YouTube channel in **batches of 50** with multi-page selection.")

# Inputs
with st.form(key="form"):
    yt_api_key = st.text_input("🔑 YouTube API Key", type="password")
    channel_id = st.text_input("📡 YouTube Channel ID (e.g. UC_xxx...)")
    total_videos = st.slider("🎬 Total videos to fetch (max 500)", min_value=50, max_value=500, step=50, value=100)
    submit = st.form_submit_button("📥 Fetch Videos")

# YouTube functions
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

# State
if "video_data_all" not in st.session_state:
    st.session_state.video_data_all = []

# Form submission
if submit:
    if not yt_api_key or not channel_id:
        st.error("❌ Please enter both API Key and Channel ID.")
    else:
        try:
            with st.spinner("📡 Fetching videos..."):
                youtube = build("youtube", "v3", developerKey=yt_api_key)
                playlist_id = get_upload_playlist(youtube, channel_id)
                video_meta = get_video_ids_and_dates(youtube, playlist_id, max_videos=total_videos)

                # Sort and store
                video_meta_sorted = sorted(video_meta, key=lambda x: x["published_at"], reverse=True)
                st.session_state.video_data_all = []
                for vid in video_meta_sorted:
                    st.session_state.video_data_all.append(vid)

                st.success(f"✅ Fetched {len(st.session_state.video_data_all)} video entries.")
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")

# Pagination + Page Multi-select
if st.session_state.video_data_all:
    per_page = 50
    total_pages = (len(st.session_state.video_data_all) + per_page - 1) // per_page
    page_options = list(range(1, total_pages + 1))

    selected_pages = st.multiselect(
        "📦 Select Pages (Each Page = 50 Videos)", page_options, default=[1]
    )

    if selected_pages:
        selected_video_ids = []
        for page in selected_pages:
            start = (page - 1) * per_page
            end = start + per_page
            selected_video_ids += st.session_state.video_data_all[start:end]

        youtube = build("youtube", "v3", developerKey=yt_api_key)
        videos_data = []
        with st.spinner(f"🔍 Fetching video details for {len(selected_video_ids)} videos..."):
            for entry in selected_video_ids:
                info = get_video_info(youtube, entry["video_id"])
                videos_data.append(info)

        df = pd.DataFrame(videos_data)
        st.write(f"📄 Showing {len(df)} videos from pages: {selected_pages}")
        st.dataframe(df)

        # Excel writer
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name="YouTube Videos")
        output.seek(0)

        st.download_button(
            label="⬇️ Download Combined Excel",
            data=output,
            file_name="youtube_selected_pages.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
