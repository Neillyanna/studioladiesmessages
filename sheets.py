import re
import os
import requests

APPS_SCRIPT_URL = os.getenv(
    "APPS_SCRIPT_URL",
    "https://script.google.com/macros/s/AKfycbwd6MCCBdMFUAeM49_lTzUrFLFV8a_Uc8WwZh5bNCGgdtClTZl0gGUfuwGH8kyNFuxD/exec"
)

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
STOPWORDS = {"je", "voudrais", "veux", "reserver", "réserver", "bonjour", "bonsoir",
             "svp", "stp", "merci", "nom", "prénom", "prenom", "au", "de", "du",
             "la", "le", "les", "un", "une", "pour", "sur", "avec", "dans", "et",
             "ou", "en", "a", "à", "mon", "ma", "mes", "oui", "non", "cest",
             "voici", "voila", "voilà", "mon", "appelle"}

# Conversations déjà sauvegardées pour éviter les doublons
saved_conversations: set = set()


def _extract_phone(text: str) -> str | None:
    """Détecte un numéro de téléphone : marocain, français, international."""
    clean = text.replace(" ", "").replace("-", "").replace(".", "")
    # Format France : +33XXXXXXXXX
    m = re.search(r"(\+33\d{9})", clean)
    if m:
        return m.group(1)
    # Format Maroc : +212XXXXXXXXX → 0XXXXXXXXX
    m = re.search(r"\+212([67]\d{8})", clean)
    if m:
        return "0" + m.group(1)
    # Format Maroc local : 06/07XXXXXXXX
    m = re.search(r"\b(0[67]\d{8})\b", clean)
    if m:
        return m.group(1)
    # Format international générique : +XXXXXXXXXXX
    m = re.search(r"(\+\d{8,14})", clean)
    if m:
        return m.group(1)
    # Fallback : 9-12 chiffres commençant par 0
    m = re.search(r"\b(0\d{8,11})\b", clean)
    if m:
        return m.group(1)
    return None


