import os
import re
import tempfile
import pandas as pd
import streamlit as st
from openai import OpenAI
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
import yt_dlp

# ----------------------------
# STREAMLIT APP SETUP
# ----------------------------
st.title("🎥 YouTube SEO, Transcript & Metadata Extractor")

# ----------------------------
# FRONT-END API KEYS
# ----------------------------
st.sidebar.header("🔑 Enter API Keys")
yt_api_key = st.sidebar.text_input("YouTube API Key", type="password")
openai_api_key = st.sidebar.text_input("OpenAI API Key (for SEO & transcription)", type="password")

if not yt_api_key:
    st.warning("Please enter your YouTube API Key to continue.")
    st.stop()

client = OpenAI(api_key=openai_api_key) if openai_api_key else None
youtube = build("youtube", "v3", developerKey=yt_api_key)
use_openai_transcript = st.sidebar.checkbox(
    "Use OpenAI transcription if YouTube captions unavailable", value=True
)

# ----------------------------
# HELPERS
# ----------------------------
def extract_video_id(url):
    match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11}).*", url)
    return match.group(1) if match else url

def fetch_fresh_transcript(video_id, client):
    if not client:
        return None
    url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmpfile:
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": tmpfile.name,
                "quiet": True,
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }],
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        with open(tmpfile.name, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="gpt-4o-mini-transcribe",
                file=audio_file
            )
        return transcript.text.strip()
    except:
        return None

def fetch_transcript(video_id, client=None, use_openai=True):
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        transcript = transcript_list.find_transcript(['en']).fetch()
        return " ".join([seg["text"] for seg in transcript])
    except (TranscriptsDisabled, NoTranscriptFound):
        if client and use_openai:
            return fetch_fresh_transcript(video_id, client)
        else:
            return None
    except:
        return None

