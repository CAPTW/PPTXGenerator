"""Official HTML screenshot capture contract and bounded DeckCompiler adapter.

The external ``slide-visual-polish-qa`` implementation remains the producer.
This module supplies deck-specific dimension authority, readiness observation,
per-slide process isolation, bounded attempts, and current-output manifests.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import struct
import subprocess
from typing import Any, Callable, Mapping, Sequence

from ..identity import content_sha256, stable_id
from ..manifest_io import write_json
from .contracts import sha256_file


SCHEMA_NAME = "html_screenshot_capture_manifest"
SCHEMA_VERSION = "1.0.0"
CAPTURE_CONTRACT_ID = "slide-visual-polish-qa-natural-source-pixels-v1"
FAULT_STATES = frozenset({"baseline", "faulty", "repaired"})
RETRYABLE_REASONS = frozenset(
    {
        "browser_startup_failure",
        "navigation_timeout",
        "official_ready_condition_timeout",
        "browser_process_crash",
        "missing_output_after_success",
        "locked_profile_or_cleanup_failure",
    }
)
NONRETRYABLE_REASONS = frozenset(
    {
        "dimension_mismatch",
        "html_hash_mismatch",
        "wrong_slide_id",
        "stale_output",
        "missing_local_asset",
        "off_canvas_geometry",
        "unsupported_output_format",
        "scaled_output_rejection",
        "unknown_nonretryable_failure",
    }
)
DEFAULT_ATTEMPT_POLICY: dict[str, Any] = {
    "max_attempts_per_slide": 2,
    "automatic_hidden_retry": False,
    "explicit_retry": True,
    "parallelism": 1,
    "retryable_reasons": sorted(RETRYABLE_REASONS),
    "nonretryable_reasons": sorted(NONRETRYABLE_REASONS),
}


class HtmlCaptureError(RuntimeError):
    """Fail-closed capture-contract error carrying a stable blocker fragment."""


@dataclass(frozen=True)
class DimensionAuthority:
    width: int
    height: int
    sources: tuple[str, ...]
    html_body_dimensions: Mapping[str, int]
    slide_css_dimensions: Mapping[str, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "width": self.width,
            "height": self.height,
            "sources": list(self.sources),
            "html_body_dimensions": dict(self.html_body_dimensions),
            "slide_css_dimensions": dict(self.slide_css_dimensions),
        }


class _BodyDimensionParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.width: int | None = None
        self.height: int | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "body" or (
            self.width is not None and self.height is not None
        ):
            return
        values = dict(attrs)
        try:
            self.width = (
                int(values["data-deck-pxw"])
                if values.get("data-deck-pxw") is not None
                else None
            )
            self.height = (
                int(values["data-deck-pxh"])
                if values.get("data-deck-pxh") is not None
                else None
            )
        except (TypeError, ValueError) as exc:
            raise HtmlCaptureError(
                "BLOCKED_HTML_SCREENSHOT_DIMENSION_AUTHORITY_UNKNOWN: invalid body dimensions"
            ) from exc


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def derive_dimension_authority(html_path: str | Path) -> DimensionAuthority:
    """Resolve the current deck's natural pixel dimensions from two sources."""

    html = Path(html_path).resolve()
    if not html.is_file():
        raise HtmlCaptureError(
            f"BLOCKED_HTML_SCREENSHOT_DIMENSION_AUTHORITY_UNKNOWN: HTML missing: {html}"
        )
    text = html.read_text(encoding="utf-8", errors="strict")
    parser = _BodyDimensionParser()
    parser.feed(text)
    css: tuple[int, int] | None = None
    for match in re.finditer(r"(?is)(?<![\w-])\.slide\s*\{([^}]*)\}", text):
        block = match.group(1)
        width_match = re.search(
            r"(?i)(?:^|;)\s*width\s*:\s*([0-9]+)px\s*(?:;|$)", block
        )
        height_match = re.search(
            r"(?i)(?:^|;)\s*height\s*:\s*([0-9]+)px\s*(?:;|$)", block
        )
        if width_match and height_match:
            css = (int(width_match.group(1)), int(height_match.group(1)))
            break
    body = (parser.width, parser.height)
    if (
        None in body
        or css is None
        or min(int(body[0] or 0), int(body[1] or 0), css[0], css[1]) <= 0
    ):
        raise HtmlCaptureError(
            "BLOCKED_HTML_SCREENSHOT_DIMENSION_AUTHORITY_UNKNOWN: body/CSS dimension source missing"
        )
    body_pair = (int(body[0]), int(body[1]))
    if body_pair != css:
        raise HtmlCaptureError(
            "BLOCKED_HTML_SCREENSHOT_DIMENSION_AUTHORITY_UNKNOWN: "
            f"body {body_pair[0]}x{body_pair[1]} != slide CSS {css[0]}x{css[1]}"
        )
    return DimensionAuthority(
        width=body_pair[0],
        height=body_pair[1],
        sources=("html_body_data_attributes", "slide_css_pixels"),
        html_body_dimensions={"width": body_pair[0], "height": body_pair[1]},
        slide_css_dimensions={"width": css[0], "height": css[1]},
    )


