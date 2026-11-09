/**
 * ARC Winter Training — coaches' check-in
 *
 * Paste this into the "2026 - 2027 Winter Training" Google Sheet:
 *   Extensions > Apps Script, replace everything in Code.gs with this file, Save.
 *   Deploy > New deployment > type "Web app"
 *     Execute as: Me
 *     Who has access: Anyone
 *   Deploy, approve the permissions, and copy the Web app URL (ends in /exec).
 *
 * It only reads and writes the "Attendance" tab:
 *   row 3 = session dates (yellow = AM, orange = PM, same colors as the key in B2 / C2)
 *   names start in row 5 (first name in column A, last name in column B)
 *   checkboxes start in column D
 */
var SHEET_NAME = 'Attendance';
var HEADER_ROW = 3;
var FIRST_NAME_ROW = 5;
var FIRST_SESSION_COL = 4; // column D

function doGet(e) {
  var p = (e && e.parameter) || {};
  var out;
  try {
    out = p.action === 'set' ? setPresent_(p) : load_(p);
  } catch (err) {
    out = { error: String(err && err.message || err) };
  }
  return ContentService.createTextOutput(JSON.stringify(out))
    .setMimeType(ContentService.MimeType.JSON);
}

function sheet_() {
  var sh = SpreadsheetApp.getActive().getSheetByName(SHEET_NAME);
  if (!sh) throw new Error('No tab named "' + SHEET_NAME + '"');
  return sh;
}

function sessions_(sh) {
  var lastCol = sh.getLastColumn();
  var n = lastCol - FIRST_SESSION_COL + 1;
  if (n < 1) return [];
  var hdr = sh.getRange(HEADER_ROW, FIRST_SESSION_COL, 1, n);
  var vals = hdr.getValues()[0];
  var bgs = hdr.getBackgrounds()[0];
  var amBg = sh.getRange('B2').getBackground();
  var pmBg = sh.getRange('C2').getBackground();
  var canxBg = sh.getRange('I2').getBackground();
  var out = [];
  for (var i = 0; i < n; i++) {
    var v = vals[i];
    if (!(v instanceof Date)) continue;
    var bg = bgs[i];
    out.push({
      col: FIRST_SESSION_COL + i,
      month: v.getMonth() + 1,
      day: v.getDate(),
      ampm: bg === amBg ? 'AM' : bg === pmBg ? 'PM' : '',
      cancelled: canxBg !== '#ffffff' && bg === canxBg
    });
  }
  return out;
}

function roster_(sh, col) {
  var last = sh.getLastRow();
  if (last < FIRST_NAME_ROW) return [];
  var n = last - FIRST_NAME_ROW + 1;
  var names = sh.getRange(FIRST_NAME_ROW, 1, n, 2).getValues();
  var marks = sh.getRange(FIRST_NAME_ROW, col, n, 1).getValues();
  var out = [];
  for (var i = 0; i < n; i++) {
    var first = String(names[i][0] || '').trim();
    var lastName = String(names[i][1] || '').trim();
    var m = marks[i][0];
    if (!first && !lastName) continue;
    if (/^total/i.test(first)) continue;
    if (!lastName && first.length <= 2 && typeof m !== 'boolean') continue; // letter dividers
    out.push({ row: FIRST_NAME_ROW + i, first: first, last: lastName, present: m === true });
  }
  return out;
}

function load_(p) {
  var sh = sheet_();
  var sessions = sessions_(sh);
  var res = { sessions: sessions };
  var col = parseInt(p.col, 10);
  if (col && sessions.some(function (s) { return s.col === col; })) {
    res.col = col;
    res.roster = roster_(sh, col);
  }
  return res;
}

function setPresent_(p) {
  var sh = sheet_();
  var col = parseInt(p.col, 10), row = parseInt(p.row, 10);
  var ok = sessions_(sh).some(function (s) { return s.col === col; });
  if (!ok || !(row >= FIRST_NAME_ROW && row <= sh.getLastRow())) throw new Error('That session or name is not in the Attendance tab');
  var lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    var present = p.present === '1' || p.present === 'true';
    sh.getRange(row, col).setValue(present);
    SpreadsheetApp.flush();
    return { ok: true, row: row, col: col, present: sh.getRange(row, col).getValue() === true };
  } finally {
    lock.releaseLock();
  }
}
