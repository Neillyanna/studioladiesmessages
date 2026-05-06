import os
import requests

INSTAGRAM_API_URL = "https://graph.instagram.com/v21.0/me/messages"


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
