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

# Page setup
st.set_page_config(page_title="YouTube & Instagram Video Exporter + SEO Generator", layout="centered")
st.title("📊 YouTube & Instagram Video Exporter + SEO Generator + Transcript")

st.markdown("Export videos from YouTube or Instagram. Optionally generate SEO-optimized titles, descriptions, keywords, and transcripts.")

# Platform selection
platform = st.radio("📺 Select Platform", ["YouTube", "Instagram"], horizontal=True)

# Mode selection
mode = st.radio("🔍 Select Mode", ["Batch Mode", "Single Video", "Upload URLs"], horizontal=True)

# Input form
with st.form(key="form"):
    if platform == "YouTube":
        yt_api_key = st.text_input("🔑 YouTube API Key", type="password")
        openai_key_input = st.text_input("🤖 OpenAI API Key (optional - for SEO tagging)", type="password")
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

    elif platform == "Instagram":
        openai_key_input = st.text_input("🤖 OpenAI API Key (optional - for SEO tagging)", type="password")
        instagram_api_key = st.text_input("🔐 Instagram API Key (optional)", type="password")

        if mode == "Single Video":
            instagram_url_input = st.text_input("🎥 Enter Instagram Video URL")
        elif mode == "Batch Mode":
            st.markdown("🔗 **Enter Instagram Profile URL and Number of Posts to Fetch**")
            instagram_profile_url = st.text_input("🔗 Instagram Profile URL")
            max_posts = st.number_input("📄 Number of posts to fetch", min_value=1, max_value=500, value=50)
        else:
            ig_urls_file = st.file_uploader("📄 Upload CSV or TXT with Instagram Video URLs", type=["csv", "txt"])

        enable_seo = st.checkbox("✨ Enable SEO Tagging using ChatGPT")
        enable_transcript = False
        yt_api_key = ""
        seo_topic = ""

    submit = st.form_submit_button("📥 Fetch Video(s)")

# Use provided API key or fallback to secrets
effective_openai_key = openai_key_input or st.secrets.get("OPENAI_API_KEY", "")
client = OpenAI(api_key=effective_openai_key) if effective_openai_key else None

# 🚀 Processing logic
if submit:
    if platform == "YouTube":
        from utils.youtube_handler import handle_youtube_batch, handle_youtube_single, handle_youtube_urls
        youtube = build("youtube", "v3", developerKey=yt_api_key)

        if mode == "Batch Mode":
            handle_youtube_batch(youtube, channel_id, start_index, num_videos, enable_seo, enable_transcript, client, seo_topic)

        elif mode == "Single Video":
            handle_youtube_single(youtube, video_id_input, enable_seo, enable_transcript, client, seo_topic)

        elif mode == "Upload URLs" and uploaded_file is not None:
            handle_youtube_urls(uploaded_file, youtube, enable_seo, enable_transcript, client, seo_topic)

    elif platform == "Instagram":
        from utils.instagram_handler import handle_instagram_single, handle_instagram_batch, handle_instagram_urls

        if mode == "Single Video":
            handle_instagram_single(instagram_url_input, enable_seo, client)

        elif mode == "Batch Mode":
            handle_instagram_batch(instagram_profile_url, max_posts, enable_seo, client)

        elif mode == "Upload URLs" and ig_urls_file is not None:
            handle_instagram_urls(ig_urls_file, enable_seo, client)
