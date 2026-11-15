import os, time, asyncio, edge_tts
from PIL import Image, ImageDraw

if not hasattr(Image, "ANTIALIAS"):
    Image.ANTIALIAS = Image.LANCZOS

from google import genai
from moviepy.editor import ImageClip, AudioFileClip
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# 1. Generate Script & Title via Gemini
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"].strip())
prompt = (
    "Write a 45-word viral YouTube Short script about an astonishing science or psychology fact. "
    "Return ONLY 2 parts separated by a pipe symbol | : "
    "Catchy Title with #shorts | Full spoken narration script"
)

res = None
for model_name in ["gemini-3.8-flash", "gemini-3.8-flash-lite"]:
    for attempt in range(3):
        try:
            res = client.models.generate_content(model=model_name, contents=prompt).text.strip()
            break
        except Exception as e:
            print(f"{model_name} attempt {attempt + 1} failed: {e}")
            time.sleep(5)
    if res:
        break

parts = [x.strip() for x in res.split("|") if x.strip()]
title = str(parts.pop(0)) if parts else "Mind Blowing Psychology Fact #shorts"
script = str(parts.pop(0)) if parts else title
print("Generated Title:", title)

# 2. Create Clean 1080x1920 Vertical Background
img = Image.new("RGB", (1080, 1920), (15, 20, 35))
draw = ImageDraw.Draw(img)
for y in range(1920):
    r = int(15 + (y / 1920) * 25)
    g = int(20 + (y / 1920) * 15)
    b = int(35 + (y / 1920) * 55)
    draw.line([(0, y), (1080, y)], fill=(r, g, b))
img.save("bg.png")

# 3. Generate Neural Voiceover
async def make_voice():
    await edge_tts.Communicate(script, "en-US-ChristopherNeural").save("voice.mp3")
asyncio.run(make_voice())

# 4. Render 1080x1920 MP4 Short
audio = AudioFileClip("voice.mp3")
duration = min(audio.duration, 58.0)
clip = ImageClip("bg.png").set_duration(duration)
final = clip.set_audio(audio)
final.write_videofile("short.mp4", fps=24, codec="libx264", audio_codec="aac")

# 5. Authenticate & Upload Directly to YouTube
token_endpoint = "https://" + "://googleapis.com" + "/token"
yt_scope = ["https://" + "://googleapis.com" + "/auth/youtube.upload"]

creds = Credentials(
    token=None,
    refresh_token=os.environ["YT_REFRESH_TOKEN"].strip(),
    token_uri=token_endpoint,
    client_id=os.environ["YT_CLIENT_ID"].strip(),
    client_secret=os.environ["YT_CLIENT_SECRET"].strip(),
    scopes=yt_scope
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
media = MediaFileUpload("short.mp4", chunksize=-1, resumable=True)
response = youtube.videos().insert(part="snippet,status", body=body, media_body=media).execute()
print("SUCCESSFULLY UPLOADED VIDEO ID:", response.get("id"))
