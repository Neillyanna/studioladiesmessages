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
MODEL = "cinematic_studio_video_v2"

SCENES = [
    {
        "id": "scene2",
        "label": "Taxi NYC de nuit",
        "timecode": "0:02 → 0:05",
        "prompt": (
            "Cinematic slow-motion yellow taxi cab driving through wet Manhattan streets at night, "
            "neon reflections on wet pavement, steam rising from vents, dark moody atmosphere, "
            "golden yellow and black color palette, 4K cinematic film grain, premium commercial feel"
        ),
    },
    {
        "id": "scene3",
        "label": "Cheese pull pizza",
        "timecode": "0:05 → 0:08",
        "prompt": (
            "Extreme close-up macro shot of melted mozzarella cheese stretching from a gourmet pizza slice "
            "being slowly lifted, warm golden side lighting, steam rising, pure black background, "
            "ultra satisfying slow motion food commercial, 4K sharp detail"
        ),
    },
    {
        "id": "scene4",
        "label": "Ouverture boîte pizza",
        "timecode": "0:08 → 0:11",
        "prompt": (
            "Slow motion cinematic reveal of a premium black and gold pizza box opening to reveal a gourmet "
            "pizza inside, dramatic overhead spotlight, dark luxury aesthetic, steam escaping, "
            "4K food commercial product reveal"
        ),
    },
    {
        "id": "scene5",
        "label": "Burger drop",
        "timecode": "0:11 → 0:13",
        "prompt": (
            "Ultra slow motion cinematic burger assembly shot, thick juicy beef patty dropping onto toasted "
            "brioche bun, melted cheddar cheese cascading down, sauce splashing in slow motion, "
            "dark moody studio, warm golden backlight, premium fast food commercial 4K"
        ),
    },
    {
        "id": "scene6",
        "label": "Brand reveal packaging",
        "timecode": "0:13 → 0:15",
        "prompt": (
            "Cinematic product shot of premium restaurant packaging arranged on dark textured marble surface, "
            "black and gold branded pizza box, paper bag, cup with logo, dramatic single side light source, "
            "luxury fast food brand reveal, 4K commercial photography style"
        ),
    },
]


def generate_scene(scene: dict, index: int) -> str | None:
    print(f"\n[{index}/{len(SCENES)}] {scene['label']} ({scene['timecode']})...")

    # Essai avec le modèle principal, fallback sur cinematic_studio_3_0
    for model in [MODEL, "cinematic_studio_3_0", "cinematic_studio_video", "kling3_0"]:
        try:
            result = higgsfield_client.subscribe(
                model,
                arguments={
                    "prompt": scene["prompt"],
                    "aspect_ratio": "9:16",
                },
            )
            print(f"  Modèle utilisé : {model}")
            break
        except Exception as e:
            print(f"  ✗ {model} : {str(e)[:50]}")
            result = None
    if result is None:
        return None

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
