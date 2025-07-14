# utils/youtube_handler.py

import pandas as pd
import time
import re
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from googleapiclient.discovery import build

def get_top_video_tags(api_key, topic, max_results=20):
    try:
        youtube = build("youtube", "v3", developerKey=api_key)
        search_res = youtube.search().list(
            q=topic,
            part="snippet",
            type="video",
            order="viewCount",
            maxResults=max_results
        ).execute()
        video_ids = [item["id"]["videoId"] for item in search_res["items"]]
        tags = []
        for vid in video_ids:
            res = youtube.videos().list(part="snippet", id=vid).execute()
            if res["items"]:
                tags.extend(res["items"][0]["snippet"].get("tags", []))
        tag_freq = pd.Series(tags).value_counts()
        return tag_freq.index.tolist()[:20]
    except Exception:
        return []

def get_video_info(youtube, video_id):
    res = youtube.videos().list(part="snippet,statistics", id=video_id).execute()
    if not res["items"]:
        return {"video_id": video_id, "error": "Video not found or unavailable"}
    item = res["items"][0]
    return {
        "video_id": video_id,
        "title": item["snippet"]["title"],
        "description": item["snippet"]["description"],
        "tags": ", ".join(item["snippet"].get("tags", [])),
        "views": item["statistics"].get("viewCount", "0"),
        "published_date": item["snippet"]["publishedAt"],
        "url": f"https://www.youtube.com/watch?v={video_id}"
    }

def fetch_transcript(video_id):
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        return " ".join([seg["text"] for seg in transcript])
    except (TranscriptsDisabled, NoTranscriptFound):
        return "Transcript not found"
    except Exception:
        return "Transcript not found"

def extract_video_ids_from_urls(file):
    content = file.read().decode("utf-8")
    urls = content.splitlines()
    ids = []
    for url in urls:
        match = re.search(r"(?:v=|youtu.be/)([\w-]{11})", url)
        if match:
            ids.append(match.group(1))
    return ids

def handle_youtube_batch(api_key, channel_id, start_index, num_videos, enable_seo, client, top_tags):
    youtube = build("youtube", "v3", developerKey=api_key)
    data = youtube.channels().list(part="contentDetails", id=channel_id).execute()
    playlist_id = data["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

    # Fetch video IDs
    videos = []
    next_token = None
    while len(videos) < start_index + num_videos:
        res = youtube.playlistItems().list(
            part="contentDetails,snippet",
            playlistId=playlist_id,
            maxResults=min(50, start_index + num_videos - len(videos)),
            pageToken=next_token
        ).execute()
        for item in res["items"]:
            videos.append({
                "video_id": item["contentDetails"]["videoId"],
                "published_at": item["contentDetails"].get("videoPublishedAt") or item["snippet"]["publishedAt"]
            })
        next_token = res.get("nextPageToken")
        if not next_token:
            break

    selected_batch = sorted(videos, key=lambda x: x["published_at"], reverse=True)[start_index:start_index + num_videos]
    results = []
    for v in selected_batch:
        info = get_video_info(youtube, v["video_id"])
        if enable_seo and client:
            info["seo_output"] = generate_seo_tags(info, client, top_tags)
        info["transcript"] = fetch_transcript(v["video_id"])
        results.append(info)
        time.sleep(5)
    return results

def handle_youtube_single(api_key, video_id, enable_seo, client, top_tags):
    youtube = build("youtube", "v3", developerKey=api_key)
    info = get_video_info(youtube, video_id)
    if enable_seo and client:
        info["seo_output"] = generate_seo_tags(info, client, top_tags)
    info["transcript"] = fetch_transcript(video_id)
    return [info]

def handle_youtube_urls(api_key, uploaded_file, enable_seo, client, top_tags):
    youtube = build("youtube", "v3", developerKey=api_key)
    video_ids = extract_video_ids_from_urls(uploaded_file)
    results = []
    for vid in video_ids:
        info = get_video_info(youtube, vid)
        if enable_seo and client:
            info["seo_output"] = generate_seo_tags(info, client, top_tags)
        info["transcript"] = fetch_transcript(vid)
        results.append(info)
        time.sleep(5)
    return results

def generate_seo_tags(video, client, top_tags=None):
    tags_string = ", ".join(top_tags) if top_tags else ""
    prompt = f"""
    You are an expert YouTube SEO optimizer. Given this video metadata:

    Title: {video['title']}
    Description: {video['description']}
    Tags: {video['tags']}
    Views: {video['views']}

    Top trending tags: {tags_string}

    Generate:
    - A compelling SEO-optimized YouTube title (under 70 characters, with keywords early)
    - A 150-word keyword-rich video description (2 paragraphs max)
    - A list of 10 relevant SEO hashtags
    - A list of 10 comma-separated long-tail keywords
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"OpenAI Error: {e}"
