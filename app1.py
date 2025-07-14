# utils/instagram_handler.py
import streamlit as st
import pandas as pd
import time
import requests
import re

# --- STEP 1: Use Meta Graph API for real Instagram data ---

def extract_shortcode_from_url(url):
    match = re.search(r"instagram.com/p/([a-zA-Z0-9_-]+)", url)
    return match.group(1) if match else None

def fetch_instagram_post_data(access_token, ig_post_shortcode):
    post_url = f"https://graph.facebook.com/v18.0/instagram_oembed?url=https://www.instagram.com/p/{ig_post_shortcode}&access_token={access_token}"
    response = requests.get(post_url)
    if response.status_code == 200:
        return response.json()
    else:
        return {"error": f"Failed to fetch post. Status {response.status_code}"}

# --- STEP 2: Single Instagram video ---
def handle_instagram_single(url, enable_seo, client, api_key):
    st.subheader("📥 Instagram Video Details - Single")
    st.write(f"🔗 Video URL: {url}")

    shortcode = extract_shortcode_from_url(url)
    if not shortcode:
        st.error("Invalid Instagram URL")
        return

    data = fetch_instagram_post_data(api_key, shortcode)
    if "error" in data:
        st.error(data["error"])
        return

    video_info = {
        "url": url,
        "caption": data.get("title", ""),
        "author": data.get("author_name"),
        "media_id": shortcode
    }

    if enable_seo and client:
        seo_output = generate_seo_tags(video_info, client)
        video_info["seo_output"] = seo_output
        st.markdown("### ✨ SEO Tags")
        st.code(seo_output)

    st.json(video_info)

# --- STEP 3: Batch Mode ---
def handle_instagram_batch(profile_url, max_posts, enable_seo, client, api_key):
    st.subheader("📥 Instagram Batch Export")
    st.warning("⚠️ Batch export using Meta API requires Instagram Business account & FB App with approved scopes.")

    st.write("Feature not fully implemented due to API constraints.")

# --- STEP 4: From file ---
def handle_instagram_urls(file, enable_seo, client, api_key):
    st.subheader("📥 Instagram URLs from File")

    if file.name.endswith("csv"):
        urls = pd.read_csv(file).iloc[:, 0].tolist()
    elif file.name.endswith("txt"):
        urls = file.read().decode().splitlines()
    else:
        st.error("Unsupported file format")
        return

    all_data = []
    for url in urls:
        shortcode = extract_shortcode_from_url(url)
        if not shortcode:
            continue

        data = fetch_instagram_post_data(api_key, shortcode)
        if "error" in data:
            continue

        info = {
            "url": url,
            "caption": data.get("title", ""),
            "author": data.get("author_name"),
            "media_id": shortcode
        }

        if enable_seo and client:
            seo_output = generate_seo_tags(info, client)
            info["seo_output"] = seo_output
            time.sleep(2)

        all_data.append(info)

    df = pd.DataFrame(all_data)
    st.dataframe(df)
    st.download_button(
        label="⬇️ Download SEO Tags",
        data=df.to_csv(index=False).encode(),
        file_name="instagram_seo_tags.csv",
        mime="text/csv"
    )

# --- STEP 5: SEO Generator ---
def generate_seo_tags(data, client):
    prompt = f"""
    Analyze this Instagram post:
    Caption: {data['caption']}
    Author: {data['author']}

    Generate:
    - SEO optimized caption
    - 5 trending hashtags
    - Keywords summary
    """
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"OpenAI Error: {e}"
