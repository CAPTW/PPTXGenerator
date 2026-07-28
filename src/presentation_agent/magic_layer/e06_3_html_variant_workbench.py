"""HTML workbench for E06.3 contract variants."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any


def build_html_variant_workbench(
    output_root: Path,
    baseline: dict[str, Any],
    variants: dict[str, dict[str, Any]],
    diff_report: dict[str, Any],
) -> dict[str, Any]:
    root = output_root / "html_workbench"
    root.mkdir(parents=True, exist_ok=True)
    _write_json(root / "layout_contract_baseline.json", baseline)
    for key, contract in variants.items():
        letter = key.split("_")[-1]
        _write_json(root / f"layout_contract_variant_{letter}.json", contract)
    _write_json(root / "contract_variant_diff_report.json", diff_report)
    (root / "index.html").write_text(_index_html(), encoding="utf-8")
    (root / "variant_diff_viewer.js").write_text(_viewer_js(), encoding="utf-8")
    (root / "styles.css").write_text(_styles_css(), encoding="utf-8")
    (root / "README.md").write_text(
        "# E06.3 Contract Variant Workbench\n\nOpen `index.html` locally. The workbench compares the baseline layout contract against variants A, B, and C and overlays changed objects by slide.\n",
        encoding="utf-8",
    )
    # Keep a canonical variant alias set for users who open only the folder.
    for key in variants:
        source = root / f"layout_contract_variant_{key.split('_')[-1]}.json"
        shutil.copy2(source, root / f"{key}.json")
    return {
        "schema_name": "html_workbench_variant_report",
        "status": "passed" if (root / "index.html").exists() and (root / "variant_diff_viewer.js").exists() else "failed",
        "html_workbench_path": root.as_posix(),
        "variant_contract_count": len(variants),
        "external_network_dependency": False,
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _index_html() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>E06.3 Contract Variant Workbench</title>
  <link rel="stylesheet" href="styles.css" />
</head>
<body>
  <header>
    <h1>E06.3 Contract Variant Workbench</h1>
    <div class="controls">
      <label>Variant <select id="variant"><option value="a">A</option><option value="b">B</option><option value="c">C</option></select></label>
      <label>Slide <select id="slide"></select></label>
      <button id="reload">Reload</button>
    </div>
  </header>
  <main>
    <section class="canvas-wrap"><canvas id="canvas" width="1280" height="720"></canvas></section>
    <aside><h2>Changed Objects</h2><div id="details"></div></aside>
  </main>
  <script src="variant_diff_viewer.js"></script>
</body>
</html>
"""


def _viewer_js() -> str:
    return """const W = 1280, H = 720;
const canvas = document.getElementById('canvas');
const ctx = canvas.getContext('2d');
const variantSelect = document.getElementById('variant');
const slideSelect = document.getElementById('slide');
const details = document.getElementById('details');
let baseline, variant;

async function loadJson(path) {
  const r = await fetch(path);
  return r.json();
}

function bbox(obj) {
  const b = obj.bbox_norm || {};
  return {x:(b.x||0)*W, y:(b.y||0)*H, w:(b.w||0)*W, h:(b.h||0)*H};
}

function objectMap(slide) {
  const m = new Map();
  (slide.objects || []).forEach(o => m.set(o.object_id, o));
  return m;
}

function draw() {
  const slideNo = Number(slideSelect.value || 1);
  const baseSlide = baseline.slides.find(s => Number(s.slide_number) === slideNo);
  const varSlide = variant.slides.find(s => Number(s.slide_number) === slideNo);
  ctx.fillStyle = '#071018';
  ctx.fillRect(0,0,W,H);
  ctx.strokeStyle = '#334155';
  ctx.strokeRect(0,0,W,H);
  const base = objectMap(baseSlide || {});
  const changed = [];
  (varSlide.objects || []).forEach(o => {
    const before = base.get(o.object_id);
    const bb = bbox(o);
    const same = before && JSON.stringify(before.bbox_norm) === JSON.stringify(o.bbox_norm) && before.style_override_fill_rgb === o.style_override_fill_rgb;
    if (!same) {
      changed.push(o);
      ctx.strokeStyle = o.object_type === 'semantic_icon' ? '#28D7E8' : '#F2A900';
      ctx.lineWidth = 2;
      ctx.strokeRect(bb.x, bb.y, bb.w, bb.h);
      ctx.fillStyle = '#F8FAFC';
      ctx.fillText(`${o.object_type}:${o.semantic_role || ''}`, bb.x + 3, bb.y + 11);
    }
  });
  details.innerHTML = changed.map(o => `<div class="row"><b>${o.object_id}</b><br>${o.name || ''}<br>${(o.e06_3_tuning_parameters||[]).map(p=>p.parameter_id).join(', ')}</div>`).join('');
}

async function reload() {
  baseline = await loadJson('layout_contract_baseline.json');
  variant = await loadJson(`layout_contract_variant_${variantSelect.value}.json`);
  slideSelect.innerHTML = baseline.slides.map(s => `<option>${s.slide_number}</option>`).join('');
  draw();
}
document.getElementById('reload').addEventListener('click', reload);
variantSelect.addEventListener('change', reload);
slideSelect.addEventListener('change', draw);
reload();
"""


def _styles_css() -> str:
    return """body{margin:0;background:#071018;color:#f8fafc;font-family:Segoe UI,Arial,sans-serif}header{padding:16px 20px;border-bottom:1px solid #243241;display:flex;justify-content:space-between;gap:16px;align-items:center}h1{font-size:18px;margin:0}.controls{display:flex;gap:10px;align-items:center}select,button{background:#0f1f2d;color:#f8fafc;border:1px solid #334155;padding:6px 8px}main{display:grid;grid-template-columns:minmax(0,1fr) 360px;gap:16px;padding:16px}.canvas-wrap{overflow:auto;border:1px solid #243241;background:#020617}canvas{width:100%;height:auto;display:block}aside{border:1px solid #243241;padding:12px;max-height:calc(100vh - 96px);overflow:auto}.row{border-bottom:1px solid #243241;padding:8px 0;font-size:12px;line-height:1.35}h2{font-size:14px;margin:0 0 8px}"""
