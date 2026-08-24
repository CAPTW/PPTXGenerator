from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from presentation_agent.deckcompiler.orchestration.one_slide_fast import (
    probe_one_slide_fast_cache,
    seal_one_slide_fast_cache,
    validate_one_slide_fast_cache,
)


class OneSlideFastTests(unittest.TestCase):
    def test_seal_hit_single_process_validation_and_invalidation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project, qa_profile, pptx, html, summary = self._fixture(Path(tmpdir))
            sealed = seal_one_slide_fast_cache(
                project=project,
                slide=1,
                pptx=pptx,
                html=html,
                summary=summary,
                qa_profile=qa_profile,
            )
            self.assertTrue(sealed["sealed"])
            probe = probe_one_slide_fast_cache(project=project, slide=1)
            self.assertTrue(probe["cache_hit"], probe)
            validation = validate_one_slide_fast_cache(project=project, slide=1)
            self.assertTrue(validation["valid"], validation)

            (project / "lib" / "slides.js").write_text("changed\n", encoding="utf-8")
            miss = probe_one_slide_fast_cache(project=project, slide=1)
            self.assertFalse(miss["cache_hit"])
            self.assertTrue(any("inputs artifact hash mismatch" in issue for issue in miss["issues"]), miss)

    def test_design_profile_cannot_be_used_as_qa_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project, _, pptx, html, summary = self._fixture(Path(tmpdir))
            with self.assertRaisesRegex(ValueError, "calibration profile"):
                seal_one_slide_fast_cache(
                    project=project,
                    slide=1,
                    pptx=pptx,
                    html=html,
                    summary=summary,
                    qa_profile=project / "styles" / "active.json",
                )

    def test_capture_metadata_must_be_hash_bound(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project, qa_profile, pptx, html, summary = self._fixture(Path(tmpdir))
            metadata_path = (
                project / "work" / "slide01" / "visual_qa" / "html_screenshot_metadata.json"
            )
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["htmlSha256"] = "0" * 64
            metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "artifact hash mismatch"):
                seal_one_slide_fast_cache(
                    project=project,
                    slide=1,
                    pptx=pptx,
                    html=html,
                    summary=summary,
                    qa_profile=qa_profile,
                )

    def _fixture(self, root: Path) -> tuple[Path, Path, Path, Path, Path]:
        project = root / "project"
        work = project / "work" / "slide01"
        vector = work / "vector_preflight"
        visual = work / "visual_qa"
        for path in (
            project / "src",
            project / "lib",
            project / "styles",
            project / "out" / "pptx_openability_debug",
            project / "assets" / "icons",
            vector,
            visual,
        ):
            path.mkdir(parents=True, exist_ok=True)
        text_files = {
            project / "src" / "slide1.png": "source",
            project / "lib" / "slides.js": "function s1() {}\n",
            project / "styles" / "active.json": json.dumps({"profileId": "academic"}),
            project / "work" / "crop_plan.json": json.dumps({"schema_version": "1.0.0", "crops": []}),
            project / "work" / "icon_usage.json": json.dumps({"schemaVersion": "slide-image-dual-render.icon-usage.v1", "icons": []}),
            project / "work" / "font_usage.json": json.dumps({"schemaVersion": "slide-image-dual-render.font-usage.v1", "fonts": [{"originalFont": "Pretendard"}]}),
            work / "reconstruction_job.json": "{}",
            work / "measurements.json": "{}",
            work / "vector_usage.json": "{}",
            work / "icon_usage.json": json.dumps({"schemaVersion": "slide-image-dual-render.icon-usage.v1", "icons": []}),
            work / "font_usage.json": json.dumps({"schemaVersion": "slide-image-dual-render.font-usage.v1", "fonts": [{"originalFont": "Pretendard"}]}),
            work / "profile_override.json": "{}",
            work / "crop_plan.json": "{}",
            work / "s1.fragment.js": "function s1(s) {}\n",
            work / "reconstruction_score.json": json.dumps({"slide": 1, "status": "pass"}),
            vector / "measurement_inventory.json": "{}",
            project / "out" / "native_object_manifest.json": "{}",
            project / "out" / "crop_coverage_summary.json": "{}",
            project / "out" / "qa_evidence_summary.json": "{}",
            project / "out" / "font_resolution_manifest.json": json.dumps({"schemaVersion": "slide-image-dual-render.font-resolution-manifest.v1", "status": "PASS", "automaticInstallationAttempted": False, "mappings": [{"original": "Pretendard", "resolved": "Pretendard"}]}),
            project / "out" / "font_install_request.json": json.dumps({"schemaVersion": "slide-image-dual-render.font-install-request.v1", "status": "NOT_REQUIRED", "automaticInstallationAttempted": False, "requestedFonts": []}),
            project / "out" / "pptx_openability_debug" / "pptx_package_validation.json": json.dumps({"passed": True}),
            project / "assets" / "icons" / "manifest.json": "{}",
            project / "assets" / "bg.manifest.json": "{}",
        }
        for path, value in text_files.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(value, encoding="utf-8")

        metrics = {"overallStatus": "pass", "issues": [], "comparisons": {}}
        (visual / "visual_metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
        summary = project / "out" / "visual_qa_summary.json"
        summary.write_text(
            json.dumps(
                {
                    "project": project.resolve().as_posix(),
                    "slidesRequested": [1],
                    "failed": 0,
                    "blockingIssues": 0,
                    "slides": [{"slide": 1, "status": "pass"}],
                }
            ),
            encoding="utf-8",
        )
        pptx = project / "out" / "deck.pptx"
        with zipfile.ZipFile(pptx, "w") as package:
            package.writestr("[Content_Types].xml", "<Types/>")
            package.writestr("_rels/.rels", "<Relationships/>")
            package.writestr("ppt/presentation.xml", "<p:presentation/>")
        html = project / "out" / "deck.html"
        html.write_text("<html></html>", encoding="utf-8")
        pptx_raster = visual / "pptx_raster.png"
        html_screenshot = visual / "html_screenshot.png"
        pptx_raster.write_bytes(b"pptx-raster")
        html_screenshot.write_bytes(b"html-screenshot")

        def sha256(path: Path) -> str:
            return hashlib.sha256(path.read_bytes()).hexdigest()

        (visual / "pptx_raster_metadata.json").write_text(
            json.dumps(
                {
                    "sourceSlideId": 1,
                    "modifiedPptx": False,
                    "pptx": pptx.resolve().as_posix(),
                    "pptxSha256": sha256(pptx),
                    "output": pptx_raster.resolve().as_posix(),
                    "outputSha256": sha256(pptx_raster),
                }
            ),
            encoding="utf-8",
        )
        (visual / "html_screenshot_metadata.json").write_text(
            json.dumps(
                {
                    "sourceSlideId": 1,
                    "captureCacheContract": "slide-visual-polish-qa.html-capture-cache.v1",
                    "cacheHit": True,
                    "qaStaticModeUsed": True,
                    "modifiedHtml": False,
                    "deviceScaleFactor": 1,
                    "dimensionCheck": "exact",
                    "expectedScreenshotDimensions": {"width": 1672, "height": 941},
                    "actualScreenshotDimensions": {"width": 1672, "height": 941},
                    "html": html.resolve().as_posix(),
                    "htmlSha256": sha256(html),
                    "output": html_screenshot.resolve().as_posix(),
                    "outputSha256": sha256(html_screenshot),
                }
            ),
            encoding="utf-8",
        )

        toolchain = root / "toolchain"
        toolchain.mkdir()
        tools = {}
        for name in ("build.js", "kit.js", "atoms_pptx.js", "atoms_html.js", "font_preflight.js"):
            path = toolchain / name
            path.write_text(name, encoding="utf-8")
            tools[name] = path
        trace = {
            "invokedByPipeline": True,
            "strictMode": True,
            "enforcementDisabled": False,
            "validation": {"passed": True},
            "finalValidation": {"passed": True},
            "reconstructionValidation": {"passed": True, "slidesPassed": [1]},
            "qaSummary": {"passed": True},
            "buildJsPath": tools["build.js"].as_posix(),
            "slidesJsPath": (project / "lib" / "slides.js").as_posix(),
            "kitJsPath": tools["kit.js"].as_posix(),
            "atomsPptxPath": tools["atoms_pptx.js"].as_posix(),
            "atomsHtmlPath": tools["atoms_html.js"].as_posix(),
            "fontPreflightPath": tools["font_preflight.js"].as_posix(),
            "fontResolution": {
                "status": "PASS",
                "originalFontCount": 1,
                "exactCount": 1,
                "fallbackCount": 0,
                "approvalRequiredCount": 0,
                "automaticInstallationAttempted": False,
            },
        }
        (project / "out" / "render_trace.json").write_text(json.dumps(trace), encoding="utf-8")
        qa_profile = root / "default-visual-qa-profile.json"
        qa_profile.write_text(
            json.dumps(
                {
                    "schemaVersion": "slide-visual-polish-qa.calibration-profile.v1",
                    "knownGoodMetricBands": {},
                    "borderlineMetricBands": {},
                    "knownBadMetricBands": {},
                }
            ),
            encoding="utf-8",
        )
        return project, qa_profile, pptx, html, summary


if __name__ == "__main__":
    unittest.main()
