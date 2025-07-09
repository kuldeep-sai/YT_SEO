import streamlit as st
from googleapiclient.discovery import build
import pandas as pd
from io import BytesIO
from datetime import datetime
from collections import defaultdict

# Page setup
st.set_page_config(page_title="YouTube Video Exporter by Month", layout="centered")
st.title("📅 YouTube Video Exporter (Auto-Detected Months)")

st.markdown("🎯 Export videos published in a specific month (auto-detected) as Excel.")

# Input API credentials
yt_api_key = st.text_input("🔑 YouTube API Key", type="password")
channel_id = st.text_input("📡 YouTube Channel ID (e.g. UC_x5XG1OV2P6uZZ5FSM9Ttw)")

def get_upload_playlist(youtube, channel_id):
    res = youtube.channels().list(part="contentDetails", id=channel_id).execute()
    return res["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

def get_video_ids_with_dates(youtube, playlist_id, max_videos=100):
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
            published_at = item["contentDetails"].get("videoPublishedAt") or item["snippet"]["publishedAt"]
            videos.append({
                "video_id": item["contentDetails"]["videoId"],
                "published_at": published_at
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

def get_available_months(videos):
    month_map = defaultdict(list)
    for v in videos:
        dt = datetime.fromisoformat(v["published_at"].replace("Z", "+00:00"))
        key = dt.strftime("%Y-%m")
        month_map[key].append(v["video_id"])
    return month_map

# Step 1: Fetch video list & show month/year dropdown
if yt_api_key and channel_id:
    try:
        with st.spinner("📡 Loading available months..."):
            youtube = build("youtube", "v3", developerKey=yt_api_key)
            playlist_id = get_upload_playlist(youtube, channel_id)
            video_meta = get_video_ids_with_dates(youtube, playlist_id, max_videos=100)
            month_map = get_available_months(video_meta)

        if not month_map:
            st.warning("⚠️ No videos found.")
        else:
            sorted_months = sorted(month_map.keys(), reverse=True)
            selected_month = st.selectbox("📅 Select Month (auto-detected):", sorted_months)

            if st.button("📥 Download Excel for Selected Month"):
                selected_ids = month_map[selected_month]
                videos_data = [get_video_info(youtube, vid) for vid in selected_ids]
                df = pd.DataFrame(videos_data)

                # Excel export
                output = BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False, sheet_name="YouTube Videos")
                output.seek(0)

                st.success(f"✅ Found {len(df)} videos for {selected_month}")
                st.dataframe(df.head())

                st.download_button(
                    label="📥 Download Excel",
                    data=output,
                    file_name=f"youtube_{selected_month}_videos.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

    except Exception as e:
        st.error(f"❌ Error: {str(e)}")
