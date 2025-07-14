# utils/instagram_handler.py

import streamlit as st
import pandas as pd

def handle_instagram_single(instagram_url, enable_seo, client, instagram_api_key):
    st.info(f"Processing single Instagram video: {instagram_url}")
    # Placeholder logic – implement scraping or API fetch here
    st.write("✅ Instagram video processed successfully.")

def handle_instagram_batch(profile_url, max_posts, enable_seo, client, instagram_api_key):
    st.info(f"Fetching {max_posts} posts from profile: {profile_url}")
    # Placeholder logic – implement scraping or API fetch here
    st.write(f"✅ Batch fetched {max_posts} Instagram videos.")

def handle_instagram_urls(file, enable_seo, client, instagram_api_key):
    st.info("Reading uploaded Instagram URLs...")
    try:
        if file.name.endswith(".csv"):
            urls = pd.read_csv(file).iloc[:, 0].tolist()
        else:
            urls = file.read().decode("utf-8").splitlines()

        for url in urls:
            st.write(f"Processing: {url}")
            # Placeholder logic
        st.success(f"✅ Processed {len(urls)} Instagram URLs.")
    except Exception as e:
        st.error(f"Error reading file: {e}")
