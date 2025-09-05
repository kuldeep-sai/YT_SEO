import streamlit as st
import pandas as pd
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
from openai import OpenAI
from io import BytesIO

# ---------------- Helper Functions ----------------
def get_upload_playlist(youtube, channel_id):
    data = youtube.channels().list(
        part="contentDetails",
        id=channel_id
    ).execute()
    return data["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

def get_videos_from_playlist(youtube, playlist_id, max_results=10):
    videos = []
    next_page_token = None
    while len(videos) < max_results:
        request = youtube.playlistItems().list(
            part="contentDetails",
            playlistId=playlist_id,
            maxResults=min(50, max_results - len(videos)),
            pageToken=next_page_token
        )
        response = request.execute()
        videos.extend(response["items"])
        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            break
    return videos

def fetch_video_transcript(video_id):
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        return " ".join([t["text"] for t in transcript_list])
    except Exception:
        return "Transcript not available."

def generate_seo_and_image(client, title, description, transcript):
    prompt = f"""
    Generate SEO-friendly tags, hashtags, and suggestions 
    for this YouTube video:

    Title: {title}
    Description: {description}
    Transcript: {transcript[:1000]}...
    """
    seo_output = "Not generated"
    image_url = None
    try:
        seo_output = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        ).choices[0].message.content
    except Exception as e:
        seo_output = f"Error generating SEO tags: {e}"

    try:
        img_resp = client.images.generate(
            model="gpt-image-1",
            prompt=f"Create an engaging YouTube thumbnail idea for video: {title}",
            size="512x512"
        )
        image_url = img_resp.data[0].url
    except Exception:
        image_url = None

    return seo_output, image_url

# ---------------- Streamlit UI ----------------
st.set_page_config(page_title="YouTube SEO Tool", layout="wide")
st.title("📊 YouTube SEO Tool")

tabs = st.tabs(["🎥 Video Export", "🔍 SEO Topic Analysis", "📈 Trending Topic Finder"])

