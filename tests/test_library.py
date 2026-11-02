import unittest
from pathlib import Path
from unittest.mock import patch
from homelab_vision.library import search_library

class LibraryTests(unittest.TestCase):
    def test_scores_are_not_compared_and_citation_types_survive(self):
        with patch('homelab_vision.library.search_document',return_value=dict(state='review_required',hits=[dict(score=900,page=2,text='fan')])) as doc, patch('homelab_vision.library.search_frames',return_value=dict(state='review_required',hits=[dict(query_token_coverage=.5,timestamp_seconds=2.2,text='fan')])):
            result=search_library('fan',[Path('document')],[Path('video')])
            self.assertEqual(len(result['hits']),2)
            self.assertEqual(result['hits'][0]['rank_weight'],result['hits'][1]['rank_weight'])
            self.assertEqual(result['hits'][0]['evidence']['page'],2)
            self.assertEqual(result['hits'][1]['evidence']['timestamp_seconds'],2.2)
            doc.assert_called_once_with(Path('document'),'fan',10)

    def test_duplicate_inputs_and_corrupt_index_are_not_silently_skipped(self):
        with self.assertRaises(ValueError):search_library('fan',[Path('same'),Path('same')],[])
        with patch('homelab_vision.library.search_document',side_effect=ValueError('changed pixels')):
            with self.assertRaisesRegex(ValueError,'changed pixels'):search_library('fan',[Path('document')],[])

if __name__=='__main__':unittest.main()
