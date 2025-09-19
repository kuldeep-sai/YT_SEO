import streamlit as st
import requests
import base64
import replicate
from openai import OpenAI

# ---- IMAGE GENERATORS ---- #

def generate_image_openai(prompt, api_key, size="1024x1024"):
    try:
        client = OpenAI(api_key=api_key)
        result = client.images.generate(
            model="gpt-image-1",
            prompt=prompt,
            size=size
        )
        img_url = result.data[0].url
        return img_url
    except Exception as e:
        st.error(f"OpenAI image generation failed: {e}")
        return None


def generate_image_stability(prompt, api_key, size="1024x1024"):
    try:
        url = "https://api.stability.ai/v2beta/stable-image/generate/core"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json"
        }
        body = {
            "prompt": prompt,
            "output_format": "png",
        }
        response = requests.post(url, headers=headers, files={}, data=body)
        if response.status_code == 200:
            img_data = response.json()["image"]
            img_bytes = base64.b64decode(img_data)
            return img_bytes
        else:
            st.error(f"Stability API error: {response.text}")
            return None
    except Exception as e:
        st.error(f"Stability AI generation failed: {e}")
        return None


def generate_image_replicate(prompt, api_token):
    try:
        client = replicate.Client(api_token=api_token)
        output = client.run(
            "stability-ai/sdxl:latest",
            input={"prompt": prompt}
        )
        return output[0]  # image URL
    except Exception as e:
        st.error(f"Replicate image generation failed: {e}")
        return None


# ---- STREAMLIT UI ---- #

st.sidebar.header("🔑 API Keys")
openai_key = st.sidebar.text_input("OpenAI API Key", type="password")
stability_key = st.sidebar.text_input("Stability AI API Key", type="password")
replicate_key = st.sidebar.text_input("Replicate API Key", type="password")

st.sidebar.header("🖼️ Image Generator Settings")
provider = st.sidebar.selectbox(
    "Choose Image Provider",
    ["OpenAI", "Stability AI", "Replicate"]
)
img_size = st.sidebar.selectbox(
    "Image Size",
    ["1024x1024", "1024x1536", "1536x1024"]
)

prompt = st.text_input("Enter your thumbnail prompt")

if st.button("Generate Thumbnail"):
    if provider == "OpenAI":
        if not openai_key:
            st.error("Please enter OpenAI API key")
        else:
            url = generate_image_openai(prompt, openai_key, size=img_size)
            if url:
                st.image(url, caption="Generated with OpenAI", use_column_width=True)

    elif provider == "Stability AI":
        if not stability_key:
            st.error("Please enter Stability AI API key")
        else:
            img_bytes = generate_image_stability(prompt, stability_key, size=img_size)
            if img_bytes:
                st.image(img_bytes, caption="Generated with Stability AI", use_column_width=True)

    elif provider == "Replicate":
        if not replicate_key:
            st.error("Please enter Replicate API key")
        else:
            url = generate_image_replicate(prompt, replicate_key)
            if url:
                st.image(url, caption="Generated with Replicate", use_column_width=True)