def generate_seo(title, transcript, client):
    if not client:
        return "N/A", "N/A", "N/A", "N/A"

    transcript_text = transcript if transcript else "N/A"

    prompt = f"""
You are an SEO expert and YouTube content strategist.
Generate SEO data based on the following:

Video Title: {title}
Transcript (if available): {transcript_text}

Instructions:
- If transcript is unavailable, generate SEO keywords, meta description, and hashtags using ONLY the title and topical trends for what people might search on Google or YouTube.
- Output:
1. Concise 3-5 line summary of the video.
2. 10 SEO-friendly keywords (comma-separated, no hashtags).
3. Meta description (max 160 characters).
4. 8–12 hashtags (each prefixed with '#').
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5
        )
        output_text = response.choices[0].message.content.strip()

        # Parse output
        summary = keywords = meta_desc = hashtags = ""
        for line in output_text.split("\n"):
            if line.startswith("1"):
                summary = line.split(":",1)[-1].strip()
            elif line.startswith("2"):
                keywords = line.split(":",1)[-1].strip()
            elif line.startswith("3"):
                meta_desc = line.split(":",1)[-1].strip()
            elif line.startswith("4"):
                hashtags = line.split(":",1)[-1].strip()

        return summary, keywords, meta_desc, hashtags
    except:
        return "", "", "", ""

def fetch_video_info(video_id, client=None):
    try:
        request = youtube.videos().list(
            part="snippet,statistics,contentDetails",
            id=video_id
        )
        response = request.execute()
        if not response["items"]:
            st.warning(f"Video {video_id} not found or unavailable")
            return None

        item = response["items"][0]
        info = {
            "video_id": video_id,
            "title": item["snippet"]["title"],
            "description": item["snippet"].get("description", ""),
            "channel_title": item["snippet"]["channelTitle"],
            "publish_date": item["snippet"]["publishedAt"],
            "views": item["statistics"].get("viewCount","0"),
            "likes": item["statistics"].get("likeCount","0"),
            "comments": item["statistics"].get("commentCount","0"),
            "duration": item["contentDetails"]["duration"],
            "video_url": f"https://www.youtube.com/watch?v={video_id}"
        }

        transcript_text = fetch_transcript(video_id, client, use_openai_transcript)
        summary, keywords, meta_desc, hashtags = generate_seo(info["title"], transcript_text, client)

        info["summary"] = summary
        info["seo_keywords"] = keywords
        info["meta_description"] = meta_desc
        info["hashtags"] = hashtags
        info["transcript"] = transcript_text or "Transcript not found"

        return info
    except HttpError as e:
        st.warning(f"Skipping video {video_id} due to HttpError: {e}")
        return None

# ----------------------------
# INPUT METHOD
# ----------------------------
option = st.radio(
    "Choose Input Method",
    ["Single Video", "Playlist", "Channel", "CSV Upload"]
)
metadata_list = []

# SINGLE VIDEO
if option == "Single Video":
    url = st.text_input("Enter YouTube video URL:")
    if st.button("Fetch Video"):
        if url:
            video_id = extract_video_id(url)
            info = fetch_video_info(video_id, client)
            if info:
                metadata_list.append(info)
                st.success(f"Fetched: {info['title']}")

# PLAYLIST
elif option == "Playlist":
    playlist_url = st.text_input("Enter YouTube Playlist URL:")
    if st.button("Fetch Playlist"):
        if playlist_url:
            match = re.search(r"list=([a-zA-Z0-9_-]+)", playlist_url)
            if match:
                playlist_id = match.group(1)
                next_page_token = None
                while True:
                    pl_request = youtube.playlistItems().list(
                        part="contentDetails",
                        playlistId=playlist_id,
                        maxResults=50,
                        pageToken=next_page_token
                    )
                    pl_response = pl_request.execute()
                    for item in pl_response["items"]:
                        video_id = item["contentDetails"]["videoId"]
                        info = fetch_video_info(video_id, client)
                        if info:
                            metadata_list.append(info)
                    next_page_token = pl_response.get("nextPageToken")
                    if not next_page_token:
                        break
                st.success("Playlist fetched successfully!")

# CHANNEL
elif option == "Channel":
    channel_id = st.text_input("Enter YouTube Channel ID:")
    max_videos = st.number_input(
        "Maximum videos to fetch", min_value=1, max_value=5000, value=50, step=10
    )
    if st.button("Fetch Channel Videos"):
        if channel_id:
            try:
                res = youtube.channels().list(
                    part="contentDetails", id=channel_id
                ).execute()
                uploads_playlist = res["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

                next_page_token = None
                total_fetched = 0
                while total_fetched < max_videos:
                    pl_request = youtube.playlistItems().list(
                        part="contentDetails",
                        playlistId=uploads_playlist,
                        maxResults=min(50, max_videos - total_fetched),
                        pageToken=next_page_token
                    )
                    pl_response = pl_request.execute()
                    for item in pl_response["items"]:
                        video_id = item["contentDetails"]["videoId"]
                        info = fetch_video_info(video_id, client)
                        if info:
                            metadata_list.append(info)
                            total_fetched += 1
                    next_page_token = pl_response.get("nextPageToken")
                    if not next_page_token or total_fetched >= max_videos:
                        break
                st.success(f"Fetched {total_fetched} videos from channel {channel_id}!")
            except Exception as e:
                st.error(f"Error fetching channel videos: {e}")

# CSV UPLOAD
elif option == "CSV Upload":
    uploaded_file = st.file_uploader("Upload CSV with column 'video_url'")
    if uploaded_file and st.button("Process CSV"):
        df = pd.read_csv(uploaded_file)
        for url in df["video_url"]:
            video_id = extract_video_id(url)
            info = fetch_video_info(video_id, client)
            if info:
                metadata_list.append(info)
        st.success("CSV processed successfully!")

# ----------------------------
# DISPLAY & EXPORT TO EXCEL
# ----------------------------
if metadata_list:
    df_meta = pd.DataFrame(metadata_list)
    
    st.subheader("✅ Fetched Video Data")
    st.dataframe(df_meta[["title","summary","seo_keywords","meta_description","hashtags","transcript"]])
    
    excel_file = "youtube_seo_data.xlsx"
    with pd.ExcelWriter(excel_file, engine="openpyxl") as writer:
        df_meta.to_excel(writer, sheet_name="Videos", index=False)

    st.download_button(
        "📥 Download Excel with SEO & Transcript",
        data=open(excel_file,"rb"),
        file_name=excel_file,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
