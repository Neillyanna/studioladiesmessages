/**
 * Studio Ladies — Google Apps Script (Web App) du Google Sheet "STUDIO LADIES".
 *
 * OBJECTIF : UNE SEULE ligne par conversation, complétée au fil de l'eau (upsert).
 * Le chatbot envoie, à chaque nouvelle info, un POST JSON de la forme :
 *   { "action": "upsert", "ref": "<sender_id>", "prenom": "...", "numero": "...", ... }
 *
 * Ce script :
 *   1. Retrouve la ligne de la conversation par `ref` (sender_id), sinon par numéro.
 *   2. Met à jour UNIQUEMENT les colonnes fournies et non vides.
 *   3. N'écrase JAMAIS une valeur déjà présente par du vide.
 *   4. Crée une nouvelle ligne (avec le ref) seulement s'il n'y a aucune correspondance.
 *   5. Envoie l'e-mail de confirmation UNE seule fois, quand la ligne est complète.
 *
 * DÉPLOIEMENT :
 *   Extensions ▸ Apps Script ▸ colle ce fichier ▸ Déployer ▸ Gérer les déploiements
 *   ▸ modifie le déploiement Web App existant (même URL) ▸ "Nouvelle version".
 *   Exécuter en tant que : moi | Accès : tout le monde.
 *
 * ⚠️ ADAPTE `FIELD_HEADERS` ci-dessous pour que les libellés correspondent EXACTEMENT
 *    aux en-têtes (ligne 1) de ton onglet. Toute colonne manquante est créée
 *    automatiquement à la fin — vérifie donc les noms pour éviter les doublons.
 */

// Onglet cible (laisser vide pour utiliser le premier onglet).
var SHEET_NAME = '';

// Colonnes techniques (créées automatiquement si absentes).
var REF_HEADER = 'sender_id';        // identifiant stable de la conversation
var EMAIL_SENT_HEADER = 'email_envoye';

// Envoi de l'e-mail de confirmation (mettre false pour désactiver).
var SEND_CONFIRMATION_EMAIL = true;

// Correspondance : clé du payload -> en-tête EXACT de la colonne dans le Sheet.
// ⚠️ Sensible à la casse et aux accents : doit correspondre au pixel près à la ligne 1.
// Onglet STUDIO LADIES = 6 colonnes (A→F) :
//   A: nom | B: prenom | C: numéro | D: adresse mail | E: date réservation | F: heure réservation
var FIELD_HEADERS = {
  nom:               'nom',
  prenom:            'prenom',
  numero:            'numéro',
  email:             'adresse mail',
  date_reservation:  'date réservation',
  heure_reservation: 'heure réservation'
};


/**
 * Diagnostic LECTURE SEULE : GET sur l'URL du Web App → renvoie le nom du
 * classeur et de l'onglet réellement utilisés, les en-têtes et la dernière ligne.
 * Ne modifie rien. Peut être retiré une fois le câblage vérifié.
 */
function doGet() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = (SHEET_NAME && ss.getSheetByName(SHEET_NAME)) || ss.getSheets()[0];
  var lastCol = sheet.getLastColumn();
  var headers = lastCol > 0 ? sheet.getRange(1, 1, 1, lastCol).getValues()[0] : [];
  return json_({
    classeur: ss.getName(),
    ongletUtilise: sheet.getName(),
    tousLesOnglets: ss.getSheets().map(function (s) { return s.getName(); }),
    derniereLigne: sheet.getLastRow(),
    enTetes: headers
  });
}


