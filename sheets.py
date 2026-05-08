import re
import os
import json
import requests

APPS_SCRIPT_URL = os.getenv(
    "APPS_SCRIPT_URL",
    "https://script.google.com/macros/s/AKfycbw3fdnaWVG8z_W33CUD0K5p3PnyqWOnylYNcrZQlWik13gxbVYtDOS5cqQ2XpsZR8l9/exec"
)

# Conversations déjà sauvegardées pour éviter les doublons
saved_conversations: set = set()


def _extract_phone(text: str) -> str | None:
    match = re.search(r"(?:\+212|0)([ \-]?\d){8,9}", text)
    if match:
        return re.sub(r"[\s\-]", "", match.group()).strip()
    match = re.search(r"\b\d{8,12}\b", text)
    return match.group().strip() if match else None


def _extract_email(text: str) -> str | None:
    match = re.search(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", text)
    return match.group() if match else None


def _extract_time(text: str) -> str | None:
    match = re.search(r"\b\d{1,2}[hH]\d{0,2}\b", text)
    return match.group() if match else None


def _extract_day(text: str) -> str | None:
    days = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
    text_lower = text.lower()
    for day in days:
        if day in text_lower:
            return day.capitalize()
    return None


def _extract_name(text: str) -> tuple[str, str]:
    """Retourne (prenom, nom) depuis un texte style 'Marie Dupont'"""
    clean = re.sub(r"[^\w\s]", "", text).strip()
    parts = clean.split()
    if len(parts) >= 2:
        return parts[0], " ".join(parts[1:])
    return parts[0] if parts else "", ""


def try_save_reservation(user_id: str, history: list[dict]) -> bool:
    """
    Analyse la conversation. Si phone + email trouvés et pas encore sauvegardé,
    enregistre dans Google Sheets. Retourne True si sauvegardé.
    """
    if user_id in saved_conversations:
        return False

    full_text = " ".join(m["content"] for m in history if m["role"] == "user")

    phone = _extract_phone(full_text)
    email = _extract_email(full_text)

    print(f"[Sheets] phone={phone} email={email}")

    if not phone or not email:
        print(f"[Sheets] Infos manquantes — pas de sauvegarde pour {user_id}")
        return False

    # Cherche nom/prénom dans les messages utilisateur
    prenom, nom = "", ""
    for msg in history:
        if msg["role"] == "user":
            p, n = _extract_name(msg["content"])
            if p and not prenom:
                prenom, nom = p, n
                break

    # Cherche jour et heure dans toute la conversation
    all_text = " ".join(m["content"] for m in history)
    heure = _extract_time(all_text) or ""
    jour = _extract_day(all_text) or ""

    payload = {
        "nom": nom,
        "prenom": prenom,
        "numero": phone,
        "email": email,
        "date_reservation": jour,
        "heure_reservation": heure,
    }

    try:
        response = requests.post(APPS_SCRIPT_URL, json=payload, timeout=10)
        if response.status_code == 200:
            saved_conversations.add(user_id)
            print(f"Réservation sauvegardée pour {user_id}: {payload}")
            return True
        else:
            print(f"Erreur Sheets: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Erreur envoi Sheets: {e}")

    return False
