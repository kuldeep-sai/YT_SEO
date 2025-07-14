import re
import pandas as pd
import time
from io import BytesIO
import streamlit as st


def extract_instagram_post_id(url):
    match = re.search(r"instagram.com/p/([\w-]+)/", url)
    return match.group(1) if match else None

def mock_fetch_instagram_post_data(url, ig_api_key=None):
    # Simulated placeholder for post data fetch (replace this with real API logic if needed)
    return {
        "post_url": url,
        "caption": f"Sample caption extracted from {url}",
        "likes": 1234,
        "hashtags": ["#ai", "#instagood", "#openai"],
        "api_key_used": bool(ig_api_key)
    }

def generate_seo_from_instagram(post, client, openai_key, top_tags):
    if not client:
        return "❌ OpenAI key missing"

    hashtags = ", ".join(post.get("hashtags", []))
    tags_string = ", ".join(top_tags) if top_tags else ""

    prompt = f"""
    You are an Instagram SEO assistant. Analyze the following:

    Caption: {post['caption']}
    Hashtags: {hashtags}
    Likes: {post['likes']}
    Trending tags: {tags_string}

    Generate:
    - A rewritten SEO-optimized caption (within 2200 characters)
    - 10 trending Instagram hashtags
    - A list of 10 comma-separated SEO keywords
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"OpenAI Error: {e}"

def handle_instagram_single(url, enable_seo, client, openai_key, top_tags, ig_api_key=None):
    st.subheader("📸 Instagram Single Post Analysis")

    with st.form(key="insta_single_form"):
        ig_api_key = st.text_input("📷 Instagram API Key (optional)", value=ig_api_key, key="single_ig_key")
        url = st.text_input("📎 Paste Instagram Post URL:", value=url, key="single_post_url")
        enable_seo = st.checkbox("✨ Enable SEO Tagging", value=enable_seo)
        submit = st.form_submit_button("📥 Fetch Instagram Data")
        if submit:
            post = mock_fetch_instagram_post_data(url, ig_api_key)
            if enable_seo:
                post["seo_output"] = generate_seo_from_instagram(post, client, openai_key, top_tags)
                time.sleep(5)
            st.json(post)

def handle_instagram_urls(file, enable_seo, client, openai_key, top_tags, ig_api_key=None):
    st.subheader("📸 Instagram Batch URL Analysis")
    if not file:
        st.info("📄 Please upload a file first.")
        return

    with st.form(key="insta_batch_form"):
        ig_api_key = st.text_input("📷 Instagram API Key (optional)", value=ig_api_key, key="batch_ig_key")
        enable_seo = st.checkbox("✨ Enable SEO Tagging", value=enable_seo)
        submit = st.form_submit_button("📥 Fetch Instagram Data")
        if submit:
            content = file.read().decode("utf-8")
            urls = content.strip().splitlines()
            results = []
            for url in urls:
                post = mock_fetch_instagram_post_data(url, ig_api_key)
                if enable_seo:
                    post["seo_output"] = generate_seo_from_instagram(post, client, openai_key, top_tags)
                    time.sleep(5)
                results.append(post)

            df = pd.DataFrame(results)
            st.dataframe(df)

            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name="Instagram SEO")
            output.seek(0)

            st.download_button(
                label=f"⬇️ Download Instagram SEO Report",
                data=output,
                file_name="instagram_seo.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

def get_top_instagram_hashtags(topic):
    sample = {
        "fitness": ["#fitness", "#fitspo", "#workout", "#gymlife"],
        "travel": ["#travelgram", "#wanderlust", "#explore", "#vacationvibes"],
        "fashion": ["#ootd", "#fashionblogger", "#styleinspo", "#lookbook"],
        "food": ["#foodie", "#yum", "#instafood", "#foodstagram"]
    }
    return sample.get(topic.lower(), [f"#{topic}", "#reels", "#trending", "#viral"])
