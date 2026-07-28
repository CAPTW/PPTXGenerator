"""HTML preview workbench for E06.1 layout contracts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def build_html_workbench(
    output_root: Path,
    contract: dict[str, Any],
    *,
    coordinate_diff: dict[str, Any],
    rendered_diff: dict[str, Any],
    icon_size_report: dict[str, Any],
    icon_anchor_report: dict[str, Any],
    collision_report: dict[str, Any],
) -> dict[str, Any]:
    root = output_root / "html_workbench"
    root.mkdir(parents=True, exist_ok=True)
    (root / "layout_contract_16_slides.json").write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (root / "index.html").write_text(_index_html(), encoding="utf-8")
    (root / "styles.css").write_text(_styles_css(), encoding="utf-8")
    (root / "layout_contract_viewer.js").write_text(
        _viewer_js(contract, coordinate_diff, rendered_diff, icon_size_report, icon_anchor_report, collision_report),
        encoding="utf-8",
    )
    (root / "README.md").write_text(
        "\n".join(
            [
                "# E06.1 Layout Contract Workbench",
                "",
                "Open `index.html` locally to inspect the E06 baseline layout contract.",
                "The workbench has no external network dependency; the contract is also embedded in the viewer JavaScript.",
                "Use category toggles to inspect semantic icon anchors, text zones, source/footer zones, z-order, and drift status.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    required = ["index.html", "layout_contract_viewer.js", "layout_contract_16_slides.json", "styles.css", "README.md"]
    return {
        "schema_name": "html_workbench_manifest",
        "status": "passed" if all((root / name).exists() for name in required) else "failed",
        "html_workbench_path": root.as_posix(),
        "index_path": (root / "index.html").as_posix(),
        "required_files": required,
    }


def _index_html() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>E06.1 Layout Contract Workbench</title>
  <link rel="stylesheet" href="styles.css" />
</head>
<body>
  <header>
    <h1>E06.1 Layout Contract Workbench</h1>
    <div id="summary"></div>
  </header>
  <main>
    <aside>
      <label>Slide <select id="slidePicker"></select></label>
      <fieldset>
        <legend>Overlays</legend>
        <label><input type="checkbox" data-category="semantic_icon" checked /> Icons</label>
        <label><input type="checkbox" data-category="text" checked /> Text</label>
        <label><input type="checkbox" data-category="source_footer" checked /> Source/footer</label>
        <label><input type="checkbox" data-category="table_region" checked /> Tables</label>
        <label><input type="checkbox" data-category="chart_region" checked /> Charts</label>
        <label><input type="checkbox" data-category="card_region" checked /> Cards</label>
      </fieldset>
      <section id="details"></section>
    </aside>
    <section id="canvasWrap">
      <div id="slideCanvas"></div>
    </section>
  </main>
  <script src="layout_contract_viewer.js"></script>
</body>
</html>
"""


def _styles_css() -> str:
    return """* { box-sizing: border-box; }
body { margin: 0; background: #071018; color: #e6edf3; font: 13px/1.4 system-ui, Segoe UI, sans-serif; }
header { padding: 14px 20px; border-bottom: 1px solid #203040; display: flex; align-items: baseline; gap: 24px; }
h1 { font-size: 18px; margin: 0; letter-spacing: 0; }
main { display: grid; grid-template-columns: 300px minmax(640px, 1fr); min-height: calc(100vh - 58px); }
aside { border-right: 1px solid #203040; padding: 16px; overflow: auto; }
fieldset { border: 1px solid #2b4054; margin: 16px 0; padding: 10px; }
label { display: block; margin: 8px 0; }
select { width: 100%; margin-top: 6px; background: #0d1a24; color: #e6edf3; border: 1px solid #2b4054; padding: 6px; }
#canvasWrap { padding: 20px; overflow: auto; }
#slideCanvas { position: relative; width: min(92vw, 1180px); aspect-ratio: 16 / 9; background: #0b131b; border: 1px solid #334a5f; box-shadow: 0 10px 34px rgba(0,0,0,.35); }
.box { position: absolute; border: 1.5px solid; background: rgba(255,255,255,.03); overflow: hidden; }
.semantic_icon { border-color: #28d7e8; background: rgba(40,215,232,.16); }
.text { border-color: #38d99e; background: rgba(56,217,158,.08); }
.source_footer { border-color: #f2a900; background: rgba(242,169,0,.12); }
.table_region { border-color: #c084fc; background: rgba(192,132,252,.10); }
.chart_region { border-color: #60a5fa; background: rgba(96,165,250,.10); }
.card_region { border-color: #f87171; background: rgba(248,113,113,.08); }
.label { position: absolute; left: 2px; top: 1px; right: 2px; color: #fff; text-shadow: 0 1px 2px #000; font-size: 10px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.fail { outline: 3px solid #ff4d4f; }
#details { color: #b8c7d6; }
code { color: #f2a900; }
"""


