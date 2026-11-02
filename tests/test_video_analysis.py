import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from homelab_vision.provider import VisionReply, ProviderError
from homelab_vision.video_analysis import analyze_frames, search_frames, verify_frames


class VideoAnalysisTests(unittest.TestCase):
    def bundle(self,root):
        source=root/'input';source.mkdir()
        path=source/'frame.png';Image.new('RGB',(64,32),'white').save(path)
        manifest=dict(state='review_required',source_sha256='a'*64,interval_seconds=1,frames=[dict(
            image='frame.png',sha256=hashlib.sha256(path.read_bytes()).hexdigest(),timestamp_seconds=2.2,frame_index=22)])
        (source/'manifest.json').write_text(json.dumps(manifest))
        return source,manifest

    def test_search_preserves_citations_and_rejects_tampering(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);source,_=self.bundle(root);out=root/'analysis'
            reply=VisionReply(dict(visible_text='FAN STOPPED',description='A fictional status display',limitations=None),{},.1)
            with patch('homelab_vision.video_analysis.LocalVisionClient') as client:
                client.return_value.analyze.return_value=reply
                analyze_frames(source,out,'fixture-model','http://127.0.0.1:1')
            hit=search_frames(out,'fan stopped')['hits'][0]
            self.assertEqual(hit['timestamp_seconds'],2.2)
            self.assertEqual(hit['source_sha256'],'a'*64)
            self.assertEqual(search_frames(out,'elephant')['state'],'not_found')
            (out/'0000.json').write_text('{}')
            with self.assertRaisesRegex(ValueError,'hash mismatch'):search_frames(out,'fan')

    def test_failed_analysis_cannot_be_searched_as_complete(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);source,_=self.bundle(root);out=root/'analysis'
            with patch('homelab_vision.video_analysis.LocalVisionClient') as client:
                client.return_value.analyze.side_effect=ProviderError('incomplete output')
                with self.assertRaises(ProviderError):analyze_frames(source,out,'fixture-model','http://127.0.0.1:1')
            self.assertEqual(json.loads((out/'manifest.json').read_text())['state'],'failed_or_interrupted')
            with self.assertRaises(ValueError):search_frames(out,'fan')

    def test_frame_path_escape_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);source,manifest=self.bundle(root)
            outside=root/'outside.png';outside.write_bytes((source/'frame.png').read_bytes())
            manifest['frames'][0]['image']='../outside.png'
            (source/'manifest.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError,'path or size'):verify_frames(source)
