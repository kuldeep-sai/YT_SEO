import streamlit as st
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import Flow
from googleapiclient.errors import HttpError
import pandas as pd
from io import BytesIO
import os
import pickle
import time

# Page setup
st.set_page_config(page_title="YouTube SEO Editor", layout="centered")
st.title("📊 YouTube SEO Manager with OAuth")

# Load OAuth credentials from secrets
oauth_client_id = st.secrets["google_oauth"]["client_id"]
oauth_client_secret = st.secrets["google_oauth"]["client_secret"]
redirect_uri = st.secrets["google_oauth"]["redirect_uri"]

# Define scopes for YouTube Data API (read & write access)
SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]

# Session state
if "credentials" not in st.session_state:
    st.session_state.credentials = None

# OAuth 2.0 Authentication
if not st.session_state.credentials:
    auth_url_params = {
        "client_id": oauth_client_id,
        "redirect_uri": redirect_uri,
        "scope": SCOPES,
        "access_type": "offline",
        "include_granted_scopes": "true",
        "response_type": "code",
        "prompt": "consent"
    }
    auth_url = "https://accounts.google.com/o/oauth2/auth?" + "&".join(
        [f"{k}={v}" for k, v in auth_url_params.items()]
    )
    st.markdown(f"🔐 [Click here to authorize with Google]({auth_url})")

    # Get authorization code from user
    auth_code = st.text_input("Paste the authorization code here:")
    if st.button("🔓 Authenticate") and auth_code:
        flow = Flow.from_client_config(
            {
                "installed": {
                    "client_id": oauth_client_id,
                    "client_secret": oauth_client_secret,
                    "redirect_uris": [redirect_uri],
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token"
                }
            },
            scopes=SCOPES,
            redirect_uri=redirect_uri
        )
        flow.fetch_token(code=auth_code)
        st.session_state.credentials = flow.credentials
        st.success("✅ Authenticated successfully!")

# Proceed if authenticated
if st.session_state.credentials:
    youtube = build("youtube", "v3", credentials=st.session_state.credentials)

    st.subheader("📺 Edit SEO Metadata of Your Videos")

    with st.form("edit_form"):
        channel_id = st.text_input("Enter your YouTube Channel ID")
        max_videos = st.slider("Number of videos to fetch", 1, 50, 10)
        submit = st.form_submit_button("Fetch & Edit Videos")

    def get_upload_playlist_id(channel_id):
        res = youtube.channels().list(part="contentDetails", id=channel_id).execute()
        return res["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

    def get_video_ids(playlist_id, max_videos):
        vids = []
        token = None
        while len(vids) < max_videos:
            pl = youtube.playlistItems().list(
                part="contentDetails",
                playlistId=playlist_id,
                maxResults=min(50, max_videos - len(vids)),
                pageToken=token
            ).execute()
            vids.extend([item["contentDetails"]["videoId"] for item in pl["items"]])
            token = pl.get("nextPageToken")
            if not token:
                break
        return vids

    def get_video_metadata(video_id):
        res = youtube.videos().list(part="snippet", id=video_id).execute()
        return res["items"][0]["snippet"]

    def update_video(video_id, title, desc, tags):
        body = {
            "id": video_id,
            "snippet": {
                "title": title,
                "description": desc,
                "tags": tags,
                "categoryId": "22"
            }
        }
        return youtube.videos().update(part="snippet", body=body).execute()

    if submit:
        try:
            playlist_id = get_upload_playlist_id(channel_id)
            video_ids = get_video_ids(playlist_id, max_videos)

            st.success(f"Fetched {len(video_ids)} videos.")
            for video_id in video_ids:
                meta = get_video_metadata(video_id)
                with st.expander(f"📹 {meta['title']}"):
                    new_title = st.text_input(f"✏️ Title ({video_id})", meta['title'], key=video_id+"_title")
                    new_desc = st.text_area(f"📝 Description ({video_id})", meta['description'], key=video_id+"_desc")
                    new_tags = st.text_input(f"🏷️ Tags (comma-separated)", ", ".join(meta.get('tags', [])), key=video_id+"_tags")
                    if st.button(f"✅ Update Video {video_id}"):
                        update_video(video_id, new_title, new_desc, [t.strip() for t in new_tags.split(",")])
                        st.success("Updated successfully!")

        except HttpError as e:
            st.error(f"API Error: {e}")
