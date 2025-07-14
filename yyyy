# utils/instagram_handler.py

import streamlit as st
import pandas as pd

def handle_instagram_single(url, enable_seo, client):
    st.info(f"📍 Instagram single video analysis not implemented yet.\nURL: {url}")
    # Future: Use API or scraping to fetch title, caption, hashtags etc.
    # If enable_seo and client: Use OpenAI to suggest SEO
    if enable_seo and client:
        st.success("✨ SEO Tagging would go here.")

def handle_instagram_batch(profile_url, max_posts, enable_seo, client):
    st.info(f"📦 Instagram batch from profile not implemented yet.\nProfile URL: {profile_url}, Posts: {max_posts}")
    # Placeholder for real Instagram batch scraping logic
    if enable_seo and client:
        st.success("✨ SEO Tagging would go here.")

def handle_instagram_urls(uploaded_file, enable_seo, client):
    urls = []
    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
        urls = df.iloc[:, 0].tolist()
    elif uploaded_file.name.endswith(".txt"):
        urls = uploaded_file.read().decode("utf-8").splitlines()

    st.write(f"Found {len(urls)} Instagram URLs.")
    for url in urls:
        st.markdown(f"- {url}")

    if enable_seo and client:
        st.success("✨ SEO Tagging would go here.")
