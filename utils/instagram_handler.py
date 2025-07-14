import re
import pandas as pd
import time

def extract_instagram_post_id(url):
    match = re.search(r"instagram.com/p/([\w-]+)/", url)
    return match.group(1) if match else None

def mock_fetch_instagram_post_data(url):
    # Simulated placeholder for post data fetch
    return {
        "post_url": url,
        "caption": f"Sample caption extracted from {url}",
        "likes": 1234,
        "hashtags": ["#ai", "#instagood", "#openai"]
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

def handle_instagram_single(url, enable_seo, client, openai_key, top_tags):
    post = mock_fetch_instagram_post_data(url)
    if enable_seo:
        post["seo_output"] = generate_seo_from_instagram(post, client, openai_key, top_tags)
        time.sleep(5)
    return [post]

def handle_instagram_urls(file, enable_seo, client, openai_key, top_tags):
    content = file.read().decode("utf-8")
    urls = content.strip().splitlines()
    results = []
    for url in urls:
        post = mock_fetch_instagram_post_data(url)
        if enable_seo:
            post["seo_output"] = generate_seo_from_instagram(post, client, openai_key, top_tags)
            time.sleep(5)
        results.append(post)
    return results

def get_top_instagram_hashtags(topic):
    sample = {
        "fitness": ["#fitness", "#fitspo", "#workout", "#gymlife"],
        "travel": ["#travelgram", "#wanderlust", "#explore", "#vacationvibes"],
        "fashion": ["#ootd", "#fashionblogger", "#styleinspo", "#lookbook"],
        "food": ["#foodie", "#yum", "#instafood", "#foodstagram"]
    }
    return sample.get(topic.lower(), [f"#{topic}", "#reels", "#trending", "#viral"])
