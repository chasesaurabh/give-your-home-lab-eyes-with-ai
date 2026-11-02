"""Deterministic, bounded image normalization with reversible coordinates."""

from __future__ import annotations

import hashlib
import json
from io import BytesIO
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError, __version__ as pillow_version

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
    normalization: dict


def _open_and_validate(data: bytes, max_pixels: int) -> tuple[str, int, int, int]:
    try:
        with Image.open(BytesIO(data)) as image:
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
        with Image.open(BytesIO(data)) as verification_image:
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
    max_bytes: int = 20_000_000,
) -> NormalizedImage:
    if type(max_edge) is not int or not 64 <= max_edge <= 4096:
        raise ValueError("max_edge must be an integer between 64 and 4096 pixels")
    if type(max_pixels) is not int or not 1 <= max_pixels <= 40_000_000 or type(max_bytes) is not int or not 1 <= max_bytes <= 20_000_000:
        raise ValueError('pixel and byte limits must be positive and within the application maximum')
    source_path = source_path.resolve(strict=True)
    with source_path.open('rb') as stream:
        data = stream.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ImageValidationError('source exceeds the configured byte limit')
    source_format, source_width, source_height, orientation = _open_and_validate(
        data, max_pixels
    )
    source_hash = hashlib.sha256(data).hexdigest()

    with Image.open(BytesIO(data)) as encoded:
        source_mode = encoded.mode
        source_has_icc = bool(encoded.info.get('icc_profile'))
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
                "algorithm": "normalize-v2",
                "pillow_version": pillow_version,
                "max_edge": max_edge,
                "background": "ffffff",
                "output": "png-rgb",
                "metadata": "strip",
                "color": "Pillow RGB conversion; no ICC color management",
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        settings_hash = hashlib.sha256(settings.encode("utf-8")).hexdigest()[:12]
        output_directory.mkdir(parents=True, exist_ok=True)
        output_path = output_directory / f"{source_hash[:16]}-{settings_hash}.png"
        # A fresh pixel-only object prevents EXIF, ICC and text metadata inheritance.
        clean = Image.frombytes('RGB', working.size, working.tobytes())
        clean.save(output_path, format="PNG", compress_level=9, optimize=False)

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
        normalization=dict(**json.loads(settings),source_mode=source_mode,source_has_icc=source_has_icc),
    )
