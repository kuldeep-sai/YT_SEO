import os
import streamlit as st
import pandas as pd
from openai import OpenAI
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
import yt_dlp

# ---------------------------
# Session State Setup
# ---------------------------
if "openai_key" not in st.session_state:
    st.session_state.openai_key = ""
if "youtube_key" not in st.session_state:
    st.session_state.youtube_key = ""
if "channel_or_video" not in st.session_state:
    st.session_state.channel_or_video = ""

# ---------------------------
# Sidebar Inputs (Keys + IDs)
# ---------------------------
st.sidebar.subheader("🔑 API & Video Settings")

st.session_state.openai_key = st.sidebar.text_input(
    "OpenAI API Key", value=st.session_state.openai_key, type="password"
)

st.session_state.youtube_key = st.sidebar.text_input(
    "YouTube API Key", value=st.session_state.youtube_key, type="password"
)

st.session_state.channel_or_video = st.sidebar.text_input(
    "Channel ID or Video URL/ID", value=st.session_state.channel_or_video
)

# Initialize OpenAI client
client = None
if st.session_state.openai_key:
    client = OpenAI(api_key=st.session_state.openai_key)

# ---------------------------
# Transcript Fetcher (YouTube + Whisper Fallback)
# ---------------------------
def fetch_transcript(video_id, client=None):
    """
    Try to fetch YouTube transcript.
    If unavailable, fallback to Whisper transcription.
    """
    try:
        # Try YouTube transcript first
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        transcript = transcript_list.find_transcript(['en']).fetch()
        return " ".join([seg["text"] for seg in transcript])
    except (TranscriptsDisabled, NoTranscriptFound):
        # Fall back to Whisper if client available
        if client:
            try:
                url = f"https://www.youtube.com/watch?v={video_id}"
                ydl_opts = {"format": "bestaudio/best", "outtmpl": f"{video_id}.%(ext)s"}
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    audio_file = ydl.prepare_filename(info)

                with open(audio_file, "rb") as f:
                    transcript = client.audio.transcriptions.create(
                        model="gpt-4o-mini-transcribe",  # Whisper model
                        file=f
                    )
                return transcript.text
            except Exception as e:
                return f"Transcript not found (error: {e})"
        return "Transcript not found"
    except Exception:
        return "Transcript not found"

# ---------------------------
# Dummy Video Processor (replace with your API call)
# ---------------------------
def process_video(video_id, enable_transcript=False):
    video_data = {
        "video_id": video_id,
        "title": f"Sample Title for {video_id}",
        "views": 12345,
        "likes": 678,
        "comments": 90,
    }
    if enable_transcript:
        video_data["transcript"] = fetch_transcript(video_id, client)
    else:
        video_data["transcript"] = None
    return video_data

# ---------------------------
# Main UI
# ---------------------------
st.title("🎥 YouTube Video Analyzer")

enable_transcript = st.checkbox("Enable Transcript (YouTube + Whisper Fallback)")

if st.button("Process Video(s)"):
    video_id = st.session_state.channel_or_video.strip()
    if not video_id:
        st.error("Please enter a channel ID or video ID first.")
    else:
        with st.spinner("Processing video..."):
            video = process_video(video_id, enable_transcript=enable_transcript)

            st.subheader(f"📌 {video['title']}")
            st.write(f"👁️ Views: {video['views']}")
            st.write(f"👍 Likes: {video['likes']}")
            st.write(f"💬 Comments: {video['comments']}")

            if enable_transcript and video.get("transcript"):
                with st.expander("Transcript"):
                    st.write(video["transcript"][:500] + "...")
                    st.download_button(
                        "⬇️ Download Full Transcript",
                        video["transcript"],
                        file_name=f"{video['video_id']}_transcript.txt"
                    )

            # Excel Export
            df = pd.DataFrame([video])
            df = df[["video_id", "title", "views", "likes", "comments", "transcript"]]  # include transcript
            df.to_excel("video_report.xlsx", index=False)
            with open("video_report.xlsx", "rb") as f:
                st.download_button("⬇️ Download Excel Report", f, file_name="video_report.xlsx")
