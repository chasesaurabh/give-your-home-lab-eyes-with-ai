import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from homelab_vision import inventory_app as app


class InventoryAppTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.database=self.root/'items.sqlite'
        app.initialize(self.database)
        analysis=self.root/'analysis';analysis.mkdir()
        Image.new('RGB',(100,100),'white').save(analysis/'evidence.png')
        image_hash=app.digest(analysis/'evidence.png')
        (analysis/'input.json').write_text(json.dumps(dict(image='evidence.png',source_sha256='a'*64,normalized_sha256=image_hash)))
        (analysis/'proposal.json').write_text(json.dumps(dict(status='review_required',task='label',source_sha256='a'*64,
            image_sha256=image_hash,fields=dict(model='LAB-17',asset_id='ASSET-1',ports=8,power='12 VDC'))))
        self.review=self.root/'review'
        app.prepare(analysis,self.database,self.review,'switch-01','switch')

    def test_edited_review_needs_new_digest_and_replay_is_rejected(self):
        old=app.inspect_review(self.review,self.database)['review_sha256']
        path=self.review/'review.json';review=json.loads(path.read_text());review['fields']['model']='LAB-18';path.write_text(json.dumps(review))
        with self.assertRaises(ValueError):app.commit_review(self.review,self.database,old,'reviewer')
        current=app.inspect_review(self.review,self.database)['review_sha256']
        app.commit_review(self.review,self.database,current,'reviewer')
        self.assertEqual(app.export_inventory(self.database)['items'][0]['model'],'LAB-18')
        with self.assertRaises(PermissionError):app.commit_review(self.review,self.database,current,'reviewer')

    def test_evidence_tamper_blocks_commit(self):
        digest=app.inspect_review(self.review,self.database)['review_sha256']
        (self.review/'evidence.png').write_bytes(b'changed')
        with self.assertRaises(ValueError):app.commit_review(self.review,self.database,digest,'reviewer')
        self.assertEqual(app.export_inventory(self.database)['items'],[])

    def test_backup_restore_preserves_items_and_events(self):
        digest=app.inspect_review(self.review,self.database)['review_sha256']
        event=app.commit_review(self.review,self.database,digest,'reviewer')['event_id']
        snapshot=self.root/'snapshot.sqlite';app.backup(self.database,snapshot)
        original=app.export_inventory(self.database)
        app.undo(self.database,event,'reviewer',True)
        self.assertEqual(app.export_inventory(snapshot),original)
        self.assertEqual(app.export_inventory(self.database)['items'],[])
        with self.assertRaises(FileExistsError):app.backup(self.database,snapshot)


if __name__=='__main__':unittest.main()
