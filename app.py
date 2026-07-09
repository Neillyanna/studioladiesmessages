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


def _handle_video_command(sender_number: str, text: str):
    import threading
    from datetime import datetime

    # Prompt personnalisé optionnel : "!video femmes pilates coucher de soleil"
    parts = text.split(maxsplit=1)
    custom_prompt = parts[1] if len(parts) > 1 else None

    send_whatsapp_message(sender_number, "Génération vidéo en cours... Je vous envoie une confirmation dans quelques minutes.")

    def _generate():
        try:
            from higgsfield import generate_video
            from scheduler import WEEKLY_PROMPTS
            if custom_prompt:
                prompt = custom_prompt
            else:
                day = datetime.now().weekday()
                _, prompt = WEEKLY_PROMPTS[day]
            filepath = generate_video(prompt)
            if filepath:
                filename = os.path.basename(filepath)
                send_whatsapp_message(sender_number, f"✅ Vidéo générée : {filename}\nDossier : {filepath}")
            else:
                send_whatsapp_message(sender_number, "❌ Erreur : aucune vidéo générée par Higgsfield.")
        except Exception as e:
            send_whatsapp_message(sender_number, f"❌ Erreur génération : {e}")

    threading.Thread(target=_generate, daemon=True).start()


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

                if text.strip().lower().startswith("!video"):
                    _handle_video_command(sender_number, text.strip())
                    continue

                response_text = get_ai_response(user_id, text)
                send_whatsapp_message(sender_number, response_text)
                print(f"WhatsApp réponse envoyée: {response_text}")

    return "OK", 200


@app.route("/generate-video", methods=["POST"])
def trigger_generate_video():
    token = request.headers.get("Authorization", "")
    if token != f"Bearer {os.getenv('VERIFY_TOKEN')}":
        return jsonify({"error": "Non autorisé"}), 403

    data = request.get_json(silent=True) or {}
    prompt = data.get("prompt")

    try:
        from higgsfield import generate_video
        from datetime import datetime

        if not prompt:
            day = datetime.now().weekday()
            from scheduler import WEEKLY_PROMPTS
            theme, prompt = WEEKLY_PROMPTS[day]

        filepath = generate_video(prompt)
        if filepath:
            return jsonify({"status": "ok", "file": filepath})
        return jsonify({"status": "error", "message": "Aucune vidéo générée"}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


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


@app.route("/admin/kaada", methods=["GET"])
def admin_kaada():
    """
    Endpoint temporaire d'EXTRACTION (à supprimer après usage).
    Parcourt histories.json, filtre les conversations mentionnant la danse
    Kaada / 9a3da / Chaabi, récupère le @handle Instagram via l'API Graph,
    et renvoie pour chaque conversation : sender_id, handle, et les extraits
    de messages concernés. N'ENVOIE AUCUN MESSAGE — lecture seule.
    """
    token = request.args.get("token")
    if token != os.getenv("VERIFY_TOKEN"):
        return "Accès refusé", 403

    import json
    from instagram import get_instagram_username

    data_dir = os.getenv("DATA_DIR", "/app/data")
    histories_file = os.path.join(data_dir, "histories.json")

    # Mots-clés recherchés (insensible à la casse)
    keywords = ["kaada", "9a3da", "qa3da", "chaabi", "sha3bi", "cha3bi"]

    try:
        with open(histories_file, "r", encoding="utf-8") as f:
            histories = json.load(f)
    except Exception as e:
        return jsonify({"error": f"Lecture histories.json: {e}"}), 500

    results = []
    for user_id, messages in histories.items():
        # Extraits (messages contenant un mot-clé), côté cliente en priorité
        matched = []
        for m in messages:
            content = (m.get("content") or "")
            low = content.lower()
            if any(kw in low for kw in keywords):
                matched.append({"role": m.get("role"), "content": content})
        if not matched:
            continue

        # Récupération du profil Instagram (uniquement pour les sender_id Instagram,
        # pas les identifiants WhatsApp préfixés "wa_")
        handle, name = None, None
        if not str(user_id).startswith("wa_"):
            profile = get_instagram_username(user_id)
            if profile:
                handle = profile.get("username")
                name = profile.get("name")

        results.append({
            "sender_id": user_id,
            "handle": handle,
            "name": name,
            "nb_messages_total": len(messages),
            "extraits": matched,
        })

    return jsonify({"kaada_mentions": results, "total": len(results)})


@app.route("/admin/rdv", methods=["GET"])
def admin_rdv():
    """
    Endpoint temporaire d'EXTRACTION (à supprimer après usage). LECTURE SEULE.
    Parcourt TOUTES les conversations (histories.json) et en extrait les infos
    de rendez-vous : téléphone, email, jour, heure, nom/prénom (mêmes
    extracteurs que sheets.py) + jour/heure de la machine à états + le @handle
    Instagram via l'API Graph. N'envoie aucun message, n'écrit rien.

    Renvoie 2 listes :
      - rdv : conversations avec au moins jour+heure ou un téléphone (RDV probable)
      - incomplets : conversations avec un intérêt mais infos partielles
    """
    token = request.args.get("token")
    if token != os.getenv("VERIFY_TOKEN"):
        return "Accès refusé", 403

    import json
    from instagram import get_instagram_username
    from sheets import _collect_fields
    from conversation import get_state

    data_dir = os.getenv("DATA_DIR", "/app/data")
    histories_file = os.path.join(data_dir, "histories.json")

    try:
        with open(histories_file, "r", encoding="utf-8") as f:
            histories = json.load(f)
    except Exception as e:
        return jsonify({"error": f"Lecture histories.json: {e}"}), 500

    rdv, incomplets = [], []
    for user_id, messages in histories.items():
        try:
            state = get_state(user_id)
        except Exception:
            state = {}
        fields = _collect_fields(messages, state)
        if not fields:
            continue

        handle, ig_name = None, None
        if not str(user_id).startswith("wa_"):
            profile = get_instagram_username(user_id)
            if profile:
                handle = profile.get("username")
                ig_name = profile.get("name")

        derniers = [m.get("content", "")[:120] for m in messages[-2:]]
        entry = {
            "sender_id": user_id,
            "handle": handle,
            "profil_instagram": ig_name,
            **fields,
            "nb_messages": len(messages),
            "derniers_messages": derniers,
        }
        complet = fields.get("numero") or (
            fields.get("date_reservation") and fields.get("heure_reservation")
        )
        (rdv if complet else incomplets).append(entry)

    return jsonify({
        "rdv": rdv,
        "incomplets": incomplets,
        "total_rdv": len(rdv),
        "total_incomplets": len(incomplets),
    })


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
