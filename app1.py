# utils/instagram_handler.py
import streamlit as st
import pandas as pd
import time

# Stub methods for now

def handle_instagram_single(url, enable_seo, client, api_key):
    st.subheader("📥 Instagram Video Details - Single")
    st.write(f"🔗 Video URL: {url}")

    # Simulated metadata extraction
    video_info = {
        "url": url,
        "caption": "Sample caption extracted from Instagram",
        "likes": 1234,
        "comments": 56
    }

    if enable_seo and client:
        seo_output = generate_seo_tags(video_info, client)
        video_info["seo_output"] = seo_output
        st.markdown("### ✨ SEO Tags")
        st.code(seo_output)

    st.json(video_info)

def handle_instagram_batch(profile_url, max_posts, enable_seo, client, api_key):
    st.subheader("📥 Instagram Batch Export")
    st.write(f"Fetching {max_posts} posts from: {profile_url}")

    # Simulated fetch
    all_data = []
    for i in range(max_posts):
        url = f"https://www.instagram.com/p/fake_id_{i}/"
        data = {
            "url": url,
            "caption": f"Sample caption {i}",
            "likes": 100 + i,
            "comments": 5 + i
        }

        if enable_seo and client:
            seo_output = generate_seo_tags(data, client)
            data["seo_output"] = seo_output
            time.sleep(2)  # Delay to avoid OpenAI rate limits

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
        data = {
            "url": url,
            "caption": f"Sample caption for {url}",
            "likes": 250,
            "comments": 30
        }

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
