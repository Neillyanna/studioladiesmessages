/**
 * Studio Ladies — Dédoublonnage des lignes existantes du Google Sheet.
 *
 * À utiliser UNE FOIS pour nettoyer les doublons créés AVANT le correctif upsert
 * (une ligne « juste le numéro », une autre « juste l'email » pour la même
 * personne, etc.). Le correctif empêche les futurs doublons ; ce script répare
 * l'existant.
 *
 * ⚠️ Ce fichier doit être dans le MÊME projet Apps Script que `Code.gs`
 *    (il réutilise SHEET_NAME, REF_HEADER, EMAIL_SENT_HEADER, FIELD_HEADERS).
 *
 * UTILISATION :
 *   1. Fais d'abord une COPIE de sauvegarde du Sheet (Fichier ▸ Créer une copie).
 *   2. Lance `dedupePreview` : n'écrit RIEN, journalise ce qui serait fusionné
 *      (Exécuter ▸ dedupePreview, puis regarde « Journaux d'exécution »).
 *   3. Si le résultat te convient, lance `dedupeApply` pour appliquer réellement.
 *
 * RÈGLE DE REGROUPEMENT (prudente) :
 *   Deux lignes sont considérées comme la même personne si elles partagent une
 *   MÊME valeur non vide de `sender_id`, de `numéro` OU d'`adresse mail`.
 *   Le regroupement est transitif (A~B et B~C ⇒ A~B~C).
 *   Les lignes qui ne partagent AUCUN de ces identifiants forts ne sont jamais
 *   fusionnées (on ne fusionne pas sur le seul prénom, pour éviter les erreurs).
 *
 * FUSION : pour chaque colonne, on garde la première valeur non vide rencontrée
 *   (en partant de la ligne la plus haute). Aucune donnée non vide n'est perdue
 *   au profit d'une case vide.
 */

function dedupePreview() { dedupe_(true); }
function dedupeApply()   { dedupe_(false); }


function dedupe_(preview) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = (typeof SHEET_NAME !== 'undefined' && SHEET_NAME && ss.getSheetByName(SHEET_NAME))
              || ss.getSheets()[0];

  var last = sheet.getLastRow();
  var width = sheet.getLastColumn();
  if (last < 3 || width < 1) { Logger.log('Rien à dédoublonner (moins de 2 lignes de données).'); return; }

  var headers = sheet.getRange(1, 1, 1, width).getValues()[0];
  var idx = {};
  for (var i = 0; i < headers.length; i++) idx[headers[i]] = i;

  var data = sheet.getRange(2, 1, last - 1, width).getValues();
  var n = data.length;

  var idCols = [];
  if (idx[REF_HEADER] !== undefined) idCols.push(idx[REF_HEADER]);
  if (idx[FIELD_HEADERS.numero] !== undefined) idCols.push(idx[FIELD_HEADERS.numero]);
  if (idx[FIELD_HEADERS.email] !== undefined) idCols.push(idx[FIELD_HEADERS.email]);

  // Union-Find : relie les lignes partageant un identifiant fort.
  var parent = [];
  for (var i = 0; i < n; i++) parent[i] = i;
  function find(x) { while (parent[x] !== x) { parent[x] = parent[parent[x]]; x = parent[x]; } return x; }
  function union(a, b) { parent[find(a)] = find(b); }

  var seen = {};
  for (var i = 0; i < n; i++) {
    for (var c = 0; c < idCols.length; c++) {
      var v = norm_(data[i][idCols[c]]);
      if (!v) continue;
      var key = idCols[c] + '::' + v.toLowerCase();
      if (seen[key] !== undefined) union(seen[key], i);
      else seen[key] = i;
    }
  }

  // Constitue les groupes.
  var groups = {};
  for (var i = 0; i < n; i++) {
    var root = find(i);
    (groups[root] = groups[root] || []).push(i);
  }

  var toDelete = [];
  var nbFusions = 0;
  for (var g in groups) {
    var members = groups[g];
    if (members.length < 2) continue;
    nbFusions++;
    members.sort(function(a, b) { return a - b; });
    var keep = members[0];

    for (var c = 0; c < width; c++) {
      if (norm_(data[keep][c])) continue; // déjà renseigné → on ne touche pas
      for (var m = 1; m < members.length; m++) {
        if (norm_(data[members[m]][c])) { data[keep][c] = data[members[m]][c]; break; }
      }
    }
    for (var m = 1; m < members.length; m++) toDelete.push(members[m]);
    Logger.log('Fusion des lignes ' + members.map(function(x){ return x + 2; }).join(', ')
               + ' → ligne ' + (keep + 2));
  }

  if (preview) {
    Logger.log('APERÇU : ' + nbFusions + ' groupe(s) à fusionner, '
               + toDelete.length + ' ligne(s) seraient supprimée(s). Rien n\'a été modifié.');
    return;
  }

  // Réécrit les lignes conservées puis supprime les doublons de bas en haut.
  sheet.getRange(2, 1, n, width).setValues(data);
  toDelete.sort(function(a, b) { return b - a; });
  for (var d = 0; d < toDelete.length; d++) sheet.deleteRow(toDelete[d] + 2);

  Logger.log('TERMINÉ : ' + nbFusions + ' fusion(s), ' + toDelete.length + ' ligne(s) supprimée(s).');
}


function norm_(v) { return String(v == null ? '' : v).trim(); }
