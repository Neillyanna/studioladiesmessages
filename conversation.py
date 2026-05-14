"""
Machine à états pour contrôler le flux de conversation.
Chaque utilisateur passe par des étapes fixes dans l'ordre.
"""
import json
import os
import re
from datetime import datetime, timedelta

DAYS_FR = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]

import os as _os
DATA_DIR = _os.getenv("DATA_DIR", "/app/data")
_os.makedirs(DATA_DIR, exist_ok=True)
STATE_FILE = _os.path.join(DATA_DIR, "conversations.json")

STATES = {
    "ACCUEIL": 0,
    "EXPERIENCE": 1,
    "JOUR": 2,
    "HEURE": 3,
    "CONTACT": 4,
    "CONFIRME": 5,
}

PLANNING = {
    "lundi":    [("10h30", "Belly Dance Academy", "IMANE"), ("13h00", "Classic Reformer", "ASMAA"), ("18h30", "Classic Reformer", "AYA")],
    "mardi":    [("15h00", "Classic Reformer", "RIM"), ("17h30", "Belly Dance Academy", "KAMILIA"), ("18h30", "Power Reformer", "JIHANE")],
    "mercredi": [("9h30", "Classic Reformer", "RIM"), ("13h00", "Posture Reformer", "ASMAA"), ("19h30", "Power Reformer", "AYA")],
    "jeudi":    [("8h30", "Power Reformer", "AYA"), ("10h30", "Belly Dance Academy", "IMANE"), ("15h00", "Power Reformer", "RIM"), ("18h30", "Posture Reformer", "ASMAA")],
    "vendredi": [("9h30", "Posture Reformer", "JIHANE"), ("17h30", "Power Reformer", "ASMAA"), ("18h30", "Belly Dance Academy", "KAMILIA"), ("19h30", "Classic Reformer", "AYA")],
    "samedi":   [("9h45", "Posture Reformer", "AYA"), ("12h00", "Danse Chaabi Kaada", "TOURIYA")],
}


def _load() -> dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save(data: dict):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Erreur sauvegarde: {e}")


def get_state(user_id: str) -> dict:
    data = _load()
    if user_id not in data:
        data[user_id] = {
            "state": "ACCUEIL",
            "jour": None,
            "heure": None,
            "cours": None,
            "coach": None,
            "nom": None,
            "prenom": None,
            "numero": None,
            "email": None,
        }
        _save(data)
    return data[user_id]


def update_state(user_id: str, updates: dict):
    data = _load()
    if user_id not in data:
        data[user_id] = get_state(user_id)
    data[user_id].update(updates)
    _save(data)


def reset_state(user_id: str):
    data = _load()
    if user_id in data:
        del data[user_id]
        _save(data)


def _detect_jour(text: str) -> str | None:
    text_lower = text.lower()
    today = datetime.now()
    if "après-demain" in text_lower or "apres-demain" in text_lower:
        return DAYS_FR[(today + timedelta(days=2)).weekday()]
    if "demain" in text_lower:
        return DAYS_FR[(today + timedelta(days=1)).weekday()]
    for jour in PLANNING:
        if jour in text_lower:
            return jour
    return None


def _detect_heure(text: str) -> str | None:
    match = re.search(r"\b(\d{1,2})[hH](\d{0,2})\b", text)
    if match:
        h = match.group(1)
        m = match.group(2)
        return f"{h}h{m}" if m else f"{h}h"
    return None


def _normalise(h: str) -> str:
    return h.lower().replace("h00", "h").replace("h0", "h").strip()


def valider_creneau(jour: str, heure: str) -> tuple[bool, str | None, str | None]:
    """Retourne (valide, cours, coach)"""
    if jour not in PLANNING:
        return False, None, None
    h_norm = _normalise(heure)
    for (h, cours, coach) in PLANNING[jour]:
        if _normalise(h) == h_norm:
            return True, cours, coach
    return False, None, None


def creneaux_du_jour(jour: str) -> str:
    if jour not in PLANNING or not PLANNING[jour]:
        return "Nous ne sommes pas disponibles ce jour-là."
    lignes = [f"• {h} — {cours} avec {coach}" for (h, cours, coach) in PLANNING[jour]]
    return "\n".join(lignes)


def get_context_injection(user_id: str, user_message: str) -> str | None:
    """
    Retourne une instruction de correction à injecter dans le prompt si nécessaire.
    Retourne None si tout est normal.
    """
    state = get_state(user_id)
    current = state["state"]

    # Valider le créneau à tout moment de la conversation
    if current not in ("CONFIRME",):
        jour = _detect_jour(user_message) or state.get("jour")
        heure = _detect_heure(user_message)

        if jour and heure:
            valide, cours, coach = valider_creneau(jour, heure)
            if not valide:
                creneaux = creneaux_du_jour(jour)
                return (
                    f"⛔ INSTRUCTION OBLIGATOIRE : La cliente demande {heure} le {jour} "
                    f"mais ce créneau N'EXISTE PAS. "
                    f"Tu dois REFUSER et proposer uniquement les créneaux disponibles :\n{creneaux}\n"
                    f"Ne confirme JAMAIS ce créneau. Ne demande PAS les coordonnées."
                )
            else:
                # Créneau valide → mettre à jour l'état
                update_state(user_id, {
                    "state": "CONTACT",
                    "jour": jour,
                    "heure": heure,
                    "cours": cours,
                    "coach": coach,
                })
                return (
                    f"✅ Le créneau {heure} le {jour} est valide ({cours} avec {coach}). "
                    f"Tu peux maintenant demander les coordonnées : nom complet, numéro de téléphone et adresse mail."
                )

        elif jour and not heure:
            update_state(user_id, {"state": "HEURE", "jour": jour})
            creneaux = creneaux_du_jour(jour)
            return (
                f"La cliente veut venir le {jour}. "
                f"Les créneaux disponibles ce jour sont :\n{creneaux}\n"
                f"Propose-lui ces créneaux et demande lequel lui convient."
            )

    return None
