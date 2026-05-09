import io
import os
import requests

WHATSAPP_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")


def send_whatsapp_message(recipient_number: str, text: str):
    """Envoie un message WhatsApp via l'API Graph Meta."""
    if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_NUMBER_ID:
        print("WhatsApp non configuré (token ou phone_id manquant)")
        return

    url = f"https://graph.facebook.com/v21.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": recipient_number,
        "type": "text",
        "text": {"body": text},
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        if response.status_code != 200:
            print(f"Erreur WhatsApp API: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Erreur envoi WhatsApp: {e}")


def download_whatsapp_media(media_id: str) -> bytes | None:
    """Télécharge un fichier média depuis l'API Meta WhatsApp."""
    if not WHATSAPP_TOKEN:
        return None
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    try:
        r = requests.get(
            f"https://graph.facebook.com/v21.0/{media_id}",
            headers=headers,
            timeout=10,
        )
        media_url = r.json().get("url")
        if not media_url:
            print(f"Impossible de récupérer l'URL du média {media_id}")
            return None
        r2 = requests.get(media_url, headers=headers, timeout=30)
        return r2.content
    except Exception as e:
        print(f"Erreur téléchargement média WhatsApp: {e}")
        return None


def transcribe_audio(audio_bytes: bytes) -> str | None:
    """Transcrit des bytes audio en texte via OpenAI Whisper."""
    try:
        from openai import OpenAI
        client = OpenAI()
        buf = io.BytesIO(audio_bytes)
        buf.name = "audio.ogg"
        result = client.audio.transcriptions.create(
            model="whisper-1",
            file=buf,
            language="fr",
        )
        return result.text
    except Exception as e:
        print(f"Erreur transcription Whisper: {e}")
        return None
