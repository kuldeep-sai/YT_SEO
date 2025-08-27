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
# CONFIG
# ----------------------------
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "YOUR_YOUTUBE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", None)

youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# ----------------------------
# HELPERS
# ----------------------------
def extract_video_id(url):
    match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11}).*", url)
    return match.group(1) if match else url

def fetch_fresh_transcript(video_id, client):
    if not client:
        return "❌ OpenAI key required for fresh transcripts."
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
    except Exception as e:
        return f"Transcript error: {str(e)}"

def fetch_transcript(video_id, client=None):
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        return " ".join([seg["text"] for seg in transcript])
    except (TranscriptsDisabled, NoTranscriptFound):
        if client:
            return fetch_fresh_transcript(video_id, client)
        else:
            return "Transcript not found"
    except Exception as e:
        return f"Transcript error: {str(e)}"

def analyze_transcript(transcript_text, client):
    if not client or not transcript_text or transcript_text.startswith("Transcript error"):
        return "", "", "", ""
    try:
        prompt = f"""
You are an SEO and YouTube content strategist.
Analyze the transcript and generate:
1. A concise 3-5 line summary.
2. 10 SEO-friendly keywords (comma-separated, no hashtags).
3. An engaging meta description (max 160 characters).
4. 8–12 relevant hashtags (each prefixed with '#').

Transcript:
{transcript_text[:5000]}
"""
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5
        )
        output = response.choices[0].message.content.strip().split("\n")
        summary = keywords = meta_desc = hashtags = ""
        for line in output:
            if line.lower().startswith("1"):
                summary = line.split(":", 1)[-1].strip()
            elif line.lower().startswith("2"):
                keywords = line.split(":", 1)[-1].strip()
            elif line.lower().startswith("3"):
                meta_desc = line.split(":", 1)[-1].strip()
            elif line.lower().startswith("4"):
                hashtags = line.split(":", 1)[-1].strip()
        return summary, keywords, meta_desc, hashtags
    except Exception as e:
        return "", "", "", f"Error generating SEO data: {str(e)}"

def fetch_video_info(video_id, client=None):
    try:
        request = youtube.videos().list(
            part="snippet,statistics,contentDetails",
            id=video_id
        )
        response = request.execute()
        if not response["items"]:
            st.warning(f"Video {video_id} not found or unavailable")
            return None, None
        item = response["items"][0]
        info = {
            "video_id": video_id,
            "title": item["snippet"]["title"],
            "description": item["snippet"].get("description", ""),
            "channel_title": item["snippet"]["channelTitle"],
            "publish_date": item["snippet"]["publishedAt"],
            "views": item["statistics"].get("viewCount", "0"),
            "likes": item["statistics"].get("likeCount", "0"),
            "comments": item["statistics"].get("commentCount", "0"),
            "duration": item["contentDetails"]["duration"],
            "video_url": f"https://www.youtube.com/watch?v={video_id}"
        }
        transcript_text = fetch_transcript(video_id, client)
        summary, keywords, meta_desc, hashtags = analyze_transcript(transcript_text, client)
        info["summary"] = summary
        info["seo_keywords"] = keywords
        info["meta_description"] = meta_desc
        info["hashtags"] = hashtags
        return info, {"video_id": video_id, "transcript": transcript_text}
    except HttpError as e:
        st.warning(f"Skipping video {video_id} due to HttpError: {e}")
        return None, None

# ----------------------------
# STREAMLIT APP
# ----------------------------
st.title("🎥 YouTube SEO & Transcript Extractor")

option = st.radio("Choose Input Method", ["Single Video", "Playlist", "CSV Upload"])
metadata_list = []
transcripts_list = []

# SINGLE VIDEO
if option == "Single Video":
    url = st.text_input("Enter YouTube video URL:")
    if st.button("Fetch"):
        if url:
            video_id = extract_video_id(url)
            info, transcript = fetch_video_info(video_id, client)
            if info:
                metadata_list.append(info)
                transcripts_list.append(transcript)
                st.success(f"Fetched: {info['title']}")
            else:
                st.error("Video not found or skipped.")

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
                        info, transcript = fetch_video_info(video_id, client)
                        if info:
                            metadata_list.append(info)
                            transcripts_list.append(transcript)
                    next_page_token = pl_response.get("nextPageToken")
                    if not next_page_token:
                        break
                st.success("Playlist fetched successfully!")

# CSV UPLOAD
elif option == "CSV Upload":
    uploaded_file = st.file_uploader("Upload CSV with column 'video_url'")
    if uploaded_file and st.button("Process CSV"):
        df = pd.read_csv(uploaded_file)
        for url in df["video_url"]:
            video_id = extract_video_id(url)
            info, transcript = fetch_video_info(video_id, client)
            if info:
                metadata_list.append(info)
                transcripts_list.append(transcript)
        st.success("CSV processed successfully!")

# EXPORT TO EXCEL
if metadata_list:
    df_meta = pd.DataFrame(metadata_list)
    df_trans = pd.DataFrame(transcripts_list)
    excel_file = "youtube_seo_data.xlsx"
    with pd.ExcelWriter(excel_file, engine="openpyxl") as writer:
        df_meta.to_excel(writer, sheet_name="Metadata", index=False)
        df_trans.to_excel(writer, sheet_name="Transcripts", index=False)

    st.dataframe(df_meta[["title", "summary", "seo_keywords", "meta_description", "hashtags"]])
    st.download_button(
        "📥 Download Excel with SEO & Hashtags",
        data=open(excel_file, "rb"),
        file_name=excel_file,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
