function escapeHtml(value) {
  return String(value).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function nativeEvidenceTable(surface, rows, palette) {
  const labels = ['OPTION A', 'OPTION B', 'DECISION RULE', 'OPERATING GUARDRAIL'];
  const colors = [palette.navy, palette.green, palette.orange, palette.blue];
  const fills = [palette.paleBlue, palette.paleGreen, palette.paleOrange, palette.paleBlue];
  const x = 44; const y = 244; const w = 1572; const h = 520;
  if (surface._pptx) {
    const backend = surface._pptx;
    const slide = backend._slides[backend._slides.length - 1];
    const ix = px => +(px * 13.333 / 1664).toFixed(3);
    const iy = px => +(px * 7.5 / 936).toFixed(3);
    const tableRows = rows.map((text, index) => ([
      {
        text: `${labels[index]}\nROW 0${index + 1}`,
        options: {
          fill: { color: colors[index] }, color: palette.white, bold: true, align: 'center', valign: 'middle',
          fontSize: 11.5, margin: 0.06, border: { type: 'solid', color: colors[index], pt: 1 },
        },
      },
      {
        text,
        options: {
          fill: { color: fills[index] }, color: palette.ink, bold: index === 2, valign: 'middle',
          fontSize: index === 3 ? 12.2 : 11.5, margin: 0.10, border: { type: 'solid', color: colors[index], pt: 1 },
        },
      },
    ]));
    slide.addTable(tableRows, {
      // Keep total height exactly divisible across four rows in EMUs.
      x: ix(x), y: iy(y), w: ix(w), h: 4.16,
      colW: [ix(250), ix(1322)],
      margin: 0, border: { type: 'solid', color: palette.border, pt: 1 },
      autoPage: false, fontFace: 'Arial',
    });
    return;
  }
  const priorHtml = surface._html.bind(surface);
  const body = rows.map((text, index) => `
    <tr style="height:130px;">
      <th scope="row" style="width:250px;background:#${colors[index]};color:#${palette.white};border:1px solid #${colors[index]};padding:12px 16px;box-sizing:border-box;text-align:center;font-size:15px;line-height:1.25;">${escapeHtml(labels[index])}<br><span style="font-size:11px;font-weight:400;">ROW 0${index + 1}</span></th>
      <td style="background:#${fills[index]};color:#${palette.ink};border:1px solid #${colors[index]};padding:14px 24px;box-sizing:border-box;font-size:${index === 3 ? 16 : 15}px;line-height:1.25;font-weight:${index === 2 ? 700 : 400};vertical-align:middle;">${escapeHtml(text)}</td>
    </tr>`).join('');
  const table = `<table data-native-slot="table" aria-label="Evidence statement matrix" style="position:absolute;left:${x}px;top:${y}px;width:${w}px;height:${h}px;border-collapse:collapse;table-layout:fixed;font-family:Arial,system-ui,sans-serif;">${body}</table>`;
  surface._html = () => `${priorHtml()}\n${table}`;
}

module.exports = { nativeEvidenceTable };
