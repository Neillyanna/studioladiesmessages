# Dédoublonnage des lignes déjà existantes

`Dedupe.gs` nettoie les doublons créés **avant** le correctif upsert (une ligne
« juste le numéro », une autre « juste l'email » pour la même personne…).

> Le correctif (`Code.gs` + `sheets.py`) empêche les **futurs** doublons.
> Ce script répare seulement l'**existant**, en une passe.

## Pré-requis

`Dedupe.gs` doit être collé dans le **même projet Apps Script** que `Code.gs`
(il réutilise `SHEET_NAME`, `REF_HEADER`, `EMAIL_SENT_HEADER`, `FIELD_HEADERS`).

## Marche à suivre

1. **Sauvegarde** : Google Sheet ▸ *Fichier ▸ Créer une copie* (filet de sécurité).
2. Colle `Dedupe.gs` dans *Extensions ▸ Apps Script* (à côté de `Code.gs`).
3. Lance **`dedupePreview`** (menu *Exécuter*). Rien n'est modifié : ouvre
   *Journaux d'exécution* pour voir quelles lignes seraient fusionnées.
4. Si l'aperçu te convient, lance **`dedupeApply`** pour appliquer réellement.

## Comment il regroupe (prudent)

Deux lignes = même personne si elles partagent une **même valeur non vide** de
`sender_id`, `numéro` **ou** `adresse mail` (regroupement transitif).

- La fusion garde, pour chaque colonne, la **première valeur non vide** →
  aucune donnée n'est perdue au profit d'une case vide.
- Les lignes qui ne partagent **aucun** de ces identifiants forts ne sont **pas**
  fusionnées (on ne fusionne jamais sur le seul prénom, pour éviter de
  confondre deux personnes différentes).

### Limite

Si un ancien doublon « numéro seul » et un « email seul » n'ont **rien** en
commun (ni `sender_id`, ni numéro, ni email partagé), ils ne peuvent pas être
reliés automatiquement et resteront séparés — à fusionner à la main si besoin.
Le `dedupePreview` te montre exactement ce qui sera fait avant toute écriture.
