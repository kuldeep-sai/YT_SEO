import streamlit as st
from googleapiclient.discovery import build
import pandas as pd
from io import BytesIO
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from openai import OpenAI
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import json

# ---------------- Page Setup ----------------
st.set_page_config(page_title="YouTube Toolkit", layout="wide")
st.title("📊 YouTube Video Toolkit: Export + SEO + Images + Trending Topics")

tabs = st.tabs(["Video Export", "SEO Topic Analysis", "Trending Topic Finder"])

# ---------------- Helper Functions ----------------
def get_upload_playlist(youtube, channel_id):
    data = youtube.channels().list(part="contentDetails", id=channel_id).execute()
    if not data.get("items"):
        raise ValueError(f"No channel found for ID: {channel_id}")
    return data["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

def get_videos_from_playlist(youtube, playlist_id, max_videos=50):
    videos = []
    next_token = None
    while len(videos) < max_videos:
        res = youtube.playlistItems().list(
            part="contentDetails,snippet",
            playlistId=playlist_id,
            maxResults=min(50, max_videos - len(videos)),
            pageToken=next_token
        ).execute()
        videos.extend(res.get("items", []))
        next_token = res.get("nextPageToken")
        if not next_token:
            break
    return videos[:max_videos]

def fetch_video_transcript(video_id):
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        transcript = transcript_list.find_transcript(['en']).fetch()
        return " ".join([seg["text"] for seg in transcript])
    except (TranscriptsDisabled, NoTranscriptFound):
        return "Transcript not found"
    except Exception:
        return "Transcript not found"

def generate_seo_and_image_structured(client, title, description, transcript):
    seo_prompt = f"""
    You are a YouTube SEO expert. Generate SEO-friendly suggestions for this video.
    Respond in JSON format exactly as below:

    {{
        "Optimized Title": "...",
        "Optimized Description": "...",
        "Suggested Hashtags": ["#hashtag1", "#hashtag2"],
        "Suggested Keywords": ["keyword1", "keyword2"]
    }}

    Video info:
    Title: {title}
    Description: {description}
    Transcript: {transcript[:1000]}...
    """
    seo_output = {"Optimized Title": "", "Optimized Description": "", 
                  "Suggested Hashtags": [], "Suggested Keywords": []}
    image_url = None

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": seo_prompt}],
            temperature=0.7
        )
        seo_output = json.loads(response.choices[0].message.content)
    except Exception as e:
        seo_output = {"Optimized Title": "Error", "Optimized Description": f"{e}",
                      "Suggested Hashtags": [], "Suggested Keywords": []}

    try:
        img_resp = client.images.generate(
            model="gpt-image-1",
            prompt=f"Create an engaging YouTube thumbnail for video: {title}",
            size="512x512"
        )
        image_url = img_resp.data[0].url
    except Exception:
        image_url = None

    return seo_output, image_url

def extract_video_ids_from_urls(file):
    content = file.read().decode("utf-8")
    urls = content.splitlines()
    ids = []
    for url in urls:
        match = re.search(r"(?:v=|youtu\.be/)([\w-]{11})", url)
        if match:
            ids.append(match.group(1))
    return ids

