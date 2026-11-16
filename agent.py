import os, time, asyncio, textwrap, edge_tts
import numpy as np
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageEnhance

if not hasattr(Image, "ANTIALIAS"):
    Image.ANTIALIAS = Image.LANCZOS

from google import genai
from google.genai import types
from moviepy.editor import ImageClip, AudioFileClip, CompositeVideoClip
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# 1. Generate High-Retention Viral Script via Gemini
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"].strip())
prompt = (
    "Write a viral 45-word YouTube Short script about a mind-blowing psychology or human brain secret. "
    "Start with an irresistible 5-word curiosity hook. Use short, punchy sentences. "
    "Return ONLY 3 parts separated by | : "
    "Viral Title with #shorts | 3-word UPPERCASE topic badge | Vertical dark moody digital art prompt | Full spoken script"
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
title = str(parts.pop(0)) if parts else "Your Brain Is Lying To You #shorts"
badge = str(parts.pop(0))[:24].upper() if len(parts) > 2 else "PSYCHOLOGY SECRET"
img_prompt = str(parts.pop(0)) if len(parts) > 1 else "Dark moody glowing human brain neural pathways, cinematic 9:16 vertical art"
script = str(parts.pop(0)) if parts else title
print("Viral Title:", title)

# 2. Generate Custom 9:16 AI Background (Darkened for Caption Contrast)
try:
    img_result = client.models.generate_images(
        model="imagen-3.0-generate-002",
        prompt=img_prompt,
        config=types.GenerateImagesConfig(number_of_images=1, aspect_ratio="9:16")
    )
    gen_img = next(iter(img_result.generated_images))
    bg_img = Image.open(BytesIO(gen_img.image.image_bytes)).convert("RGB").resize((1080, 1920), Image.LANCZOS)
    bg_img = ImageEnhance.Brightness(bg_img).enhance(0.55)  # Darken so white captions pop
    bg_img.save("bg.png")
    print("AI background created.")
except Exception as e:
    print("Using dark studio gradient:", e)
    bg_img = Image.new("RGB", (1080, 1920), (10, 12, 22))
    draw = ImageDraw.Draw(bg_img)
    for y in range(1920):
        r = int(10 + (y / 1920) * 20)
        g = int(12 + (y / 1920) * 15)
        b = int(22 + (y / 1920) * 45)
        draw.line([(0, y), (1080, y)], fill=(r, g, b))
    bg_img.save("bg.png")

# 3. Generate Energetic Voiceover + Exact Word Timestamps
word_timings = []
async def make_voice_and_timings():
    communicate = edge_tts.Communicate(script, "en-US-AndrewMultilingualNeural", rate="+8%")
    with open("voice.mp3", "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                start_sec = chunk["offset"] / 10_000_000
                dur_sec = chunk["duration"] / 10_000_000
                word_timings.append((start_sec, start_sec + max(dur_sec, 0.25), chunk["text"]))

asyncio.run(make_voice_and_timings())

# 4. Helper to Draw Crisp Captions & Top Hook Badge via Pillow
def get_font(size):
    for path in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
    ]:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()

caption_font = get_font(84)
badge_font = get_font(44)

def make_text_layer(text, font, y_pos, fill_color=(255, 255, 255, 255), box_bg=False):
    layer = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    wrapped = textwrap.fill(text, width=18)
    bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, align="center")
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (1080 - tw) // 2
    if box_bg:
        pad = 24
        draw.rounded_rectangle([x - pad, y_pos - pad, x + tw + pad, y_pos + th + pad], radius=20, fill=(220, 38, 38, 230))
    draw.multiline_text(
        (x, y_pos), wrapped, font=font, fill=fill_color,
        align="center", stroke_width=6, stroke_fill=(0, 0, 0, 255)
    )
    return np.array(layer)

# 5. Assemble Dynamic Video (Zoom Background + Top Badge + Synced Captions)
audio = AudioFileClip("voice.mp3")
duration = min(audio.duration, 58.0)

bg_clip = (
    ImageClip("bg.png")
    .set_duration(duration)
    .resize(lambda t: 1.0 + 0.06 * (t / duration))
    .set_position("center")
)

badge_clip = ImageClip(make_text_layer(badge, badge_font, y_pos=240, box_bg=True)).set_duration(duration)

layers = [bg_clip, badge_clip]

# Group words into punchy 2-word viral subtitle chunks
for i in range(0, len(word_timings), 2):
    chunk_group = word_timings[i:i + 2]
    t_start = chunk_group[0][0]
    t_end = min(chunk_group[-1][1] + 0.08, duration)
    if t_start >= duration:
        break
    phrase = " ".join(w[2].upper() for w in chunk_group)
    cap_np = make_text_layer(phrase, caption_font, y_pos=880, fill_color=(255, 230, 0, 255))
    cap_clip = ImageClip(cap_np).set_start(t_start).set_duration(max(t_end - t_start, 0.15))
    layers.append(cap_clip)

final = CompositeVideoClip(layers, size=(1080, 1920)).set_audio(audio)
final.write_videofile("short.mp4", fps=24, codec="libx264", audio_codec="aac")

# 6. Upload Directly to YouTube
creds = Credentials.from_authorized_user_info({
    "refresh_token": os.environ["YT_REFRESH_TOKEN"].strip(),
    "client_id": os.environ["YT_CLIENT_ID"].strip(),
    "client_secret": os.environ["YT_CLIENT_SECRET"].strip(),
})

youtube = build("youtube", "v3", credentials=creds)
body = {
    "snippet": {
        "title": title[:95],
        "description": f"{script}\n\n#shorts #psychology #facts",
        "categoryId": "22"
    },
    "status": {"privacyStatus": "public"}
}
media = MediaFileUpload("short.mp4", chunksize=-1, resumable=True)
response = youtube.videos().insert(part="snippet,status", body=body, media_body=media).execute()
print("SUCCESSFULLY UPLOADED VIRAL SHORT ID:", response.get("id"))