def png_dimensions(path: str | Path) -> tuple[int, int]:
    png = Path(path)
    try:
        header = png.read_bytes()[:24]
    except OSError as exc:
        raise HtmlCaptureError(
            f"BLOCKED_HTML_SCREENSHOT_PNG_DECODE: {png}: {exc}"
        ) from exc
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        raise HtmlCaptureError(
            f"BLOCKED_HTML_SCREENSHOT_PNG_DECODE: invalid PNG header: {png}"
        )
    width, height = struct.unpack(">II", header[16:24])
    if width <= 0 or height <= 0:
        raise HtmlCaptureError(
            f"BLOCKED_HTML_SCREENSHOT_PNG_DECODE: invalid PNG dimensions: {png}"
        )
    return int(width), int(height)


def classify_capture_failure(
    returncode: int | None, stdout: str, stderr: str, output_exists: bool
) -> str:
    text = f"{stdout}\n{stderr}".lower()
    if "dimensions" in text and (
        "do not match expected" in text or "dimension mismatch" in text
    ):
        return "dimension_mismatch"
    if "current html hash mismatch" in text or "html parent hash mismatch" in text:
        return "html_hash_mismatch"
    if "wrong slide" in text:
        return "wrong_slide_id"
    if "stale screenshot" in text or "stale output" in text:
        return "stale_output"
    if "missing local asset" in text or "local asset" in text and "missing" in text:
        return "missing_local_asset"
    if "off-canvas" in text or "off_canvas" in text:
        return "off_canvas_geometry"
    if "unsupported output format" in text or "unsupported format" in text:
        return "unsupported_output_format"
    if "scaled" in text and "rejected" in text:
        return "scaled_output_rejection"
    if returncode == 0 and not output_exists:
        return "missing_output_after_success"
    if (
        "user data directory is already in use" in text
        or "profile" in text
        and "lock" in text
    ):
        return "locked_profile_or_cleanup_failure"
    if "ready condition" in text and "timeout" in text:
        return "official_ready_condition_timeout"
    if "page.goto" in text and "timeout" in text or "navigation timeout" in text:
        return "navigation_timeout"
    if "crash" in text or "target closed" in text or "browser closed" in text:
        return "browser_process_crash"
    if (
        "failed to launch" in text
        or "browser startup" in text
        or "executable doesn't exist" in text
    ):
        return "browser_startup_failure"
    return "unknown_nonretryable_failure"


def validate_attempt_policy(policy: Mapping[str, Any]) -> None:
    required = {
        "max_attempts_per_slide": 2,
        "automatic_hidden_retry": False,
        "explicit_retry": True,
        "parallelism": 1,
    }
    if any(policy.get(key) != value for key, value in required.items()):
        raise HtmlCaptureError(
            "BLOCKED_HTML_SCREENSHOT_ATTEMPT_POLICY: bounded serial policy mismatch"
        )
    if set(policy.get("retryable_reasons", [])) != RETRYABLE_REASONS:
        raise HtmlCaptureError(
            "BLOCKED_HTML_SCREENSHOT_ATTEMPT_POLICY: retryable reason set mismatch"
        )
    if set(policy.get("nonretryable_reasons", [])) != NONRETRYABLE_REASONS:
        raise HtmlCaptureError(
            "BLOCKED_HTML_SCREENSHOT_ATTEMPT_POLICY: nonretryable reason set mismatch"
        )


def can_retry(
    reason: str, attempt_number: int, policy: Mapping[str, Any] = DEFAULT_ATTEMPT_POLICY
) -> bool:
    validate_attempt_policy(policy)
    return reason in RETRYABLE_REASONS and attempt_number < int(
        policy["max_attempts_per_slide"]
    )


