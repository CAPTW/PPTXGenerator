const fs = require('fs');
const path = require('path');
const kit = require('./kit');
const { nativeEvidenceTable } = require('./native_table');
const { T } = kit;

const ROOT = process.env.DECK_PROJECT_ROOT || path.resolve(__dirname, '..');
const P = {
  bg: 'F7F9FC', white: 'FFFFFF', navy: '0E2A47', blue: '315E91', green: '3F765C',
  orange: 'C64B1B', ink: '14223A', muted: '51627A', border: 'D7E0EA', gray: '98A5B3',
  paleBlue: 'EDF3F9', paleGreen: 'EEF5F1', paleOrange: 'FFF2EC', paleGray: 'F1F3F5',
};
const COLORS = [P.navy, P.green, P.orange, P.blue, P.gray];
const FILLS = [P.paleBlue, P.paleGreen, P.paleOrange, P.paleBlue, P.paleGray];

function load(n) {
  const file = path.join(ROOT, 'work', `slide${String(n).padStart(2, '0')}`, 'semantic_sidecar.json');
  const metadata = JSON.parse(fs.readFileSync(file, 'utf8')).phase4_metadata;
  return {
    title: metadata.exact_title,
    subtitle: metadata.exact_subtitle,
    body: metadata.exact_body_blocks.map(item => item.text),
    citations: metadata.citations.map(item => item.label),
    notes: metadata.speaker_note_candidates[0],
  };
}
const DATA = [null, ...[1, 2, 3, 4, 5, 6].map(load)];

function line(s, x, y, w, color = P.border, width = 1) { s.ln(x, y, w, 0, { color, width }); }
function box(s, x, y, w, h, fill = P.white, stroke = P.border, lineW = 1) {
  s.rrect(x, y, w, h, { fill, line: stroke, lineW, radius: 8 });
}
function bar(s, label, x, y, w, color) {
  s.rrect(x, y, w, 36, { fill: color, line: color, lineW: 0, radius: 2 });
  T(s, label, x + 12, y, w - 24, 36, { sz: 12.5, b: true, color: P.white, align: 'center', wrap: false, shrink: true });
}
function badge(s, value, x, y, color, d = 44) {
  s.ell(x, y, d, d, { fill: P.white, line: color, lineW: 2 });
  T(s, value, x, y, d, d, { sz: 14, b: true, color, align: 'center', valign: 'middle', wrap: false });
}
function header(s, d, n) {
  const multilineTitle = d.title.length > 52;
  s.bgFill(P.bg);
  s.rrect(14, 16, 8, 140, { fill: P.navy, line: P.navy, lineW: 0, radius: 0 });
  s.rrect(22, 16, 70, 8, { fill: P.navy, line: P.navy, lineW: 0, radius: 0 });
  T(s, d.title, 52, multilineTitle ? 22 : 36, 1280, multilineTitle ? 94 : 62, {
    sz: multilineTitle ? 26 : 30, b: true, color: P.navy,
    valign: multilineTitle ? 'top' : 'middle', shrink: true,
  });
  T(s, d.subtitle, 54, multilineTitle ? 124 : 104, 980, multilineTitle ? 22 : 28, {
    sz: multilineTitle ? 13.5 : 15, color: P.muted, wrap: false, shrink: true,
  });
  T(s, `0${n}`, 1450, 42, 150, 54, { sz: 26, b: true, color: P.border, align: 'right', wrap: false });
  for (let i = 0; i < 5; i += 1) line(s, 1320 + i * 28, 122 - i * 7, 180, 'D9E7F4', 0.7);
  line(s, 22, 156, 1590, P.navy, 1.2);
}
function footer(s, d, n) {
  line(s, 22, 838, 1590, P.border, 1);
  s.rrect(22, 852, 18, 18, { fill: P.navy, line: P.navy, lineW: 0, radius: 0 });
  T(s, d.citations.join('  |  '), 52, 845, 1450, 24, { sz: 7.1, color: P.muted, wrap: false, shrink: true });
  T(s, d.notes, 52, 871, 1450, 36, { sz: 6.4, color: P.gray, valign: 'top', shrink: true });
  T(s, `${n} / 6`, 1515, 852, 96, 28, { sz: 10, b: true, color: P.navy, align: 'right', wrap: false });
  s.ell(1600, 900, 12, 12, { fill: P.navy, line: P.navy, lineW: 0 });
}
function card(s, index, text, x, y, w, h, color, fill) {
  box(s, x, y, w, h, fill, color, 1.2);
  badge(s, String(index).padStart(2, '0'), x + 18, y + 18, color, 42);
  T(s, text, x + 76, y + 16, w - 96, h - 32, { sz: 12.2, color: P.ink, valign: 'middle', lh: 1.05, shrink: true });
}