def _viewer_js(
    contract: dict[str, Any],
    coordinate_diff: dict[str, Any],
    rendered_diff: dict[str, Any],
    icon_size_report: dict[str, Any],
    icon_anchor_report: dict[str, Any],
    collision_report: dict[str, Any],
) -> str:
    payload = {
        "contract": contract,
        "reports": {
            "coordinate": coordinate_diff,
            "rendered": rendered_diff,
            "iconSize": icon_size_report,
            "iconAnchor": icon_anchor_report,
            "collision": collision_report,
        },
    }
    return "const EMBEDDED = " + json.dumps(payload, sort_keys=True) + ";\n" + r"""
const state = { slide: 0, enabled: new Set(["semantic_icon", "text", "source_footer", "table_region", "chart_region", "card_region"]) };

function init() {
  const contract = EMBEDDED.contract;
  const picker = document.getElementById("slidePicker");
  contract.slides.forEach((slide, index) => {
    const opt = document.createElement("option");
    opt.value = index;
    opt.textContent = `${slide.slide_number}. ${slide.archetype_id}`;
    picker.appendChild(opt);
  });
  picker.addEventListener("change", () => { state.slide = Number(picker.value); render(); });
  document.querySelectorAll("input[data-category]").forEach((box) => {
    box.addEventListener("change", () => {
      if (box.checked) state.enabled.add(box.dataset.category);
      else state.enabled.delete(box.dataset.category);
      render();
    });
  });
  const summary = contract.summary;
  document.getElementById("summary").innerHTML = `slides <code>${summary.slide_count}</code> objects <code>${summary.object_count}</code> icons <code>${summary.semantic_icon_count}</code>`;
  render();
}

function render() {
  const contract = EMBEDDED.contract;
  const slide = contract.slides[state.slide];
  const canvas = document.getElementById("slideCanvas");
  canvas.innerHTML = "";
  const failures = new Set([
    ...EMBEDDED.reports.coordinate.failures.map((f) => f.object_id),
    ...EMBEDDED.reports.iconSize.failures.map((f) => f.object_id),
    ...EMBEDDED.reports.iconAnchor.failures.map((f) => f.object_id),
  ].filter(Boolean));
  slide.objects.forEach((obj) => {
    if (!state.enabled.has(obj.object_type)) return;
    const b = obj.bbox_norm;
    const el = document.createElement("div");
    el.className = `box ${obj.object_type}${failures.has(obj.object_id) ? " fail" : ""}`;
    el.style.left = `${b.x * 100}%`;
    el.style.top = `${b.y * 100}%`;
    el.style.width = `${b.w * 100}%`;
    el.style.height = `${b.h * 100}%`;
    const label = document.createElement("div");
    label.className = "label";
    label.textContent = obj.object_type === "semantic_icon" ? `${obj.semantic_role} / ${obj.size_token}` : obj.name;
    el.appendChild(label);
    el.title = `${obj.object_id}\n${obj.name}\nz=${obj.z_order}`;
    canvas.appendChild(el);
  });
  document.getElementById("details").innerHTML = `
    <h2>${slide.slide_number}. ${slide.archetype_id}</h2>
    <p>Objects: <code>${slide.objects.length}</code></p>
    <p>Icons: <code>${slide.semantic_icon_slots.length}</code></p>
    <p>Text zones: <code>${slide.text_zones.length}</code></p>
    <p>Source/footer zones: <code>${slide.source_footer_regions.length}</code></p>
    <p>Coordinate diff failures: <code>${EMBEDDED.reports.coordinate.coordinate_diff_failure_count}</code></p>
    <p>Rendered bbox failures: <code>${EMBEDDED.reports.rendered.rendered_bbox_failure_count}</code></p>
    <p>Icon size failures: <code>${EMBEDDED.reports.iconSize.icon_size_token_failure_count}</code></p>
    <p>Icon anchor failures: <code>${EMBEDDED.reports.iconAnchor.icon_anchor_failure_count}</code></p>
    <p>Text collision failures: <code>${EMBEDDED.reports.collision.text_collision_failure_count}</code></p>
  `;
}

init();
"""
