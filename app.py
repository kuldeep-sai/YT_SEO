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
st.set_page_config(page_title="YouTube Exporter + SEO + Transcript + Images", layout="centered")
st.title("📊 YouTube Video Exporter + SEO + Transcript + Images")
st.markdown(
    "Export videos from YouTube channel, single video, or uploaded list. "
    "Optionally generate SEO titles/descriptions, transcripts, and images from video titles."
)

# ---------------- Tabs ----------------
tab1, tab2 = st.tabs(["Video Export", "SEO Topic Analysis"])

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

def generate_seo_tags(video, client):
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

def generate_image(prompt, client):
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

def process_video(video, enable_seo, enable_transcript, enable_images, client):
    if enable_seo:
        video["seo_output"] = generate_seo_tags(video, client)
    if enable_transcript:
        video["transcript"] = fetch_transcript(video["video_id"])
    if enable_images:
        video["image_url"] = generate_image(video["title"], client)
    return video

# ---------------- Tab 1: Video Export ----------------
with tab1:
    mode = st.radio("🔍 Select Mode", ["Batch Mode", "Single Video", "Upload URLs"], horizontal=True)

    with st.form(key="video_form"):
        yt_api_key = st.text_input("🔑 YouTube API Key", type="password")
        openai_key_input = st.text_input("🤖 OpenAI API Key (optional - for SEO & Images)", type="password")

        if mode == "Batch Mode":
            channel_id = st.text_input("📡 YouTube Channel ID (e.g. UC_xxx...)")
            batch_number = st.selectbox("📦 Select Batch (500 videos each)", options=list(range(1, 21)), index=0)
            start_index = (batch_number - 1) * 500
            num_videos = st.number_input("🎬 Number of videos to fetch", min_value=1, max_value=50, value=10, step=1)
        elif mode == "Single Video":
            video_id_input = st.text_input("🎥 Enter Video ID (e.g. dQw4w9WgXcQ)")
        else:
            uploaded_file = st.file_uploader("📄 Upload CSV or TXT with YouTube Video URLs", type=["csv", "txt"])

        enable_seo = st.checkbox("✨ Enable SEO Tagging using ChatGPT")
        enable_transcript = st.checkbox("📝 Generate Transcripts")
        enable_images = st.checkbox("🖼️ Generate Images from Video Title")
        submit = st.form_submit_button("📥 Fetch Video(s)")

    effective_openai_key = openai_key_input or st.secrets.get("OPENAI_API_KEY", "")
    client = OpenAI(api_key=effective_openai_key) if effective_openai_key else None
    if enable_images and not client:
        st.warning("⚠️ OpenAI API key missing. Image generation will not work.")

    if submit:
        if not yt_api_key:
            st.error("YouTube API Key required")
        else:
            try:
                youtube = build("youtube", "v3", developerKey=yt_api_key)
                videos_to_process = []

                if mode == "Batch Mode":
                    playlist_id = get_upload_playlist(youtube, channel_id)
                    video_meta = get_video_ids(youtube, playlist_id, max_videos=start_index + num_videos)
                    selected_batch = sorted(video_meta, key=lambda x: x["published_at"], reverse=True)[start_index:start_index + num_videos]
                    videos_to_process = [get_video_info(youtube, v["video_id"]) for v in selected_batch]

                elif mode == "Single Video":
                    videos_to_process = [get_video_info(youtube, video_id_input)]

                elif mode == "Upload URLs":
                    video_ids = extract_video_ids_from_urls(uploaded_file)
                    videos_to_process = [get_video_info(youtube, vid) for vid in video_ids]

                progress_bar = st.progress(0)
                video_details = []
                total_videos = len(videos_to_process)

                with ThreadPoolExecutor(max_workers=5) as executor:
                    futures = [executor.submit(process_video, v, enable_seo, enable_transcript, enable_images, client) for v in videos_to_process]
                    for i, future in enumerate(as_completed(futures), 1):
                        video_details.append(future.result())
                        progress_bar.progress(i / total_videos)

                if video_details:
                    for video in video_details:
                        st.markdown("---")
                        st.markdown(f"**Title:** [{video['title']}]({video['url']})")
                        st.markdown(f"**Views:** {video['views']}  |  **Published:** {video['published_date']}")
                        if enable_transcript and video.get("transcript"):
                            with st.expander("Transcript"):
                                st.write(video["transcript"][:300] + "...")
                        if enable_seo and video.get("seo_output"):
                            with st.expander("SEO Output"):
                                st.write(video["seo_output"])
                        if enable_images and video.get("image_url"):
                            st.image(video["image_url"], use_container_width=True)

                    df = pd.DataFrame(video_details)
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                        df.to_excel(writer, index=False)
                    output.seek(0)
                    st.download_button("⬇️ Download Excel", output, "youtube_videos.xlsx",
                                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            except Exception as e:
                st.error(f"Error: {e}")

# ---------------- Tab 2: SEO Topic Analysis ----------------
with tab2:
    st.markdown("### 🔍 SEO Topic Analysis (Top Videos)")

    yt_api_key_seo = st.text_input("🔑 YouTube API Key for SEO Analysis (Tab 2)", type="password")
    openai_key_seo = st.text_input("🤖 OpenAI API Key for SEO Analysis (Tab 2)", type="password")
    seo_topics_input = st.text_input(
        "📈 Enter Topics/Keywords for SEO Analysis (comma separated, e.g. Python, AI, SEO)"
    )
    top_video_count = st.number_input("🎬 Number of top videos to analyze per topic", min_value=1, max_value=50, value=10, step=1)
    
    analyze_seo = st.button("Analyze Videos")

    if analyze_seo:
        if not yt_api_key_seo or not openai_key_seo:
            st.error("Please provide both YouTube and OpenAI API keys for SEO analysis")
        elif not seo_topics_input:
            st.warning("Please enter at least one topic to analyze")
        else:
            topics = [t.strip() for t in seo_topics_input.split(",") if t.strip()]
            try:
                youtube_seo = build("youtube", "v3", developerKey=yt_api_key_seo)
                openai_seo_client = OpenAI(api_key=openai_key_seo)

                for topic in topics:
                    st.info(f"Fetching top {top_video_count} videos for topic: '{topic}'")
                    
                    search_res = youtube_seo.search().list(
                        q=topic,
                        part="snippet",
                        type="video",
                        order="viewCount",
                        maxResults=top_video_count
                    ).execute()
                    
                    top_videos = []
                    for item in search_res.get("items", []):
                        vid_id = item["id"]["videoId"]
                        vid_info = youtube_seo.videos().list(part="snippet,statistics", id=vid_id).execute()
                        if vid_info["items"]:
                            info = vid_info["items"][0]
                            top_videos.append({
                                "video_id": vid_id,
                                "title": info["snippet"]["title"],
                                "description": info["snippet"]["description"],
                                "tags": ", ".join(info["snippet"].get("tags", [])),
                                "views": int(info["statistics"].get("viewCount", 0)),
                                "url": f"https://www.youtube.com/watch?v={vid_id}"
                            })

                    if not top_videos:
                        st.warning(f"No videos found for topic: '{topic}'")
                        continue

                    for idx, video in enumerate(top_videos, 1):
                        st.markdown("---")
                        st.markdown(f"### {idx}. [{video['title']}]({video['url']})")
                        st.markdown(f"**Views:** {video['views']}")
                        st.markdown(f"**Description:** {video['description'][:300]}...")
                        st.markdown(f"**Tags:** {video['tags'] or 'N/A'}")
                        
                        prompt = f"""
                        You are a YouTube SEO expert. Video info:

                        Title: {video['title']}
                        Description: {video['description']}
                        Tags: {video['tags']}

                        Suggest:
                        - 10 SEO-optimized hashtags
                        - 10 long-tail keywords
                        - A better SEO-friendly title (if needed)
                        """
                        try:
                            seo_output = openai_seo_client.chat.completions.create(
                                model="gpt-4o",
                                messages=[{"role": "user", "content": prompt}]
                            )
                            st.write(seo_output.choices[0].message.content)
                        except Exception as e:
                            st.warning(f"SEO generation failed for video '{video['title']}': {e}")
            except Exception as e:
                st.error(f"Error in SEO Topic Analysis: {e}")