def validate_readiness_probe(
    payload: Mapping[str, Any], *, slide_id: str, width: int, height: int
) -> None:
    rect = payload.get("slide_bounding_rect", {})
    viewport = payload.get("viewport", {})
    passed = all(
        (
            payload.get("slide_id") == slide_id,
            payload.get("document_ready_state") == "complete",
            payload.get("fonts_ready") is True,
            payload.get("images_ready") is True,
            payload.get("layout_stable") is True,
            payload.get("target_visible") is True,
            payload.get("qa_static_mode") is True,
            payload.get("remote_network_dependency") is False,
            payload.get("device_scale_factor") == 1,
            viewport.get("width") == width,
            viewport.get("height") == height,
            rect.get("width") == width,
            rect.get("height") == height,
        )
    )
    if not passed:
        raise HtmlCaptureError(
            f"BLOCKED_HTML_SCREENSHOT_READY_CONDITION: {slide_id}: {dict(payload)}"
        )


def bind_attempt_record(record: Mapping[str, Any]) -> dict[str, Any]:
    payload = {key: value for key, value in record.items() if key != "record_hash"}
    payload["record_hash"] = content_sha256(payload)
    return payload


def _attempt_hash_valid(record: Mapping[str, Any]) -> bool:
    expected = record.get("record_hash")
    return isinstance(expected, str) and expected == content_sha256(
        {key: value for key, value in record.items() if key != "record_hash"}
    )


def validate_attempt_record(
    record: Mapping[str, Any],
    *,
    runtime_root: str | Path,
    run_id: str,
    html_sha256: str,
    expected_slide_id: str | None = None,
) -> None:
    if not _attempt_hash_valid(record):
        raise HtmlCaptureError(
            "BLOCKED_HTML_SCREENSHOT_ATTEMPT_HASH: record hash mismatch"
        )
    if record.get("run_id") != run_id:
        raise HtmlCaptureError("BLOCKED_HTML_SCREENSHOT_RUN_ID: cross-run attempt")
    if record.get("current_html_sha256") != html_sha256:
        raise HtmlCaptureError(
            "BLOCKED_HTML_SCREENSHOT_HTML_HASH: parent HTML mismatch"
        )
    slide_id = str(record.get("slide_id", ""))
    if expected_slide_id is not None and slide_id != expected_slide_id:
        raise HtmlCaptureError("BLOCKED_HTML_SCREENSHOT_SLIDE_ID: wrong slide")
    if not re.fullmatch(r"slide-[0-9]{3}", slide_id):
        raise HtmlCaptureError("BLOCKED_HTML_SCREENSHOT_SLIDE_ID: invalid slide ID")
    output_value = record.get("output_path")
    if not isinstance(output_value, str) or not _inside(
        Path(output_value), Path(runtime_root)
    ):
        raise HtmlCaptureError(
            "BLOCKED_HTML_SCREENSHOT_OUTPUT_PATH: output outside current runtime"
        )
    requested = record.get("requested_dimensions", {})
    actual = record.get("actual_dimensions", {})
    if record.get("selected") is True:
        if record.get("status") != "PASS" or requested != actual:
            raise HtmlCaptureError(
                "BLOCKED_HTML_SCREENSHOT_DIMENSION_MISMATCH: selected attempt is not exact"
            )
        output = Path(output_value)
        if not output.is_file() or sha256_file(output) != record.get("output_sha256"):
            raise HtmlCaptureError(
                "BLOCKED_HTML_SCREENSHOT_OUTPUT_HASH: selected output missing/mismatched"
            )
        if png_dimensions(output) != (requested.get("width"), requested.get("height")):
            raise HtmlCaptureError(
                "BLOCKED_HTML_SCREENSHOT_DIMENSION_MISMATCH: PNG dimensions mismatch"
            )
        validate_readiness_probe(
            record.get("readiness", {}),
            slide_id=slide_id,
            width=int(requested.get("width", 0)),
            height=int(requested.get("height", 0)),
        )


def _manifest_hash(payload: Mapping[str, Any]) -> str:
    return content_sha256(
        {key: value for key, value in payload.items() if key != "manifest_hash"}
    )


def verify_capture_manifest_hash(payload: Mapping[str, Any]) -> bool:
    expected = payload.get("manifest_hash")
    return isinstance(expected, str) and expected == _manifest_hash(payload)


