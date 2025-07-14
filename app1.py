import streamlit as st
from utils.instagram_handler import handle_instagram_single, handle_instagram_batch, handle_instagram_urls, get_top_instagram_hashtags
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="📸 Instagram SEO Helper", layout="centered")
st.title("📸 Instagram SEO Analyzer + Tag Generator")

# Mode and SEO setup
mode = st.sidebar.selectbox("Select Mode", ["Single Video", "Batch (CSV/TXT)", "Batch (Not supported)", "About"])
openai_key = st.sidebar.text_input("🔐 OpenAI API Key", type="password")
seo_topic = st.sidebar.text_input("📈 (Optional) SEO Topic for trending hashtags")
enable_seo = st.sidebar.checkbox("✨ Enable SEO Tagging", value=True)

# OpenAI Client
client = None
if openai_key:
    from openai import OpenAI
    client = OpenAI(api_key=openai_key)

# Get top tags (optional)
top_tags = get_top_instagram_hashtags(seo_topic) if seo_topic else []
if seo_topic and top_tags:
    st.markdown(f"🔝 **Top Instagram hashtags for {seo_topic}:**")
    st.write(", ".join(top_tags))

# Results container
results = []

if mode == "Single Video":
    url = st.text_input("Paste Instagram Post URL:")
    if url:
        results = handle_instagram_single(url, enable_seo, client, openai_key, top_tags)

elif mode == "Batch (CSV/TXT)":
    file = st.file_uploader("Upload .csv or .txt file with Instagram post URLs")
    if file:
        results = handle_instagram_urls(file, enable_seo, client, openai_key, top_tags)

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

# Display results and allow download
if results:
    df = pd.DataFrame(results)
    st.dataframe(df)

    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name="Instagram SEO")
    output.seek(0)

    st.download_button(
        label="⬇️ Download SEO Report",
        data=output,
        file_name="instagram_seo.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
