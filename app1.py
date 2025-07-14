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

def generate_seo_tags(video, top_tags=None, client=None):
    if not client:
        return "❌ OpenAI API key is missing or not set."

    tags_string = ", ".join(top_tags) if top_tags else ""
    prompt = f"""
You are a seasoned SEO strategist and social media growth expert.

Your task is to generate a **high-converting, keyword-rich title** for this video/post that performs well on both YouTube and Instagram. The goal is to maximize **visibility, click-through rate (CTR), and search rankings** by including:

- 🔑 High-volume keywords (especially early in the title)
- ✅ Emotional triggers or curiosity elements
- 📱 Social-first appeal (snackable, clickable phrasing)
- 📈 Clear value proposition or outcome
- ⏱ Keep it under 70 characters for best performance

### Video Metadata:
Title: {video['title']}
Description: {video['description']}
Tags: {video['tags']}
Views: {video['views']}

### Top trending tags from similar viral content:
{tags_string}

Now generate:
1. A compelling SEO-optimized title (max 70 characters)
2. A 150-word keyword-rich video description (2 short paras). At the end of the description, include this sentence exactly:
[Download Naukri APP](https://play.google.com/store/apps/details?id=naukriApp.appModules.login&hl=en&utm_source=youtube&utm_medium=videos)
3. 10 SEO-relevant hashtags
4. 10 comma-separated long-tail keywords
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"OpenAI Error: {e}"

st.set_page_config(page_title="📊 SEO Tools Hub", layout="centered")
st.title("📊 YouTube & Instagram SEO Generator")

# App tabs
app = st.radio("Select Platform", ["YouTube", "Instagram"], horizontal=True)

# Common input fields
openai_key = st.text_input("🔐 OpenAI API Key", type="password")
seo_topic = st.text_input("📈 (Optional) SEO Topic for trending tags")

client = None
if openai_key:
    client = OpenAI(api_key=openai_key)

# ----------- YOUTUBE ----------- #
if app == "YouTube":
    yt_api_key = st.text_input("🔑 YouTube API Key", type="password")
    yt_mode = st.radio("Select Mode", ["Batch Mode", "Single Video", "Upload URLs"], horizontal=True)

    enable_seo = st.checkbox("✨ Enable SEO Tagging", value=True)

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
    ig_api_key = st.text_input("📷 Instagram API Key (optional)", type="password")

    url = st.text_input("Paste Instagram Post URL:") if ig_mode == "Single Video" else None
    file = st.file_uploader("Upload .csv or .txt file with Instagram post URLs") if ig_mode == "Batch (CSV/TXT)" else None
    enable_seo = st.checkbox("✨ Enable SEO Tagging", value=True)

    top_tags = get_top_instagram_hashtags(seo_topic) if seo_topic else []
    if seo_topic and top_tags:
        st.markdown(f"🔝 **Top Instagram hashtags for {seo_topic}:**")
        st.write(", ".join(top_tags))

    results = []
    if ig_mode == "Single Video" and url and st.button("📥 Fetch Post"):
        results = handle_instagram_single(url, enable_seo, client, openai_key, top_tags, ig_api_key)

    elif ig_mode == "Batch (CSV/TXT)" and file and st.button("📥 Process File"):
        results = handle_instagram_urls(file, enable_seo, client, openai_key, top_tags, ig_api_key)

    elif ig_mode == "About":
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
