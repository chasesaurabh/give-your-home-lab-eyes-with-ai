import importlib.util
from pathlib import Path
import unittest

path = Path(__file__).resolve().parents[1]/'experiments/compare_label_ocr.py'
spec = importlib.util.spec_from_file_location('compare_label_ocr', path)
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)


class OcrScoringTests(unittest.TestCase):
    def test_missing_duplicate_and_case_sensitive_fields(self):
        result = module.extract(['asset id: LAB-1333', 'model: Cedar-54', 'ports: 8', 'power: 12 V DC'])
        self.assertEqual(result, dict(asset_id='LAB-1333', model='Cedar-54', ports=8, power='12 V DC'))
        self.assertIsNone(module.extract(['ports: 8', 'ports: 8'])['ports'])
        self.assertIsNone(module.extract(['Model: Cedar-54'])['model'])
        self.assertIsNone(module.extract(['ports: 8.0'])['ports'])

    def test_punctuation_and_power_spacing_not_silently_repaired(self):
        result = module.extract(['asset id: LAB-1333,', 'power: 12V Dc'])
        self.assertEqual(result['asset_id'], 'LAB-1333,')
        self.assertNotEqual(result['power'], '12 V DC')

    def test_tsv_lines_do_not_merge_separate_blocks(self):
        tsv = 'level\tpage_num\tblock_num\tpar_num\tline_num\ttext\n'
        tsv += '5\t1\t1\t1\t1\tports:\n5\t1\t1\t1\t1\t8\n5\t1\t2\t1\t1\tpower:\n'
        self.assertEqual(module.parse_tsv(tsv), ['ports: 8', 'power:'])
