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
