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
            return N
