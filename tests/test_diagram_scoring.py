import importlib.util,json
from pathlib import Path
import unittest

path=Path(__file__).resolve().parents[1]/'experiments/score_diagrams.py'
spec=importlib.util.spec_from_file_location('diagram_scoring',path)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class DiagramScoringTests(unittest.TestCase):
    def setUp(self):self.expected=dict(nodes=['A','B'],directed_edges=['A->B'],undirected_edges=[],dashed_edges=[],
        group_membership=['A=Input','B=Output'],dashed_meaning='none',tls_labeled=False)

    def test_order_only_variation_passes(self):
        actual={**self.expected,'nodes':['B','A'],'group_membership':['B=Output','A=Input']}
        self.assertTrue(module.score_diagram(json.dumps(actual),self.expected)['exact'])

    def test_duplicate_and_wrong_direction_are_counted(self):
        actual={**self.expected,'nodes':['A','B','B'],'directed_edges':['B->A']}
        result=module.score_diagram(json.dumps(actual),self.expected)
        self.assertFalse(result['exact'])
        self.assertEqual(result['differences']['nodes']['extra'],['B'])
        self.assertEqual(result['differences']['directed_edges'],dict(missing=['A->B'],extra=['B->A']))

    def test_no_type_punctuation_or_extra_key_repair(self):
        for actual in [{**self.expected,'tls_labeled':0},{**self.expected,'directed_edges':['A -> B']},
                       {**self.expected,'unsupported':'encrypted'},{**self.expected,'nodes':['A',1]}]:
            self.assertFalse(module.score_diagram(json.dumps(actual),self.expected)['exact'])

    def test_incomplete_output_fails(self):
        self.assertFalse(module.score_diagram('{"nodes":',self.expected)['exact'])
        self.assertFalse(module.score_diagram('[]',self.expected)['exact'])
