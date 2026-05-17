import re
import os
import json
import requests

APPS_SCRIPT_URL = os.getenv(
    "APPS_SCRIPT_URL",
    "https://script.google.com/macros/s/AKfycbwcBkEPvvSaPDAN-LwI36zX_bwwthoIETx_bQTwaolPQkToCSNGEf1-6xEAKSMFbtAt/exec"
)

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
STOPWORDS = {"je", "voudrais", "veux", "reserver", "réserver", "bonjour", "bonsoir",
             "svp", "stp", "merci", "nom", "prénom", "prenom", "au", "de", "du",
             "la", "le", "les", "un", "une", "pour", "sur", "avec", "dans", "et",
             "ou", "en", "a", "à", "mon", "ma", "mes", "oui", "non", "cest",
             "voici", "voila", "voilà", "appelle", "parfait", "appel", "uniquement",
             "whatsapp", "email", "mail", "telephone", "numero", "coordonnees",
             "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche",
             "matin", "soir", "apres", "midi", "après"}

DATA_DIR = os.getenv("DATA_DIR", "/app/data")
SAVED_FILE = os.path.join(DATA_DIR, "saved.json")


def _load_saved() -> set:
    if os.path.exists(SAVED_FILE):
        try:
            with open(SAVED_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            pass
    return set()


def _save_saved(data: set):
    try:
        with open(SAVED_FILE, "w", encoding="utf-8") as f:
            json.dump(list(data), f)
    except Exception as e:
        print(f"[Sheets] Erreur sauvegarde saved: {e}")


def _extract_phone(text: str) -> str | None:
    """Détecte un numéro de téléphone : marocain, français, international."""
    # +33 France : +33 X XX XX XX XX
    m = re.search(r"\+33[\s\-]?(\d[\s\-]?){9}", text)
    if m:
        return re.sub(r"[\s\-]", "", m.group(0))
    # +212 Maroc : +212 XXXXXXXXX → 0XXXXXXXXX
    m = re.search(r"\+212[\s\-]?(\d[\s\-]?){9}", text)
    if m:
        digits = re.sub(r"[\s\-]", "", m.group(0))
        return "0" + digits[4:]
    # Local Maroc 06/07 : 0X XX XX XX XX
    m = re.search(r"(?<!\d)(0[5-9][\s\-]?\d{2}[\s\-]?\d{2}[\s\-]?\d{2}[\s\-]?\d{2})(?!\d)", text)
    if m:
        return re.sub(r"[\s\-]", "", m.group(1))
    # International générique +XX...
    m = re.search(r"\+\d{1,3}[\s\-]?\d{4,14}", text)
    if m:
        return re.sub(r"[\s\-]", "", m.group(0))
    # Fallback : 9-12 chiffres consécutifs
    m = re.search(r"(?<!\d)(\d{9,12})(?!\d)", text)
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
            m = re.search(rf"{kw}\s+([A-Za-zÀ-ÿ0-9\s\-]+?)(?:[,\.\n]|$)", t, re.IGNORECASE)
            if m:
                return m.group(1).strip().upper()
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
    saved_conversations = _load_saved()
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
            _save_saved(saved_conversations)
            print(f"[Sheets] ✅ Sauvegardé pour {user_id}: {payload}")
            return True
        else:
            print(f"[Sheets] Erreur {response.status_code}: {response.text}")
    except Exception as e:
        print(f"[Sheets] Erreur envoi: {e}")

    return False
