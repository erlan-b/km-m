from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps

MAX_IMAGE_DIMENSIONS = (1920, 1920)
THUMBNAIL_DIMENSIONS = (480, 480)
THUMBNAIL_SUFFIX = "_thumb.webp"


@dataclass(slots=True)
class ProcessedListingImage:
    file_size: int
    thumbnail_path: Path


def get_thumbnail_path(image_path: Path) -> Path:
    return image_path.with_name(f"{image_path.stem}{THUMBNAIL_SUFFIX}")


def _normalize_image_mode(image: Image.Image, *, output_format: str) -> Image.Image:
    if output_format == "JPEG" and image.mode not in {"RGB", "L"}:
        return image.convert("RGB")
    if image.mode == "P":
        return image.convert("RGBA")
    return image


def _save_optimized(image: Image.Image, *, file_path: Path, output_format: str) -> None:
    if output_format == "JPEG":
        image.save(file_path, format="JPEG", optimize=True, quality=84, progressive=True)
        return
    if output_format == "PNG":
        image.save(file_path, format="PNG", optimize=True)
        return
    if output_format == "WEBP":
        image.save(file_path, format="WEBP", quality=84, method=6)
        return

    image.save(file_path, format=output_format)


def process_listing_image(*, image_path: Path, mime_type: str) -> ProcessedListingImage:
    format_by_mime = {
        "image/jpeg": "JPEG",
        "image/png": "PNG",
        "image/webp": "WEBP",
    }
    output_format = format_by_mime.get(mime_type.lower())
    if output_format is None:
        raise ValueError(f"Unsupported image mime type for optimization: {mime_type}")

    with Image.open(image_path) as opened:
        main_image = ImageOps.exif_transpose(opened)
        main_image = _normalize_image_mode(main_image, output_format=output_format)
        main_image.thumbnail(MAX_IMAGE_DIMENSIONS, Image.Resampling.LANCZOS)
        _save_optimized(main_image, file_path=image_path, output_format=output_format)

        thumbnail = main_image.copy()
        thumbnail.thumbnail(THUMBNAIL_DIMENSIONS, Image.Resampling.LANCZOS)
        if thumbnail.mode not in {"RGB", "RGBA"}:
            thumbnail = thumbnail.convert("RGB")

        thumbnail_path = get_thumbnail_path(image_path)
        thumbnail.save(thumbnail_path, format="WEBP", quality=78, method=6)

    return ProcessedListingImage(
        file_size=image_path.stat().st_size,
        thumbnail_path=thumbnail_path,
    )
