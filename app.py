from flask import Flask, render_template, request
import requests
import cv2
import os
import base64
import logging
import http.client
import json
from openai import OpenAI, APIConnectionError, APIError

# Set template_folder to the root directory
app = Flask(__name__, template_folder='.')

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Set your OpenAI API key and instantiate the client
openai_client = OpenAI(api_key="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")

rapidapi_key = "d0a12cd2a9msh53f7653581d62d0p1f2b5ejsn35b61c563e54"

def download_tiktok_video(tiktok_url):
    try:
        conn = http.client.HTTPSConnection("auto-download-all-in-one.p.rapidapi.com")
        payload = json.dumps({"url": tiktok_url})

        headers = {
            'x-rapidapi-key': rapidapi_key,
            'x-rapidapi-host': "auto-download-all-in-one.p.rapidapi.com",
            'Content-Type': "application/json"
        }

        logging.info("Sending request to TikTok Video Downloader API...")
        conn.request("POST", "/v1/social/autolink", payload, headers)
        res = conn.getresponse()
        data = res.read().decode("utf-8")
        
        logging.info(f"API Response: {data}")
        
        video_info = json.loads(data)

        if video_info.get("error") or not video_info.get("medias"):
            logging.error("Failed to retrieve media URLs from the API response.")
            return None

        video_url = None
        for media in video_info["medias"]:
            if media["type"] == "video" and "no_watermark" in media["quality"]:
                video_url = media["url"]
                break

        if not video_url:
            logging.error("Failed to find a suitable video URL in the API response.")
            return None

        logging.info(f"Downloading video from URL: {video_url}")
        video_data = requests.get(video_url).content

        video_path = "tiktok_video.mp4"
        with open(video_path, "wb") as f:
            f.write(video_data)

        logging.info(f"Video downloaded and saved as {video_path}")
        return video_path

    except Exception as e:
        logging.error(f"Error during video download: {e}")
        return None

def extract_keyframe(video_path, output_folder="static/keyframes"):
    cap = cv2.VideoCapture(video_path)
    success, frame = cap.read()
    if not success:
        logging.error("Failed to extract frame from video.")
        return None

    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    frame_filename = f"{output_folder}/keyframe.jpg"
    cv2.imwrite(frame_filename, frame)

    cap.release()
    logging.info(f"Extracted and saved keyframe as {frame_filename}.")
    return frame_filename

def analyze_image_with_gpt4v(image_path):
    try:
        with open(image_path, "rb") as image_file:
            encoded_image = base64.b64encode(image_file.read()).decode('utf-8')

        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text", 
                            "text": "Individually identify each clothing item in the image, provide a custom google shopping search link for each. Include gender, color, style, shape, trend and vibe. Separate each link with a comma. Your output should ALWAYS have this format: 'https://www.google.com/search?q=womens+pink+slip-on+shoes+casual+comfortable'."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{encoded_image}"
                            }
                        }
                    ],
                }
            ],
            max_tokens=300,
        )

        description = response.choices[0].message.content
        logging.info(f"Analyzed image {image_path} and received descriptions.")
        return description
    except APIConnectionError as e:
        logging.error(f"API connection error: {e}")
        return None
    except APIError as e:
        logging.error(f"API error: {e}")
        return None

def parse_gpt_output(gpt_output):
    # Split the output by commas and strip whitespace
    links = [link.strip() for link in gpt_output.split(',')]
    
    # Filter out any non-link text (assuming all valid links start with 'http')
    valid_links = [link for link in links if link.startswith('http')]
    
    logging.debug(f"Parsed GPT output. Found {len(valid_links)} valid links: {valid_links}")
    return valid_links

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        tiktok_url = request.form["tiktok_url"]
        logging.info(f"Received TikTok URL: {tiktok_url}")
        
        video_path = download_tiktok_video(tiktok_url)
        if video_path:
            logging.info(f"Successfully downloaded TikTok video: {video_path}")
            frame_path = extract_keyframe(video_path)
            if frame_path:
                logging.info(f"Successfully extracted keyframe: {frame_path}")
                description = analyze_image_with_gpt4v(frame_path)
                if description:
                    logging.info("Received description from GPT-4 Vision")
                    logging.debug(f"GPT-4 Vision description: {description}")
                    links = parse_gpt_output(description)
                    
                    return render_template("results.html", links=links, gpt_output=description, frame_path=frame_path)
                else:
                    logging.error("Failed to get description from GPT-4 Vision")
            else:
                logging.error("Failed to extract keyframe from video")
        else:
            logging.error("Failed to download TikTok video")
        
        return render_template("error.html", message="Failed to process video or image.")
    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True)
