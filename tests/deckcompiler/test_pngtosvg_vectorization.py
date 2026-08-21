from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw

from presentation_agent.deckcompiler.vectorization import (
    trace_png_to_svg,
    validate_svg,
)


class PngToSvgVectorizationTests(unittest.TestCase):
    def test_bounded_flat_icon_traces_to_sanitized_svg(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "icon.png"
            output = root / "icon.svg"
            image = Image.new("RGBA", (64, 64), (255, 255, 255, 255))
            draw = ImageDraw.Draw(image)
            draw.rounded_rectangle((12, 10, 52, 54), radius=8, fill=(8, 32, 64, 255))
            draw.ellipse((26, 24, 38, 36), fill=(0, 210, 220, 255))
            image.save(source)

            def synthetic_fidelity(
                original: Image.Image,
                _svg_path: Path,
                preview_path: Path,
            ) -> dict[str, object]:
                original.convert("RGB").save(preview_path, format="PNG")
                return {
                    "mean_absolute_error": 0.0,
                    "pixel_difference_ratio": 0.0,
                    "thresholds": {
                        "mean_absolute_error_max": 0.09,
                        "pixel_difference_ratio_max": 0.18,
                    },
                }

            with patch(
                "presentation_agent.deckcompiler.vectorization.bounded_trace._fidelity_report",
                synthetic_fidelity,
            ):
                report = trace_png_to_svg(
                    source,
                    output,
                    region_area_ratio=0.02,
                    semantic_text_overlap=False,
                )

            self.assertEqual(report["status"], "passed", report)
            gate = validate_svg(output)
            self.assertEqual(gate["status"], "passed", gate)
            self.assertEqual(gate["embedded_raster_count"], 0)
            self.assertEqual(gate["text_element_count"], 0)

    def test_continuous_tone_input_is_rejected_before_svg_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "photo-like.png"
            output = root / "photo-like.svg"
            image = Image.new("RGB", (128, 128))
            image.putdata(
                [
                    ((x * 17 + y * 3) % 256, (x * 5 + y * 19) % 256, (x * 11 + y * 7) % 256)
                    for y in range(128)
                    for x in range(128)
                ]
            )
            image.save(source)

            report = trace_png_to_svg(
                source,
                output,
                region_area_ratio=0.02,
                semantic_text_overlap=False,
            )

            self.assertEqual(report["status"], "rejected")
            self.assertEqual(report["reason"], "continuous_tone_not_vector_safe")
            self.assertFalse(output.exists())

    def test_svg_gate_rejects_text_and_embedded_raster(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "unsafe.svg"
            path.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
                '<text x="1" y="4">copy</text>'
                '<image href="data:image/png;base64,AAAA" width="2" height="2"/>'
                "</svg>",
                encoding="utf-8",
            )

            report = validate_svg(path)

            self.assertEqual(report["status"], "failed")
            self.assertGreater(report["embedded_raster_count"], 0)
            self.assertGreater(report["text_element_count"], 0)

    def test_trace_rejects_missing_bounded_region_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "full-slide.png"
            output = root / "full-slide.svg"
            Image.new("RGB", (160, 90), (255, 255, 255)).save(source)

            report = trace_png_to_svg(
                source,
                output,
                region_area_ratio=1.0,
                semantic_text_overlap=False,
            )

            self.assertEqual(report["status"], "rejected")
            self.assertEqual(report["reason"], "bounded_region_context_required")
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