function s1(s) {
  const d = DATA[1]; header(s, d, 1);
  box(s, 44, 190, 660, 348, P.paleOrange, P.orange, 1.4); bar(s, 'RECOMMENDED DECISION', 44, 190, 660, P.orange);
  s.ell(78, 256, 104, 104, { fill: P.orange, line: P.orange, lineW: 1 });
  T(s, '✓', 78, 256, 104, 104, { sz: 42, b: true, color: P.white, align: 'center', valign: 'middle' });
  T(s, d.body[0], 210, 246, 452, 128, { sz: 16.5, b: true, color: P.ink, valign: 'middle', lh: 1.06, shrink: true });
  line(s, 78, 400, 584, P.orange, 1);
  ['BASELINE', 'FAILOVER', 'GOVERNANCE'].forEach((label, i) => {
    const x = 84 + i * 190; badge(s, String(i + 1), x, 432, P.orange, 36);
    T(s, label, x + 46, 430, 128, 40, { sz: 10.5, b: true, color: P.orange, wrap: false, shrink: true });
  });
  bar(s, 'EVIDENCE', 742, 190, 874, P.navy);
  card(s, 1, d.body[1], 742, 242, 874, 138, P.green, P.paleGreen);
  card(s, 2, d.body[2], 742, 398, 874, 140, P.navy, P.paleBlue);
  bar(s, 'PHASED DECISION PATH', 44, 576, 1572, P.blue);
  ['INSTRUMENT THE BASELINE', 'COMMISSION AUTOMATED PUMP FAILOVER', 'TIGHTEN SENSOR CALIBRATION GOVERNANCE'].forEach((label, i) => {
    const x = 80 + i * 500; s.chev(x, 646, 456, 86, { fill: COLORS[i], line: COLORS[i], lineW: 1 });
    T(s, label, x + 28, 646, 382, 86, { sz: 12, b: true, color: P.white, align: 'center', valign: 'middle', shrink: true });
  });
  footer(s, d, 1);
}

function s2(s) {
  const d = DATA[2]; header(s, d, 2); bar(s, 'CLOSED-LOOP OPERATING PROCESS', 44, 190, 1572, P.navy);
  const labels = ['HEAT REJECTION', 'PRIMARY LOOP', 'SENSE & CONTROL', 'COLD-PLATE INTAKE'];
  d.body.forEach((text, i) => {
    const x = 44 + i * 393; box(s, x, 254, 354, 456, FILLS[i], COLORS[i], 1.2);
    s.ell(x + 122, 278, 110, 110, { fill: P.white, line: COLORS[i], lineW: 2 });
    T(s, String(i + 1), x + 122, 278, 110, 110, { sz: 32, b: true, color: COLORS[i], align: 'center', valign: 'middle' });
    T(s, `STEP 0${i + 1}`, x + 24, 410, 306, 22, { sz: 10, b: true, color: COLORS[i], align: 'center', wrap: false });
    T(s, labels[i], x + 24, 442, 306, 40, { sz: 13, b: true, color: P.ink, align: 'center', shrink: true });
    line(s, x + 32, 496, 290, COLORS[i], 1);
    T(s, text, x + 28, 516, 298, 158, { sz: 11.3, color: P.muted, valign: 'top', lh: 1.03, shrink: true });
    if (i < 3) T(s, '→', x + 350, 402, 44, 52, { sz: 22, b: true, color: P.gray, align: 'center' });
  });
  box(s, 44, 740, 1572, 72); T(s, 'PRIMARY LOOP  →  SENSORS  →  CONTROLLER  →  HEAT REJECTION', 70, 740, 1520, 72, { sz: 12.5, b: true, color: P.navy, align: 'center', wrap: false, shrink: true });
  footer(s, d, 2);
}

function s3(s) {
  const d = DATA[3]; header(s, d, 3); bar(s, 'EVIDENCE-BACKED RISK FIELD', 44, 190, 1572, P.navy);
  const positions = [[44, 246, 500, 220], [566, 246, 500, 220], [1088, 246, 528, 220], [304, 492, 500, 220], [826, 492, 500, 220]];
  d.body.forEach((text, i) => {
    const [x, y, w, h] = positions[i]; card(s, i + 1, text, x, y, w, h, COLORS[i], FILLS[i]);
    T(s, `RISK FINDING 0${i + 1}`, x + 78, y + 26, w - 102, 24, { sz: 9.8, b: true, color: COLORS[i], wrap: false });
  });
  box(s, 44, 748, 1572, 64); T(s, 'SENSING  ·  FLOW  ·  SHARED HEAT REJECTION  ·  COMBINED RESPONSE', 70, 748, 1520, 64, { sz: 12, b: true, color: P.muted, align: 'center', wrap: false, shrink: true });
  footer(s, d, 3);
}

