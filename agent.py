import os, asyncio, requests, edge_tts
from google import genai
from moviepy.editor import VideoFileClip, AudioFileClip, vfx
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# 1. Generate Script & SEO Metadata via Gemini
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
prompt = (
    "Write a 45-word viral YouTube Short script about an astonishing science or psychology fact. "
    "Return ONLY 3 parts separated by a pipe symbol | : "
    "Catchy Title with #shorts | 1-word visual search keyword | Full spoken narration script"
)
res = client.models.generate_content(model="gemini-3.8-flash", contents=prompt).text.strip()
parts = [x.strip() for x in res.split("|")]
title, keyword, script = parts[0], parts[1], parts[2]

# 2. Generate Free Neural Voiceover
async def make_voice():
    await edge_tts.Communicate(script, "en-US-ChristopherNeural").save("voice.mp3")
asyncio.run(make_voice())

# 3. Fetch HD Stock Video from Pixabay
pix_key = os.environ["PIXABAY_API_KEY"].strip()
url = f"https://pixabay.com{pix_key}&q={keyword}&per_page=3"
v_data = requests.get(url).json()
if not v_data.get("hits"):
    v_data = requests.get(f"https://pixabay.com{pix_key}&q=nature&per_page=3").json()
video_url = v_data["hits"]["videos"]["medium"]["url"]

open("bg.mp4", "wb").write(requests.get(video_url).content)

# 4. Assemble, Center-Crop to 9:16 & Loop Video
audio = AudioFileClip("voice.mp3")
duration = min(audio.duration, 58.0)
clip = VideoFileClip("bg.mp4").without_audio()
if clip.duration < duration:
    clip = clip.fx(vfx.loop, duration=duration)
else:
    clip = clip.subclip(0, duration)

w, h = clip.size
target_w = int(h * 9 / 16)
if w > target_w:
    clip = clip.crop(x_center=w / 2, width=target_w)
final = clip.resize((1080, 1920)).set_audio(audio)
final.write_videofile("short.mp4", fps=24, codec="libx264", audio_codec="aac")

# 5. Upload Directly to YouTube
creds = Credentials(
    None,
    refresh_token=os.environ["YT_REFRESH_TOKEN"],
    token_uri="https://googleapis.com",
    client_id=os.environ["YT_CLIENT_ID"],
    client_secret=os.environ["YT_CLIENT_SECRET"],
)
youtube = build("youtube", "v3", credentials=creds)
body = {
    "snippet": {
        "title": title[:95],
        "description": f"{script}\n\n#shorts #facts",
        "categoryId": "22"
    },
    "status": {"privacyStatus": "public"}
}
youtube.videos().insert(
    part="snippet,status",
    body=body,
    media_body=MediaFileUpload("short.mp4")
).execute()
print("SUCCESSFULLY UPLOADED:", title)
