from __future__ import annotations

import tempfile
import unittest
import json
from pathlib import Path
from unittest.mock import patch
from PIL import Image,PngImagePlugin

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

    def test_byte_limit_rejects_before_decoder(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'too-large.png';source.write_bytes(b'x'*101)
            with patch('homelab_vision.image.Image.open') as decoder:
                with self.assertRaisesRegex(ImageValidationError,'byte limit'):
                    normalize_image(source,root/'out',max_bytes=100)
                decoder.assert_not_called()

    def test_all_exif_orientations_map_pixels_and_strip_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            original=Image.new('RGB',(6,4))
            original.putdata([(x*30,y*50,20) for y in range(4) for x in range(6)])
            for orientation in range(1,9):
                exif=Image.Exif();exif[274]=orientation;exif[315]='fictional metadata'
                info=PngImagePlugin.PngInfo();info.add_text('Comment','fixture private comment')
                source=root/f'orientation-{orientation}.png'
                original.save(source,exif=exif,pnginfo=info,icc_profile=b'fictional profile')
                before=source.read_bytes();result=normalize_image(source,root/'out')
                self.assertEqual(before,source.read_bytes())
                with Image.open(result.output_path) as output:
                    self.assertNotIn('exif',output.info);self.assertNotIn('icc_profile',output.info);self.assertNotIn('Comment',output.info)
                    for y in range(output.height):
                        for x in range(output.width):
                            sx,sy=result.transform.output_to_source(x,y)
                            self.assertEqual(output.getpixel((x,y)),original.getpixel((round(sx),round(sy))))
                self.assertTrue(result.normalization['source_has_icc'])
                self.assertEqual(result.normalization['algorithm'],'normalize-v2')

    def test_transparency_and_animation_policy(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'alpha.png'
            Image.new('RGBA',(10,10),(255,0,0,0)).save(source)
            result=normalize_image(source,root/'out')
            with Image.open(result.output_path) as output:
                self.assertEqual(output.getpixel((0,0)),(255,255,255));self.assertEqual(output.mode,'RGB')
            Image.new('RGB',(10,10),'red').save(root/'animation.png',save_all=True,append_images=[Image.new('RGB',(10,10),'blue')],duration=100)
            with self.assertRaisesRegex(ImageValidationError,'multi-frame'):
                normalize_image(root/'animation.png',root/'out')

    def test_pixel_limit_and_decoded_format_are_enforced(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'misleading.jpg'
            Image.new('RGB',(10,10)).save(source,format='PNG')
            self.assertEqual(normalize_image(source,root/'out').source_format,'PNG')
            with self.assertRaisesRegex(ImageValidationError,'dimensions'):
                normalize_image(source,root/'out',max_pixels=99)

    def test_cli_rejection_records_stage_without_calling_model(self):
        from homelab_vision.cli import main
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'bad.png';source.write_bytes(b'not an image')
            with patch('homelab_vision.cli.LocalVisionClient') as client:
                with self.assertRaises(ImageValidationError):
                    main(['analyze',str(source),'--task','label','--model','unused','--output',str(root/'out')])
                client.assert_not_called()
            self.assertEqual(json.loads((root/'out/failure.json').read_text())['stage'],'normalization')

    def test_normalize_cli_preserves_evidence_without_provider(self):
        from homelab_vision.cli import main
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            with patch('homelab_vision.cli.LocalVisionClient') as client:
                main(['normalize',str(ROOT/'fixtures/source/status-panel.png'),'--max-edge','320','--output',str(root/'out')])
                client.assert_not_called()
            record=json.loads((root/'out/input.json').read_text())
            self.assertEqual(record['transform']['output_width'],320)
            self.assertEqual(record['normalization']['algorithm'],'normalize-v2')
            self.assertTrue((root/'out'/record['image']).is_file())
            self.assertFalse((root/'out/proposal.json').exists())


if __name__ == "__main__":
    unittest.main()
