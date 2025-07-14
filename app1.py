import streamlit as st
import pandas as pd
from io import BytesIO
from openai import OpenAI
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
import os
import re

# Custom imports
from utils.instagram_handler import handle_instagram_single, handle_instagram_urls, get_top_instagram_hashtags
from utils.youtube_handler import (
    handle_youtube_batch,
    handle_youtube_single,
    handle_youtube_urls,
    get_top_video_tags
)

st.set_page_config(page_title="📊 SEO Tools Hub", layout="centered")
st.title("📊 YouTube & Instagram SEO Generator")

# App tabs
app = st.radio("Select Platform", ["YouTube", "Instagram"], horizontal=True)

# Common input fields
openai_key = st.text_input("🔐 OpenAI API Key", type="password")
seo_topic = st.text_input("📈 (Optional) SEO Topic for trending tags")
enable_seo = st.checkbox("✨ Enable SEO Tagging", value=True)

client = None
if openai_key:
    client = OpenAI(api_key=openai_key)

# ----------- YOUTUBE ----------- #
if app == "YouTube":
    yt_api_key = st.text_input("🔑 YouTube API Key", type="password")
    yt_mode = st.radio("Select Mode", ["Batch Mode", "Single Video", "Upload URLs"], horizontal=True)

    top_tags = get_top_video_tags(yt_api_key, seo_topic) if seo_topic else []
    if seo_topic and top_tags:
        st.markdown(f"🔝 **Top YouTube tags for {seo_topic}:**")
        st.write(", ".join(top_tags))

    results = []
    if yt_mode == "Batch Mode":
        channel_id = st.text_input("📡 YouTube Channel ID (e.g. UC_xxx...)")
        batch_number = st.selectbox("📦 Select Batch (500 videos each)", options=list(range(1, 21)), index=0)
        start_index = (batch_number - 1) * 500
        num_videos = st.number_input("🎬 Number of videos to fetch", min_value=1, max_value=500, value=500, step=1)
        if st.button("📥 Fetch Batch"):
            results = handle_youtube_batch(yt_api_key, channel_id, start_index, num_videos, enable_seo, client, top_tags)

    elif yt_mode == "Single Video":
        video_id_input = st.text_input("🎥 Enter Video ID (e.g. dQw4w9WgXcQ)")
        if st.button("📥 Fetch Single"):
            results = handle_youtube_single(yt_api_key, video_id_input, enable_seo, client, top_tags)

    elif yt_mode == "Upload URLs":
        uploaded_file = st.file_uploader("📄 Upload CSV or TXT with YouTube Video URLs", type=["csv", "txt"])
        if uploaded_file and st.button("📥 Process URLs"):
            results = handle_youtube_urls(yt_api_key, uploaded_file, enable_seo, client, top_tags)

    if results:
        df = pd.DataFrame(results)
        st.dataframe(df)

        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name="YouTube SEO")
        output.seek(0)

        st.download_button(
            label="⬇️ Download YouTube SEO Report",
            data=output,
            file_name="youtube_seo.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# ----------- INSTAGRAM ----------- #
elif app == "Instagram":
    ig_mode = st.radio("Select Mode", ["Single Video", "Batch (CSV/TXT)", "About"], horizontal=True)

    top_tags = get_top_instagram_hashtags(seo_topic) if seo_topic else []
    if seo_topic and top_tags:
        st.markdown(f"🔝 **Top Instagram hashtags for {seo_topic}:**")
        st.write(", ".join(top_tags))

    results = []
    if ig_mode == "Single Video":
        url = st.text_input("Paste Instagram Post URL:")
        if url and st.button("📥 Fetch Post"):
            results = handle_instagram_single(url, enable_seo, client, openai_key, top_tags)

    elif ig_mode == "Batch (CSV/TXT)":
        file = st.file_uploader("Upload .csv or .txt file with Instagram post URLs")
        if file and st.button("📥 Process File"):
            results = handle_instagram_urls(file, enable_seo, client, openai_key, top_tags)

    else:
        st.markdown("""
            This tool extracts Instagram post info and generates SEO content using ChatGPT.

            ✅ Supports:
            - Public Instagram posts via URL
            - SEO captions, hashtags, keywords

            ⚠️ Batch mode requires CSV/TXT upload.

            Built using [Streamlit](https://streamlit.io/)
        """)

    if results:
        df = pd.DataFrame(results)
        st.dataframe(df)

        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name="Instagram SEO")
        output.seek(0)

        st.download_button(
            label="⬇️ Download Instagram SEO Report",
            data=output,
            file_name="instagram_seo.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
