from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from homelab_vision.image import ImageTransform, ImageValidationError, normalize_image


ROOT = Path(__file__).resolve().parents[1]


class ImageTests(unittest.TestCase):
    def test_fixture_normalizes_deterministically(self) -> None:
        source = ROOT / "fixtures" / "source" / "status-panel.png"
        with tempfile.TemporaryDirectory() as directory:
            first = normalize_image(source, Path(directory), max_edge=320)
            second = normalize_image(source, Path(directory), max_edge=320)
            self.assertEqual(first.output_sha256, second.output_sha256)
            self.assertEqual(
                (first.transform.output_width, first.transform.output_height),
                (320, 180),
            )
            self.assertEqual(first.source_sha256, "4f0c7399fcacb45e5851b77aace49cdd0fac1a3e35936fef6be182e7bde8fcc4")

    def test_identity_coordinate_mapping_at_half_scale(self) -> None:
        transform = ImageTransform(640, 360, 640, 360, 320, 180, 1)
        source_x, source_y = transform.output_to_source(159.5, 89.5)
        self.assertAlmostEqual(source_x, 319.5)
        self.assertAlmostEqual(source_y, 179.5)

    def test_out_of_bounds_coordinate_is_rejected(self) -> None:
        transform = ImageTransform(10, 10, 10, 10, 10, 10, 1)
        with self.assertRaises(ValueError):
            transform.output_to_source(10, 0)

    def test_non_image_is_rejected(self) -> None:
        source = ROOT / "fixtures" / "source" / "untrusted-note.md"
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ImageValidationError):
                normalize_image(source, Path(directory))


if __name__ == "__main__":
    unittest.main()
