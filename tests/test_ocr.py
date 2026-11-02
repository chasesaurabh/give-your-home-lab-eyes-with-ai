import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from homelab_vision.ocr import ocr_bundle


class OcrInputTests(unittest.TestCase):
    def test_tampered_page_rejected_before_external_process(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);image=root/'page.png'
            Image.new('RGB',(20,20),'white').save(image)
            manifest=dict(state='review_required',source_sha256='a'*64,pages=[dict(
                page=1,image='page.png',image_sha256='0'*64,width=20,height=20)])
            (root/'manifest.json').write_text(json.dumps(manifest))
            with patch('homelab_vision.ocr.subprocess.run') as process:
                with self.assertRaisesRegex(ValueError,'hash mismatch'):ocr_bundle(root,root/'output')
                process.assert_not_called()

    def test_path_escape_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);bundle=root/'bundle';bundle.mkdir()
            image=root/'outside.png';Image.new('RGB',(20,20),'white').save(image)
            manifest=dict(state='review_required',source_sha256='a'*64,pages=[dict(
                page=1,image='../outside.png',image_sha256=hashlib.sha256(image.read_bytes()).hexdigest(),width=20,height=20)])
            (bundle/'manifest.json').write_text(json.dumps(manifest))
            with patch('homelab_vision.ocr.subprocess.run') as process:
                with self.assertRaisesRegex(ValueError,'escapes'):ocr_bundle(bundle,root/'output')
                process.assert_not_called()
