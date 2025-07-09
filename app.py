import streamlit as st
from googleapiclient.discovery import build

# Page setup
st.set_page_config(page_title="YouTube Channel Video Info", layout="centered")
st.title("📺 YouTube Channel Video Info Viewer")

st.markdown("Enter your credentials and YouTube Channel ID to fetch recent videos.")

# Inputs
with st.form(key="form"):
    yt_api_key = st.text_input("🔑 YouTube API Key", type="password")
    channel_id = st.text_input("📡 YouTube Channel ID (e.g. UC_x5XG1OV2P6uZZ5FSM9Ttw)")
    num_videos = st.slider("🎬 Number of recent videos to fetch", 1, 10, 3)
    submit = st.form_submit_button("🔍 Fetch Video Info")

# YouTube API functions
def get_upload_playlist(youtube, channel_id):
    data = youtube.channels().list(
        part="contentDetails",
        id=channel_id
    ).execute()
    return data["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

def get_video_ids(youtube, playlist_id, max_videos):
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
        "title": item["snippet"]["title"],
        "description": item["snippet"]["description"],
        "tags": item["snippet"].get("tags", []),
        "views": item["statistics"].get("viewCount", "0")
    }

# On form submission
if submit:
    if not yt_api_key or not channel_id:
        st.error("Please provide both API key and channel ID.")
    else:
        with st.spinner("📡 Fetching data from YouTube..."):
            try:
                youtube = build("youtube", "v3", developerKey=yt_api_key)
                playlist_id = get_upload_playlist(youtube, channel_id)
                video_ids = get_video_ids(youtube, playlist_id, num_videos)

                st.success(f"Fetched {len(video_ids)} videos from channel.")
                for i, vid in enumerate(video_ids, start=1):
                    video_data = get_video_info(youtube, vid)

                    st.markdown(f"---")
                    st.subheader(f"🎬 Video {i}: {video_data['title']}")
                    st.write(f"👁️ **Views:** {video_data['views']}")
                    st.write("🏷️ **Tags:**", ", ".join(video_data["tags"]) if video_data["tags"] else "None")
                    with st.expander("📝 Description"):
                        st.code(video_data["description"])

            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