def build_capture_manifest(
    *,
    run_id: str,
    fault_state: str,
    runtime_root: str | Path,
    source_html: str | Path,
    browser_identity: str,
    browser_version: str,
    dimension_authority: DimensionAuthority,
    attempts: Sequence[Mapping[str, Any]],
    ordered_slide_ids: Sequence[str],
    created_at: str,
) -> dict[str, Any]:
    records = [dict(row) for row in attempts]
    selected = [
        row
        for row in records
        if row.get("selected") is True and row.get("status") == "PASS"
    ]
    selected_slides = {str(row.get("slide_id")) for row in selected}
    ordered = list(ordered_slide_ids)
    missing_count = len([slide for slide in ordered if slide not in selected_slides])
    timeout_count = sum(1 for row in records if row.get("timeout_stage"))
    dimension_mismatch_count = sum(
        1 for row in records if row.get("reason") == "dimension_mismatch"
    )
    stale_count = sum(1 for row in records if row.get("reason") == "stale_output")
    cross_run_count = sum(1 for row in records if row.get("run_id") != run_id)
    payload: dict[str, Any] = {
        "schema_name": SCHEMA_NAME,
        "schema_version": SCHEMA_VERSION,
        "manifest_id": stable_id(
            "htmlcap", run_id, fault_state, str(source_html), ordered
        ),
        "run_id": run_id,
        "fault_state": fault_state,
        "runtime_root": str(Path(runtime_root).resolve()),
        "source_html_path": str(Path(source_html).resolve()),
        "source_html_sha256": sha256_file(Path(source_html)),
        "browser_identity": browser_identity,
        "browser_version": browser_version,
        "capture_contract_id": CAPTURE_CONTRACT_ID,
        "expected_dimension_authority": dimension_authority.to_dict(),
        "capture_mode": "official-visible-slide-selector",
        "slide_count": len(ordered),
        "ordered_slide_ids": ordered,
        "attempt_policy": deepcopy_json(DEFAULT_ATTEMPT_POLICY),
        "records": records,
        "missing_count": missing_count,
        "timeout_count": timeout_count,
        "dimension_mismatch_count": dimension_mismatch_count,
        "stale_record_count": stale_count,
        "cross_run_reuse_count": cross_run_count,
        "selected_screenshot_count": len(selected),
        "validation_status": "PASS"
        if not any(
            (
                missing_count,
                timeout_count,
                dimension_mismatch_count,
                stale_count,
                cross_run_count,
            )
        )
        and len(selected) == len(ordered)
        else "BLOCKED",
        "external_skill_modified": False,
        "stretch_applied": False,
        "created_at": created_at,
        "timezone": "Asia/Seoul",
    }
    payload["manifest_hash"] = _manifest_hash(payload)
    return payload


def deepcopy_json(value: Any) -> Any:
    return json.loads(json.dumps(value))


