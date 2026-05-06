import os
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Historique des conversations par utilisateur (en mémoire)
conversation_history: dict[str, list[dict]] = {}

SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT", """
Tu es un assistant Instagram professionnel et chaleureux.
Réponds de façon concise, amicale et utile.
Si quelqu'un pose une question sur les services ou produits, donne une réponse claire.
Reste toujours poli et professionnel.
""").strip()

MAX_HISTORY = 10  # Nombre de messages à garder en mémoire par utilisateur


def get_ai_response(user_id: str, user_message: str) -> str:
    if user_id not in conversation_history:
        conversation_history[user_id] = []

    history = conversation_history[user_id]
    history.append({"role": "user", "content": user_message})

    # Limite l'historique pour éviter de dépasser les tokens
    if len(history) > MAX_HISTORY:
        history = history[-MAX_HISTORY:]
        conversation_history[user_id] = history

    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history

    try:
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=messages,
            max_tokens=300,
            temperature=0.7,
        )
        reply = response.choices[0].message.content.strip()
        history.append({"role": "assistant", "content": reply})
        return reply

    except Exception as e:
        print(f"Erreur OpenAI: {e}")
        return "Désolé, je rencontre un problème technique. Réessayez dans quelques instants !"
