import streamlit as st
from utils.instagram_handler import handle_instagram_single, handle_instagram_batch, handle_instagram_urls

st.set_page_config(page_title="📸 Instagram SEO Helper")
st.title("📸 Instagram SEO Analyzer")

mode = st.sidebar.selectbox("Select Mode", ["Single Video", "Batch (CSV/TXT)", "Batch (Not supported)", "About"])

openai_key = st.sidebar.text_input("🔐 OpenAI API Key", type="password")
enable_seo = st.sidebar.checkbox("✨ Enable SEO Tagging", value=True)

client = None
if openai_key:
    from openai import OpenAI
    client = OpenAI(api_key=openai_key)

if mode == "Single Video":
    url = st.text_input("Paste Instagram Post URL:")
    if url:
        handle_instagram_single(url, enable_seo, client, openai_key)

elif mode == "Batch (CSV/TXT)":
    file = st.file_uploader("Upload .csv or .txt file with Instagram post URLs")
    if file:
        handle_instagram_urls(file, enable_seo, client, openai_key)

elif mode == "Batch (Not supported)":
    st.warning("Batch mode using public Instagram API is not supported.")
    st.markdown("Use the CSV or TXT option instead.")

else:
    st.markdown("""
        This tool extracts Instagram post info and generates SEO content using ChatGPT.

        ✅ Supports:
        - Public Instagram posts via URL
        - SEO captions, hashtags, keywords

        ⚠️ Batch mode requires CSV/TXT upload.

        Built using [Streamlit](https://streamlit.io/)
    """)
