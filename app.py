import streamlit as st
from googleapiclient.discovery import build
import pandas as pd
from io import BytesIO
import time
from googleapiclient.errors import HttpError
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from openai import OpenAI
import os
import re
import yt_dlp
import tempfile
import requests
import zipfile
import io

# ---------------- Page Setup ----------------
st.set_page_config(page_title="YouTube Video Exporter + SEO + Transcript + Images", layout="centered")
st.title("📊 YouTube Video Exporter + SEO + Transcript + Images")
st.markdown(
    "Export videos from your YouTube channel, single video, or uploaded list. "
    "Optionally generate SEO-optimized titles/descriptions, transcripts, and images based on video titles."
)

# ---------------- Mode Selection ----------------
mode = st.radio("🔍 Select Mode", ["Batch Mode", "Single Video", "Upload URLs"], horizontal=True)

# ---------------- Input Form ----------------
with st.form(key="form"):
    yt_api_key = st.text_input("🔑 YouTube API Key", type="password")
    openai_key_input = st.text_input("🤖 OpenAI API Key (optional - for SEO, Whisper, Image)", type="password")
    seo_topic = st.text_input("📈 (Optional) Topic for analyzing top-ranking SEO tags")

    if mode == "Batch Mode":
        channel_id = st.text_input("📡 YouTube Channel ID (e.g. UC_xxx...)")
        batch_number = st.selectbox("📦 Select Batch (500 videos each)", options=list(range(1, 21)), index=0)
        start_index = (batch_number - 1) * 500
        num_videos = st.number_input("🎬 Number of videos to fetch", min_value=1, max_value=500, value=500, step=1)
    elif mode == "Single Video":
        video_id_input = st.text_input("🎥 Enter Video ID (e.g. dQw4w9WgXcQ)")
    else:
        uploaded_file = st.file_uploader("📄 Upload CSV or TXT with YouTube Video URLs", type=["csv", "txt"])

    enable_seo = st.checkbox("✨ Enable SEO Tagging using ChatGPT")
    enable_transcript = st.checkbox("📝 Generate Transcripts")
    enable_images = st.checkbox("🖼️ Generate Images from Video Title")
    submit = st.form_submit_button("📥 Fetch Video(s)")

# ---------------- OpenAI Client ----------------
effective_openai_key = openai_key_input or st.secrets.get("OPENAI_API_KEY", "")
client = OpenAI(api_key=effective_openai_key) if effective_openai_key else None

