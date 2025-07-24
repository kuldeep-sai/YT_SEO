
import streamlit as st
import requests
from bs4 import BeautifulSoup
import openai
import pandas as pd
import json

# Set up OpenAI API key (Streamlit Cloud users: set this in Secrets)
openai.api_key = st.secrets["OPENAI_API_KEY"]

st.set_page_config(page_title="MCP Scorecard Generator", page_icon="🧠")
st.title("🧠 MCP Scorecard Generator")
st.markdown("Analyze a webpage for LLM SEO readiness using the Model Context Protocol (MCP).")

# Step 1: Input URL
url = st.text_input("🔗 Enter a webpage URL:")

# Function to fetch and clean page content
def fetch_page_content(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        return soup.get_text(separator=' ', strip=True)
    except Exception as e:
        return f"Error fetching URL: {e}"

# Function to get scorecard from OpenAI
def generate_mcp_scorecard(content, url):
    prompt = f"""
You are a content auditor evaluating SEO visibility for Large Language Models (LLMs). Review the following webpage content and score it (0 = No, 1 = Yes) for the 10 criteria below:

1. Title follows prompt style
2. Clear intro that answers query
3. Structured subheadings
4. Includes FAQs
5. Uses bullets or lists
6. Author/source/credibility present
7. Schema markup present
8. Conversational tone
9. LLM-friendly (likely to be summarized)
10. Recently updated

Respond with a JSON object including the URL and the 10 binary scores plus total.

Webpage content:
"""
    prompt += content[:6000]  # Limit to 6000 characters

    response = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )

    return response.choices[0].message['content']

# Step 2: Run analysis
if url:
    with st.spinner("🔍 Fetching and analyzing the content..."):
        content = fetch_page_content(url)
        if content.startswith("Error"):
            st.error(content)
        else:
            scorecard_raw = generate_mcp_scorecard(content, url)
            st.subheader("✅ MCP Scorecard JSON Output")
            st.code(scorecard_raw, language="json")

            try:
                score_data = json.loads(scorecard_raw)
                df = pd.DataFrame([score_data])
                st.subheader("📊 Parsed MCP Scorecard Table")
                st.dataframe(df)
            except Exception as e:
                st.warning("⚠️ Unable to parse the output. Please check JSON formatting.")
