import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from homelab_vision.document_app import index_document, search_document, ask_document
from homelab_vision.provider import VisionReply, ProviderError


class DocumentApplicationTests(unittest.TestCase):
    def bundle(self,root):
        source=root/'pages';source.mkdir()
        image=source/'page.png';Image.new('RGB',(80,100),'white').save(image)
        text=source/'page.txt';text.write_text('Invoice: INV-2042\nTotal: USD 69.00',encoding='utf-8')
        manifest=dict(state='review_required',source_sha256='a'*64,pages=[dict(page=1,image='page.png',text='page.txt',
            image_sha256=hashlib.sha256(image.read_bytes()).hexdigest(),text_sha256=hashlib.sha256(text.read_bytes()).hexdigest(),
            width=80,height=100,route='text_layer_review')])
        (source/'manifest.json').write_text(json.dumps(manifest))
        return source

    def test_source_citations_and_image_tamper_detection(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);source=self.bundle(root);index=root/'index'
            index_document(source,index)
            hit=search_document(index,'INV-2042')['hits'][0]
            self.assertEqual(hit['source']['locator'],'page:1;lines:1-2')
            self.assertIn('69.00',hit['text'])
            (index/'page-001.png').write_bytes(b'tampered')
            with self.assertRaisesRegex(ValueError,'hash mismatch'):search_document(index,'total')

    def test_ocr_from_another_pdf_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);source=self.bundle(root);ocr=root/'ocr.json'
            ocr.write_text(json.dumps(dict(state='review_required',source_sha256='b'*64,pages=[])))
            with self.assertRaisesRegex(ValueError,'another PDF'):index_document(source,root/'index',ocr)

    def test_no_match_does_not_call_model(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);source=self.bundle(root);index=root/'index'
            index_document(source,index)
            with patch('homelab_vision.provider.LocalVisionClient') as client:
                result=ask_document(index,'elephant',root/'answer','fixture-model','http://127.0.0.1:1')
                self.assertEqual(result['state'],'not_found');client.assert_not_called()
            self.assertEqual(json.loads((root/'answer/answer.json').read_text())['cited_pages'],[])

    def test_duplicate_or_inconsistent_citations_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);source=self.bundle(root);index=root/'index'
            index_document(source,index)
            values=[dict(answer='USD69.00',cited_pages=[1,1],limitations=None),
                    dict(answer='USD69.00',cited_pages=[],limitations=None),
                    dict(answer=None,cited_pages=[1],limitations=None)]
            for number,value in enumerate(values):
                with patch('homelab_vision.provider.LocalVisionClient') as client:
                    client.return_value.analyze.return_value=VisionReply(value,{'fixture':True},.1)
                    with self.assertRaises(ProviderError):
                        ask_document(index,'total',root/f'answer-{number}','fixture-model','http://127.0.0.1:1')
                record=json.loads((root/f'answer-{number}/answer.json').read_text())
                self.assertEqual(record['state'],'failed_or_interrupted')
                self.assertEqual(record['provider_response'],{'fixture':True})