# ---------------- Helper Functions ----------------
def get_upload_playlist(youtube, channel_id):
    data = youtube.channels().list(part="contentDetails", id=channel_id).execute()
    if not data.get("items"):
        raise ValueError(f"❌ No channel found for ID: {channel_id}. Please check the Channel ID.")
    return data["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

def get_video_ids(youtube, playlist_id, max_videos=10000):
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
        return {"video_id": video_id, "error": "Video not found or unavailable"}
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

def get_top_video_tags(youtube, search_query, max_results=20):
    try:
        search_res = youtube.search().list(
            q=search_query,
            part="snippet",
            type="video",
            order="viewCount",
            maxResults=max_results
        ).execute()
        video_ids = [item["id"]["videoId"] for item in search_res["items"]]
        tags = []
        for vid in video_ids:
            res = youtube.videos().list(part="snippet", id=vid).execute()
            if res["items"]:
                tags.extend(res["items"][0]["snippet"].get("tags", []))
        tag_freq = pd.Series(tags).value_counts()
        return tag_freq.index.tolist()[:20]
    except Exception as e:
        return [f"Error: {str(e)}"]

def generate_seo_tags(video, top_tags=None):
    if not client:
        return "❌ OpenAI API key is missing or not set."
    tags_string = ", ".join(top_tags) if top_tags else ""
    prompt = f"""
    You are an expert YouTube SEO optimizer. Given this video metadata:

    Title: {video['title']}
    Description: {video['description']}
    Tags: {video['tags']}
    Views: {video['views']}

    Top trending tags: {tags_string}

    Generate:
    - A compelling SEO-optimized YouTube title (under 70 characters, with keywords early)
    - A 150-word keyword-rich video description (2 paragraphs max)
    - A list of 10 relevant SEO hashtags
    - A list of 10 comma-separated long-tail keywords
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"OpenAI Error: {e}"

def fetch_transcript(video_id):
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=["en", "en-US", "hi"])
        return " ".join([seg["text"] for seg in transcript])
    except (TranscriptsDisabled, NoTranscriptFound):
        pass
    except Exception as e:
        return f"⚠️ Transcript API error: {str(e)}"

    if not client:
        return "❌ OpenAI API key is required for Whisper fallback."

    try:
        url = f"https://www.youtube.com/watch?v={video_id}"
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = f"{tmpdir}/{video_id}.mp3"
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": audio_path,
                "quiet": True,
                "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}],
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            with open(audio_path, "rb") as f:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=f
                )
            return transcript.text
    except Exception as e:
        return f"❌ Whisper fallback failed: {str(e)}"

def generate_image(prompt):
    if not client:
        return None, "❌ OpenAI API key required for image generation."
    try:
        response = client.images.generate(
            model="gpt-image-1",
            prompt=f"Create a YouTube thumbnail style image for: {prompt}",
            size="1024x1024"
        )
        image_url = response.data[0].url
        return image_url, None
    except Exception as e:
        return None, f"❌ Image generation failed: {str(e)}"

def extract_video_ids_from_urls(file):
    content = file.read().decode("utf-8")
    urls = content.splitlines()
    ids = []
    for url in urls:
        match = re.search(r"(?:v=|youtu.be/)([\w-]{11})", url)
        if match:
            ids.append(match.group(1))
    return ids

# ---------------- Fetch Logic ----------------
if submit:
    if not yt_api_key:
        st.error("❌ Please enter your YouTube API Key.")
    else:
        try:
            youtube = build("youtube", "v3", developerKey=yt_api_key)
            top_tags = get_top_video_tags(youtube, seo_topic) if seo_topic else []

            if seo_topic and top_tags:
                st.markdown(f"🔝 Top tags for **{seo_topic}**:")
                st.write(", ".join(top_tags))

            video_details = []

            # ---------------- Mode: Batch ----------------
            if mode == "Batch Mode":
                if not channel_id:
                    st.error("❌ Please enter Channel ID.")
                else:
                    try:
                        playlist_id = get_upload_playlist(youtube, channel_id)
                    except ValueError as e:
                        st.error(str(e))
                        st.stop()
                    with st.spinner("📡 Fetching videos..."):
                        video_meta = get_video_ids(youtube, playlist_id, max_videos=start_index + num_videos)
                        video_meta_sorted = sorted(video_meta, key=lambda x: x["published_at"], reverse=True)
                        selected_batch = video_meta_sorted[start_index:start_index + num_videos]
                        for v in selected_batch:
                            info = get_video_info(youtube, v["video_id"])
                            if enable_seo:
                                info["seo_output"] = generate_seo_tags(info, top_tags)
                                time.sleep(5)
                            if enable_transcript:
                                info["transcript"] = fetch_transcript(v["video_id"])
                            if enable_images:
                                img_url, err = generate_image(info["title"])
                                info["image_url"] = img_url if img_url else err
                            video_details.append(info)

            # ---------------- Mode: Single ----------------
            elif mode == "Single Video":
                if not video_id_input:
                    st.error("❌ Please enter a Video ID.")
                else:
                    with st.spinner("🔍 Fetching video..."):
                        info = get_video_info(youtube, video_id_input)
                        if "error" in info:
                            st.error(f"❌ {info['error']}")
                        else:
                            if enable_seo:
                                info["seo_output"] = generate_seo_tags(info, top_tags)
                                time.sleep(5)
                            if enable_transcript:
                                info["transcript"] = fetch_transcript(video_id_input)
                            if enable_images:
                                img_url, err = generate_image(info["title"])
                                info["image_url"] = img_url if img_url else err
                            video_details.append(info)

            # ---------------- Mode: Upload ----------------
            elif mode == "Upload URLs":
                if not uploaded_file:
                    st.error("❌ Please upload a file with video URLs.")
                else:
                    video_ids = extract_video_ids_from_urls(uploaded_file)
                    with st.spinner("📄 Processing uploaded video URLs..."):
                        for vid in video_ids:
                            info = get_video_info(youtube, vid)
                            if enable_seo:
                                info["seo_output"] = generate_seo_tags(info, top_tags)
                                time.sleep(5)
                            if enable_transcript:
                                info["transcript"] = fetch_transcript(vid)
                            if enable_images:
                                img_url, err = generate_image(info["title"])
                                info["image_url"] = img_url if img_url else err
                            video_details.append(info)

            # ---------------- Display Preview Cards ----------------
            if video_details:
                st.markdown("## 🎬 Video Preview Cards")
                for idx, video in enumerate(video_details):
                    st.markdown("---")
                    cols = st.columns([1, 2])
                    with cols[0]:
                        img_url = video.get("image_url")
                        if img_url and "http" in img_url:
                            st.image(img_url, use_column_width=True)
                        else:
                            st.write(img_url)
                    with cols[1]:
                        st.markdown(f"**Title:** [{video['title']}]({video['url']})")
                        st.markdown(f"**Views:** {video['views']}  |  **Published:** {video['published_date']}")
                        if enable_seo and video.get("seo_output"):
                            with st.expander("SEO Output"):
                                st.write(video['seo_output'])
                        if enable_transcript and video.get("transcript"):
                            snippet = video['transcript'][:300] + "..." if len(video['transcript']) > 300 else video['transcript']
                            with st.expander("Transcript Snippet"):
                                st.write(snippet)

                # ---------------- Excel Download ----------------
                df = pd.DataFrame(video_details)
                output = BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False, sheet_name="Videos")
                output.seek(0)
                st.download_button(
                    label=f"⬇️ Download Excel",
                    data=output,
                    file_name="youtube_videos.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

                # ---------------- Images ZIP Download ----------------
                if enable_images:
                    image_files = []
                    for idx, video in enumerate(video_details):
                        img_url = video.get("image_url")
                        if img_url and "http" in img_url:
                            try:
                                response = requests.get(img_url)
                                if response.status_code == 200:
                                    image_files.append((f"{idx+1}_{video['video_id']}.png", response.content))
                            except Exception as e:
                                st.write(f"❌ Failed to fetch image: {e}")
                    if image_files:
                        zip_buffer = io.BytesIO()
                        with zipfile.ZipFile(zip_buffer, "w") as zip_file:
                            for filename, data in image_files:
                                zip_file.writestr(filename, data)
                        zip_buffer.seek(0)
                        st.download_button(
                            label="⬇️ Download All Images as ZIP",
                            data=zip_buffer,
                            file_name="youtube_images.zip",
                            mime="application/zip"
                        )

        except HttpError as e:
            st.error(f"API Error: {e}")
