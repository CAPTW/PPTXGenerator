from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageOps
from pptx.util import Inches

from ..slide_scene import ImageObject
from .common import (
    append_warning,
    resolve_scene_path,
    sanitize_filename_component,
    set_shape_alt_text,
    stable_scene_shape_name,
)


def render_image_object(
    slide: Any,
    image_object: ImageObject,
    *,
    root: Path | None,
    asset_output_dir: Path,
    used_shape_names: set[str],
    slide_number: int,
    slide_id: str,
    warnings: list[Any],
) -> str | None:
    source_path = resolve_scene_path(image_object.source_path, root=root)
    if source_path is None:
        append_warning(
            warnings,
            code="missing_image_source_path",
            severity="error",
            slide_number=slide_number,
            slide_id=slide_id,
            object_id=image_object.object_id,
            message="ImageObject is missing a source_path, so it cannot be rendered in the scene compile path.",
            details={"asset_id": image_object.asset_id},
        )
        return None
    if not source_path.is_file():
        append_warning(
            warnings,
            code="missing_image_asset",
            severity="error",
            slide_number=slide_number,
            slide_id=slide_id,
            object_id=image_object.object_id,
            message=f"Image asset {source_path.as_posix()!r} does not exist.",
            details={"asset_id": image_object.asset_id, "source_path": source_path.as_posix()},
        )
        return None

    picture_path = source_path
    left = image_object.bounds.x
    top = image_object.bounds.y
    width = image_object.bounds.width
    height = image_object.bounds.height

    if image_object.crop.mask != "rect":
        append_warning(
            warnings,
            code="unsupported_image_mask",
            severity="warning",
            slide_number=slide_number,
            slide_id=slide_id,
            object_id=image_object.object_id,
            message=f"Image mask {image_object.crop.mask!r} is not supported in the scene compile path; rendered as a rectangle.",
            details={"mask": image_object.crop.mask},
        )

    if image_object.crop.mode == "contain" and not _has_explicit_crop(image_object):
        fitted_width, fitted_height = _fit_contain(source_path, width, height)
        left = left + ((width - fitted_width) / 2.0)
        top = top + ((height - fitted_height) / 2.0)
        width = fitted_width
        height = fitted_height
    else:
        asset_output_dir.mkdir(parents=True, exist_ok=True)
        picture_path = _prepare_cropped_asset(source_path, image_object, asset_output_dir)

    shape = slide.shapes.add_picture(
        str(picture_path),
        Inches(left),
        Inches(top),
        width=Inches(width),
        height=Inches(height),
    )
    shape.name = stable_scene_shape_name("image", image_object.object_id, used_shape_names)
    set_shape_alt_text(shape, image_object.alt_text)
    return shape.name


def _has_explicit_crop(image_object: ImageObject) -> bool:
    crop = image_object.crop
    return any(value > 0 for value in (crop.crop_left, crop.crop_top, crop.crop_right, crop.crop_bottom))


def _fit_contain(image_path: Path, width: float, height: float) -> tuple[float, float]:
    try:
        with Image.open(image_path) as image:
            image_width, image_height = image.size
    except Exception:
        return (width, height)
    if image_width <= 0 or image_height <= 0:
        return (width, height)
    image_ratio = image_width / image_height
    box_ratio = width / height
    if image_ratio >= box_ratio:
        fitted_width = width
        fitted_height = width / image_ratio
    else:
        fitted_height = height
        fitted_width = height * image_ratio
    return (round(fitted_width, 6), round(fitted_height, 6))


def _prepare_cropped_asset(source_path: Path, image_object: ImageObject, asset_output_dir: Path) -> Path:
    file_name = sanitize_filename_component(image_object.object_id)
    output_path = asset_output_dir / f"{file_name}.png"
    target_size = (
        max(1, int(round(image_object.bounds.width * 200))),
        max(1, int(round(image_object.bounds.height * 200))),
    )
    with Image.open(source_path) as source_image:
        working = source_image.convert("RGBA")
        crop_box = _crop_box(working.size, image_object)
        working = working.crop(crop_box)
        if image_object.crop.mode in {"cover", "crop"} or _has_explicit_crop(image_object):
            rendered = ImageOps.fit(working, target_size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
        else:
            rendered = working.resize(target_size, Image.Resampling.LANCZOS)
        rendered.save(output_path)
    return output_path


def _crop_box(image_size: tuple[int, int], image_object: ImageObject) -> tuple[int, int, int, int]:
    width, height = image_size
    crop = image_object.crop
    left = int(round(width * crop.crop_left))
    right = int(round(width * (1.0 - crop.crop_right)))
    top = int(round(height * crop.crop_top))
    bottom = int(round(height * (1.0 - crop.crop_bottom)))
    right = max(left + 1, right)
    bottom = max(top + 1, bottom)
    return (left, top, right, bottom)

