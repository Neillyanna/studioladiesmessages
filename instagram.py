import os
import requests

INSTAGRAM_API_URL = "https://graph.instagram.com/v21.0/me/messages"


def download_instagram_media(url: str) -> bytes | None:
    """Télécharge un fichier média Instagram depuis l'URL du webhook."""
    token = os.getenv("INSTAGRAM_ACCESS_TOKEN")
    try:
        params = {"access_token": token} if token else {}
        r = requests.get(url, params=params, timeout=30)
        if r.status_code != 200:
            print(f"Erreur téléchargement média Instagram: {r.status_code}")
            return None
        return r.content
    except Exception as e:
        print(f"Erreur téléchargement média Instagram: {e}")
        return None


def get_instagram_username(user_id: str) -> dict | None:
    """
    Récupère le profil public (username / name) d'un utilisateur Instagram
    à partir de son sender_id (IGSID) via l'API Instagram Graph.
    Retourne {"username": ..., "name": ...} ou None si indisponible.
    """
    token = os.getenv("INSTAGRAM_ACCESS_TOKEN")
    if not token:
        return None
    try:
        r = requests.get(
            f"https://graph.instagram.com/v21.0/{user_id}",
            params={"fields": "username,name", "access_token": token},
            timeout=10,
        )
        if r.status_code != 200:
            print(f"Erreur profil Instagram {user_id}: {r.status_code} - {r.text}")
            return None
        data = r.json()
        return {"username": data.get("username"), "name": data.get("name")}
    except Exception as e:
        print(f"Erreur profil Instagram {user_id}: {e}")
        return None


def send_instagram_message(recipient_id: str, text: str) -> bool:
    token = os.getenv("INSTAGRAM_ACCESS_TOKEN")
    if not token:
        print("Erreur: INSTAGRAM_ACCESS_TOKEN manquant")
        return False

    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text},
        "messaging_type": "RESPONSE",
    }

    response = requests.post(
        INSTAGRAM_API_URL,
        params={"access_token": token},
        json=payload,
        timeout=10,
    )

    if response.status_code != 200:
        print(f"Erreur Instagram API: {response.status_code} - {response.text}")
        return False

    return True