function doPost(e) {
  var lock = LockService.getScriptLock();
  lock.waitLock(30000); // écritures concurrentes : on sérialise
  try {
    var payload = JSON.parse(e.postData.contents);
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var sheet = (SHEET_NAME && ss.getSheetByName(SHEET_NAME)) || ss.getSheets()[0];

    var headers = ensureHeaders_(sheet);
    var colIndex = {};
    for (var i = 0; i < headers.length; i++) colIndex[headers[i]] = i;

    var ref = payload.ref || '';
    var numero = payload.numero || '';

    var rowNum = findRow_(sheet, headers, colIndex, ref, numero);
    var isNew = (rowNum < 0);
    if (isNew) rowNum = sheet.getLastRow() + 1;

    var width = headers.length;
    var rowRange = sheet.getRange(rowNum, 1, 1, width);
    var rowValues = isNew ? emptyRow_(width) : rowRange.getValues()[0];

    // Référence stable de la conversation (ne pas écraser si déjà posée).
    if (ref && colIndex[REF_HEADER] !== undefined && !rowValues[colIndex[REF_HEADER]]) {
      rowValues[colIndex[REF_HEADER]] = ref;
    }

    // UPSERT : chaque champ fourni non vide remplit sa colonne. Jamais d'écrasement par du vide.
    for (var key in FIELD_HEADERS) {
      var ci = colIndex[FIELD_HEADERS[key]];
      if (ci === undefined) continue;
      var incoming = payload[key];
      if (incoming === undefined || incoming === null || String(incoming) === '') continue;
      rowValues[ci] = incoming;
    }

    rowRange.setValues([rowValues]);

    var emailed = maybeSendEmail_(sheet, colIndex, rowNum, rowValues);

    return json_({ ok: true, row: rowNum, created: isNew, emailed: emailed });
  } catch (err) {
    return json_({ ok: false, error: String(err) });
  } finally {
    lock.releaseLock();
  }
}


/** Garantit la présence de toutes les colonnes attendues (mappées + techniques). */
function ensureHeaders_(sheet) {
  var lastCol = sheet.getLastColumn();
  var headers = lastCol > 0 ? sheet.getRange(1, 1, 1, lastCol).getValues()[0] : [];

  var needed = [];
  for (var key in FIELD_HEADERS) needed.push(FIELD_HEADERS[key]);
  needed.push(REF_HEADER);
  needed.push(EMAIL_SENT_HEADER);

  var changed = false;
  for (var i = 0; i < needed.length; i++) {
    if (headers.indexOf(needed[i]) === -1) {
      headers.push(needed[i]);
      changed = true;
    }
  }
  if (changed) sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  return headers;
}


/** Retrouve la ligne d'une conversation : d'abord par ref, sinon par numéro. */
function findRow_(sheet, headers, colIndex, ref, numero) {
  var last = sheet.getLastRow();
  if (last < 2) return -1;
  var data = sheet.getRange(2, 1, last - 1, headers.length).getValues();

  var refCol = colIndex[REF_HEADER];
  if (ref && refCol !== undefined) {
    for (var i = 0; i < data.length; i++) {
      if (String(data[i][refCol]) === String(ref)) return i + 2;
    }
  }
  var numCol = colIndex[FIELD_HEADERS.numero];
  if (numero && numCol !== undefined) {
    for (var j = 0; j < data.length; j++) {
      if (String(data[j][numCol]) === String(numero)) return j + 2;
    }
  }
  return -1;
}


function emptyRow_(width) {
  var r = [];
  for (var i = 0; i < width; i++) r.push('');
  return r;
}


/** Envoie l'e-mail de confirmation une seule fois, quand la ligne est complète. */
function maybeSendEmail_(sheet, colIndex, rowNum, rowValues) {
  if (!SEND_CONFIRMATION_EMAIL) return false;

  var emailCol  = colIndex[FIELD_HEADERS.email];
  var dateCol   = colIndex[FIELD_HEADERS.date_reservation];
  var heureCol  = colIndex[FIELD_HEADERS.heure_reservation];
  var prenomCol = colIndex[FIELD_HEADERS.prenom];
  var sentCol   = colIndex[EMAIL_SENT_HEADER];

  if (emailCol === undefined) return false;
  var email = rowValues[emailCol];
  var complete = email
    && dateCol  !== undefined && rowValues[dateCol]
    && heureCol !== undefined && rowValues[heureCol];
  var already = (sentCol !== undefined && rowValues[sentCol]);
  if (!complete || already) return false;

  var prenom = (prenomCol !== undefined ? rowValues[prenomCol] : '') || '';
  try {
    MailApp.sendEmail({
      to: email,
      subject: 'Confirmation de votre séance découverte — Studio Ladies',
      body: 'Bonjour ' + prenom + ',\n\n'
          + 'Votre séance découverte est confirmée pour ' + rowValues[dateCol]
          + ' à ' + rowValues[heureCol] + '.\n'
          + 'Tarif : 150 dh. Merci d\'arriver quelques minutes avant la séance, '
          + 'en tenue confortable.\n\n'
          + 'À très bientôt chez Studio Ladies !'
    });
    if (sentCol !== undefined) {
      rowValues[sentCol] = 'oui';
      sheet.getRange(rowNum, sentCol + 1).setValue('oui');
    }
    return true;
  } catch (mailErr) {
    return false;
  }
}


function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
