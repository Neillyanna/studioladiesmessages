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
             "matin", "soir", "apres", "midi", "après",
             "seance", "séance", "reformer", "posture", "classic", "power", "pilates",
             "cours", "belly", "dance", "academy", "decouverte", "découverte",
             "votre", "retour", "suis", "freelance", "monteur", "videaste", "vidéaste",
             "bonjour", "bonsoir", "merci", "bcp", "beaucoup", "svp", "stp",
             "inscription", "abonnement", "pack", "tarif", "prix", "info", "infos"}

DATA_DIR = os.getenv("DATA_DIR", "/app/data")
SAVED_FILE = os.path.join(DATA_DIR, "saved.json")


def _load_saved() -> dict:
    """
    État de sauvegarde par utilisateur : {user_id: {"saved": bool, "email_sent": bool}}.
    Rétro-compatible avec l'ancien format (simple liste d'user_id).
    """
    if os.path.exists(SAVED_FILE):
        try:
            with open(SAVED_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, list):  # ancien format
                return {uid: {"saved": True, "email_sent": False} for uid in raw}
            if isinstance(raw, dict):
                return raw
        except Exception:
            pass
    return {}


def _save_saved(data: dict):
    try:
        with open(SAVED_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception as e:
        print(f"[Sheets] Erreur sauvegarde saved: {e}")


def _clean_name_part(value: str) -> str:
    """Rejette tout ce qui n'est pas un vrai nom/prénom (jour, heure, email, chiffres)."""
    if not value:
        return ""
    v = value.strip()
    low = v.lower()
    if low in JOURS:
        return ""
    if "@" in v:
        return ""
    if re.search(r"\d", v):  # contient un chiffre (heure, numéro…) → pas un nom
        return ""
    return v


def _sanitize_name(prenom: str, nom: str) -> tuple[str, str]:
    """Garantit qu'aucun jour/heure/email/chiffre ne finit dans nom/prénom."""
    prenom = _clean_name_part(prenom)
    nom = " ".join(part for part in (_clean_name_part(w) for w in (nom or "").split()) if part)
    return prenom, nom


def _post_to_sheet(payload: dict) -> tuple[bool, str]:
    """POST vers l'Apps Script. Retourne (ok, message_erreur)."""
    try:
        response = requests.post(APPS_SCRIPT_URL, json=payload, timeout=10)
        if response.status_code == 200:
            return True, ""
        return False, f"HTTP {response.status_code}: {response.text}"
    except Exception as e:
        return False, str(e)


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
    Analyse la conversation et enregistre la réservation dans Google Sheets.

    Deux cas gérés (corrige le bug du mail qui ne partait pas) :
      1. Première sauvegarde dès que téléphone + jour + heure sont présents
         (email envoyé s'il est déjà disponible).
      2. Si la réservation était déjà sauvegardée SANS email et que l'email arrive
         plus tard (ex: donné après la confirmation), on renvoie une mise à jour
         à l'Apps Script pour déclencher l'e-mail de confirmation.

    Logs émis : reservationSaved / emailProvided / emailSent / emailError.
    """
    saved = _load_saved()
    entry = saved.get(user_id, {"saved": False, "email_sent": False})

    # Recherche phone et email uniquement dans les messages utilisateur
    user_text = " ".join(m["content"] for m in history if m["role"] == "user")
    phone = _extract_phone(user_text)
    email = _extract_email(user_text) or ""

    # --- Cas 2 : déjà sauvegardé mais e-mail pas encore envoyé, et un email apparaît ---
    if entry.get("saved") and not entry.get("email_sent"):
        if email:
            update_payload = {
                "email_update": True,
                "numero": phone or "",
                "email": email,
            }
            ok, err = _post_to_sheet(update_payload)
            print(f"[Sheets] reservationSaved=True emailProvided=True "
                  f"emailSent={ok}" + (f" emailError={err}" if not ok else ""))
            if ok:
                entry["email_sent"] = True
                saved[user_id] = entry
                _save_saved(saved)
            return False  # la ligne existait déjà, on ne recrée rien
        return False

    if entry.get("saved"):
        return False  # déjà tout fait

    # --- Cas 1 : première sauvegarde ---
    if not phone:
        print(f"[Sheets] reservationSaved=False (téléphone manquant) pour {user_id}")
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
    # Garde-fou colonnes : jamais un jour/heure/email/chiffre dans nom/prénom
    prenom, nom = _sanitize_name(prenom, nom)

    # Jour/heure depuis la machine à états en priorité
    jour = (state or {}).get("jour") or ""
    heure = (state or {}).get("heure") or ""
    if not jour:
        jour = _extract_day(user_text) or ""
    if not heure:
        heure = _extract_time(user_text) or ""

    if not jour or not heure:
        print(f"[Sheets] reservationSaved=False (jour={jour!r} ou heure={heure!r} manquant) pour {user_id}")
        return False

    # Détection contact B2B / société — on ne remplit les colonnes société
    # QUE si une vraie société est détectée (évite de polluer le tableau).
    societe_nom = _detect_company(user_text)
    societe_demande = _detect_company_request(user_text) if societe_nom else ""

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

    ok, err = _post_to_sheet(payload)
    email_provided = bool(email)
    # L'Apps Script envoie l'e-mail de confirmation si un email est présent dans le payload.
    email_sent = ok and email_provided
    print(f"[Sheets] reservationSaved={ok} emailProvided={email_provided} "
          f"emailSent={email_sent}" + (f" emailError={err}" if not ok else ""))

    if ok:
        saved[user_id] = {"saved": True, "email_sent": email_sent}
        _save_saved(saved)
        return True

    return False
