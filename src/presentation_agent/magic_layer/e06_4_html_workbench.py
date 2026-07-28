"""HTML workbench for E06.4 human-guided tuning."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def build_e06_4_html_workbench(
    output_root: Path,
    baseline_contract: dict[str, Any],
    e06_3_selected_contract: dict[str, Any],
    human_tuned_contract: dict[str, Any],
    controls: dict[str, Any],
) -> dict[str, Any]:
    root = output_root / "html_workbench"
    root.mkdir(parents=True, exist_ok=True)
    _write(root / "layout_contract_baseline.json", baseline_contract)
    _write(root / "layout_contract_e06_3_selected.json", e06_3_selected_contract)
    _write(root / "layout_contract_human_tuned.json", human_tuned_contract)
    _write(root / "tuning_controls.json", controls)
    (root / "index.html").write_text(_index_html(), encoding="utf-8")
    (root / "variant_diff_viewer.js").write_text(_viewer_js(), encoding="utf-8")
    (root / "styles.css").write_text(_styles_css(), encoding="utf-8")
    (root / "README.md").write_text(
        "# E06.4 Human-Guided Contract Tuning Workbench\n\nOpen `index.html` locally to compare baseline, E06.3 selected, and E06.4 human-tuned contracts for target slides 2, 9, 10, 11, and 14.\n",
        encoding="utf-8",
    )
    return {
        "schema_name": "html_workbench_report",
        "status": "passed" if (root / "index.html").exists() else "failed",
        "html_workbench_path": root.as_posix(),
        "external_network_dependency": False,
    }


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _index_html() -> str:
    return """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>E06.4 Human-Guided Contract Tuning</title><link rel="stylesheet" href="styles.css"></head><body><header><h1>E06.4 Human-Guided Contract Tuning</h1><div><label>Slide <select id="slide"></select></label><label>Compare <select id="mode"><option value="human">Baseline vs Human Tuned</option><option value="e063">E06.3 vs Human Tuned</option></select></label></div></header><main><canvas id="canvas" width="1280" height="720"></canvas><aside><h2>Changed Contract Objects</h2><div id="details"></div></aside></main><script src="variant_diff_viewer.js"></script></body></html>"""


def _viewer_js() -> str:
    return """const W=1280,H=720,targets=[2,9,10,11,14];const c=document.getElementById('canvas'),ctx=c.getContext('2d'),slideSel=document.getElementById('slide'),modeSel=document.getElementById('mode'),details=document.getElementById('details');let base,e063,human;async function j(p){return fetch(p).then(r=>r.json())}function m(s){let out=new Map;(s.objects||[]).forEach(o=>out.set(o.object_id,o));return out}function b(o){let x=o.bbox_norm||{};return{x:(x.x||0)*W,y:(x.y||0)*H,w:(x.w||0)*W,h:(x.h||0)*H}}function changed(before,after){let bm=m(before||{});return(after.objects||[]).filter(o=>{let p=bm.get(o.object_id);return !p||JSON.stringify(p.bbox_norm)!==JSON.stringify(o.bbox_norm)||p.style_override_fill_rgb!==o.style_override_fill_rgb||JSON.stringify(p.e06_4_tuning_parameters||[])!==JSON.stringify(o.e06_4_tuning_parameters||[])})}function draw(){let n=Number(slideSel.value),from=(modeSel.value==='e063'?e063:base).slides.find(s=>s.slide_number===n),to=human.slides.find(s=>s.slide_number===n),rows=changed(from,to);ctx.fillStyle='#071018';ctx.fillRect(0,0,W,H);ctx.strokeStyle='#334155';ctx.strokeRect(0,0,W,H);rows.forEach(o=>{let bb=b(o);ctx.strokeStyle=o.object_type==='semantic_icon'?'#28D7E8':'#F2A900';ctx.lineWidth=2;ctx.strokeRect(bb.x,bb.y,bb.w,bb.h);ctx.fillStyle='#F8FAFC';ctx.fillText((o.object_type||'')+':' +(o.semantic_role||''),bb.x+3,bb.y+12)});details.innerHTML=rows.map(o=>`<div class=row><b>${o.object_id}</b><br>${o.name||''}<br>${(o.e06_4_tuning_parameters||[]).map(p=>p.control_id).join(', ')}</div>`).join('')}async function boot(){[base,e063,human]=await Promise.all([j('layout_contract_baseline.json'),j('layout_contract_e06_3_selected.json'),j('layout_contract_human_tuned.json')]);slideSel.innerHTML=targets.map(n=>`<option>${n}</option>`).join('');draw()}slideSel.onchange=draw;modeSel.onchange=draw;boot();"""


def _styles_css() -> str:
    return "body{margin:0;background:#071018;color:#f8fafc;font-family:Segoe UI,Arial,sans-serif}header{padding:14px 18px;border-bottom:1px solid #243241;display:flex;justify-content:space-between;align-items:center}h1{font-size:18px;margin:0}main{display:grid;grid-template-columns:minmax(0,1fr)360px;gap:16px;padding:16px}canvas{width:100%;height:auto;border:1px solid #243241;background:#020617}aside{border:1px solid #243241;padding:12px;max-height:calc(100vh - 92px);overflow:auto}.row{font-size:12px;line-height:1.35;border-bottom:1px solid #243241;padding:8px 0}select{background:#0f1f2d;color:#fff;border:1px solid #334155;padding:5px 8px;margin-left:8px}"
