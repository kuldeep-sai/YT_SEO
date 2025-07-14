# utils/instagram_handler.py
import streamlit as st
import pandas as pd
import requests
import time


def get_instagram_post_data(access_token, ig_user_id, limit=10):
    url = f"https://graph.facebook.com/v19.0/{ig_user_id}/media"
    params = {
        "fields": "caption,media_url,permalink,like_count,comments_count,timestamp",
        "access_token": access_token,
        "limit": limit
    }
    res = requests.get(url, params=params)
    if res.status_code != 200:
        raise Exception(f"Graph API Error: {res.text}")
    return res.json().get("data", [])

def get_instagram_video_details(permalink):
    return {
        "url": permalink,
        "caption": "Could not fetch caption via scraping",
        "likes": 0,
        "comments": 0
    }

def handle_instagram_single(url, enable_seo, client, api_key):
    st.subheader("📥 Instagram Video Details - Single")
    st.write(f"🔗 Video URL: {url}")

    # Meta Graph API doesn't support public scraping by URL; you'd need to resolve URL to media ID
    video_info = get_instagram_video_details(url)

    if enable_seo and client:
        seo_output = generate_seo_tags(video_info, client)
        video_info["seo_output"] = seo_output
        st.markdown("### ✨ SEO Tags")
        st.code(seo_output)

    st.json(video_info)

def handle_instagram_batch(profile_id, max_posts, enable_seo, client, access_token):
    st.subheader("📥 Instagram Batch Export")
    st.write(f"Fetching {max_posts} posts for profile ID: {profile_id}")

    try:
        posts = get_instagram_post_data(access_token, profile_id, limit=max_posts)
    except Exception as e:
        st.error(f"❌ Error: {e}")
        return

    all_data = []
    for post in posts:
        data = {
            "url": post.get("permalink"),
            "caption": post.get("caption", ""),
            "likes": post.get("like_count", 0),
            "comments": post.get("comments_count", 0),
            "timestamp": post.get("timestamp")
        }

        if enable_seo and client:
            seo_output = generate_seo_tags(data, client)
            data["seo_output"] = seo_output
            time.sleep(2)

        all_data.append(data)

    df = pd.DataFrame(all_data)
    st.dataframe(df)

    st.download_button(
        label="⬇️ Download Instagram Data",
        data=df.to_csv(index=False).encode(),
        file_name="instagram_data.csv",
        mime="text/csv"
    )

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
        data = get_instagram_video_details(url)

        if enable_seo and client:
            seo_output = generate_seo_tags(data, client)
            data["seo_output"] = seo_output
            time.sleep(2)

        all_data.append(data)

    df = pd.DataFrame(all_data)
    st.dataframe(df)
    st.download_button(
        label="⬇️ Download SEO Tags",
        data=df.to_csv(index=False).encode(),
        file_name="instagram_seo_tags.csv",
        mime="text/csv"
    )

def generate_seo_tags(data, client):
    prompt = f"""
    Analyze this Instagram post:
    Caption: {data['caption']}
    Likes: {data['likes']}
    Comments: {data['comments']}

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