def _extract_email(text: str) -> str | None:
    m = re.search(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", text)
    return m.group() if m else None


def _extract_time(text: str) -> str | None:
    m = re.search(r"\b(\d{1,2})[hH](\d{0,2})\b", text)
    if m:
        h, mn = m.group(1), m.group(2)
        return f"{h}h{mn}" if mn else f"{h}h"
    return None


def _extract_day(text: str) -> str | None:
    t = text.lower()
    for jour in JOURS:
        if jour in t:
            return jour
    return None


def _extract_name(text: str) -> tuple[str, str]:
    """
    Extrait (prenom, nom) d'un message utilisateur.
    Stratégie :
    1. Cherche 'au nom (de) Prenom Nom'
    2. Sinon, enlève email/téléphone/stopwords et prend les mots restants
    """
    # 1. Pattern "au nom de/du Prenom Nom"
    m = re.search(
        r"\bau\s+nom\s+(?:de\s+|du\s+)?([A-Za-zÀ-ÿ\-]+(?:\s+[A-Za-zÀ-ÿ\-]+)+)",
        text, re.IGNORECASE
    )
    if m:
        parts = m.group(1).strip().split()
        return parts[0].capitalize(), " ".join(p.capitalize() for p in parts[1:])

    # 2. Nettoyer le texte : enlever email, téléphone, chiffres
    clean = re.sub(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", "", text)
    clean = re.sub(r"(?:\+212\s*|0)[67][\d\s\-]{8,}", "", clean)
    clean = re.sub(r"\b\d+\b", "", clean)
    clean = re.sub(r"[^\w\sÀ-ÿ]", " ", clean)
    clean = re.sub(r"\s+", " ", clean).strip()

    # Filtrer les stopwords
    words = [
        w for w in clean.split()
        if len(w) >= 2 and w.lower() not in STOPWORDS and w.isalpha()
    ]

    if len(words) >= 2:
        return words[0].capitalize(), " ".join(w.capitalize() for w in words[1:])
    elif len(words) == 1:
        return words[0].capitalize(), ""
    return "", ""


def _detect_company(text: str) -> str:
    """Détecte le nom d'une société dans un message."""
    keywords = ["société", "entreprise", "marque", "brand", "studio", "concept", "groupe",
                "agence", "au nom de", "je contacte au nom", "je vous contacte au nom"]
    t = text.lower()
    for kw in keywords:
        if kw in t:
            # Essaie d'extraire le nom après le mot clé
            m = re.search(rf"{kw}\s+([A-Za-zÀ-ÿ0-9\s\-]+?)(?:[,\.\n]|$)", t, re.IGNORECASE)
            if m:
                return m.group(1).strip().upper()
    # Cherche si un mot entièrement en majuscules existe (ex: AURALED)
    m = re.search(r"\b([A-Z]{3,})\b", text)
    if m:
        return m.group(1)
    return ""


def _detect_company_request(text: str) -> str:
    """Détecte le type de demande d'une société."""
    keywords_map = [
        (["partenariat", "partnership", "collaborer", "collaboration"], "Partenariat"),
        (["présentation", "presentation", "présenter"], "Demande de présentation"),
        (["call", "appel", "rdv", "rendez-vous", "réunion"], "Appel/Réunion"),
        (["intégrer", "integrer", "intégration"], "Intégration produit/service"),
        (["tapis", "machine", "équipement", "therapy", "thérapie"], "Équipement/Thérapie"),
        (["sponsoring", "sponsor"], "Sponsoring"),
    ]
    t = text.lower()
    for keywords, label in keywords_map:
        if any(kw in t for kw in keywords):
            return label
    return "Contact professionnel"


def try_save_reservation(user_id: str, history: list[dict], state: dict | None = None) -> bool:
    """
    Analyse la conversation. Si phone + email trouvés et pas encore sauvegardé,
    enregistre dans Google Sheets. Retourne True si sauvegardé.
    """
    if user_id in saved_conversations:
        return False

    # Recherche phone et email uniquement dans les messages utilisateur
    user_text = " ".join(m["content"] for m in history if m["role"] == "user")

    phone = _extract_phone(user_text)
    email = _extract_email(user_text)

    print(f"[Sheets] phone={phone} email={email}")

    if not phone or not email:
        print(f"[Sheets] Infos manquantes — pas de sauvegarde pour {user_id}")
        return False

    # Extraction du nom depuis le message qui contient phone ou email
    prenom, nom = "", ""
    for msg in history:
        if msg["role"] != "user":
            continue
        content = msg["content"]
        if _extract_phone(content) or _extract_email(content):
            p, n = _extract_name(content)
            if p:
                prenom, nom = p, n
                break

    # Jour/heure depuis la machine à états en priorité
    jour = (state or {}).get("jour") or ""
    heure = (state or {}).get("heure") or ""

    # Fallback depuis les messages utilisateur seulement
    if not jour:
        jour = _extract_day(user_text) or ""
    if not heure:
        heure = _extract_time(user_text) or ""

    # Détection contact B2B / société
    societe_nom = _detect_company(user_text)
    societe_demande = _detect_company_request(user_text)

    payload = {
        "nom": nom,
        "prenom": prenom,
        "numero": phone,
        "email": email,
        "date_reservation": jour,
        "heure_reservation": heure,
        "societe_nom": societe_nom,
        "societe_demande": societe_demande,
        "societe_adresse": "",
        "societe_date_reservation": jour if societe_nom else "",
        "societe_numero": phone if societe_nom else "",
    }

    print(f"[Sheets] Payload: {payload}")

    try:
        response = requests.post(APPS_SCRIPT_URL, json=payload, timeout=10)
        if response.status_code == 200:
            saved_conversations.add(user_id)
            print(f"[Sheets] ✅ Sauvegardé pour {user_id}: {payload}")
            return True
        else:
            print(f"[Sheets] Erreur {response.status_code}: {response.text}")
    except Exception as e:
        print(f"[Sheets] Erreur envoi: {e}")

    return False
