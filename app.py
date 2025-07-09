import streamlit as st
from googleapiclient.discovery import build
import pandas as pd
from io import BytesIO
from datetime import datetime
from collections import defaultdict

st.set_page_config(page_title="YouTube Monthly Video Exporter", layout="centered")
st.title("📅 YouTube Video Exporter (By Month)")

st.markdown("Export YouTube videos published in a specific month to Excel.")

# 🔐 Input
yt_api_key = st.text_input("🔑 YouTube API Key", type="password")
channel_id = st.text_input("📡 YouTube Channel ID")

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

# ✨ Step 1: Detect available months
if yt_api_key and channel_id:
    try:
        youtube = build("youtube", "v3", developerKey=yt_api_key)
        with st.spinner("🔎 Fetching uploaded videos..."):
            playlist_id = get_upload_playlist(youtube, channel_id)
            video_meta = get_video_ids_with_dates(youtube, playlist_id, max_videos=100)
            month_map = get_available_months(video_meta)

        if not month_map:
            st.warning("⚠️ No videos found.")
        else:
            sorted_months = sorted(month_map.keys(), reverse=True)
            selected_month = st.selectbox("📅 Select Month to Export", sorted_months)

            # ✅ Fetch button inside a form
            with st.form("fetch_form"):
                st.form_submit_button("📥 Download Excel for Selected Month")

                if selected_month:
                    selected_ids = month_map[selected_month]
                    with st.spinner(f"📦 Fetching {len(selected_ids)} videos..."):
                        videos_data = [get_video_info(youtube, vid) for vid in selected_ids]
                        df = pd.DataFrame(videos_data)

                        output = BytesIO()
                        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                            df.to_excel(writer, index=False, sheet_name="YouTube Videos")
                        output.seek(0)

                        st.success(f"✅ Found {len(df)} videos in {selected_month}")
                        st.dataframe(df.head())

                        st.download_button(
                            label="⬇️ Download Excel",
                            data=output,
                            file_name=f"youtube_{selected_month}_videos.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
    except Exception as e:
        st.error(f"❌ Error: {str(e)}")
