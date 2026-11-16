/**
 * ARC Winter Training — results board (read-only)
 *
 * Paste this into the "2026 - 2027 ARC Winter Training Data" Google Sheet:
 *   Extensions > Apps Script, replace everything in Code.gs with this file, Save.
 *   Deploy > New deployment > type "Web app"
 *     Execute as: Me
 *     Who has access: Anyone
 *   Deploy, approve the permissions, and copy the Web app URL (ends in /exec).
 *
 * It only READS tabs whose names start with a date, like "11.7 5k" or "11.21.26 5 x 4'".
 * Every other tab (for example the survey responses) is never read or sent.
 * It sends the values exactly as they appear in the sheet; the website does the ranking.
 */
var RESULT_TAB = /^\s*\d{1,2}\.\d{1,2}(\.\d{2,4})?\s+\S/;

function doGet() {
  var out;
  try {
    var tabs = [];
    SpreadsheetApp.getActive().getSheets().forEach(function (sh) {
      var name = sh.getName();
      if (sh.isSheetHidden() || !RESULT_TAB.test(name)) return;
      var rows = sh.getLastRow(), cols = sh.getLastColumn();
      if (rows < 1 || cols < 1) return;
      tabs.push({ name: name, values: sh.getRange(1, 1, rows, cols).getDisplayValues() });
    });
    out = { tabs: tabs, updated: new Date().toISOString() };
  } catch (err) {
    out = { error: String(err && err.message || err) };
  }
  return ContentService.createTextOutput(JSON.stringify(out))
    .setMimeType(ContentService.MimeType.JSON);
}