def validate_capture_manifest(
    payload: Mapping[str, Any],
    *,
    runtime_root: str | Path,
    require_full_deck: bool = False,
) -> dict[str, Any]:
    if (
        payload.get("schema_name") != SCHEMA_NAME
        or payload.get("schema_version") != SCHEMA_VERSION
    ):
        raise HtmlCaptureError(
            "BLOCKED_HTML_SCREENSHOT_MANIFEST_SCHEMA: identity mismatch"
        )
    fault_state = payload.get("fault_state")
    if fault_state not in FAULT_STATES:
        raise HtmlCaptureError("BLOCKED_HTML_SCREENSHOT_FAULT_STATE: unsupported state")
    run_id = str(payload.get("run_id", ""))
    if not run_id:
        raise HtmlCaptureError("BLOCKED_HTML_SCREENSHOT_RUN_ID: missing run ID")
    root = Path(runtime_root).resolve()
    source = Path(str(payload.get("source_html_path", ""))).resolve()
    if not _inside(source, root):
        raise HtmlCaptureError(
            "BLOCKED_HTML_SCREENSHOT_SOURCE_HTML_PATH: HTML outside current runtime"
        )
    if not source.is_file() or sha256_file(source) != payload.get("source_html_sha256"):
        raise HtmlCaptureError(
            "BLOCKED_HTML_SCREENSHOT_HTML_HASH: manifest parent HTML mismatch"
        )
    ordered = payload.get("ordered_slide_ids")
    if (
        not isinstance(ordered, list)
        or not ordered
        or len(set(ordered)) != len(ordered)
    ):
        raise HtmlCaptureError(
            "BLOCKED_HTML_SCREENSHOT_SLIDE_ORDER: missing/duplicate slide IDs"
        )
    if any(
        not isinstance(slide_id, str) or not re.fullmatch(r"slide-[0-9]{3}", slide_id)
        for slide_id in ordered
    ):
        raise HtmlCaptureError("BLOCKED_HTML_SCREENSHOT_SLIDE_ORDER: invalid slide ID")
    slide_numbers = [int(slide_id.rsplit("-", 1)[1]) for slide_id in ordered]
    if any(slide <= 0 for slide in slide_numbers) or slide_numbers != sorted(
        slide_numbers
    ):
        raise HtmlCaptureError(
            "BLOCKED_HTML_SCREENSHOT_SLIDE_ORDER: nondeterministic slide order"
        )
    if require_full_deck and ordered != [f"slide-{index:03d}" for index in range(1, 7)]:
        raise HtmlCaptureError(
            "BLOCKED_HTML_SCREENSHOT_SELECTED_COUNT: full deck requires slides 1-6"
        )
    validate_attempt_policy(payload.get("attempt_policy", {}))
    records = payload.get("records")
    if not isinstance(records, list):
        raise HtmlCaptureError(
            "BLOCKED_HTML_SCREENSHOT_MANIFEST_SCHEMA: records missing"
        )
    selected = [
        row
        for row in records
        if row.get("selected") is True and row.get("status") == "PASS"
    ]
    selected_order = [str(row.get("slide_id")) for row in selected]
    if selected_order != ordered or int(
        payload.get("selected_screenshot_count", -1)
    ) != len(ordered):
        raise HtmlCaptureError(
            "BLOCKED_HTML_SCREENSHOT_SELECTED_COUNT: selected screenshots do not cover ordered slides"
        )
    output_hashes = [str(row.get("output_sha256")) for row in selected]
    if len(set(output_hashes)) != len(output_hashes):
        raise HtmlCaptureError(
            "BLOCKED_HTML_SCREENSHOT_DUPLICATE_OUTPUT: selected output hash reused"
        )
    for record in records:
        validate_attempt_record(
            record,
            runtime_root=root,
            run_id=run_id,
            html_sha256=str(payload.get("source_html_sha256")),
        )
    counters = (
        int(payload.get("missing_count", -1)),
        int(payload.get("timeout_count", -1)),
        int(payload.get("dimension_mismatch_count", -1)),
        int(payload.get("stale_record_count", -1)),
    )
    if any(counters) or payload.get("validation_status") != "PASS":
        raise HtmlCaptureError(
            "BLOCKED_HTML_SCREENSHOT_MANIFEST_COUNTS: unresolved prerequisite count"
        )
    if int(payload.get("cross_run_reuse_count", -1)) != 0:
        raise HtmlCaptureError(
            "BLOCKED_HTML_SCREENSHOT_CROSS_RUN: cross-run reuse detected"
        )
    if (
        payload.get("external_skill_modified") is not False
        or payload.get("stretch_applied") is not False
    ):
        raise HtmlCaptureError(
            "BLOCKED_HTML_SCREENSHOT_CONTRACT_UNSUPPORTED: prohibited capture mutation"
        )
    if not verify_capture_manifest_hash(payload):
        raise HtmlCaptureError(
            "BLOCKED_HTML_SCREENSHOT_MANIFEST_HASH: manifest hash mismatch"
        )
    return dict(payload)


