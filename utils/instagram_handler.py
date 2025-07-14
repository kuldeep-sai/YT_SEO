import streamlit as st
import pandas as pd
import time
import re
from io import BytesIO

# Placeholder function to simulate fetching IG post data
def get_instagram_video_info(post_url, instagram_api_key=None):
    # TODO: Replace this mock with real scraping or Instagram Graph API
    return {
        "url": post_url,
        "caption": "Sample Instagram caption for post.",
        "hashtags": "#instagood #reels #viral",
        "video_description": "Mock video description extracted from post content",
        "likes": 1234,
        "comments": 56
    }

def generate_instagram_seo_tags(video_info, client):
    if not client:
        return "❌ OpenAI API key is missing or not set."

    prompt = f"""
    You are an expert Instagram SEO specialist. Analyze the following video post data:

    Caption: {video_info['caption']}
    Hashtags: {video_info['hashtags']}
    Video Description: {video_info['video_description']}
    Likes: {video_info['likes']}
    Comments: {video_info['comments']}

    Generate:
    - A short SEO-optimized post title
    - A 100-word Instagram caption optimized with trending keywords
    - A list of 10 Instagram hashtags
    - A comma-separated list of SEO keywords
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"OpenAI Error: {e}"

def handle_instagram_single(instagram_url_input, enable_seo, client, instagram_api_key):
    st.subheader("📥 Instagram Post Preview")
    video_info = get_instagram_video_info(instagram_url_input, instagram_api_key)

    if enable_seo:
        video_info["seo_output"] = generate_instagram_seo_tags(video_info, client)
        time.sleep(3)

    st.write(video_info)

def handle_instagram_batch(profile_url, max_posts, enable_seo, client, instagram_api_key):
    # TODO: Fetch posts from profile (currently mocked as duplicates)
    video_details = []
    for i in range(max_posts):
        post_url = f"{profile_url}?post={i}"
        info = get_instagram_video_info(post_url, instagram_api_key)
        if enable_seo:
            info["seo_output"] = generate_instagram_seo_tags(info, client)
            time.sleep(3)
        video_details.append(info)

    df = pd.DataFrame(video_details)
    st.dataframe(df)

    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name="Instagram Videos")
    output.seek(0)

    st.download_button(
        label="⬇️ Download Instagram SEO Report",
        data=output,
        file_name="instagram_seo_report.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

def handle_instagram_urls(file, enable_seo, client, instagram_api_key):
    content = file.read().decode("utf-8")
    urls = content.splitlines()
    urls = [line.strip() for line in urls if line.strip()]

    video_details = []
    for url in urls:
        info = get_instagram_video_info(url, instagram_api_key)
        if enable_seo:
            info["seo_output"] = generate_instagram_seo_tags(info, client)
            time.sleep(3)
        video_details.append(info)

    df = pd.DataFrame(video_details)
    st.dataframe(df)

    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name="Instagram URLs")
    output.seek(0)

    st.download_button(
        label="⬇️ Download Instagram SEO from URLs",
        data=output,
        file_name="instagram_urls_seo.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
