import streamlit as st
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
import pandas as pd
import io
from openai import OpenAI

# ============ STREAMLIT CONFIG ============
st.set_page_config(page_title="YouTube SEO Toolkit", layout="wide")

st.title("🎥 YouTube SEO Toolkit")
st.markdown("Enhance your YouTube strategy with **SEO insights, video data, and trending topics.**")

# Utility: safe join for tags list/str
def join_tags(tags):
    if isinstance(tags, list):
        return ", ".join(tags)
    if isinstance(tags, str):
        return tags
    return ""

# ============ TABS ============
tab1, tab2, tab3 = st.tabs([
    "📊 Channel Video Exporter",
    "🔍 SEO Topic Analysis",
    "📈 Trending Topic Discovery"
])

# ================== TAB 1 ==================
with tab1:
    st.subheader("📊 Export Your YouTube Channel Videos (with optional AI SEO & Thumbnails)")

    # Keys & channel
    youtube_api_key = st.text_input("🔑 YouTube API Key (Tab 1)", type="password")
    openai_api_key_tab1 = st.text_input("🤖 OpenAI API Key (for SEO & Image generation in Tab 1)", type="password")
    channel_id = st.text_input("📺 Channel ID (e.g. UC_xxx...)")

    # Options
    num_to_fetch = st.number_input("🎬 How many recent uploads to fetch?", min_value=1, max_value=200, value=30, step=1)
    enable_seo_tab1 = st.checkbox("✨ Generate SEO suggestions (tags/hashtags/better title) with OpenAI", value=False)
    enable_images_tab1 = st.checkbox("🖼️ Generate AI thumbnail from video title (OpenAI Images)", value=False)

    if st.button("📥 Fetch Channel Videos", type="primary"):
        if not youtube_api_key or not channel_id:
            st.warning("⚠️ Please enter both **YouTube API Key** and **Channel ID**.")
        else:
            # Initialize services
            client_tab1 = OpenAI(api_key=openai_api_key_tab1) if (openai_api_key_tab1 and (enable_seo_tab1 or enable_images_tab1)) else None

            try:
                youtube = build("youtube", "v3", developerKey=youtube_api_key)

                # Get uploads playlist
                channel_res = youtube.channels().list(part="contentDetails", id=channel_id).execute()
                if not channel_res.get("items"):
                    st.error("❌ No channel found for that ID.")
                else:
                    playlist_id = channel_res["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

                    # Fetch playlist items until we reach num_to_fetch
                    all_results = []
                    next_page_token = None

                    with st.spinner("Fetching videos..."):
                        while len(all_results) < num_to_fetch:
                            playlist_items = youtube.playlistItems().list(
                                part="snippet,contentDetails",
                                playlistId=playlist_id,
                                maxResults=min(50, num_to_fetch - len(all_results)),
                                pageToken=next_page_token
                            ).execute()

                            vid_ids_batch = []
                            for item in playlist_items.get("items", []):
                                vid_ids_batch.append(item["contentDetails"]["videoId"])

                            if vid_ids_batch:
                                videos_res = youtube.videos().list(
                                    part="snippet,statistics",
                                    id=",".join(vid_ids_batch)
                                ).execute()

                                for v in videos_res.get("items", []):
                                    video_id = v["id"]
                                    all_results.append({
                                        "title": v["snippet"]["title"],
                                        "video_id": video_id,
                                        "url": f"https://www.youtube.com/watch?v={video_id}",
                                        "views": v["statistics"].get("viewCount", "0"),
                                        "tags": join_tags(v["snippet"].get("tags", [])),
                                        "description": v["snippet"].get("description", "")
                                    })

                            next_page_token = playlist_items.get("nextPageToken")
                            if not next_page_token:
                                break

                    # Generate optional AI outputs
                    progress = st.progress(0)
                    enriched_rows = []
                    total = len(all_results)

                    for idx, video in enumerate(all_results, start=1):
                        row = {**video}
                        # SEO suggestions
                        if enable_seo_tab1:
                            if client_tab1 is None:
                                row["seo_suggestions"] = "OpenAI API key missing."
                            else:
                                try:
                                    prompt = (
                                        "You are a YouTube SEO expert. Based on the following video info, "
                                        "suggest:\n- 10 SEO-friendly tags (comma separated)\n"
                                        "- 10 hashtags (comma separated)\n"
                                        "- A better, keyword-rich title (<=70 chars)\n\n"
                                        f"Title: {video['title']}\n"
                                        f"Description: {video['description']}\n"
                                        f"Existing tags: {video['tags']}\n"
                                    )
                                    seo_output = client_tab1.chat.completions.create(
                                        model="gpt-4o-mini",
                                        messages=[
                                            {"role": "system", "content": "You are an SEO expert."},
                                            {"role": "user", "content": prompt}
                                        ]
                                    )
                                    row["seo_suggestions"] = seo_output.choices[0].message.content
                                except Exception as e:
                                    row["seo_suggestions"] = f"SEO generation error: {e}"

                        # AI thumbnail
                        if enable_images_tab1:
                            if client_tab1 is None:
                                row["ai_image_url"] = ""
                            else:
                                try:
                                    img = client_tab1.images.generate(
                                        model="gpt-image-1",
                                        prompt=f"YouTube thumbnail for: {video['title']}. High-contrast, bold title text, dramatic composition, eye-catching.",
                                        size="512x512"
                                    )
                                    row["ai_image_url"] = img.data[0].url
                                except Exception as e:
                                    row["ai_image_url"] = ""
                                    st.warning(f"Image generation failed for “{video['title']}”: {e}")
                        enriched_rows.append(row)
                        progress.progress(idx / max(total, 1))

                    # Show cards
                    st.markdown("---")
                    st.markdown(f"### ✅ Fetched {len(enriched_rows)} videos")

                    for i, video in enumerate(enriched_rows, start=1):
                        with st.container():
                            st.markdown(f"#### {i}. [{video['title']}]({video['url']})")
                            cols = st.columns([1, 3])

                            # Thumbnail preference: AI image if generated, else YouTube thumbnail
                            preferred_image_url = video.get("ai_image_url") or f"https://img.youtube.com/vi/{video['video_id']}/hqdefault.jpg"
                            with cols[0]:
                                st.image(preferred_image_url, use_container_width=True)
                                if video.get("ai_image_url"):
                                    with st.expander("🖼️ View default YouTube thumbnail"):
                                        st.image(f"https://img.youtube.com/vi/{video['video_id']}/hqdefault.jpg", use_container_width=True)

                            with cols[1]:
                                st.markdown(f"**👁️ Views:** {video['views']}")
                                st.markdown(f"**🏷️ Tags:** {video['tags'] or 'N/A'}")
                                st.markdown(f"**📝 Description:** {video['description'][:240]}...")

                                if enable_seo_tab1:
                                    with st.expander("✨ SEO Suggestions"):
                                        st.write(video.get("seo_suggestions", "N/A"))

                    # Excel export
                    if enriched_rows:
                        df = pd.DataFrame(enriched_rows)
                        buffer = io.BytesIO()
                        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
                            df.to_excel(writer, index=False, sheet_name="Videos")
                        buffer.seek(0)
                        st.download_button(
                            "📥 Download Excel",
                            data=buffer,
                            file_name="channel_videos.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )

            except Exception as e:
                st.error(f"❌ Error: {e}")

# ================== TAB 2 ==================
with tab2:
    st.subheader("🔍 SEO Topic Analysis")
    openai_api_key = st.text_input("🔑 OpenAI API Key (Tab 2)", type="password")
    youtube_api_key_2 = st.text_input("🔑 YouTube API Key (Tab 2)", type="password", key="yt2")

    keywords_input = st.text_area("Enter Topic/Keyword(s) (comma separated)")
    uploaded_keywords = st.file_uploader("📂 Or upload Excel/CSV with keywords (first column)", type=["csv", "xlsx"])
    video_count = st.slider("How many top videos per keyword?", 5, 20, 10)

    if st.button("Analyze SEO Topics", type="primary"):
        if not openai_api_key or not youtube_api_key_2:
            st.warning("⚠️ Please enter both API keys.")
        else:
            # Build list of keywords
            keywords = []
            if uploaded_keywords is not None:
                try:
                    if uploaded_keywords.name.endswith(".csv"):
                        df_kw = pd.read_csv(uploaded_keywords)
                    else:
                        df_kw = pd.read_excel(uploaded_keywords)
                    keywords = df_kw.iloc[:, 0].dropna().astype(str).tolist()
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

                        for idx, item in enumerate(search_res.get("items", []), 1):
                            video_id = item["id"]["videoId"]
                            video_res = youtube.videos().list(
                                part="snippet,statistics",
                                id=video_id
                            ).execute()
                            if not video_res.get("items"):
                                continue

                            v = video_res["items"][0]
                            video_info = {
                                "keyword": keyword,
                                "title": v["snippet"]["title"],
                                "url": f"https://www.youtube.com/watch?v={video_id}",
                                "views": v["statistics"].get("viewCount", "0"),
                                "tags": join_tags(v["snippet"].get("tags", [])),
                                "description": v["snippet"].get("description", "")
                            }

                            with st.container():
                                st.markdown(f"#### {idx}. [{video_info['title']}]({video_info['url']})")
                                cols = st.columns([1, 3])
                                with cols[0]:
                                    st.image(f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg", use_container_width=True)
                                with cols[1]:
                                    st.markdown(f"**👁️ Views:** {video_info['views']}")
                                    st.markdown(f"**🏷️ Tags:** {video_info['tags'] or 'N/A'}")
                                    st.markdown(f"**📝 Description:** {video_info['description'][:200]}...")

                            # SEO Suggestions from OpenAI
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
                    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
                        df.to_excel(writer, index=False, sheet_name="SEO Analysis")
                    buffer.seek(0)
                    st.download_button("📥 Download SEO Analysis", buffer, "seo_analysis.xlsx",
                                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ================== TAB 3 ==================
with tab3:
    st.subheader("📈 Trending Topic Discovery")
    openai_api_key_3 = st.text_input("🔑 OpenAI API Key (Tab 3)", type="password", key="ai3")
    youtube_api_key_3 = st.text_input("🔑 YouTube API Key (Tab 3)", type="password", key="yt3")

    topics_input = st.text_area("Enter Base Topic(s) (comma separated)")
    uploaded_topics = st.file_uploader("📂 Or upload Excel/CSV with topics (first column)", type=["csv", "xlsx"], key="topics_upload")
    video_count_trend = st.slider("How many top videos per topic?", 5, 20, 10)

    if st.button("Discover Trending Topics", type="primary"):
        if not openai_api_key_3 or not youtube_api_key_3:
            st.warning("⚠️ Please enter both API keys.")
        else:
            topics = []
            if uploaded_topics is not None:
                try:
                    if uploaded_topics.name.endswith(".csv"):
                        df_tp = pd.read_csv(uploaded_topics)
                    else:
                        df_tp = pd.read_excel(uploaded_topics)
                    topics = df_tp.iloc[:, 0].dropna().astype(str).tolist()
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

                        for idx, item in enumerate(search_res.get("items", []), 1):
                            video_id = item["id"]["videoId"]
                            video_res = youtube.videos().list(
                                part="snippet,statistics",
                                id=video_id
                            ).execute()
                            if not video_res.get("items"):
                                continue
                            v = video_res["items"][0]
                            video_info = {
                                "topic": topic,
                                "title": v["snippet"]["title"],
                                "url": f"https://www.youtube.com/watch?v={video_id}",
                                "views": v["statistics"].get("viewCount", "0"),
                                "tags": join_tags(v["snippet"].get("tags", [])),
                                "description": v["snippet"].get("description", "")
                            }

                            with st.container():
                                st.markdown(f"#### {idx}. [{video_info['title']}]({video_info['url']})")
                                cols = st.columns([1, 3])
                                with cols[0]:
                                    st.image(f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg", use_container_width=True)
                                with cols[1]:
                                    st.markdown(f"**👁️ Views:** {video_info['views']}")
                                    st.markdown(f"**🏷️ Tags:** {video_info['tags'] or 'N/A'}")
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
                    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
                        df.to_excel(writer, index=False, sheet_name="Trending")
                    buffer.seek(0)
                    st.download_button("📥 Download Trending Topics", buffer, "trending_topics.xlsx",
                                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
