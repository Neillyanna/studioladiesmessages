# Google Apps Script — Google Sheet « STUDIO LADIES »

Ce dossier contient le script (`Code.gs`) qui reçoit les données du chatbot et
les écrit dans le Google Sheet en mode **upsert** : **une seule ligne par
conversation**, complétée au fur et à mesure.

## Pourquoi ce script

Avant, chaque nouvelle info (nom, puis numéro, puis email…) créait une
**nouvelle ligne** → doublons et lignes incomplètes. Ce script retrouve la ligne
existante de la conversation et met à jour **uniquement les colonnes
concernées**, sans jamais écraser une valeur déjà remplie par du vide.

## Comment le chatbot l'appelle

`sheets.py` envoie un POST JSON à l'URL de l'Apps Script (`APPS_SCRIPT_URL`) :

```json
{
  "action": "upsert",
  "ref": "17841400000000000",
  "prenom": "Rim",
  "numero": "0612345678",
  "email": "rim@example.com",
  "date_reservation": "mardi",
  "heure_reservation": "9h30"
}
```

- `ref` = `sender_id` Instagram (ou `wa_<numéro>` pour WhatsApp) : identifiant
  **stable et unique** de la conversation.
- Seuls les champs **non vides** sont envoyés.

## Déploiement (à faire AVANT ou EN MÊME TEMPS que le déploiement Railway)

1. Ouvre le Google Sheet « STUDIO LADIES ».
2. **Extensions ▸ Apps Script**.
3. Remplace le contenu par celui de `Code.gs`.
4. **Adapte `FIELD_HEADERS`** en haut du fichier pour que les libellés
   correspondent EXACTEMENT aux en-têtes de la **ligne 1** de ton onglet.
   ⚠️ Un libellé qui ne correspond pas → une **nouvelle colonne** est créée à la
   fin. Vérifie donc les noms pour éviter les doublons de colonnes.
5. **Déployer ▸ Gérer les déploiements ▸** modifie le déploiement Web App
   **existant** (pour garder la **même URL**) ▸ **Nouvelle version**.
   - Exécuter en tant que : **moi**
   - Qui a accès : **tout le monde**
6. Les colonnes techniques `sender_id` et `email_envoye` sont créées
   automatiquement au premier appel (tu peux masquer `sender_id` si tu veux).

## Ordre recommandé

1. **D'abord** : mets à jour + redéploie l'Apps Script (ci-dessus).
   > Ce script est déjà compatible avec l'ancien code : même sans le nouveau
   > `sheets.py`, il fusionne les lignes par numéro. Le mettre à jour en premier
   > est donc sans risque.
2. **Ensuite** : fusionne la PR (nouveau `sheets.py`) → Railway redéploie.

## Lignes déjà dupliquées

Ce correctif empêche les **futurs** doublons. Les lignes déjà dupliquées dans le
Sheet doivent être nettoyées à la main (ou dis-le-moi, je peux préparer une
petite fonction de dédoublonnage).
