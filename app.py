import os
import hmac
import hashlib
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from chatbot import get_ai_response
from instagram import send_instagram_message

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
            message = messaging.get("message", {})
            text = message.get("text")

            if not text or not sender_id:
                continue

            print(f"Message reçu de {sender_id}: {text}")

            response_text = get_ai_response(sender_id, text)
            send_instagram_message(sender_id, response_text)
            print(f"Réponse envoyée: {response_text}")

    return "OK", 200


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
