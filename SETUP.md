# Guide de configuration - Bot Instagram Automatique

## Architecture
```
Nouveau DM Instagram → Webhook (Flask) → ChatGPT → Réponse Instagram
```

---

## Étape 1 — Installer Python et les dépendances

```bash
# Créer un environnement virtuel
python -m venv venv

# Activer (Windows)
venv\Scripts\activate

# Installer les dépendances
pip install -r requirements.txt
```

---

## Étape 2 — Créer l'app Meta Developer

1. Va sur https://developers.facebook.com
2. Clique **Mes apps** → **Créer une app**
3. Choisis **Business** comme type
4. Note ton **App ID** et **App Secret** (Paramètres → Paramètres de base)

---

## Étape 3 — Configurer Instagram Messaging

1. Dans ton app Meta, ajoute le produit **Messenger** ou **Instagram Graph API**
2. Connecte ta **Page Facebook** liée à ton compte Instagram Business
3. Génère un **Page Access Token** (token d'accès de page)
4. Donne les permissions : `instagram_basic`, `instagram_manage_messages`, `pages_messaging`

---

## Étape 4 — Configurer les variables d'environnement

```bash
# Copie le fichier exemple
copy .env.example .env

# Ouvre .env et remplis :
VERIFY_TOKEN=          # Invente un mot secret (ex: zenbox_bot_2024)
APP_SECRET=            # App Secret de Meta Developer
INSTAGRAM_ACCESS_TOKEN= # Page Access Token
OPENAI_API_KEY=        # Ta clé sur platform.openai.com
SYSTEM_PROMPT=         # Personnalise la personnalité du bot
```

---

## Étape 5 — Lancer le serveur en local pour tester

```bash
python app.py
```

### Exposer le serveur avec ngrok (pour les tests)

```bash
# Installer ngrok : https://ngrok.com
ngrok http 5000
# → Copie l'URL https générée (ex: https://abc123.ngrok.io)
```

---

## Étape 6 — Configurer le Webhook Meta

1. Dans Meta Developer → ton app → **Webhooks**
2. Clique **Configurer** pour Instagram
3. **URL de rappel** : `https://TON_URL/webhook`
4. **Token de vérification** : même valeur que `VERIFY_TOKEN` dans ton `.env`
5. Clique **Vérifier et enregistrer**
6. Abonne-toi à l'événement **`messages`**

---

## Étape 7 — Déploiement en production

### Option A — Railway (simple, gratuit pour commencer)
1. Va sur https://railway.app
2. Connecte ton repo GitHub
3. Ajoute les variables d'environnement
4. Railway génère une URL publique → utilise-la comme webhook Meta

### Option B — Render.com
1. Va sur https://render.com
2. Crée un **Web Service** depuis ton repo GitHub
3. **Start command** : `gunicorn app:app`
4. Ajoute les variables d'environnement dans le dashboard

---

## Personnaliser le bot

Modifie `SYSTEM_PROMPT` dans ton `.env` pour adapter le bot à ta marque :

```
SYSTEM_PROMPT=Tu es l'assistante de Zenbox, un studio de Pilates à [VILLE].
Réponds en français, de façon chaleureuse et professionnelle.
Les cours coûtent [PRIX]. Pour réserver, dis-leur d'appeler le [TÉLÉPHONE] ou de visiter [SITE WEB].
```

---

## Dépannage

| Problème | Solution |
|----------|----------|
| Webhook non vérifié | Vérifie que `VERIFY_TOKEN` est identique dans `.env` et Meta |
| Pas de réponse | Vérifie les logs du serveur (`python app.py`) |
| Erreur 403 | `APP_SECRET` incorrect ou signature invalide |
| Erreur OpenAI | Vérifie ta clé API et ton solde sur platform.openai.com |
