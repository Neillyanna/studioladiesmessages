import re

# Planning exact du studio
PLANNING = {
    "lundi":    ["10h30", "13h00", "18h30"],
    "mardi":    ["9h30", "17h30", "18h30"],
    "mercredi": ["9h30", "13h00", "17h30", "19h30"],
    "jeudi":    ["9h30", "10h30", "15h00", "18h30"],
    "vendredi": ["8h30", "18h30"],
    "samedi":   ["9h45", "12h00"],
    "dimanche": [],
}

CORRECTIONS = {
    "samedi":   "Le samedi, les créneaux disponibles sont 9h45 et 12h00 uniquement.",
    "dimanche": "Le studio est fermé le dimanche.",
}

def _normalise_heure(h: str) -> str:
    return h.lower().replace("h00", "h").replace(" ", "").strip(".")

def verifier_creneau(message: str) -> str | None:
    """
    Retourne un message de correction si la cliente demande un créneau inexistant.
    Retourne None si le créneau est valide ou non détecté.
    """
    msg = message.lower()

    jour_detecte = None
    for jour in PLANNING:
        if jour in msg:
            jour_detecte = jour
            break

    if not jour_detecte:
        return None

    # Cherche une heure dans le message
    match = re.search(r"\b(\d{1,2})[hH](\d{0,2})\b", msg)
    if not match:
        if jour_detecte == "dimanche":
            return CORRECTIONS["dimanche"]
        return None

    heure_brute = match.group(0).lower()
    heure_norm = _normalise_heure(heure_brute)

    creneaux = [_normalise_heure(c) for c in PLANNING[jour_detecte]]

    if heure_norm not in creneaux:
        jours_creneaux = ", ".join(PLANNING[jour_detecte]) if PLANNING[jour_detecte] else "aucun"
        return (
            f"IMPORTANT : Le créneau {heure_brute} le {jour_detecte} n'existe pas dans notre planning. "
            f"Les créneaux disponibles le {jour_detecte} sont uniquement : {jours_creneaux}. "
            f"Tu dois impérativement proposer ces créneaux à la cliente et ne pas confirmer {heure_brute}."
        )

    return None