function s4(s) {
  const d = DATA[4];
  // PptxGenJS assigns a table-local non-visual id. Keep the native table first
  // so its id remains unique while later editable shapes retain normal z-order.
  nativeEvidenceTable(s, d.body, P);
  header(s, d, 4); bar(s, 'EVIDENCE STATEMENT MATRIX', 44, 190, 1572, P.navy);
  box(s, 44, 788, 1572, 34); T(s, 'TABLE  ·  4 ROWS  ·  NATIVE EDITABLE TEXT', 66, 788, 1528, 34, { sz: 10.5, color: P.muted, align: 'center', wrap: false });
  footer(s, d, 4);
}

function s5(s) {
  const d = DATA[5]; header(s, d, 5); box(s, 44, 190, 1572, 224, P.paleOrange, P.orange, 1.5);
  s.ell(78, 242, 118, 118, { fill: P.orange, line: P.orange, lineW: 1 });
  T(s, '★', 78, 242, 118, 118, { sz: 42, b: true, color: P.white, align: 'center', valign: 'middle' });
  T(s, 'RECOMMENDATION', 232, 220, 1320, 38, { sz: 18, b: true, color: P.orange });
  T(s, d.body[0], 232, 270, 1320, 108, { sz: 19, b: true, color: P.ink, valign: 'middle', lh: 1.05, shrink: true });
  bar(s, 'RATIONALE', 44, 444, 1572, P.navy);
  d.body.slice(1).forEach((text, i) => {
    const x = 44 + i * 524; box(s, x, 492, 500, 250, FILLS[i + 1], COLORS[i + 1], 1.2); badge(s, String(i + 1), x + 22, 516, COLORS[i + 1], 44);
    T(s, `RATIONALE 0${i + 1}`, x + 82, 520, 388, 30, { sz: 11.5, b: true, color: COLORS[i + 1], wrap: false }); line(s, x + 24, 578, 452, COLORS[i + 1], 1);
    T(s, text, x + 24, 600, 452, 110, { sz: 12.2, color: P.ink, valign: 'top', lh: 1.04, shrink: true });
  });
  ['BASELINE', 'FAILOVER', 'CALIBRATION'].forEach((label, i) => { const x = 280 + i * 380; s.chev(x, 770, 350, 46, { fill: COLORS[i], line: COLORS[i], lineW: 1 }); T(s, label, x + 26, 770, 286, 46, { sz: 11, b: true, color: P.white, align: 'center', wrap: false }); });
  footer(s, d, 5);
}

function s6(s) {
  const d = DATA[6]; header(s, d, 6); bar(s, 'IMPLEMENTATION SEQUENCE', 44, 190, 1572, P.navy);
  const labels = ['CONTROL INPUTS', 'HEAT CAPTURE', 'PHASED COMMISSIONING', 'ALARM RESPONSE'];
  d.body.forEach((text, i) => {
    const x = 44 + i * 393; s.chev(x, 248, 366, 92, { fill: COLORS[i], line: COLORS[i], lineW: 1 }); badge(s, String(i + 1), x + 18, 269, COLORS[i], 48);
    T(s, labels[i], x + 80, 258, 242, 58, { sz: 12, b: true, color: P.white, valign: 'middle', shrink: true });
    box(s, x, 370, 350, 342, FILLS[i], COLORS[i], 1.2); T(s, `STAGE 0${i + 1}`, x + 24, 394, 302, 26, { sz: 10.5, b: true, color: COLORS[i], align: 'center', wrap: false });
    line(s, x + 30, 438, 290, COLORS[i], 1); T(s, text, x + 26, 466, 298, 210, { sz: 11.4, color: P.ink, valign: 'top', lh: 1.04, shrink: true });
    if (i < 3) T(s, '→', x + 350, 398, 44, 52, { sz: 22, b: true, color: P.gray, align: 'center' });
  });
  box(s, 44, 744, 1572, 68); T(s, 'OBSERVE  →  COMMISSION  →  AUDIT  →  RESPOND', 70, 744, 1520, 68, { sz: 12, b: true, color: P.navy, align: 'center', wrap: false });
  footer(s, d, 6);
}

module.exports = { s1, s2, s3, s4, s5, s6 };