def inspect_html_readiness(
    html_path: str | Path,
    slides: Sequence[int],
    *,
    width: int,
    height: int,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Observe readiness without changing HTML bytes or depending on network."""

    html = Path(html_path).resolve()
    before_hash = sha256_file(html)
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except Exception as exc:  # pragma: no cover - environment gate
        raise HtmlCaptureError(
            f"BLOCKED_HTML_SCREENSHOT_CONTRACT_UNSUPPORTED: Playwright unavailable: {exc}"
        ) from exc
    rows: list[dict[str, Any]] = []
    browser_meta: dict[str, str] = {}
    with sync_playwright() as playwright:  # pragma: no cover - browser integration
        browser = playwright.chromium.launch()
        browser_meta = {
            "identity": "Playwright Chromium",
            "version": browser.version,
            "executable_path": playwright.chromium.executable_path,
        }
        try:
            for slide in slides:
                page = browser.new_page(
                    viewport={"width": width, "height": height}, device_scale_factor=1
                )
                remote: list[str] = []
                page.on(
                    "request",
                    lambda request: remote.append(request.url)
                    if request.url.startswith(("http://", "https://"))
                    else None,
                )
                try:
                    page.goto(
                        f"{html.as_uri()}?qa=1", wait_until="load", timeout=30_000
                    )
                    page.wait_for_function(
                        "document.readyState === 'complete'", timeout=10_000
                    )
                    page.evaluate(
                        "document.fonts ? document.fonts.ready : Promise.resolve()"
                    )
                    images_ready = bool(
                        page.evaluate(
                            "Array.from(document.images).every(i => i.complete && i.naturalWidth > 0)"
                        )
                    )
                    probe = page.evaluate(
                        """
                        async ({slide, width, height}) => {
                          const el = document.querySelector(`#slide-${slide}`) || document.querySelector(`[data-slide="${slide}"]`);
                          if (!el) return { target_visible: false };
                          const first = el.getBoundingClientRect();
                          await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
                          const second = el.getBoundingClientRect();
                          const style = getComputedStyle(el);
                          const de = document.documentElement;
                          const body = document.body;
                          const rect = r => ({x:r.x,y:r.y,width:r.width,height:r.height,right:r.right,bottom:r.bottom});
                          return {
                            slide_id: `slide-${String(slide).padStart(3,'0')}`,
                            document_ready_state: document.readyState,
                            fonts_ready: !document.fonts || document.fonts.status === 'loaded',
                            layout_stable: JSON.stringify(rect(first)) === JSON.stringify(rect(second)),
                            target_visible: style.visibility !== 'hidden' && style.display !== 'none' && second.width > 0 && second.height > 0,
                            qa_static_mode: body.dataset.qaStatic === '1' || de.dataset.qaStatic === '1',
                            viewport: {width: innerWidth, height: innerHeight},
                            browser_window: {inner_width:innerWidth,inner_height:innerHeight,outer_width:outerWidth,outer_height:outerHeight},
                            device_scale_factor: devicePixelRatio,
                            zoom: visualViewport ? visualViewport.scale : 1,
                            document_element: {client_width:de.clientWidth,client_height:de.clientHeight,scroll_width:de.scrollWidth,scroll_height:de.scrollHeight},
                            body: {client_width:body.clientWidth,client_height:body.clientHeight,scroll_width:body.scrollWidth,scroll_height:body.scrollHeight},
                            slide_bounding_rect: rect(second),
                            slide_css: {width:style.width,height:style.height,border:style.border,padding:style.padding,margin:style.margin,transform:style.transform,overflow:style.overflow,box_sizing:style.boxSizing},
                          };
                        }
                        """,
                        {"slide": slide, "width": width, "height": height},
                    )
                    probe["images_ready"] = images_ready
                    probe["remote_network_dependency"] = bool(remote)
                    validate_readiness_probe(
                        probe, slide_id=f"slide-{slide:03d}", width=width, height=height
                    )
                    rows.append(probe)
                finally:
                    page.close()
        finally:
            browser.close()
    if sha256_file(html) != before_hash:
        raise HtmlCaptureError(
            "BLOCKED_CANONICAL_BASELINE_MUTATION: readiness probe changed HTML"
        )
    return rows, browser_meta


@dataclass(frozen=True)
class _ProcessOutcome:
    returncode: int | None
    stdout: str
    stderr: str
    pid: int
    timeout_stage: str | None
    cleanup_status: str
    started_at: str
    ended_at: str


def _run_process(
    command: Sequence[str], *, cwd: Path, env: Mapping[str, str], timeout_seconds: int
) -> _ProcessOutcome:
    started = datetime.now(timezone.utc).isoformat()
    process = subprocess.Popen(
        [str(value) for value in command],
        cwd=cwd,
        env=dict(env),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    timeout_stage: str | None = None
    cleanup = "PASS"
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        timeout_stage = "child_process_wait"
        process.kill()
        stdout, stderr = process.communicate()
        cleanup = "PASS" if process.poll() is not None else "BLOCKED"
    ended = datetime.now(timezone.utc).isoformat()
    return _ProcessOutcome(
        process.returncode,
        stdout,
        stderr,
        process.pid,
        timeout_stage,
        cleanup,
        started,
        ended,
    )


def capture_official_html_screenshots(
    *,
    runtime_root: str | Path,
    project_root: str | Path,
    html_path: str | Path,
    out_dir: str | Path,
    external_skill_root: str | Path,
    python_executable: str | Path,
    slides: Sequence[int],
    run_id: str,
    fault_state: str,
    created_at: str,
    logs_dir: str | Path,
    manifest_path: str | Path,
    environment: Mapping[str, str],
    stage_name: str,
    timeout_seconds: int = 180,
    process_runner: Callable[..., _ProcessOutcome] = _run_process,
    readiness_inspector: Callable[
        ..., tuple[list[dict[str, Any]], dict[str, str]]
    ] = inspect_html_readiness,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Invoke the pinned official producer once per slide and validate outputs."""

    validate_attempt_policy(DEFAULT_ATTEMPT_POLICY)
    runtime = Path(runtime_root).resolve()
    project = Path(project_root).resolve()
    html = Path(html_path).resolve()
    output_root = Path(out_dir).resolve()
    logs = Path(logs_dir).resolve()
    manifest_file = Path(manifest_path).resolve()
    if not all(
        _inside(path, runtime)
        for path in (project, html, output_root, logs, manifest_file)
    ):
        raise HtmlCaptureError(
            "BLOCKED_HTML_SCREENSHOT_CROSS_RUN: capture path outside current runtime"
        )
    if fault_state not in FAULT_STATES:
        raise HtmlCaptureError("BLOCKED_HTML_SCREENSHOT_FAULT_STATE: unsupported state")
    expected_slides = tuple(sorted(set(int(slide) for slide in slides)))
    if expected_slides != tuple(int(slide) for slide in slides) or any(
        slide <= 0 for slide in expected_slides
    ):
        raise HtmlCaptureError(
            "BLOCKED_HTML_SCREENSHOT_SLIDE_ORDER: slides must be unique and ordered"
        )
    authority = derive_dimension_authority(html)
    html_hash = sha256_file(html)
    readiness, browser = readiness_inspector(
        html, expected_slides, width=authority.width, height=authority.height
    )
    readiness_by_slide = {row["slide_id"]: row for row in readiness}
    script = (
        Path(external_skill_root).resolve()
        / "slide-visual-polish-qa"
        / "scripts"
        / "capture_html_screenshot.py"
    )
    if not script.is_file():
        raise HtmlCaptureError(
            f"BLOCKED_HTML_SCREENSHOT_CONTRACT_UNSUPPORTED: official script missing: {script}"
        )
    logs.mkdir(parents=True, exist_ok=True)
    attempts: list[dict[str, Any]] = []
    commands: list[dict[str, Any]] = []
    for slide in expected_slides:
        slide_id = f"slide-{slide:03d}"
        prior_attempt_id: str | None = None
        next_reason = "initial_capture"
        selected = False
        for attempt_number in range(
            1, int(DEFAULT_ATTEMPT_POLICY["max_attempts_per_slide"]) + 1
        ):
            attempt_id = f"{run_id}-{slide_id}-attempt-{attempt_number:02d}"
            output = (
                output_root / f"slide{slide:02d}" / "visual_qa" / "html_screenshot.png"
            )
            metadata_path = output.with_name("html_screenshot_metadata.json")
            for stale_path in (output, metadata_path):
                if stale_path.exists():
                    stale_path.unlink()
            command = [
                str(Path(python_executable).resolve()),
                str(script),
                "--html",
                str(html),
                "--out-dir",
                str(output_root),
                "--slides",
                str(slide),
                "--width",
                str(authority.width),
                "--height",
                str(authority.height),
                "--project",
                str(project),
            ]
            outcome = process_runner(
                command, cwd=project, env=environment, timeout_seconds=timeout_seconds
            )
            label = f"{stage_name}-slide-{slide:03d}-attempt-{attempt_number:02d}"
            stdout_path = logs / f"{label}.stdout.log"
            stderr_path = logs / f"{label}.stderr.log"
            stdout_path.write_text(outcome.stdout, encoding="utf-8")
            stderr_path.write_text(outcome.stderr, encoding="utf-8")
            output_exists = output.is_file() and output.stat().st_size > 0
            failure_reason = None
            actual_dimensions: dict[str, int] | None = None
            output_hash: str | None = None
            metadata: dict[str, Any] = {}
            if output_exists:
                output_hash = sha256_file(output)
                try:
                    width, height = png_dimensions(output)
                    actual_dimensions = {"width": width, "height": height}
                except HtmlCaptureError:
                    failure_reason = "unsupported_output_format"
            if outcome.timeout_stage:
                failure_reason = (
                    "navigation_timeout"
                    if not output_exists
                    else "browser_process_crash"
                )
            elif outcome.returncode != 0:
                failure_reason = classify_capture_failure(
                    outcome.returncode, outcome.stdout, outcome.stderr, output_exists
                )
            elif not output_exists:
                failure_reason = "missing_output_after_success"
            elif metadata_path.is_file():
                try:
                    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                except (OSError, ValueError, json.JSONDecodeError):
                    failure_reason = "stale_output"
            else:
                failure_reason = "stale_output"
            if failure_reason is None:
                expected = {"width": authority.width, "height": authority.height}
                if (
                    actual_dimensions != expected
                    or metadata.get("actualScreenshotDimensions") != expected
                ):
                    failure_reason = "dimension_mismatch"
                elif metadata.get("htmlSha256") != html_hash:
                    failure_reason = "html_hash_mismatch"
                elif (
                    metadata.get("slide") != slide
                    or metadata.get("sourceSlideId") != slide
                ):
                    failure_reason = "wrong_slide_id"
                elif metadata.get("outputSha256") != output_hash:
                    failure_reason = "stale_output"
                elif (
                    metadata.get("dimensionCheck") != "exact"
                    or metadata.get("modifiedHtml") is not False
                ):
                    failure_reason = "scaled_output_rejection"
            record = {
                "attempt_id": attempt_id,
                "prior_attempt_id": prior_attempt_id,
                "run_id": run_id,
                "fault_state": fault_state,
                "slide_id": slide_id,
                "attempt_number": attempt_number,
                "reason": failure_reason or next_reason,
                "current_html_sha256": html_hash,
                "browser_identity": browser.get(
                    "identity", metadata.get("tool", "unknown")
                ),
                "browser_version": browser.get("version", "unknown"),
                "browser_executable_path": browser.get("executable_path"),
                "requested_dimensions": {
                    "width": authority.width,
                    "height": authority.height,
                },
                "actual_dimensions": actual_dimensions,
                "exit_status": outcome.returncode,
                "process_id": outcome.pid,
                "stage_started_at": outcome.started_at,
                "stage_ended_at": outcome.ended_at,
                "configured_timeout_seconds": timeout_seconds,
                "timeout_stage": outcome.timeout_stage,
                "stdout_sha256": hashlib.sha256(
                    outcome.stdout.encode("utf-8")
                ).hexdigest(),
                "stderr_sha256": hashlib.sha256(
                    outcome.stderr.encode("utf-8")
                ).hexdigest(),
                "stdout_log": str(stdout_path),
                "stderr_log": str(stderr_path),
                "output_path": str(output),
                "output_sha256": output_hash,
                "selected": failure_reason is None,
                "status": "PASS" if failure_reason is None else "REJECTED",
                "cleanup_status": outcome.cleanup_status,
                "readiness": readiness_by_slide[slide_id],
                "official_metadata_sha256": sha256_file(metadata_path)
                if metadata_path.is_file()
                else None,
                "official_tool": metadata.get("tool"),
                "external_skill_modified": False,
                "stretch_applied": False,
            }
            attempts.append(bind_attempt_record(record))
            commands.append(
                {
                    "stage": f"{stage_name} {slide_id} attempt {attempt_number}",
                    "executable": Path(command[0]).name,
                    "returncode": outcome.returncode,
                    "accepted_returncodes": [0],
                    "stdout_log": str(stdout_path.relative_to(runtime)).replace(
                        "\\", "/"
                    ),
                    "stderr_log": str(stderr_path.relative_to(runtime)).replace(
                        "\\", "/"
                    ),
                    "status": "PASS" if failure_reason is None else "BLOCKED",
                    "attempt_id": attempt_id,
                    "timeout_stage": outcome.timeout_stage,
                }
            )
            if failure_reason is None:
                selected = True
                break
            if not can_retry(failure_reason, attempt_number):
                blocker = (
                    "BLOCKED_HTML_SCREENSHOT_DIMENSION_MISMATCH"
                    if failure_reason == "dimension_mismatch"
                    else "BLOCKED_HTML_SCREENSHOT_CAPTURE_TIMEOUT"
                    if outcome.timeout_stage
                    else "BLOCKED_HTML_SCREENSHOT_EVIDENCE_UNAVAILABLE"
                )
                raise HtmlCaptureError(
                    f"{blocker}: {slide_id} attempt {attempt_number}: {failure_reason}"
                )
            prior_attempt_id = attempt_id
            next_reason = failure_reason
        if not selected:
            raise HtmlCaptureError(
                f"BLOCKED_HTML_SCREENSHOT_EVIDENCE_UNAVAILABLE: {slide_id} exhausted attempts"
            )
    manifest = build_capture_manifest(
        run_id=run_id,
        fault_state=fault_state,
        runtime_root=runtime,
        source_html=html,
        browser_identity=browser.get("identity", "unknown"),
        browser_version=browser.get("version", "unknown"),
        dimension_authority=authority,
        attempts=attempts,
        ordered_slide_ids=tuple(f"slide-{slide:03d}" for slide in expected_slides),
        created_at=created_at,
    )
    validate_capture_manifest(
        manifest,
        runtime_root=runtime,
        require_full_deck=expected_slides == tuple(range(1, 7)),
    )
    write_json(manifest_file, manifest)
    return manifest, commands


__all__ = [
    "CAPTURE_CONTRACT_ID",
    "DEFAULT_ATTEMPT_POLICY",
    "DimensionAuthority",
    "HtmlCaptureError",
    "bind_attempt_record",
    "build_capture_manifest",
    "can_retry",
    "capture_official_html_screenshots",
    "classify_capture_failure",
    "derive_dimension_authority",
    "inspect_html_readiness",
    "png_dimensions",
    "validate_attempt_policy",
    "validate_attempt_record",
    "validate_capture_manifest",
    "validate_readiness_probe",
    "verify_capture_manifest_hash",
]
