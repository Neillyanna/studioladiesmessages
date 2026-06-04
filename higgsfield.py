import os
import requests
import higgsfield_client
from datetime import datetime

DATA_DIR = os.getenv("DATA_DIR", "/app/data")
VIDEOS_DIR = os.path.join(DATA_DIR, "videos")
HIGGSFIELD_MODEL = os.getenv("HIGGSFIELD_MODEL", "bytedance/seedance/v2/text-to-video")


def generate_video(
    prompt: str,
    filename: str | None = None,
    duration: int = 5,
    resolution: str = "720p",
    aspect_ratio: str = "9:16",
) -> str | None:
    os.makedirs(VIDEOS_DIR, exist_ok=True)

    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"studio_ladies_{timestamp}.mp4"

    filepath = os.path.join(VIDEOS_DIR, filename)

    print(f"[Higgsfield] Génération vidéo : {prompt[:80]}...")

    result = higgsfield_client.subscribe(
        HIGGSFIELD_MODEL,
        arguments={
            "prompt": prompt,
            "duration": duration,
            "resolution": resolution,
            "aspect_ratio": aspect_ratio,
        },
    )

    # Le SDK retourne result['videos'][0]['url'] pour la vidéo générée
    videos = result.get("videos", [])
    if not videos:
        print(f"[Higgsfield] Aucune vidéo dans le résultat : {result}")
        return None

    video_url = videos[0].get("url")
    if not video_url:
        print(f"[Higgsfield] URL manquante dans le résultat : {result}")
        return None

    print(f"[Higgsfield] Téléchargement depuis {video_url[:60]}...")
    response = requests.get(video_url, timeout=120)
    response.raise_for_status()

    with open(filepath, "wb") as f:
        f.write(response.content)

    print(f"[Higgsfield] Vidéo sauvegardée : {filepath}")
    return filepath
