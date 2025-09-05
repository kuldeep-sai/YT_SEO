import streamlit as st
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
import pandas as pd
import time
from openai import OpenAI
import re
import io

# ============ STREAMLIT CONFIG ============
st.set_page_config(page_title="YouTube SEO Toolkit", layout="wide")

st.title("🎥 YouTube SEO Toolkit")
st.markdown("Enhance your YouTube strategy with **SEO insights, video data, and trending topics.**")

# ============ TABS ============
tab1, tab2, tab3 = st.tabs([
    "📊 Channel Video Exporter",
    "🔍 SEO Topic Analysis",
    "📈 Trending Topic Discovery"
])

# ================== TAB 1 ==================
with tab1:
    st.subheader("📊 Export Your YouTube Channel Videos")
    youtube_api_key = st.text_input("🔑 Enter YouTube API Key", type="password")
    channel_id = st.text_input("📺 Enter Channel ID")

    if st.button("Fetch Videos", type="primary"):
        if not youtube_api_key or not channel_id:
            st.warning("⚠️ Please enter both API key and Channel ID.")
        else:
            with st.spinner("Fetching videos... Please wait."):
                try:
                    youtube = build("youtube", "v3", developerKey=youtube_api_key)
                    channel_res = youtube.channels().list(part="contentDetails", id=channel_id).execute()
                    playlist_id = channel_res["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

                    all_results = []
                    next_page_token = None
                    while True:
                        playlist_items = youtube.playlistItems().list(
                            part="snippet,contentDetails",
                            playlistId=playlist_id,
                            maxResults=50,
                            pageToken=next_page_token
                        ).execute()

                        for item in playlist_items["items"]:
                            video_id = item["contentDetails"]["videoId"]
                            video_res = youtube.videos().list(
                                part="snippet,statistics",
                                id=video_id
                            ).execute()

                            if video_res["items"]:
                                v = video_res["items"][0]
                                all_results.append({
                                    "title": v["snippet"]["title"],
                                    "video_id": video_id,
                                    "url": f"https://www.youtube.com/watch?v={video_id}",
                                    "views": v["statistics"].get("viewCount", "0"),
                                    "tags": ", ".join(v["snippet"].get("tags", [])),
                                    "description": v["snippet"].get("description", "")
                                })

                        next_page_token = playlist_items.get("nextPageToken")
                        if not next_page_token:
                            break

                    # Display cards
                    for idx, video in enumerate(all_results, 1):
                        with st.container():
                            st.markdown(f"### {idx}. [{video['title']}]({video['url']})")
                            cols = st.columns([1, 3])
                            with cols[0]:
                                st.image(f"https://img.youtube.com/vi/{video['video_id']}/hqdefault.jpg", use_container_width=True)
                            with cols[1]:
                                st.markdown(f"**👁️ Views:** {video['views']}")
                                st.markdown(f"**🏷️ Tags:** {video['tags'] if video['tags'] else 'N/A'}")
                                st.markdown(f"**📝 Description:** {video['description'][:200]}...")

                    # Excel export
                    df = pd.DataFrame(all_results)
                    buffer = io.BytesIO()
                    df.to_excel(buffer, index=False)
                    st.download_button("📥 Download Excel", buffer.getvalue(), "videos.xlsx", "application/vnd.ms-excel")

                except Exception as e:
                    st.error(f"❌ Error: {e}")


# ================== TAB 2 ==================
with tab2:
    st.subheader("🔍 SEO Topic Analysis")
    openai_api_key = st.text_input("🔑 Enter OpenAI API Key", type="password")
    youtube_api_key_2 = st.text_input("🔑 Enter YouTube API Key", type="password", key="yt2")

    # Keyword input options
    keywords_input = st.text_area("Enter Topic/Keyword(s) (comma separated)")
    uploaded_keywords = st.file_uploader("📂 Or upload Excel/CSV with keywords", type=["csv", "xlsx"])
    video_count = st.slider("How many top videos per keyword?", 5, 20, 10)

    if st.button("Analyze SEO Topics", type="primary"):
        if not openai_api_key or not youtube_api_key_2:
            st.warning("⚠️ Please enter both API keys.")
        else:
            # Process keywords
            keywords = []
            if uploaded_keywords is not None:
                try:
                    if uploaded_keywords.name.endswith(".csv"):
                        df = pd.read_csv(uploaded_keywords)
                    else:
                        df = pd.read_excel(uploaded_keywords)
                    keywords = df.iloc[:, 0].dropna().astype(str).tolist()
                except Exception as e:
                    st.error(f"Error reading uploaded file: {e}")
            elif keywords_input:
                keywords = [k.strip() for k in keywords_input.split(",") if k.strip()]

            if not keywords:
                st.warning("⚠️ No keywords found. Please input manually or upload a file.")
            else:
                youtube = build("youtube", "v3", developerKey=youtube_api_key_2)
                client = OpenAI(api_key=openai_api_key)
                seo_results = []

                for keyword in keywords:
                    st.markdown(f"### 🔑 Keyword: **{keyword}**")
                    with st.spinner(f"Analyzing top {video_count} videos for '{keyword}'..."):
                        search_res = youtube.search().list(
                            part="snippet",
                            q=keyword,
                            type="video",
                            order="viewCount",
                            maxResults=video_count
                        ).execute()

                        for idx, item in enumerate(search_res["items"], 1):
                            video_id = item["id"]["videoId"]
                            video_res = youtube.videos().list(
                                part="snippet,statistics",
                                id=video_id
                            ).execute()
                            if not video_res["items"]:
                                continue
                            v = video_res["items"][0]
                            video_info = {
                                "keyword": keyword,
                                "title": v["snippet"]["title"],
                                "url": f"https://www.youtube.com/watch?v={video_id}",
                                "views": v["statistics"].get("viewCount", "0"),
                                "tags": ", ".join(v["snippet"].get("tags", [])),
                                "description": v["snippet"].get("description", "")
                            }

                            with st.container():
                                st.markdown(f"#### {idx}. [{video_info['title']}]({video_info['url']})")
                                cols = st.columns([1, 3])
                                with cols[0]:
                                    st.image(f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg", use_container_width=True)
                                with cols[1]:
                                    st.markdown(f"**👁️ Views:** {video_info['views']}")
                                    st.markdown(f"**🏷️ Tags:** {video_info['tags'] if video_info['tags'] else 'N/A'}")
                                    st.markdown(f"**📝 Description:** {video_info['description'][:200]}...")

                            # SEO Suggestions
                            with st.expander("✨ Suggested SEO Tags & Hashtags"):
                                try:
                                    seo_output = client.chat.completions.create(
                                        model="gpt-4o-mini",
                                        messages=[
                                            {"role": "system", "content": "You are an SEO expert."},
                                            {"role": "user", "content": f"Suggest SEO-friendly tags, hashtags, and keywords for this YouTube video:\n\nTitle: {video_info['title']}\nDescription: {video_info['description']}"}
                                        ]
                                    )
                                    suggestions = seo_output.choices[0].message.content
                                    st.write(suggestions)
                                    video_info["seo_suggestions"] = suggestions
                                except Exception as e:
                                    st.error(f"❌ SEO generation failed: {e}")
                                    video_info["seo_suggestions"] = "N/A"

                            seo_results.append(video_info)

                if seo_results:
                    df = pd.DataFrame(seo_results)
                    buffer = io.BytesIO()
                    df.to_excel(buffer, index=False)
                    st.download_button("📥 Download SEO Analysis", buffer.getvalue(), "seo_analysis.xlsx", "application/vnd.ms-excel")


# ================== TAB 3 ==================
with tab3:
    st.subheader("📈 Trending Topic Discovery")
    openai_api_key_3 = st.text_input("🔑 Enter OpenAI API Key", type="password", key="ai3")
    youtube_api_key_3 = st.text_input("🔑 Enter YouTube API Key", type="password", key="yt3")

    # Topic input options
    topics_input = st.text_area("Enter Base Topic(s) (comma separated)")
    uploaded_topics = st.file_uploader("📂 Or upload Excel/CSV with topics", type=["csv", "xlsx"], key="topics_upload")
    video_count_trend = st.slider("How many top videos per topic?", 5, 20, 10)

    if st.button("Discover Trending Topics", type="primary"):
        if not openai_api_key_3 or not youtube_api_key_3:
            st.warning("⚠️ Please enter both API keys.")
        else:
            topics = []
            if uploaded_topics is not None:
                try:
                    if uploaded_topics.name.endswith(".csv"):
                        df = pd.read_csv(uploaded_topics)
                    else:
                        df = pd.read_excel(uploaded_topics)
                    topics = df.iloc[:, 0].dropna().astype(str).tolist()
                except Exception as e:
                    st.error(f"Error reading uploaded file: {e}")
            elif topics_input:
                topics = [t.strip() for t in topics_input.split(",") if t.strip()]

            if not topics:
                st.warning("⚠️ No topics found. Please input manually or upload a file.")
            else:
                youtube = build("youtube", "v3", developerKey=youtube_api_key_3)
                client = OpenAI(api_key=openai_api_key_3)
                trend_results = []

                for topic in topics:
                    st.markdown(f"### 🔑 Topic: **{topic}**")
                    with st.spinner(f"Finding trending videos for '{topic}'..."):
                        search_res = youtube.search().list(
                            part="snippet",
                            q=topic,
                            type="video",
                            order="viewCount",
                            maxResults=video_count_trend
                        ).execute()

                        for idx, item in enumerate(search_res["items"], 1):
                            video_id = item["id"]["videoId"]
                            video_res = youtube.videos().list(
                                part="snippet,statistics",
                                id=video_id
                            ).execute()
                            if not video_res["items"]:
                                continue
                            v = video_res["items"][0]
                            video_info = {
                                "topic": topic,
                                "title": v["snippet"]["title"],
                                "url": f"https://www.youtube.com/watch?v={video_id}",
                                "views": v["statistics"].get("viewCount", "0"),
                                "tags": ", ".join(v["snippet"].get("tags", [])),
                                "description": v["snippet"].get("description", "")
                            }

                            with st.container():
                                st.markdown(f"#### {idx}. [{video_info['title']}]({video_info['url']})")
                                cols = st.columns([1, 3])
                                with cols[0]:
                                    st.image(f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg", use_container_width=True)
                                with cols[1]:
                                    st.markdown(f"**👁️ Views:** {video_info['views']}")
                                    st.markdown(f"**🏷️ Tags:** {video_info['tags'] if video_info['tags'] else 'N/A'}")
                                    st.markdown(f"**📝 Description:** {video_info['description'][:200]}...")

                            with st.expander("🚀 Trending Topic Insights"):
                                try:
                                    trend_output = client.chat.completions.create(
                                        model="gpt-4o-mini",
                                        messages=[
                                            {"role": "system", "content": "You are a YouTube SEO strategist."},
                                            {"role": "user", "content": f"Analyze trending content for topic '{topic}'. Based on this video, suggest potential sub-topics, SEO ideas, and posting strategies."}
                                        ]
                                    )
                                    insights = trend_output.choices[0].message.content
                                    st.write(insights)
                                    video_info["insights"] = insights
                                except Exception as e:
                                    st.error(f"❌ AI analysis failed: {e}")
                                    video_info["insights"] = "N/A"

                            trend_results.append(video_info)

                if trend_results:
                    df = pd.DataFrame(trend_results)
                    buffer = io.BytesIO()
                    df.to_excel(buffer, index=False)
                    st.download_button("📥 Download Trending Topics", buffer.getvalue(), "trending_topics.xlsx", "application/vnd.ms-excel")
