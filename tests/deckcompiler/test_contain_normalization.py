"""Content-preserving normalization tests; no detector or rendering shortcuts."""
from __future__ import annotations

import copy
import hashlib
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from presentation_agent.deckcompiler.errors import DeckCompilerError
from presentation_agent.deckcompiler.platform_image_execution.contracts import verify_hash_bound_payload
from presentation_agent.deckcompiler.platform_image_execution.ingestion import normalize_generated_image


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def legacy_crop_reference(source, output):
    """Frozen valid-image oracle from main bf0487b; no unpublished files.

    Keep this independent of the implementation under test so the default's
    PNG bytes and evidence-record shape remain covered in a fresh checkout.
    All callers create synthetic images inside temporary directories.
    """
    with Image.open(source) as image:
        source_format = image.format.upper()
        width, height = image.size
        units = min(width // 16, height // 9)
        crop_width, crop_height = units * 16, units * 9
        left, top = (width - crop_width) // 2, (height - crop_height) // 2
        crop_box = (left, top, left + crop_width, top + crop_height)
        requires_crop = (crop_width, crop_height) != (width, height)
        requires_resize = crop_width < 1600 or crop_height < 900
        final_size = (1600, 900) if requires_resize else (crop_width, crop_height)
        expected = image.crop(crop_box) if requires_crop else image.copy()
        if requires_resize:
            expected = expected.resize(final_size, Image.Resampling.LANCZOS)
        if expected.mode not in {"RGB", "RGBA"}:
            expected = expected.convert("RGBA" if "A" in expected.getbands() else "RGB")
        expected.save(output, format="PNG", optimize=True)
    if requires_crop and requires_resize:
        transformation_type = "aspect_preserving_crop_and_uniform_resize"
    elif requires_crop:
        transformation_type = "aspect_preserving_crop"
    elif requires_resize:
        transformation_type = "uniform_resize"
    else:
        transformation_type = "png_reencode_only"
    return {
        "original_format": source_format,
        "original_dimensions": {"width": width, "height": height},
        "original_file_size_bytes": source.stat().st_size,
        "original_sha256": sha(source),
        "normalized_format": "PNG",
        "normalized_dimensions": {"width": final_size[0], "height": final_size[1]},
        "normalized_file_size_bytes": output.stat().st_size,
        "normalized_sha256": sha(output),
        "transformation": {
            "type": transformation_type,
            "crop_box": list(crop_box),
            "uniform_resize_to": list(final_size) if requires_resize else None,
            "stretch_used": False,
            "nonuniform_resize_used": False,
        },
    }

class ContainNormalizationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def source(self, size=(517, 233), mode="RGB"):
        # Distinct corner pixels reveal any content clipping or alpha loss.
        image = Image.new(mode, size, (31, 47, 59, 128) if mode == "RGBA" else (31, 47, 59))
        for xy, color in zip(
            [(0, 0), (size[0]-1, 0), (0, size[1]-1), (size[0]-1, size[1]-1)],
            [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)],
        ):
            image.putpixel(xy, (*color, 64) if mode == "RGBA" else color)
        path = self.root / "source.png"
        image.save(path)
        return path

    def test_crop_default_is_byte_and_record_identical_to_current_main(self):
        for size in [(517,233), (1600,900), (1920,1080), (400,700), (1701,1001)]:
            with self.subTest(size=size):
                source = self.source(size)
                old = self.root / (str(size)+"-old.png")
                new = self.root / (str(size)+"-new.png")
                expected = legacy_crop_reference(source, old)
                actual = normalize_generated_image(source, new)
                self.assertEqual(actual, expected)
                self.assertEqual(new.read_bytes(), old.read_bytes())

    def test_explicit_crop_matches_default(self):
        source=self.source()
        self.assertEqual(normalize_generated_image(source,self.root/"default.png"),
                         normalize_generated_image(source,self.root/"crop.png",mode="crop"))

    def test_contain_small_has_exact_uniform_transform_and_bound_bytes(self):
        source = self.source()
        before = sha(source)
        output = self.root / "contained.png"
        record = normalize_generated_image(source, output, mode="contain", padding_color=(21,34,55))
        self.assertEqual(sha(source), before)
        self.assertEqual(record["normalized_dimensions"], {"width":1600,"height":900})
        transform=record["transformation"]
        self.assertEqual(transform["crop_box"], [0,0,517,233])
        self.assertEqual(transform["padding_px"], {"left":5,"top":32,"right":6,"bottom":32})
        mapping=transform["geometry_mapping"]
        self.assertTrue(verify_hash_bound_payload(mapping,"mapping_sha256"))
        self.assertEqual(mapping["source_sha256"],before)
        self.assertEqual(mapping["normalized_sha256"],sha(output))
        self.assertEqual(mapping["uniform_scale"],[100,33])
        self.assertEqual(mapping["translation"],{"x":[500,33],"y":[3200,33]})
        self.assertEqual(mapping["source_box_on_normalized_canvas"],[[500,33],[3200,33],[17400,11],[26500,33]])
        self.assertFalse(mapping["semantic_geometry_authority"])

    def test_pre_resize_contains_every_source_pixel(self):
        source=self.source()
        captured=[]
        original_resize=Image.Image.resize
        def capture(image,*args,**kwargs):
            captured.append(image.copy())
            return original_resize(image,*args,**kwargs)
        with patch.object(Image.Image,"resize",capture):
            normalize_generated_image(source,self.root/"out.png",mode="contain",padding_color=(21,34,55))
        self.assertEqual(len(captured),1)
        with Image.open(source) as expected:
            self.assertEqual(captured[0].crop((5,32,522,265)).tobytes(),expected.tobytes())
        self.assertEqual(captured[0].getpixel((0,0)),(21,34,55))

    def test_large_source_pixels_are_preserved_without_resampling(self):
        source=self.source((1701,1001))
        output=self.root/"out.png"
        record=normalize_generated_image(source,output,mode="contain",padding_color=(1,2,3))
        t=record["transformation"]
        self.assertIsNone(t["uniform_resize_to"])
        m=t["geometry_mapping"]
        self.assertEqual(m["uniform_scale"],[1,1])
        with Image.open(source) as expected,Image.open(output) as actual:
            self.assertEqual(actual.crop(tuple(m["source_box_on_padded_canvas"])).tobytes(),expected.tobytes())
            self.assertEqual(actual.getpixel((0,0)),(1,2,3))

    def test_portrait_and_odd_padding_round_trip_geometry(self):
        source=self.source((401,701))
        record=normalize_generated_image(source,self.root/"out.png",mode="contain",padding_color=(0,0,0))
        m=record["transformation"]["geometry_mapping"]
        scale=Fraction(*m["uniform_scale"])
        tx,ty=Fraction(*m["translation"]["x"]),Fraction(*m["translation"]["y"])
        edges=[Fraction(*v) for v in m["source_box_on_normalized_canvas"]]
        self.assertEqual([(edges[0]-tx)/scale,(edges[1]-ty)/scale,(edges[2]-tx)/scale,(edges[3]-ty)/scale],[0,0,401,701])
        pad=record["transformation"]["padding_px"]
        self.assertLessEqual(abs(pad["left"]-pad["right"]),1)
        self.assertLessEqual(abs(pad["top"]-pad["bottom"]),1)

    def test_rgba_alpha_is_copied_not_flattened(self):
        source=self.source((1601,901),"RGBA")
        output=self.root/"out.png"
        record=normalize_generated_image(source,output,mode="contain",padding_color=(9,8,7))
        box=record["transformation"]["geometry_mapping"]["source_box_on_padded_canvas"]
        with Image.open(source) as expected,Image.open(output) as actual:
            self.assertEqual(actual.mode,"RGBA")
            self.assertEqual(actual.crop(tuple(box)).tobytes(),expected.tobytes())
            self.assertEqual(actual.getpixel((0,0)),(9,8,7,255))

    def test_palette_transparency_is_preserved(self):
        source=self.root/"source.png"
        im=Image.new("P",(1601,901),0)
        im.putpalette([255,0,0,0,255,0]+[0]*762)
        im.info["transparency"]=0
        im.putpixel((20,20),1)
        im.save(source)
        record=normalize_generated_image(source,self.root/"out.png",mode="contain",padding_color=(4,5,6))
        box=record["transformation"]["geometry_mapping"]["source_box_on_padded_canvas"]
        with Image.open(source) as expected,Image.open(self.root/"out.png") as actual:
            self.assertEqual(actual.crop(tuple(box)).tobytes(),expected.convert("RGBA").tobytes())

    def test_mapping_detects_geometry_or_hash_tampering(self):
        record=normalize_generated_image(self.source(),self.root/"out.png",mode="contain",padding_color=(0,0,0))
        mapping=record["transformation"]["geometry_mapping"]
        for key,value in [("source_sha256","0"*64),("normalized_sha256","1"*64),("uniform_scale",[1,1]),("source_box",[1,0,517,233])]:
            altered=copy.deepcopy(mapping);altered[key]=value
            self.assertFalse(verify_hash_bound_payload(altered,"mapping_sha256"))

    def test_invalid_padding_and_mode_rejected_before_write(self):
        source=self.source()
        cases=[{"mode":"contain"},{"mode":"contain","padding_color":(1,2)},
               {"mode":"contain","padding_color":(True,2,3)}, {"mode":"contain","padding_color":(0,256,1)},
               {"mode":"contain","padding_color":(0,-1,1)}, {"mode":"contain","padding_color":"#152237"},
               {"mode":"contain","padding_color":(1.0,2,3)}, {"mode":"other"},
               {"mode":"crop","padding_color":(1,2,3)}]
        for kwargs in cases:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(DeckCompilerError):
                    normalize_generated_image(source,self.root/"out.png",**kwargs)
                self.assertFalse((self.root/"out.png").exists())

    def test_existing_output_not_overwritten(self):
        source=self.source();output=self.root/"out.png";output.write_bytes(b"keep")
        with self.assertRaises(DeckCompilerError):
            normalize_generated_image(source,output,mode="contain",padding_color=(0,0,0))
        self.assertEqual(output.read_bytes(),b"keep")

    def test_missing_source_and_invalid_image_rejected(self):
        for source in [self.root/"missing.png",self.root/"invalid.png"]:
            if source.name=="invalid.png":source.write_bytes(b"invalid")
            with self.assertRaises(DeckCompilerError):
                normalize_generated_image(source,self.root/"out.png",mode="contain",padding_color=(0,0,0))

    def test_tiny_source_remains_inside_minimum_canvas(self):
        source=self.source((1,1))
        result=normalize_generated_image(source,self.root/"out.png",mode="contain",padding_color=(0,0,0))
        self.assertEqual(result["normalized_dimensions"],{"width":1600,"height":900})
        self.assertEqual(result["transformation"]["geometry_mapping"]["source_box"],[0,0,1,1])

    def test_source_icc_profile_survives_padding_and_resize(self):
        source=self.source()
        with Image.open(source) as image:
            image.save(self.root/"profile.png",icc_profile=b"retained-color-profile")
        normalize_generated_image(self.root/"profile.png",self.root/"out.png",mode="contain",padding_color=(0,0,0))
        with Image.open(self.root/"out.png") as image:
            self.assertEqual(image.info["icc_profile"],b"retained-color-profile")

    def test_extreme_aspect_ratio_rejected_before_canvas_allocation(self):
        source=self.source((100000,1))
        with patch.object(Image,"new",side_effect=AssertionError("must reject before allocating")):
            with self.assertRaises(DeckCompilerError):
                normalize_generated_image(source,self.root/"out.png",mode="contain",padding_color=(0,0,0))
        self.assertFalse((self.root/"out.png").exists())


if __name__ == "__main__":
    unittest.main()
