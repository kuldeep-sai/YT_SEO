import streamlit as st
from googleapiclient.discovery import build
import pandas as pd
from io import BytesIO
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from openai import OpenAI
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

# ---------------- Page Setup ----------------
st.set_page_config(page_title="YouTube Exporter + SEO + Images", layout="centered")
st.title("📊 YouTube Video Exporter + SEO + Transcript + Images")
st.markdown(
    "Export videos from YouTube channel, single video, or uploaded list. "
    "Optionally generate SEO titles/descriptions, transcripts, and images from video titles."
)

# ---------------- Tabs ----------------
tabs = st.tabs(["Video Export", "SEO Topic Analysis"])

# ---------------- Helper Functions ----------------
def get_upload_playlist(youtube, channel_id):
    data = youtube.channels().list(part="contentDetails", id=channel_id).execute()
    if not data.get("items"):
        raise ValueError(f"No channel found for ID: {channel_id}")
    return data["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

def get_video_ids(youtube, playlist_id, max_videos=1000):
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
    if not res["items"]:
        return {"video_id": video_id, "error": "Video not found"}
    item = res["items"][0]
    views = int(item["statistics"].get("viewCount", 0))
    return {
        "video_id": video_id,
        "title": item["snippet"]["title"],
        "description": item["snippet"]["description"],
        "tags": ", ".join(item["snippet"].get("tags", [])),
        "views": views,
        "published_date": item["snippet"]["publishedAt"],
        "url": f"https://www.youtube.com/watch?v={video_id}"
    }

def fetch_transcript(video_id):
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        transcript = transcript_list.find_transcript(['en']).fetch()
        return " ".join([seg["text"] for seg in transcript])
    except (TranscriptsDisabled, NoTranscriptFound):
        return "Transcript not found"
    except Exception:
        return "Transcript not found"

def generate_seo_tags(client, video):
    if not client:
        return "OpenAI API key missing"
    prompt = f"""
    You are a YouTube SEO expert. Video info:

    Title: {video['title']}
    Description: {video['description']}
    Views: {video['views']}

    Generate:
    - SEO title (≤70 chars)
    - 150-word description
    - 10 hashtags
    - 10 long-tail keywords
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error generating SEO: {e}"

def generate_image(client, prompt):
    if not client:
        return None
    try:
        response = client.images.generate(
            model="gpt-image-1",
            prompt=f"Thumbnail for: {prompt}",
            size="512x512"
        )
        return response.data[0].url
    except Exception as e:
        st.warning(f"Image generation failed for '{prompt}': {e}")
        return None

def extract_video_ids_from_urls(file):
    content = file.read().decode("utf-8")
    urls = content.splitlines()
    ids = []
    for url in urls:
        match = re.search(r"(?:v=|youtu\.be/)([\w-]{11})", url)
        if match:
            ids.append(match.group(1))
    return ids

def process_video(video, client, enable_seo, enable_transcript, enable_images):
    if enable_seo:
        video["seo_output"] = generate_seo_tags(client, video)
    if enable_transcript:
        video["transcript"] = fetch_transcript(video["video_id"])
    if enable_images:
        video["image_url"] = generate_image(client, video["title"])
    return video

# ---------------- Tab 1: Video Export ----------------
with tabs[0]:
    st.header("🎥 Video Export + SEO + Images + Transcript")
    youtube_api_key = st.text_input("YouTube API Key", key="tab1_yt", type="password")
    openai_api_key = st.text_input("OpenAI API Key (SEO & Images)", key="tab1_openai", type="password")
    
    mode_tab1 = st.radio("Select Mode", ["Single Video", "Batch Mode", "Upload URLs"], key="tab1_mode")
    
    if mode_tab1 == "Single Video":
        video_id_input = st.text_input("Enter Video ID", key="tab1_single_vid")
    elif mode_tab1 == "Batch Mode":
        channel_id = st.text_input("YouTube Channel ID", key="tab1_channel")
        num_videos = st.number_input("Number of videos to fetch", min_value=1, max_value=50, value=10, step=1)
    else:
        uploaded_file_tab1 = st.file_uploader("Upload CSV/TXT with Video URLs", type=["csv", "txt"], key="tab1_file")

    enable_seo = st.checkbox("Enable SEO suggestions", key="tab1_seo")
    enable_images = st.checkbox("Enable AI Thumbnail", key="tab1_img")
    enable_transcript = st.checkbox("Enable Transcript", key="tab1_transcript")

    if st.button("Fetch Videos", key="tab1_btn"):
        if not youtube_api_key:
            st.error("YouTube API Key required")
        else:
            youtube = build("youtube", "v3", developerKey=youtube_api_key)
            client = OpenAI(api_key=openai_api_key) if openai_api_key else None
            videos_to_process = []

            if mode_tab1 == "Single Video":
                if not video_id_input:
                    st.error("Enter Video ID")
                else:
                    videos_to_process = [get_video_info(youtube, video_id_input)]
            elif mode_tab1 == "Batch Mode":
                playlist_id = get_upload_playlist(youtube, channel_id)
                videos_meta = get_video_ids(youtube, playlist_id, max_videos=num_videos)
                videos_to_process = [get_video_info(youtube, v["video_id"]) for v in videos_meta[:num_videos]]
            else:
                if uploaded_file_tab1:
                    video_ids = extract_video_ids_from_urls(uploaded_file_tab1)
                    videos_to_process = [get_video_info(youtube, vid) for vid in video_ids]

            video_details = []
            for v in videos_to_process:
                video_details.append(process_video(v, client, enable_seo, enable_transcript, enable_images))

            for video in video_details:
                st.markdown("---")
                st.markdown(f"**Title:** [{video['title']}]({video['url']})")
                st.markdown(f"**Views:** {video['views']} | **Published:** {video['published_date']}")
                st.markdown(f"**Current Description:** {video['description']}")
                st.markdown(f"**Tags:** {video['tags']}")
                if enable_transcript and video.get("transcript"):
                    with st.expander("Transcript"):
                        st.write(video["transcript"][:300] + "...")
                if enable_seo and video.get("seo_output"):
                    with st.expander("SEO Output"):
                        st.write(video["seo_output"])
                if enable_images and video.get("image_url"):
                    st.image(video["image_url"], use_container_width=True)

            if video_details:
                df = pd.DataFrame(video_details)
                output = BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False)
                output.seek(0)
                st.download_button("⬇️ Download Excel", output, "youtube_videos.xlsx",
                                   "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ---------------- Tab 2: SEO Topic Analysis ----------------
with tabs[1]:
    st.header("📈 SEO Topic Analysis")
    youtube_api_key_tab2 = st.text_input("YouTube API Key", key="tab2_yt", type="password")
    openai_api_key_tab2 = st.text_input("OpenAI API Key", key="tab2_openai", type="password")
    topics_input = st.text_area("Enter Topic/Keyword(s) (comma-separated)", key="tab2_topics")
    uploaded_file_tab2 = st.file_uploader("Or upload Excel/CSV with topics", type=["csv", "xlsx"], key="tab2_file")
    top_n = st.number_input("Number of top videos to fetch per keyword", min_value=1, max_value=50, value=10, step=1)
    
    if st.button("Analyze SEO Topics", key="tab2_btn"):
        if uploaded_file_tab2:
            if uploaded_file_tab2.name.endswith(".xlsx"):
                df_topics = pd.read_excel(uploaded_file_tab2)
            else:
                df_topics = pd.read_csv(uploaded_file_tab2)
            topics = df_topics.iloc[:, 0].astype(str).tolist()
        else:
            topics = [t.strip() for t in topics_input.split(",") if t.strip()]
        
        if not youtube_api_key_tab2:
            st.error("YouTube API Key required")
        else:
            youtube = build("youtube", "v3", developerKey=youtube_api_key_tab2)
            client = OpenAI(api_key=openai_api_key_tab2) if openai_api_key_tab2 else None
            all_results = []

            for topic in topics:
                search_res = youtube.search().list(q=topic, part="snippet", type="video", order="viewCount", maxResults=top_n).execute()
                video_ids = [item["id"]["videoId"] for item in search_res["items"]]
                for vid in video_ids:
                    info = get_video_info(youtube, vid)
                    info["keyword"] = topic
                    if client:
                        info["seo_suggestion"] = generate_seo_tags(client, info)
                    all_results.append(info)

            if all_results:
                df_res = pd.DataFrame(all_results)
                st.dataframe(df_res)
                output = BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df_res.to_excel(writer, index=False)
                output.seek(0)
                st.download_button("⬇️ Download SEO Analysis", output, "seo_analysis.xlsx",
                                   "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
