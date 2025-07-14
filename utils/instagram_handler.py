import requests
import re
import pandas as pd
from urllib.parse import urlparse


def extract_instagram_shortcode(url):
    match = re.search(r"instagram.com/p/([\w-]+)/", url)
    return match.group(1) if match else None


def scrape_instagram_metadata(shortcode):
    try:
        url = f"https://www.instagram.com/p/{shortcode}/?__a=1&__d=dis"
        headers = {
            "User-Agent": "Mozilla/5.0"
        }
        res = requests.get(url, headers=headers)
        if res.status_code != 200:
            return {"error": f"Unable to fetch data: {res.status_code}"}

        data = res.json()
        try:
            media = data['graphql']['shortcode_media']
        except:
            media = data['items'][0]

        return {
            "shortcode": shortcode,
            "caption": media['edge_media_to_caption']['edges'][0]['node']['text'] if media['edge_media_to_caption']['edges'] else '',
            "hashtags": ", ".join(re.findall(r"#\w+", media['edge_media_to_caption']['edges'][0]['node']['text'])) if media['edge_media_to_caption']['edges'] else '',
            "likes": media.get('edge_media_preview_like', {}).get('count', 0),
            "comments": media.get('edge_media_to_comment', {}).get('count', 0),
            "url": f"https://www.instagram.com/p/{shortcode}/"
        }

    except Exception as e:
        return {"shortcode": shortcode, "error": str(e)}


def generate_instagram_seo(meta, client, openai_key, top_tags=[]):
    if not client:
        return "OpenAI key missing"

    prompt = f"""
    You are an expert Instagram SEO strategist.

    Caption: {meta['caption']}
    Hashtags: {meta['hashtags']}
    Likes: {meta['likes']}
    Comments: {meta['comments']}
    Top Industry Hashtags: {', '.join(top_tags)}

    Generate:
    - A short, viral SEO caption (under 150 characters)
    - 10 SEO-optimized hashtags
    - A comma-separated list of keyword phrases
    """

    try:
        res = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}]
        )
        return res.choices[0].message.content
    except Exception as e:
        return f"OpenAI Error: {str(e)}"


def handle_instagram_single(url, enable_seo, client, openai_key, top_tags):
    shortcode = extract_instagram_shortcode(url)
    if not shortcode:
        return [{"url": url, "error": "Invalid Instagram URL"}]
    meta = scrape_instagram_metadata(shortcode)
    if enable_seo and "error" not in meta:
        meta["seo_output"] = generate_instagram_seo(meta, client, openai_key, top_tags)
    return [meta]


def handle_instagram_urls(file, enable_seo, client, openai_key, top_tags):
    content = file.read().decode("utf-8")
    urls = re.findall(r"https?://www.instagram.com/p/[\w-]+/?", content)
    results = []
    for url in urls:
        results.extend(handle_instagram_single(url, enable_seo, client, openai_key, top_tags))
    return results


def get_top_instagram_hashtags(topic):
    # Placeholder for trend-based hashtags, ideally use a real API or database
    trending = {
        "fitness": ["#fitlife", "#workout", "#gymlife", "#fitnessgoals", "#fitfam"],
        "travel": ["#wanderlust", "#travelgram", "#adventure", "#explore", "#travelphotography"],
        "fashion": ["#ootd", "#fashionblogger", "#styleinspo", "#streetstyle", "#fashionista"]
    }
    return trending.get(topic.lower(), [])
