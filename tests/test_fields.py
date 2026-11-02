import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from homelab_vision.fields import candidate, check_candidates, collect_invoice_fields, normalize, ocr_lines


class FieldEvidenceTests(unittest.TestCase):
    def fixture(self, root):
        bundle = root/'bundle'; bundle.mkdir()
        image = bundle/'page.png'; Image.new('RGB', (600, 800), 'white').save(image)
        lines = ['Invoice: INV-2042', 'Asset: LAB-GW-17', 'Quantity: 2',
                 'Unit price: USD 34.50', 'Total: USD 69.00']
        text = bundle/'page.txt'; text.write_text('\n'.join(lines), encoding='utf-8')
        page = dict(page=1, image='page.png', text='page.txt', width=600, height=800,
                    image_sha256=hashlib.sha256(image.read_bytes()).hexdigest(),
                    text_sha256=hashlib.sha256(text.read_bytes()).hexdigest())
        source = dict(state='review_required', source_sha256='a'*64, pages=[page])
        (bundle/'manifest.json').write_text(json.dumps(source))
        words = []
        for n, line in enumerate(lines):
            for j, token in enumerate(line.split()):
                words.append(dict(text=token, box=[20+j*90, 30+n*40, 80, 20], block=1, paragraph=1, line=n+1))
        ocr = dict(state='review_required', source_sha256='a'*64, pages=[dict(
            page=1, width=600, height=800, image_sha256=page['image_sha256'], words=words)])
        path = root/'ocr.json'; path.write_text(json.dumps(ocr))
        return bundle, path, ocr

    def test_evidence_report_preserves_both_paths_and_never_accepts(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); bundle, path, _ = self.fixture(root)
            record = collect_invoice_fields(bundle, path, root/'output')
            self.assertEqual(record['state'], 'review_required')
            page = record['pages'][0]
            self.assertEqual(len(page['candidates']), 10)
            self.assertEqual(page['checks']['direct_text']['arithmetic'], 'pass')
            self.assertEqual(page['checks']['ocr']['arithmetic'], 'pass')
            self.assertTrue(all(v == 'agree' for v in page['checks']['path_agreement'].values()))
            self.assertTrue(all(c['box'] is None for c in page['candidates'] if c['method']=='direct_text'))
            self.assertEqual(next(c['box'] for c in page['candidates'] if c['method']=='ocr'), [20,30,170,20])
            with self.assertRaises(FileExistsError): collect_invoice_fields(bundle, path, root/'output')

    def test_duplicate_total_is_retained_and_not_selected(self):
        values = [candidate(line, 'ocr') for line in
                  ['Quantity: 2', 'Unit price: USD 34.50', 'Total: USD 69.00', 'Total: USD 96.00']]
        checks = check_candidates(values)
        self.assertEqual(checks['ocr']['counts']['total'], 2)
        self.assertEqual(checks['ocr']['arithmetic'], 'not_checkable')

    def test_wrong_currency_arithmetic_and_path_disagreement(self):
        values = [candidate(line, 'ocr') for line in
                  ['Quantity: 2', 'Unit price: USD 34.50', 'Total: EUR 69.00']]
        values.append(candidate('Total: USD 69.00', 'direct_text'))
        checks = check_candidates(values)
        self.assertEqual(checks['ocr']['arithmetic'], 'fail')
        self.assertEqual(checks['path_agreement']['total'], 'disagree')

    def test_no_forgiving_identifier_or_locale_repair(self):
        self.assertIsNone(normalize('invoice_id', 'INV-2042,'))
        self.assertEqual(normalize('invoice_id', 'INV-2O42'), 'INV-2O42')
        self.assertIsNone(normalize('total', 'USD 69,00'))
        self.assertIsNone(normalize('quantity', '2.0'))
        self.assertIsNone(candidate('Subtotal: USD 69.00', 'ocr'))

    def test_stale_ocr_hash_and_out_of_bounds_box_fail(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); bundle, path, original = self.fixture(root)
            altered = copy.deepcopy(original); altered['pages'][0]['image_sha256'] = 'b'*64
            path.write_text(json.dumps(altered))
            with self.assertRaisesRegex(ValueError, 'identity'): collect_invoice_fields(bundle, path, root/'wrong-hash')
            altered = copy.deepcopy(original); altered['pages'][0]['words'][0]['box'] = [590,0,50,20]
            path.write_text(json.dumps(altered))
            with self.assertRaisesRegex(ValueError, 'outside'): collect_invoice_fields(bundle, path, root/'wrong-box')
            self.assertEqual(json.loads((root/'wrong-box/fields.json').read_text())['state'], 'failed_or_interrupted')

    def test_report_escapes_raw_content(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); bundle, path, ocr = self.fixture(root)
            ocr['pages'][0]['words'][1]['text'] = '<script>alert(1)</script>'
            path.write_text(json.dumps(ocr))
            collect_invoice_fields(bundle, path, root/'report')
            html = (root/'report/review.html').read_text()
            self.assertNotIn('<script>', html)
            self.assertIn('&lt;script&gt;', html)


if __name__ == '__main__': unittest.main()
