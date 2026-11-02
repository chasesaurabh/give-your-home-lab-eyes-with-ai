"""Deterministic, bounded image normalization with reversible coordinates."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from .lineage import sha256_file


ALLOWED_FORMATS = frozenset({"JPEG", "PNG", "WEBP"})


class ImageValidationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ImageTransform:
    source_width: int
    source_height: int
    oriented_width: int
    oriented_height: int
    output_width: int
    output_height: int
    exif_orientation: int

    def output_to_source(self, x: float, y: float) -> tuple[float, float]:
        """Map an output pixel center back to the original encoded orientation."""

        if not (0 <= x < self.output_width and 0 <= y < self.output_height):
            raise ValueError("output coordinate is outside the image")

        oriented_x = (x + 0.5) * self.oriented_width / self.output_width - 0.5
        oriented_y = (y + 0.5) * self.oriented_height / self.output_height - 0.5
        max_x = self.source_width - 1
        max_y = self.source_height - 1

        orientation = self.exif_orientation
        if orientation == 1:
            source_x, source_y = oriented_x, oriented_y
        elif orientation == 2:
            source_x, source_y = max_x - oriented_x, oriented_y
        elif orientation == 3:
            source_x, source_y = max_x - oriented_x, max_y - oriented_y
        elif orientation == 4:
            source_x, source_y = oriented_x, max_y - oriented_y
        elif orientation == 5:
            source_x, source_y = oriented_y, oriented_x
        elif orientation == 6:
            source_x, source_y = oriented_y, max_y - oriented_x
        elif orientation == 7:
            source_x, source_y = max_x - oriented_y, max_y - oriented_x
        elif orientation == 8:
            source_x, source_y = max_x - oriented_y, oriented_x
        else:
            raise ImageValidationError(f"unsupported EXIF orientation: {orientation}")

        return (
            min(max(source_x, 0.0), float(max_x)),
            min(max(source_y, 0.0), float(max_y)),
        )


@dataclass(frozen=True, slots=True)
class NormalizedImage:
    source_sha256: str
    output_sha256: str
    output_path: Path
    source_format: str
    transform: ImageTransform


def _open_and_validate(path: Path, max_pixels: int) -> tuple[str, int, int, int]:
    try:
        with Image.open(path) as image:
            source_format = image.format or ""
            if source_format not in ALLOWED_FORMATS:
                raise ImageValidationError(f"unsupported image format: {source_format or 'unknown'}")
            if getattr(image, "n_frames", 1) != 1:
                raise ImageValidationError("animated or multi-frame images are not accepted")
            width, height = image.size
            if width <= 0 or height <= 0 or width * height > max_pixels:
                raise ImageValidationError("image dimensions exceed the configured limit")
            orientation = int(image.getexif().get(274, 1))
            if orientation not in range(1, 9):
                raise ImageValidationError("EXIF orientation is outside the supported range")
        with Image.open(path) as verification_image:
            verification_image.verify()
        return source_format, width, height, orientation
    except (OSError, UnidentifiedImageError) as error:
        raise ImageValidationError("image cannot be decoded safely") from error


def normalize_image(
    source_path: Path,
    output_directory: Path,
    *,
    max_edge: int = 1600,
    max_pixels: int = 40_000_000,
) -> NormalizedImage:
    if max_edge < 64:
        raise ValueError("max_edge must be at least 64 pixels")
    source_path = source_path.resolve(strict=True)
    source_format, source_width, source_height, orientation = _open_and_validate(
        source_path, max_pixels
    )
    source_hash = sha256_file(source_path)

    with Image.open(source_path) as encoded:
        oriented = ImageOps.exif_transpose(encoded)
        oriented.load()
        oriented_width, oriented_height = oriented.size
        if oriented.mode in {"RGBA", "LA"} or "transparency" in oriented.info:
            rgba = oriented.convert("RGBA")
            background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
            working = Image.alpha_composite(background, rgba).convert("RGB")
        else:
            working = oriented.convert("RGB")

        scale = min(1.0, max_edge / max(working.size))
        output_size = (
            max(1, round(working.width * scale)),
            max(1, round(working.height * scale)),
        )
        if output_size != working.size:
            working = working.resize(output_size, Image.Resampling.LANCZOS)

        settings = json.dumps(
            {
                "algorithm": "normalize-v1",
                "max_edge": max_edge,
                "background": "ffffff",
                "output": "png-rgb",
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        settings_hash = hashlib.sha256(settings.encode("utf-8")).hexdigest()[:12]
        output_directory.mkdir(parents=True, exist_ok=True)
        output_path = output_directory / f"{source_hash[:16]}-{settings_hash}.png"
        working.save(output_path, format="PNG", compress_level=9, optimize=False)

    transform = ImageTransform(
        source_width=source_width,
        source_height=source_height,
        oriented_width=oriented_width,
        oriented_height=oriented_height,
        output_width=output_size[0],
        output_height=output_size[1],
        exif_orientation=orientation,
    )
    return NormalizedImage(
        source_sha256=source_hash,
        output_sha256=sha256_file(output_path),
        output_path=output_path,
        source_format=source_format,
        transform=transform,
    )
