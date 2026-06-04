#!/usr/bin/env python3
"""
Scheduler de génération vidéo Higgsfield pour Studio Ladies.

Usage :
    python scheduler.py              # Lance le scheduler continu (cron interne)
    python scheduler.py --now        # Génère une vidéo immédiatement et quitte

Variables d'environnement :
    HIGGSFIELD_SCHEDULE        daily | weekly  (défaut: daily)
    HIGGSFIELD_SCHEDULE_TIME   HH:MM           (défaut: 09:00)
    HF_API_KEY                 Clé API Higgsfield
    HF_API_SECRET              Secret API Higgsfield
"""

import os
import sys
import time
import schedule
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from higgsfield import generate_video

# Prompts rotatifs par jour de la semaine — thèmes Studio Ladies Casablanca
WEEKLY_PROMPTS = {
    0: (
        "Lundi_Motivation",
        "Cinematic slow motion of elegant women practicing Pilates Reformer in a luxurious "
        "studio in Casablanca Morocco, soft morning light, pink and white tones, "
        "empowering energy, high-end gym decor, 4K quality",
    ),
    1: (
        "Mardi_Bienetre",
        "Beautiful women doing controlled Pilates movements on reformer machines, "
        "peaceful wellness studio atmosphere in Casablanca, warm lighting, "
        "minimalist white decor, mindfulness and balance, cinematic quality",
    ),
    2: (
        "Mercredi_Force",
        "Dynamic Pilates reformer workout session with strong graceful Moroccan women, "
        "premium fitness studio, elegant fluid movements, strength and flexibility, "
        "soft studio lighting, cinematic slow motion",
    ),
    3: (
        "Jeudi_Flexibilite",
        "Graceful flexibility training on Pilates reformer equipment, female athletes "
        "stretching and balancing in a high-end studio Casablanca, smooth camera movement, "
        "natural daylight, serene and focused atmosphere",
    ),
    4: (
        "Vendredi_Resultats",
        "Confident beautiful women completing their Pilates reformer session, glowing skin, "
        "toned bodies, luxury gym environment, empowerment and wellness, "
        "golden hour lighting, cinematic feel-good footage",
    ),
    5: (
        "Samedi_Collectif",
        "Group of elegant women enjoying a Pilates reformer class together in Casablanca, "
        "joyful atmosphere, premium studio, community and friendship, "
        "soft natural lighting, high-end production quality",
    ),
    6: (
        "Dimanche_Recuperation",
        "Gentle recovery Pilates session for women, serene Casablanca studio environment, "
        "peaceful slow movement, mindfulness, soft morning sunlight through large windows, "
        "calming and luxurious ambiance",
    ),
}


def generate_daily_video():
    day = datetime.now().weekday()
    theme, prompt = WEEKLY_PROMPTS[day]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"studio_ladies_{timestamp}_{theme}.mp4"

    print(f"\n[Scheduler] Thème du jour : {theme}")
    try:
        filepath = generate_video(prompt, filename=filename)
        if filepath:
            print(f"[Scheduler] Succès → {filepath}")
        else:
            print("[Scheduler] Échec : aucune vidéo retournée par l'API")
    except Exception as e:
        print(f"[Scheduler] Erreur : {e}")


def run_scheduler(mode: str = "daily", time_str: str = "09:00"):
    print(f"[Scheduler] Démarrage — mode={mode}, heure={time_str}")

    if mode == "now":
        generate_daily_video()
        return

    if mode == "weekly":
        schedule.every().monday.at(time_str).do(generate_daily_video)
        print(f"[Scheduler] Planifié chaque lundi à {time_str}")
    else:
        schedule.every().day.at(time_str).do(generate_daily_video)
        print(f"[Scheduler] Planifié chaque jour à {time_str}")

    print("[Scheduler] En attente... (Ctrl+C pour arrêter)")
    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    if "--now" in sys.argv:
        run_scheduler("now")
    else:
        schedule_mode = os.getenv("HIGGSFIELD_SCHEDULE", "daily")
        schedule_time = os.getenv("HIGGSFIELD_SCHEDULE_TIME", "09:00")
        run_scheduler(schedule_mode, schedule_time)
