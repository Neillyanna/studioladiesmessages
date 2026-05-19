import os
import hmac
import hashlib
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from chatbot import get_ai_response
from instagram import download_instagram_media, send_instagram_message
from whatsapp import download_whatsapp_media, send_whatsapp_message, transcribe_audio

load_dotenv()

app = Flask(__name__)

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
APP_SECRET = os.getenv("APP_SECRET")


def verify_signature(payload: bytes, signature: str) -> bool:
    if not APP_SECRET:
        return True
    try:
        expected = "sha256=" + hmac.new(
            APP_SECRET.encode(), payload, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)
    except Exception as e:
        print(f"Erreur vérification signature: {e}")
        return False


@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("Webhook vérifié !")
        return challenge, 200
    return "Token invalide", 403


@app.route("/webhook", methods=["POST"])
def handle_webhook():
    signature = request.headers.get("X-Hub-Signature-256", "")
    if APP_SECRET and signature and not verify_signature(request.data, signature):
        print(f"Signature reçue: {signature[:30]}...")
        print("Signature invalide - on continue quand même pour le debug")
        # return "Signature invalide", 403  # Désactivé temporairement

    data = request.get_json()

    if data.get("object") != "instagram":
        return "OK", 200

    for entry in data.get("entry", []):
        for messaging in entry.get("messaging", []):
            sender_id = messaging.get("sender", {}).get("id")
            if not sender_id:
                continue

            message = messaging.get("message", {})
            text = message.get("text")

            if not text:
                attachments = message.get("attachments", [])
                if attachments:
                    print(f"[DEBUG] Attachments reçus: {attachments}")
                audio = next((a for a in attachments if a.get("type") in ("audio", "voice_message")), None)
                if audio:
                    media_url = audio.get("payload", {}).get("url")
                    audio_bytes = download_instagram_media(media_url) if media_url else None
                    if not audio_bytes:
                        send_instagram_message(sender_id, "Je n'ai pas pu accéder à votre message vocal.")
                        continue
                    text = transcribe_audio(audio_bytes)
                    if not text:
                        send_instagram_message(sender_id, "Désolé, je n'ai pas compris votre message vocal. Pouvez-vous écrire votre demande ?")
                        continue
                    print(f"Transcription audio Instagram de {sender_id}: {text}")
                else:
                    continue

            print(f"Message reçu de {sender_id}: {text}")

            response_text = get_ai_response(sender_id, text)
            send_instagram_message(sender_id, response_text)
            print(f"Réponse envoyée: {response_text}")

    return "OK", 200


@app.route("/whatsapp", methods=["GET"])
def verify_whatsapp():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("Webhook WhatsApp vérifié !")
        return challenge, 200
    return "Token invalide", 403


@app.route("/whatsapp", methods=["POST"])
def handle_whatsapp():
    data = request.get_json()

    if data.get("object") != "whatsapp_business_account":
        return "OK", 200

    for entry in data.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            messages = value.get("messages", [])

            for message in messages:
                msg_type = message.get("type")
                sender_number = message.get("from")

                if not sender_number:
                    continue

                if msg_type == "text":
                    text = message.get("text", {}).get("body")
                    if not text:
                        continue
                elif msg_type == "audio":
                    audio_id = message.get("audio", {}).get("id")
                    audio_bytes = download_whatsapp_media(audio_id)
                    if not audio_bytes:
                        send_whatsapp_message(sender_number, "Je n'ai pas pu accéder à votre message vocal.")
                        continue
                    text = transcribe_audio(audio_bytes)
                    if not text:
                        send_whatsapp_message(sender_number, "Désolé, je n'ai pas compris votre message vocal. Pouvez-vous écrire votre demande ?")
                        continue
                    print(f"Transcription audio WhatsApp de {sender_number}: {text}")
                else:
                    continue

                # Préfixe "wa_" pour distinguer des users Instagram
                user_id = f"wa_{sender_number}"
                print(f"WhatsApp reçu de {sender_number}: {text}")

                response_text = get_ai_response(user_id, text)
                send_whatsapp_message(sender_number, response_text)
                print(f"WhatsApp réponse envoyée: {response_text}")

    return "OK", 200


@app.route("/admin/histories", methods=["GET"])
def admin_histories():
    """Endpoint temporaire - à supprimer après usage"""
    token = request.args.get("token")
    if token != os.getenv("VERIFY_TOKEN"):
        return "Accès refusé", 403
    import json
    data_dir = os.getenv("DATA_DIR", "/app/data")
    histories_file = os.path.join(data_dir, "histories.json")
    saved_file = os.path.join(data_dir, "saved.json")
    try:
        with open(histories_file, "r", encoding="utf-8") as f:
            histories = json.load(f)
        saved = []
        if os.path.exists(saved_file):
            with open(saved_file, "r") as f:
                saved = json.load(f)
        # Extraire users avec phone mais pas encore sauvegardés
        import re
        results = []
        for user_id, messages in histories.items():
            if user_id in saved:
                continue
            user_text = " ".join(m["content"] for m in messages if m["role"] == "user")
            phone_match = re.search(r"(?<!\d)(0[5-9][\d]{8})(?!\d)", re.sub(r"[\s\-]", "", user_text))
            if not phone_match:
                phone_match = re.search(r"\+212[\d]{9}", re.sub(r"[\s\-]", "", user_text))
            if phone_match:
                last_msg = messages[-1]["content"] if messages else ""
                results.append({
                    "user_id": user_id,
                    "phone": phone_match.group(),
                    "nb_messages": len(messages),
                    "dernier_message": last_msg[:100]
                })
        return jsonify({"non_sauvegardees": results, "total": len(results)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
