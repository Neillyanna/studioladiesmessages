#!/usr/bin/env python3
"""
NEW YORK PIZZA & BURGER — Pub Premium 15s
Génération des 5 scènes via Higgsfield (cinematic_studio_3_0)

Usage :
    python generate_nypb_ad.py
"""

import os
import requests
import higgsfield_client
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

OUTPUT_DIR = os.getenv("DATA_DIR", "/app/data") + "/nypb_ad"
RESULTS_FILE = os.path.join(OUTPUT_DIR, "ad_urls.txt")
MODEL = "higgsfield-ai/dop/standard"

SCENES = [
    {
        "id": "scene2",
        "label": "Taxi NYC de nuit",
        "timecode": "0:02 → 0:05",
        "image_url": "https://images.unsplash.com/photo-1541417904950-b855846fe074?w=1080",
        "prompt": "Cinematic slow-motion yellow taxi cab driving through wet Manhattan streets at night, neon reflections, steam rising, dark moody atmosphere, golden yellow and black color palette, premium commercial feel",
    },
    {
        "id": "scene3",
        "label": "Cheese pull pizza",
        "timecode": "0:05 → 0:08",
        "image_url": "https://images.unsplash.com/photo-1513104890138-7c749659a591?w=1080",
        "prompt": "Extreme close-up of melted mozzarella cheese stretching from a gourmet pizza slice being slowly lifted, warm golden side lighting, steam rising, ultra satisfying slow motion food commercial",
    },
    {
        "id": "scene4",
        "label": "Ouverture boîte pizza",
        "timecode": "0:08 → 0:11",
        "image_url": "https://images.unsplash.com/photo-1571407970349-bc81e7e96d47?w=1080",
        "prompt": "Slow motion cinematic reveal of a premium pizza box opening to reveal a gourmet pizza inside, dramatic overhead spotlight, dark luxury aesthetic, steam escaping, 4K food commercial",
    },
    {
        "id": "scene5",
        "label": "Burger drop",
        "timecode": "0:11 → 0:13",
        "image_url": "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=1080",
        "prompt": "Ultra slow motion cinematic burger assembly shot, thick juicy beef patty, melted cheddar cheese cascading down, dark moody studio, warm golden backlight, premium fast food commercial 4K",
    },
    {
        "id": "scene6",
        "label": "Brand reveal packaging",
        "timecode": "0:13 → 0:15",
        "image_url": "https://images.unsplash.com/photo-1594007654729-407eedc4be65?w=1080",
        "prompt": "Cinematic product shot of premium restaurant packaging on dark textured marble surface, dramatic single side light source, luxury fast food brand reveal, 4K commercial photography style",
    },
]


def generate_scene(scene: dict, index: int) -> str | None:
    print(f"\n[{index}/{len(SCENES)}] {scene['label']} ({scene['timecode']})...")

    # Animer l'image de stock avec DOP
    print(f"  → Animation vidéo (DOP)...")
    result = higgsfield_client.subscribe(
        MODEL,
        arguments={
            "prompt": scene["prompt"],
            "image_url": scene["image_url"],
            "aspect_ratio": "9:16",
        },
    )

    videos = result.get("videos", [])
    if not videos:
        print(f"  ❌ Aucune vidéo retournée : {result}")
        return None

    video_url = videos[0].get("url")
    if not video_url:
        print(f"  ❌ URL manquante : {result}")
        return None

    filename = f"{scene['id']}_{scene['label'].replace(' ', '_')}.mp4"
    filepath = os.path.join(OUTPUT_DIR, filename)

    print(f"  ↓ Téléchargement...")
    response = requests.get(video_url, timeout=120)
    response.raise_for_status()
    with open(filepath, "wb") as f:
        f.write(response.content)

    print(f"  ✅ Sauvegardé : {filepath}")
    return filepath


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("\n" + "=" * 54)
    print("  NEW YORK PIZZA & BURGER — Génération pub 15s")
    print("=" * 54)
    print(f"  Date    : {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print(f"  Modèle  : {MODEL}")
    print(f"  Scènes  : {len(SCENES)} × 3s = 15s")
    print(f"  Dossier : {OUTPUT_DIR}")
    print("=" * 54)

    results = []

    for i, scene in enumerate(SCENES, 1):
        try:
            filepath = generate_scene(scene, i)
            results.append((scene["id"], scene["label"], filepath or "ERREUR"))
        except Exception as e:
            print(f"  ❌ Erreur scène {i} : {e}")
            results.append((scene["id"], scene["label"], f"ERREUR: {e}"))

    # Rapport final
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        f.write("=== NEW YORK PIZZA & BURGER — Fichiers générés ===\n")
        f.write(f"Date : {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n")
        for scene_id, label, path in results:
            f.write(f"{scene_id.upper()} ({label}) : {path}\n")

    print("\n" + "=" * 54)
    print("  TOUTES LES SCÈNES TRAITÉES !")
    print(f"  Rapport : {RESULTS_FILE}")
    print("=" * 54 + "\n")


if __name__ == "__main__":
    main()