# ---------------- Tab 1: Video Export ----------------
with tabs[0]:
    st.header("🎥 YouTube Channel Video Exporter")

    youtube_api_key = st.text_input("Enter YouTube API Key", type="password")
    openai_api_key = st.text_input("Enter OpenAI API Key (for SEO tags & images)", type="password")
    channel_id = st.text_input("Enter YouTube Channel ID")
    max_results = st.number_input("Number of videos to fetch", min_value=1, max_value=50, value=10, step=1)

    if st.button("Fetch Videos"):
        if not youtube_api_key:
            st.error("Please enter your YouTube API key.")
        else:
            youtube = build("youtube", "v3", developerKey=youtube_api_key)
            results = []

            try:
                playlist_id = get_upload_playlist(youtube, channel_id)
                videos = get_videos_from_playlist(youtube, playlist_id, max_results=max_results)

                client = OpenAI(api_key=openai_api_key) if openai_api_key else None

                for video in videos:
                    video_id = video["contentDetails"]["videoId"]

                    video_info = youtube.videos().list(
                        part="snippet,statistics",
                        id=video_id
                    ).execute()
                    snippet = video_info["items"][0]["snippet"]
                    stats = video_info["items"][0].get("statistics", {})

                    title = snippet["title"]
                    description = snippet.get("description", "N/A")
                    views = stats.get("viewCount", "0")
                    transcript = fetch_video_transcript(video_id)

                    seo_output, image_url = ("Not generated", None)
                    if client:
                        seo_output, image_url = generate_seo_and_image(client, title, description, transcript)

                    results.append({
                        "Video ID": video_id,
                        "Title": title,
                        "Description": description,
                        "Views": views,
                        "Transcript": transcript,
                        "SEO Suggestions": seo_output,
                        "Image": image_url
                    })

                df = pd.DataFrame(results)
                st.success("✅ Video details fetched successfully!")
                st.dataframe(df)

                for r in results:
                    if r["Image"]:
                        st.image(r["Image"], caption=r["Title"], use_container_width=True)

                output = BytesIO()
                with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                    df.to_excel(writer, index=False, sheet_name="Videos")
                st.download_button(
                    "📥 Download Video Data (Excel)",
                    data=output.getvalue(),
                    file_name="video_export.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

            except Exception as e:
                st.error(f"Error fetching videos: {e}")

# ---------------- Tab 2: SEO Topic Analysis ----------------
with tabs[1]:
    st.header("🔍 SEO Topic Analysis")
    st.write("Enter comma-separated keywords or upload an Excel file with keywords.")

    youtube_api_key = st.text_input("Enter YouTube API Key (Tab 2)", type="password")
    openai_api_key = st.text_input("Enter OpenAI API Key (Tab 2)", type="password")

    keyword_input = st.text_area("Enter Topic/Keyword for SEO Analysis (comma-separated)")
    uploaded_file = st.file_uploader("Or upload an Excel file with a column named 'keywords'", type=["xlsx"])

    max_results_tab2 = st.number_input("Number of videos per keyword", min_value=1, max_value=20, value=10)

    if st.button("Analyze SEO Topics"):
        if not youtube_api_key:
            st.error("Please enter YouTube API key.")
        else:
            youtube = build("youtube", "v3", developerKey=youtube_api_key)
            client = OpenAI(api_key=openai_api_key) if openai_api_key else None

            if uploaded_file:
                df_keywords = pd.read_excel(uploaded_file)
                keywords = df_keywords["keywords"].dropna().tolist()
            else:
                keywords = [kw.strip() for kw in keyword_input.split(",") if kw.strip()]

            results = []
            for kw in keywords:
                search = youtube.search().list(
                    part="snippet",
                    q=kw,
                    type="video",
                    order="viewCount",
                    maxResults=max_results_tab2
                ).execute()

                for item in search["items"]:
                    video_id = item["id"]["videoId"]
                    title = item["snippet"]["title"]
                    description = item["snippet"].get("description", "")
                    seo_tags = "Not generated"

                    if client:
                        try:
                            prompt = f"Suggest SEO-friendly tags and hashtags for this YouTube video:\n\nTitle: {title}\nDescription: {description}"
                            seo_tags = client.chat.completions.create(
                                model="gpt-4o-mini",
                                messages=[{"role": "user", "content": prompt}],
                                temperature=0.7
                            ).choices[0].message.content
                        except Exception:
                            seo_tags = "Error generating tags"

                    results.append({
                        "Keyword": kw,
                        "Video ID": video_id,
                        "Title": title,
                        "Description": description,
                        "SEO Suggestions": seo_tags
                    })

            df = pd.DataFrame(results)
            st.dataframe(df)

            output = BytesIO()
            with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                df.to_excel(writer, index=False, sheet_name="SEO_Analysis")
            st.download_button(
                "📥 Download SEO Analysis (Excel)",
                data=output.getvalue(),
                file_name="seo_analysis.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

# ---------------- Tab 3: Trending Topic Finder ----------------
with tabs[2]:
    st.header("📈 Trending Topic Finder")
    st.write("Enter comma-separated topics or upload Excel file to discover trending video topics.")

    youtube_api_key = st.text_input("Enter YouTube API Key (Tab 3)", type="password")
    openai_api_key = st.text_input("Enter OpenAI API Key (Tab 3)", type="password")

    topic_input = st.text_area("Enter topics (comma-separated)")
    uploaded_file = st.file_uploader("Or upload an Excel file with a column named 'topics'", type=["xlsx"])

    max_results_tab3 = st.number_input("Number of videos per topic", min_value=1, max_value=20, value=10)

    if st.button("Find Trending Topics"):
        if not youtube_api_key:
            st.error("Please enter YouTube API key.")
        else:
            youtube = build("youtube", "v3", developerKey=youtube_api_key)

            if uploaded_file:
                df_topics = pd.read_excel(uploaded_file)
                topics = df_topics["topics"].dropna().tolist()
            else:
                topics = [tp.strip() for tp in topic_input.split(",") if tp.strip()]

            results = []
            for tp in topics:
                search = youtube.search().list(
                    part="snippet",
                    q=tp,
                    type="video",
                    order="viewCount",
                    maxResults=max_results_tab3
                ).execute()

                for item in search["items"]:
                    video_id = item["id"]["videoId"]
                    title = item["snippet"]["title"]
                    description = item["snippet"].get("description", "")
                    results.append({
                        "Topic": tp,
                        "Video ID": video_id,
                        "Title": title,
                        "Description": description
                    })

            df = pd.DataFrame(results)
            st.dataframe(df)

            output = BytesIO()
            with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                df.to_excel(writer, index=False, sheet_name="Trending_Topics")
            st.download_button(
                "📥 Download Trending Topics (Excel)",
                data=output.getvalue(),
                file_name="trending_topics.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
