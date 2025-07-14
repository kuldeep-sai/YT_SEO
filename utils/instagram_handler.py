import re
import requests
import random

def get_instagram_metadata(url):
    # Simulated scraping logic for demo purposes
    return {
        "url": url,
        "caption": "Sample caption about travel and nature.",
        "hashtags": "#travel #nature #adventure",
        "likes": random.randint(100, 10000),
        "comments": random.randint(10, 500)
    }

def generate_seo_content(metadata, client, top_tags):
    prompt = f"""
    Given this Instagram post:
    - Caption: {metadata['caption']}
    - Hashtags: {metadata['hashtags']}

    Top trending hashtags: {', '.join(top_tags)}

    Generate:
    - A more SEO-friendly Instagram caption (max 250 characters)
    - 10 relevant SEO hashtags
    - 10 comma-separated keyword phrases
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
    metadata = get_instagram_metadata(url)
    if enable_seo and client:
        metadata["seo_output"] = generate_seo_content(metadata, client, top_tags)
    return [metadata]

def handle_instagram_urls(file, enable_seo, client, openai_key, top_tags):
    content = file.read().decode("utf-8")
    urls = re.findall(r"https?://www\.instagram\.com/p/[a-zA-Z0-9_-]+", content)
    results = []
    for url in urls:
        metadata = get_instagram_metadata(url)
        if enable_seo and client:
            metadata["seo_output"] = generate_seo_content(metadata, client, top_tags)
        results.append(metadata)
    return results

def get_top_instagram_hashtags(topic):
    # Simulated tag list
    sample_tags = {
        "travel": ["#travelgram", "#wanderlust", "#travelphotography", "#nature", "#vacation"],
        "fitness": ["#fitspo", "#workout", "#gym", "#health", "#fitnessmotivation"],
        "fashion": ["#ootd", "#fashionblogger", "#style", "#trend", "#streetstyle"]
    }
    return sample_tags.get(topic.lower(), ["#instagood", "#photooftheday", "#love"])
