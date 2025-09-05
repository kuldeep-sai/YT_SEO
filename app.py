import streamlit as st
from googleapiclient.discovery import build
import pandas as pd
from io import BytesIO
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from openai import OpenAI
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

# ---------------- Page Setup ----------------
st.set_page_config(page_title="YouTube SEO Toolkit", layout="wide")
st.title("🎥 YouTube SEO Toolkit")

# ---------------- Tabs ----------------
tab1, tab2, tab3 = st.tabs([
    "📊 Video Exporter",
    "📈 SEO Topic Analysis",
    "🔥 Trending Topic Finder"
])

# ---------------- Shared Functions ----------------
def get_upload_playlist(youtube, channel_id):
    data = youtube.channels().list(part="contentDetails", id=channel_id).execute()
    if not data.get("items"):
        raise ValueError(f"No channel found for ID: {channel_id}")
    return data["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

def get_video_ids(youtube, playlist_id, max_videos=1000):
    videos = []
    next_token = None
    while len(videos) < max_videos:
        res = youtube.playlistItems().list(
            part="contentDetails,snippet",
            playlistId=playlist_id,
            maxResults=min(50, max_videos - len(videos)),
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
    return videos

def get_video_info(youtube, video_id):
    res = youtube.videos().list(part="snippet,statistics", id=video_id).execute()
    if not res["items"]:
        return {"video_id": video_id, "error": "Video not found"}
    item = res["items"][0]
    return {
        "video_id": video_id,
        "title": item["snippet"]["title"],
        "description": item["snippet"]["description"],
        "tags": ", ".join(item["snippet"].get("tags", [])),
        "views": int(item["statistics"].get("viewCount", 0)),
        "published_date": item["snippet"]["publishedAt"],
        "url": f"https://www.youtube.com/watch?v={video_id}"
    }

def fetch_transcript(video_id):
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        transcript = transcript_list.find_transcript(['en']).fetch()
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
        match = re.search(r"(?:v=|youtu\.be/)([\w-]{11})", url)
        if match:
            ids.append(match.group(1))
    return ids

def save_to_excel(data, filename):
    output = BytesIO()
    df = pd.DataFrame(data)
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False)
    output.seek(0)
    st.download_button(
        f"⬇️ Download {filename}",
        output,
        filename,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# ---------------- Tab 1: Video Exporter ----------------
with tab1:
    st.subheader("📊 Export Videos + SEO + Transcript + Images")

    with st.form("export_form"):
        yt_api_key = st.text_input("🔑 YouTube API Key", type="password")
        openai_key_input = st.text_input("🤖 OpenAI API Key (optional)", type="password")

        mode = st.radio("Mode", ["Batch Mode", "Single Video", "Upload URLs"], horizontal=True)
        if mode == "Batch Mode":
            channel_id = st.text_input("📡 Channel ID")
            num_videos = st.number_input("🎬 Number of videos", 1, 50, 10)
        elif mode == "Single Video":
            video_id_input = st.text_input("🎥 Video ID")
        else:
            uploaded_file = st.file_uploader("📄 Upload CSV/TXT with video URLs", type=["csv", "txt"])

        enable_seo = st.checkbox("✨ Enable SEO (ChatGPT)")
        enable_transcript = st.checkbox("📝 Fetch Transcripts")
        enable_images = st.checkbox("🖼️ Generate Thumbnails")
        submit1 = st.form_submit_button("📥 Fetch")

    if submit1 and yt_api_key:
        youtube = build("youtube", "v3", developerKey=yt_api_key)
        client = OpenAI(api_key=openai_key_input) if openai_key_input else None

        videos = []
        if mode == "Batch Mode":
            playlist_id = get_upload_playlist(youtube, channel_id)
            video_meta = get_video_ids(youtube, playlist_id, max_videos=num_videos)
            videos = [get_video_info(youtube, v["video_id"]) for v in video_meta]
        elif mode == "Single Video":
            videos = [get_video_info(youtube, video_id_input)]
        else:
            ids = extract_video_ids_from_urls(uploaded_file)
            videos = [get_video_info(youtube, vid) for vid in ids]

        results = []
        for v in videos:
            if enable_transcript:
                v["transcript"] = fetch_transcript(v["video_id"])
            if enable_images and client:
                try:
                    img = client.images.generate(model="gpt-image-1", prompt=f"Thumbnail for {v['title']}", size="512x512")
                    v["image_url"] = img.data[0].url
                except:
                    v["image_url"] = None
            results.append(v)

        for r in results:
            st.markdown(f"### [{r['title']}]({r['url']}) ({r['views']} views)")
            if "transcript" in r:
                with st.expander("Transcript"):
                    st.write(r["transcript"][:400] + "...")
            if r.get("image_url"):
                st.image(r["image_url"], use_container_width=True)

        save_to_excel(results, "video_export.xlsx")

# ---------------- Tab 2: SEO Topic Analysis ----------------
with tab2:
    st.subheader("📈 Analyze SEO for Topics")

    with st.form("seo_form"):
        yt_api_key2 = st.text_input("🔑 YouTube API Key (Tab 2)", type="password")
        openai_key2 = st.text_input("🤖 OpenAI Key (Tab 2)", type="password")
        keywords_input = st.text_area("Enter topics (comma separated)")
        uploaded_excel = st.file_uploader("📄 Or upload Excel with topics", type=["xlsx"])
        top_count = st.number_input("Top videos per topic", 1, 20, 10)
        submit2 = st.form_submit_button("🔍 Analyze")

    if submit2 and yt_api_key2:
        youtube = build("youtube", "v3", developerKey=yt_api_key2)
        client2 = OpenAI(api_key=openai_key2) if openai_key2 else None

        topics = []
        if keywords_input:
            topics = [t.strip() for t in keywords_input.split(",") if t.strip()]
        elif uploaded_excel:
            df = pd.read_excel(uploaded_excel)
            topics = df.iloc[:, 0].dropna().tolist()

        all_results = []
        for topic in topics:
            search = youtube.search().list(q=topic, part="snippet", type="video", order="viewCount", maxResults=top_count).execute()
            for item in search.get("items", []):
                vid = item["id"]["videoId"]
                info = get_video_info(youtube, vid)
                all_results.append(info)
                st.markdown(f"### [{info['title']}]({info['url']}) ({info['views']} views)")
                st.write(f"Tags: {info['tags']}")
                if client2:
                    prompt = f"Suggest SEO tags, hashtags, and a better title for:\nTitle: {info['title']}\nDescription: {info['description']}"
                    try:
                        seo_out = client2.chat.completions.create(model="gpt-4o", messages=[{"role":"user","content":prompt}])
                        st.write(seo_out.choices[0].message.content)
                    except:
                        st.warning("SEO generation failed")

        save_to_excel(all_results, "seo_topic_analysis.xlsx")

# ---------------- Tab 3: Trending Topic Finder ----------------
with tab3:
    st.subheader("🔥 Find Trending Topics for Strategy")

    with st.form("trend_form"):
        yt_api_key3 = st.text_input("🔑 YouTube API Key (Tab 3)", type="password")
        keywords_input3 = st.text_area("Enter seed topics (comma separated)")
        uploaded_excel3 = st.file_uploader("📄 Or upload Excel with seed topics", type=["xlsx"])
        top_count3 = st.number_input("Top videos per topic", 1, 20, 10, key="trend_count")
        submit3 = st.form_submit_button("🚀 Find Trends")

    if submit3 and yt_api_key3:
        youtube = build("youtube", "v3", developerKey=yt_api_key3)

        seeds = []
        if keywords_input3:
            seeds = [t.strip() for t in keywords_input3.split(",") if t.strip()]
        elif uploaded_excel3:
            df = pd.read_excel(uploaded_excel3)
            seeds = df.iloc[:, 0].dropna().tolist()

        trend_results = []
        for seed in seeds:
            st.info(f"Analyzing trending videos for: {seed}")
            search = youtube.search().list(q=seed, part="snippet", type="video", order="viewCount", maxResults=top_count3).execute()
            for item in search.get("items", []):
                vid = item["id"]["videoId"]
                info = get_video_info(youtube, vid)
                trend_results.append(info)
                st.markdown(f"### [{info['title']}]({info['url']}) ({info['views']} views)")
                st.write(f"Tags: {info['tags']}")
                st.write(f"Description: {info['description'][:300]}...")

        save_to_excel(trend_results, "trending_topics.xlsx")
