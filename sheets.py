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
    État de sauvegarde par conversation :
      {user_id: {"ref": user_id, "fields": {...champs déjà envoyés...}, "complete": bool}}
    `fields` mémorise ce qui a déjà été poussé vers le Sheet pour n'envoyer un
    upsert que lorsqu'une info a réellement changé.
    Rétro-compatible avec les anciens formats (liste d'user_id, ou dict
    {"saved": bool, "email_sent": bool}) : les entrées sans "fields" repartent
    d'un instantané vide et seront simplement re-synchronisées au prochain upsert.
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
    # 1. Patterns explicites : "au nom de X", "je m'appelle X", "mon nom est X", "c'est X"
    m = re.search(
        r"\b(?:au\s+nom\s+(?:de\s+|du\s+)?|je\s+m'?\s?appelle\s+|mon\s+nom\s+(?:est|c'?est)\s+)"
        r"([A-Za-zÀ-ÿ\-]+(?:\s+[A-Za-zÀ-ÿ\-]+)*)",
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


def _find_name(history: list[dict]) -> tuple[str, str]:
    """
    Cherche le nom/prénom dans les messages utilisateur, en priorité dans les
    messages qui contiennent un nom explicite, un téléphone ou un email
    (évite de prendre un mot au hasard comme nom).
    """
    for msg in history:
        if msg.get("role") != "user":
            continue
        content = msg.get("content", "")
        has_name_cue = re.search(r"\bau\s+nom\b|je\s+m'?\s?appelle|mon\s+nom", content, re.IGNORECASE)
        if has_name_cue or _extract_phone(content) or _extract_email(content):
            p, n = _extract_name(content)
            if p:
                return p, n
    return "", ""


def _collect_fields(history: list[dict], state: dict | None) -> dict:
    """
    Rassemble TOUTES les infos actuellement connues de la conversation.
    Ne renvoie QUE les champs non vides (on n'envoie jamais de valeur vide au
    Sheet, pour ne rien écraser). Jour/heure viennent de la machine à états en
    priorité. Le nom est nettoyé (jamais de jour/heure/email/chiffre dedans).
    """
    user_text = " ".join(m["content"] for m in history if m.get("role") == "user")

    phone = _extract_phone(user_text) or ""
    email = _extract_email(user_text) or ""
    prenom, nom = _sanitize_name(*_find_name(history))

    jour = (state or {}).get("jour") or _extract_day(user_text) or ""
    heure = (state or {}).get("heure") or _extract_time(user_text) or ""

    # Société : uniquement si une vraie société est détectée
    societe_nom = _detect_company(user_text)
    societe_demande = _detect_company_request(user_text) if societe_nom else ""

    candidate = {
        "prenom": prenom,
        "nom": nom,
        "numero": phone,
        "email": email,
        "date_reservation": jour,
        "heure_reservation": heure,
        "societe_nom": societe_nom,
        "societe_demande": societe_demande,
        "societe_date_reservation": jour if societe_nom else "",
        "societe_numero": phone if societe_nom else "",
    }
    # On ne garde que les champs réellement renseignés
    return {k: v for k, v in candidate.items() if v}


def try_save_reservation(user_id: str, history: list[dict], state: dict | None = None) -> bool:
    """
    Enregistre la réservation dans Google Sheets en mode UPSERT :
    UNE SEULE ligne par conversation, complétée au fil de l'eau.

    - `user_id` (sender_id Instagram / wa_<numéro>) sert d'identifiant stable et
      unique : il est envoyé dans le champ `ref` de chaque payload.
    - À chaque nouvelle info capturée (nom, numéro, email, jour, heure…), on
      envoie un upsert à l'Apps Script, qui retrouve la ligne existante (par
      `ref`, ou à défaut par numéro) et met à jour UNIQUEMENT les colonnes
      concernées, sans jamais écraser une valeur déjà présente par du vide.
    - On n'appelle le Sheet que si une info a réellement changé (évite les
      écritures inutiles à chaque message).

    L'e-mail de confirmation (envoi unique) est géré côté Apps Script dès que la
    ligne est complète (numéro + jour + heure + email).
    """
    saved = _load_saved()
    entry = saved.get(user_id) or {}
    known = dict(entry.get("fields") or {})

    fields = _collect_fields(history, state)
    if not fields:
        return False

    # Fusion : une info ne remplace une valeur connue que par une NOUVELLE valeur non vide
    merged = dict(known)
    changed = False
    for k, v in fields.items():
        if v and v != known.get(k):
            merged[k] = v
            changed = True

    if not changed:
        return False  # rien de nouveau depuis le dernier envoi

    # On envoie l'instantané complet des champs non vides + la référence stable
    payload = {"action": "upsert", "ref": user_id}
    payload.update({k: v for k, v in merged.items() if v})

    ok, err = _post_to_sheet(payload)
    complete = all(merged.get(k) for k in ("numero", "date_reservation", "heure_reservation"))
    print(f"[Sheets] upsert ref={user_id} ok={ok} champs={sorted(fields.keys())} "
          f"complet={complete}" + (f" err={err}" if not ok else ""))

    if ok:
        entry["ref"] = user_id
        entry["fields"] = merged
        entry["complete"] = complete
        saved[user_id] = entry
        _save_saved(saved)
        return True

    return False