# ---------------- Tab 1: Video Export ----------------
with tabs[0]:
    st.header("🎥 Video Export + SEO + Images + Transcript")
    youtube_api_key = st.text_input("YouTube API Key", key="tab1_yt", type="password")
    openai_api_key = st.text_input("OpenAI API Key (SEO & Images)", key="tab1_openai", type="password")
    channel_id = st.text_input("YouTube Channel ID", key="tab1_channel")
    num_videos = st.number_input("Number of videos to fetch", min_value=1, max_value=50, value=10, step=1)
    uploaded_file_tab1 = st.file_uploader("Upload CSV/TXT with Video URLs (optional)", type=["csv", "txt"], key="tab1_file")

    enable_seo = st.checkbox("Enable SEO suggestions", key="tab1_seo")
    enable_images = st.checkbox("Enable AI Thumbnail", key="tab1_img")
    enable_transcript = st.checkbox("Enable Transcript", key="tab1_transcript")

    if st.button("Fetch Videos", key="tab1_btn"):
        if not youtube_api_key:
            st.error("YouTube API Key required")
        else:
            try:
                youtube = build("youtube", "v3", developerKey=youtube_api_key)
                client = OpenAI(api_key=openai_api_key) if openai_api_key else None

                # Collect videos
                videos_to_process = []
                if uploaded_file_tab1:
                    video_ids = extract_video_ids_from_urls(uploaded_file_tab1)
                    videos_to_process = [{"contentDetails": {"videoId": vid}} for vid in video_ids]
                else:
                    playlist_id = get_upload_playlist(youtube, channel_id)
                    videos_to_process = get_videos_from_playlist(youtube, playlist_id, max_videos=num_videos)

                results = []
                progress_bar = st.progress(0)
                total_videos = len(videos_to_process)

                def process_video_item(v):
                    vid = v["contentDetails"]["videoId"]
                    info_res = youtube.videos().list(part="snippet,statistics", id=vid).execute()
                    snippet = info_res["items"][0]["snippet"]
                    stats = info_res["items"][0].get("statistics", {})
                    title = snippet["title"]
                    description = snippet.get("description", "")
                    tags = snippet.get("tags", [])
                    views = stats.get("viewCount", "0")
                    published_date = snippet.get("publishedAt", "N/A")
                    transcript = fetch_video_transcript(vid)
                    hashtags = [w for w in description.split() if w.startswith("#")]

                    seo_output, image_url = ({}, None)
                    if client and enable_seo:
                        seo_output, image_url = generate_seo_and_image_structured(client, title, description, transcript)

                    return {
                        "Video ID": vid,
                        "Current Title": title,
                        "Current Description": description,
                        "Tags": ", ".join(tags),
                        "Hashtags": ", ".join(hashtags),
                        "Views": views,
                        "Published Date": published_date,
                        "Transcript": transcript,
                        "SEO Suggestions": seo_output,
                        "Thumbnail Image": image_url
                    }

                with ThreadPoolExecutor(max_workers=5) as executor:
                    futures = [executor.submit(process_video_item, v) for v in videos_to_process]
                    for i, future in enumerate(as_completed(futures), 1):
                        results.append(future.result())
                        progress_bar.progress(i / total_videos)

                # Display results
                for r in results:
                    st.markdown("---")
                    st.subheader(f"🎥 {r['Current Title']}")
                    st.write(f"**Views:** {r['Views']} | **Published:** {r['Published Date']}")
                    st.write(f"**Description:** {r['Current Description']}")
                    if r["Tags"]:
                        st.write(f"**Tags:** {r['Tags']}")
                    if r["Hashtags"]:
                        st.write(f"**Hashtags:** {r['Hashtags']}")
                    if r["Transcript"]:
                        with st.expander("Transcript"):
                            st.write(r["Transcript"][:500] + "...")
                    if r["SEO Suggestions"]:
                        seo = r["SEO Suggestions"]
                        st.subheader("✨ SEO Suggestions")
                        st.write(f"**Optimized Title:** {seo.get('Optimized Title','')}")
                        st.write(f"**Optimized Description:** {seo.get('Optimized Description','')}")
                        st.write(f"**Suggested Hashtags:** {', '.join(seo.get('Suggested Hashtags',[]))}")
                        st.write(f"**Suggested Keywords:** {', '.join(seo.get('Suggested Keywords',[]))}")
                    if r["Thumbnail Image"]:
                        st.image(r["Thumbnail Image"], caption="AI-generated Thumbnail", use_container_width=True)

                # Excel export
                df = pd.DataFrame(results)
                df['Optimized Title'] = df['SEO Suggestions'].apply(lambda x: x.get('Optimized Title') if isinstance(x, dict) else "")
                df['Optimized Description'] = df['SEO Suggestions'].apply(lambda x: x.get('Optimized Description') if isinstance(x, dict) else "")
                df['Suggested Hashtags'] = df['SEO Suggestions'].apply(lambda x: ", ".join(x.get('Suggested Hashtags', [])) if isinstance(x, dict) else "")
                df['Suggested Keywords'] = df['SEO Suggestions'].apply(lambda x: ", ".join(x.get('Suggested Keywords', [])) if isinstance(x, dict) else "")

                output = BytesIO()
                with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                    df.to_excel(writer, index=False, sheet_name="Videos")
                output.seek(0)
                st.download_button("📥 Download Video Data (Excel)", data=output.getvalue(),
                                   file_name="video_export.xlsx",
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

            except Exception as e:
                st.error(f"Error: {e}")

# ---------------- Tab 2: SEO Topic Analysis ----------------
with tabs[1]:
    st.header("🔍 SEO Topic Analysis")
    youtube_api_key2 = st.text_input("YouTube API Key", key="tab2_yt", type="password")
    openai_api_key2 = st.text_input("OpenAI API Key", key="tab2_openai", type="password")
    topics_input = st.text_input("Enter comma-separated keywords/topics", key="tab2_keywords")
    uploaded_file_tab2 = st.file_uploader("Upload Excel/CSV with keywords (optional)", type=["xlsx","csv"], key="tab2_file")
    top_n_videos = st.number_input("Number of top videos to analyze per topic", min_value=1, max_value=20, value=5)

    if st.button("Analyze Topics", key="tab2_btn"):
        if not youtube_api_key2:
            st.error("YouTube API Key required")
        else:
            try:
                youtube2 = build("youtube", "v3", developerKey=youtube_api_key2)
                client2 = OpenAI(api_key=openai_api_key2) if openai_api_key2 else None

                # Prepare topics list
                topics = []
                if uploaded_file_tab2:
                    df_upload = pd.read_excel(uploaded_file_tab2) if uploaded_file_tab2.name.endswith(".xlsx") else pd.read_csv(uploaded_file_tab2)
                    topics = df_upload.iloc[:,0].astype(str).tolist()
                else:
                    topics = [t.strip() for t in topics_input.split(",") if t.strip()]

                all_results = []

                for topic in topics:
                    st.subheader(f"Keyword/Topic: {topic}")
                    # Search top videos
                    search_res = youtube2.search().list(q=topic, part="snippet", maxResults=top_n_videos, order="viewCount", type="video").execute()
                    video_ids = [item["id"]["videoId"] for item in search_res.get("items", [])]
                    for vid in video_ids:
                        info_res = youtube2.videos().list(part="snippet,statistics", id=vid).execute()
                        snippet = info_res["items"][0]["snippet"]
                        stats = info_res["items"][0].get("statistics", {})
                        title = snippet["title"]
                        description = snippet.get("description","")
                        tags = snippet.get("tags",[])
                        views = stats.get("viewCount","0")
                        hashtags = [w for w in description.split() if w.startswith("#")]

                        seo_output = {}
                        if client2:
                            seo_output, _ = generate_seo_and_image_structured(client2, title, description, "")

                        result_item = {
                            "Topic": topic,
                            "Video ID": vid,
                            "Title": title,
                            "Description": description,
                            "Tags": ", ".join(tags),
                            "Hashtags": ", ".join(hashtags),
                            "Views": views,
                            "SEO Suggestions": seo_output
                        }
                        all_results.append(result_item)

                        st.write(f"**Title:** {title} | **Views:** {views}")
                        st.write(f"**Description:** {description[:200]}...")
                        st.write(f"**Tags:** {', '.join(tags)}")
                        st.write(f"**Hashtags:** {', '.join(hashtags)}")
                        if seo_output:
                            st.write(f"**SEO Optimized Title:** {seo_output.get('Optimized Title','')}")
                            st.write(f"**SEO Keywords:** {', '.join(seo_output.get('Suggested Keywords',[]))}")

                # Export Excel
                if all_results:
                    df_all = pd.DataFrame(all_results)
                    df_all['Optimized Title'] = df_all['SEO Suggestions'].apply(lambda x: x.get('Optimized Title') if isinstance(x, dict) else "")
                    df_all['Optimized Description'] = df_all['SEO Suggestions'].apply(lambda x: x.get('Optimized Description') if isinstance(x, dict) else "")
                    df_all['Suggested Hashtags'] = df_all['SEO Suggestions'].apply(lambda x: ", ".join(x.get('Suggested Hashtags', [])) if isinstance(x, dict) else "")
                    df_all['Suggested Keywords'] = df_all['SEO Suggestions'].apply(lambda x: ", ".join(x.get('Suggested Keywords', [])) if isinstance(x, dict) else "")

                    output2 = BytesIO()
                    with pd.ExcelWriter(output2, engine="xlsxwriter") as writer:
                        df_all.to_excel(writer, index=False, sheet_name="SEO_Topics")
                    output2.seek(0)
                    st.download_button("📥 Download SEO Topic Analysis", data=output2.getvalue(),
                                       file_name="seo_topic_analysis.xlsx",
                                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

            except Exception as e:
                st.error(f"Error: {e}")

# ---------------- Tab 3: Trending Topic Finder ----------------
with tabs[2]:
    st.header("📈 Trending Topic Finder")
    youtube_api_key3 = st.text_input("YouTube API Key", key="tab3_yt", type="password")
    openai_api_key3 = st.text_input("OpenAI API Key", key="tab3_openai", type="password")
    topics_input3 = st.text_input("Enter comma-separated topics", key="tab3_keywords")
    uploaded_file_tab3 = st.file_uploader("Upload Excel/CSV with topics (optional)", type=["xlsx","csv"], key="tab3_file")
    top_videos_tab3 = st.number_input("Number of top videos per topic", min_value=1, max_value=20, value=5)

    if st.button("Find Trending Topics", key="tab3_btn"):
        if not youtube_api_key3:
            st.error("YouTube API Key required")
        else:
            try:
                youtube3 = build("youtube", "v3", developerKey=youtube_api_key3)
                client3 = OpenAI(api_key=openai_api_key3) if openai_api_key3 else None

                topics3 = []
                if uploaded_file_tab3:
                    df_upload3 = pd.read_excel(uploaded_file_tab3) if uploaded_file_tab3.name.endswith(".xlsx") else pd.read_csv(uploaded_file_tab3)
                    topics3 = df_upload3.iloc[:,0].astype(str).tolist()
                else:
                    topics3 = [t.strip() for t in topics_input3.split(",") if t.strip()]

                all_trends = []

                for topic in topics3:
                    st.subheader(f"Analyzing Topic: {topic}")
                    search_res = youtube3.search().list(q=topic, part="snippet", maxResults=top_videos_tab3, order="viewCount", type="video").execute()
                    for item in search_res.get("items", []):
                        vid = item["id"]["videoId"]
                        snippet = item["snippet"]
                        title = snippet["title"]
                        desc = snippet.get("description","")
                        result_item = {
                            "Topic": topic,
                            "Video ID": vid,
                            "Title": title,
                            "Description": desc
                        }
                        all_trends.append(result_item)
                        st.write(f"**Title:** {title} | **Description:** {desc[:200]}...")

                if all_trends:
                    df_trends = pd.DataFrame(all_trends)
                    output3 = BytesIO()
                    with pd.ExcelWriter(output3, engine="xlsxwriter") as writer:
                        df_trends.to_excel(writer, index=False, sheet_name="Trending_Topics")
                    output3.seek(0)
                    st.download_button("📥 Download Trending Topics", data=output3.getvalue(),
                                       file_name="trending_topics.xlsx",
                                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            except Exception as e:
                st.error(f"Error: {e}")
