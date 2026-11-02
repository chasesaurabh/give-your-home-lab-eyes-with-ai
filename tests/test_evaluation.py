import importlib.util
from pathlib import Path
import unittest

path=Path(__file__).resolve().parents[1]/'experiments/evaluate.py'
spec=importlib.util.spec_from_file_location('evaluation',path)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class EvaluationTests(unittest.TestCase):
    def test_boolean_does_not_count_as_integer(self):
        self.assertFalse(module.score('{"n":true}',{'n':1})['exact'])
    def test_extra_claim_disqualifies_exact(self):
        result=module.score('{"n":2,"unsafe":"invented"}',{'n':2})
        self.assertFalse(result['exact'])
        self.assertEqual(result['correct_fields'],1)
    def test_prose_is_not_silently_repaired(self):
        self.assertFalse(module.score('Here: {"n":2}',{'n':2})['json_valid'])
    def test_abstention_is_recorded(self):
        self.assertEqual(module.score('{"n":null}',{'n':2})['abstained_fields'],1)
    def test_array_is_not_object(self):
        self.assertFalse(module.score('[2]',{'n':2})['exact'])
    def test_exact(self):
        self.assertTrue(module.score('{"n":2}',{'n':2})['exact'])
    def test_equivalent_json_number(self):
        self.assertTrue(module.score('{"n":72.0}',{'n':72})['exact'])
    def test_fraction_not_integer_target(self):
        self.assertFalse(module.score('{"n":2.5}',{'n':2})['exact'])
