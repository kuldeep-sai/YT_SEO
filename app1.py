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

st.set_page_config(page_title="📊 SEO Tools Hub", layout="centered")
st.title("📊 YouTube & Instagram SEO Generator")

# App tabs
app = st.radio("Select Platform", ["YouTube", "Instagram"], horizontal=True)

# Common sidebar config
openai_key = st.sidebar.text_input("🔐 OpenAI API Key", type="password")
seo_topic = st.sidebar.text_input("📈 (Optional) SEO Topic for trending tags")
enable_seo = st.sidebar.checkbox("✨ Enable SEO Tagging", value=True)

client = None
if openai_key:
    client = OpenAI(api_key=openai_key)

# ----------- INSTAGRAM ----------- #
if app == "Instagram":
    mode = st.radio("Select Mode", ["Single Video", "Batch (CSV/TXT)", "About"], horizontal=True)

    top_tags = get_top_instagram_hashtags(seo_topic) if seo_topic else []
    if seo_topic and top_tags:
        st.markdown(f"🔝 **Top Instagram hashtags for {seo_topic}:**")
        st.write(", ".join(top_tags))

    results = []
    if mode == "Single Video":
        url = st.text_input("Paste Instagram Post URL:")
        if url:
            results = handle_instagram_single(url, enable_seo, client, openai_key, top_tags)

    elif mode == "Batch (CSV/TXT)":
        file = st.file_uploader("Upload .csv or .txt file with Instagram post URLs")
        if file:
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
