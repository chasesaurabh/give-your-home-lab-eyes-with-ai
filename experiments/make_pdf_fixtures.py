"""Create six original PDFs for actual conversion, routing and rejection tests."""
import hashlib
import json
import argparse
from contextlib import closing
from pathlib import Path
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.utils import ImageReader
from pypdf import PdfReader, PdfWriter
import pypdfium2 as pdfium

parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
root=parser.parse_args().output;root.mkdir(parents=True,exist_ok=False)
def page(c):
    c.setFont('Helvetica-Bold',22);c.drawString(54,735,'SYNTHETIC MAINTENANCE INVOICE')
    c.setFont('Helvetica',14)
    for n,line in enumerate(['Invoice: INV-2042','Asset: LAB-GW-17','Service: Replace cooling fan',
        'Quantity: 2','Unit price: USD 34.50','Total: USD 69.00','This is fictional test data.']):
        c.drawString(54,675-n*42,line)
    c.showPage()
c=Canvas(str(root/'digital.pdf'),pagesize=(612,792));page(c);c.save()
with pdfium.PdfDocument(root/'digital.pdf') as doc:
    with closing(doc[0]) as p:
        with closing(p.render(scale=2)) as bitmap:
            im=bitmap.to_pil().convert('RGB');im.save(root/'invoice-scan.png')
c=Canvas(str(root/'scanned.pdf'),pagesize=(612,792));c.drawImage(str(root/'invoice-scan.png'),0,0,width=612,height=792);c.showPage();c.save()
c=Canvas(str(root/'mixed.pdf'),pagesize=(612,792));page(c);c.drawImage(str(root/'invoice-scan.png'),0,0,width=612,height=792);c.showPage();c.save()
writer=PdfWriter();writer.add_page(PdfReader(root/'digital.pdf').pages[0]);writer.pages[0].rotate(90)
with (root/'rotated.pdf').open('wb') as f:writer.write(f)
c=Canvas(str(root/'blank.pdf'),pagesize=(612,792));c.showPage();c.save()
writer=PdfWriter();writer.append(root/'digital.pdf');writer.encrypt('fixture-only')
with (root/'encrypted.pdf').open('wb') as f:writer.write(f)
(root/'malformed.pdf').write_bytes(b'%PDF-1.7\nnot a real PDF\n')
record=dict(provenance='Original fictional reportlab fixtures, no user document. Encrypted fixture password is fixture-only.',
    expected={'digital.pdf':['text_layer_review'],'scanned.pdf':['ocr_or_blank_review'],
        'mixed.pdf':['text_layer_review','ocr_or_blank_review'],'rotated.pdf':['text_layer_review'],
        'blank.pdf':['ocr_or_blank_review'],'encrypted.pdf':'reject','malformed.pdf':'reject'},
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in root.iterdir() if p.is_file()})
(root/'manifest.json').write_text(json.dumps(record,indent=2))
print(root)
