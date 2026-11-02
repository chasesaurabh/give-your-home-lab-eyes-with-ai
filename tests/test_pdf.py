import importlib.util
import tempfile
import unittest
from pathlib import Path

from homelab_vision.pdf import prepare_pdf, PdfValidationError

AVAILABLE=all(importlib.util.find_spec(name) for name in ['pypdfium2','reportlab','pypdf'])


@unittest.skipUnless(AVAILABLE,'Install the documents and test extras for real PDF conversion checks')
class PdfTests(unittest.TestCase):
    def setUp(self):
        from reportlab.pdfgen.canvas import Canvas
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.source=self.root/'digital.pdf'
        c=Canvas(str(self.source),pagesize=(300,300))
        c.drawString(20,250,'Invoice INV-2042 total USD 69.00')
        c.drawString(20,225,'<script>alert(1)</script>')
        c.showPage();c.save()

    def tearDown(self): self.temp.cleanup()

    def test_real_render_text_provenance_and_escaped_preview(self):
        result=prepare_pdf(self.source,self.root/'pages')
        self.assertEqual(result['state'],'review_required')
        self.assertEqual(result['pages'][0]['route'],'text_layer_review')
        self.assertIn('INV-2042',(self.root/'pages/page-001.txt').read_text())
        preview=(self.root/'pages/review.html').read_text()
        self.assertIn('&lt;script&gt;',preview);self.assertNotIn('<script>',preview)
        with self.assertRaises(FileExistsError): prepare_pdf(self.source,self.root/'pages')

    def test_limits_reject_before_render_output(self):
        with self.assertRaises(PdfValidationError): prepare_pdf(self.source,self.root/'too-large',max_bytes=10)
        with self.assertRaises(PdfValidationError): prepare_pdf(self.source,self.root/'too-many-pixels',max_page_pixels=10)
        self.assertFalse((self.root/'too-many-pixels').exists())

    def test_encrypted_and_malformed_rejected(self):
        from pypdf import PdfReader,PdfWriter
        writer=PdfWriter();writer.append(self.source);writer.encrypt('fixture-only')
        encrypted=self.root/'encrypted.pdf'
        with encrypted.open('wb') as stream:writer.write(stream)
        with self.assertRaises(PdfValidationError):prepare_pdf(encrypted,self.root/'encrypted-out')
        bad=self.root/'bad.pdf';bad.write_bytes(b'%PDF-1.7\nbroken')
        with self.assertRaises(PdfValidationError):prepare_pdf(bad,self.root/'bad-out')

    def test_blank_page_is_not_assumed_scanned_text(self):
        from reportlab.pdfgen.canvas import Canvas
        source=self.root/'blank.pdf';c=Canvas(str(source));c.showPage();c.save()
        result=prepare_pdf(source,self.root/'blank-out')
        self.assertEqual(result['pages'][0]['route'],'ocr_or_blank_review')
        self.assertEqual(result['pages'][0]['nonspace_characters'],0)
