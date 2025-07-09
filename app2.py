import streamlit as st
from googleapiclient.discovery import build
import pandas as pd
from io import BytesIO
import openai
import time

# Page setup
st.set_page_config(page_title="YouTube Channel Video Exporter", layout="centered")
st.title("📊 YouTube Channel Video Exporter + SEO Generator + Transcript")

st.markdown("Export videos from your YouTube channel by specifying how many videos to fetch and from which offset. Optionally generate SEO-optimized titles, descriptions, keywords, and simulated transcripts using OpenAI.")

# Input form
with st.form(key="form"):
    yt_api_key = st.text_input("🔑 YouTube API Key", type="password")
    openai_key = st.text_input("🤖 OpenAI API Key (optional - for SEO & transcript)", type="password")
    channel_id = st.text_input("📡 YouTube Channel ID (e.g. UC_xxx...)")
    start_index = st.number_input("▶️ Start from video number", min_value=1, value=1, step=1)
    video_count = st.number_input("🎬 Number of videos to fetch", min_value=1, max_value=500, value=50, step=1)
    enable_seo = st.checkbox("✨ Enable SEO Tagging using ChatGPT")
    enable_transcript = st.checkbox("📝 Generate Video Transcript using GPT")
    submit = st.form_submit_button("📥 Fetch Videos")

# Helper functions
def get_upload_playlist(youtube, channel_id):
    data = youtube.channels().list(part="contentDetails", id=channel_id).execute()
    return data["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

def get_video_ids(youtube, playlist_id, max_videos=100):
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

def safe_openai_call(prompt, retries=3):
    for i in range(retries):
        try:
            response = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7
            )
            return response.choices[0].message.content
        except openai.RateLimitError:
            wait = 2 ** (i + 1)
            time.sleep(wait)
        except Exception as e:
            return f"OpenAI Error: {e}"
    return "⚠️ Failed after retries."

def generate_seo_tags(video):
    prompt = f"""
    Analyze the following YouTube video metadata:

    Title: {video['title']}
    Description: {video['description']}
    Tags: {video['tags']}
    Views: {video['views']}

    Generate:
    - An SEO-optimized title
    - A 150-word keyword-rich video description
    - A list of 10 SEO-relevant hashtags
    - A comma-separated list of SEO keywords
    """
    return safe_openai_call(prompt)

def generate_transcript(video):
    prompt = f"""
    Generate a simulated transcript for this YouTube video titled '{video['title']}'. Make it 100–150 words based on the topic implied in the title and description.

    Description:
    {video['description']}
    """
    return safe_openai_call(prompt)

# Fetch logic
if submit:
    if not yt_api_key or not channel_id:
        st.error("❌ Please enter both API Key and Channel ID.")
    else:
        try:
            youtube = build("youtube", "v3", developerKey=yt_api_key)
            if (enable_seo or enable_transcript) and openai_key:
                openai.api_key = openai_key
            playlist_id = get_upload_playlist(youtube, channel_id)

            # Adjust range
            start = max(0, start_index - 1)
            end = start + video_count

            with st.spinner("📡 Fetching videos..."):
                video_meta = get_video_ids(youtube, playlist_id, max_videos=end)
                video_meta_sorted = sorted(video_meta, key=lambda x: x["published_at"], reverse=True)
                selected_batch = video_meta_sorted[start:end]

                video_details = []
                for v in selected_batch:
                    info = get_video_info(youtube, v["video_id"])
                    if enable_seo and openai_key:
                        info["seo_output"] = generate_seo_tags(info)
                        time.sleep(5)
                    if enable_transcript and openai_key:
                        info["transcript"] = generate_transcript(info)
                        time.sleep(5)
                    video_details.append(info)

                df = pd.DataFrame(video_details)
                st.write(f"📄 Showing videos {start+1} to {end}")
                st.dataframe(df)

                # Excel download
                output = BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False, sheet_name="Videos")
                output.seek(0)

                st.download_button(
                    label=f"⬇️ Download Excel for videos {start+1}–{end}",
                    data=output,
                    file_name=f"youtube_videos_{start+1}_{end}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
