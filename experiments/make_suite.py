"""Generate original synthetic vision fixtures with explicit ground truth.

These test controlled visual tasks, not real-world or population accuracy.
"""
import argparse
import hashlib
import json
import random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

TASKS = ['label', 'document', 'screenshot', 'chart', 'counting', 'frames']

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def canvas(font_path, size=30, background='white'):
    image = Image.new('RGB', (960, 640), background)
    return image, ImageDraw.Draw(image), ImageFont.truetype(str(font_path), size)

def generate(task, index, rng, font_path):
    image, draw, font = canvas(font_path, 24 if index % 3 == 2 else 32)
    images = [image]
    variant = 'small-text' if index % 3 == 2 else 'standard'
    if task == 'label':
        asset = f'LAB-{rng.randrange(100,999)}'
        model = rng.choice(['Juniper', 'Aspen', 'Maple'])+'-'+str(rng.randrange(2,20))
        ports = rng.choice([4,8,16,24])
        power = rng.choice(['5 V DC','12 V DC','24 V DC'])
        lines = ['EQUIPMENT RECORD', f'Asset: {asset}', f'Model: {model}', f'Ports: {ports}', f'Power: {power}']
        for y,line in zip(range(80,580,90),lines): draw.text((70,y),line,font=font,fill='black')
        expected = dict(asset_id=asset, model=model, ports=ports, power=power)
        instruction = 'Read the equipment label. Return asset_id, model, ports (integer), power.'
    elif task == 'document':
        invoice = f'INV-{rng.randrange(1000,9999)}'
        qty = rng.randrange(2,9)
        price = rng.randrange(10,60)
        total = qty*price
        lines = ['SYNTHETIC INVOICE', f'Invoice: {invoice}', 'Item            Qty       Unit USD', f'Cable kit        {qty}          {price}.00', f'Total USD: {total}.00', 'Terms: Net 30']
        for y,line in zip(range(55,600,85),lines): draw.text((60,y),line,font=font,fill='black')
        expected = dict(invoice_id=invoice, quantity=qty, total_usd=total)
        instruction = 'Read the invoice. Return invoice_id, quantity (integer), total_usd (number).'
    elif task == 'screenshot':
        draw.rectangle((0,0,960,640),fill='#15202b')
        service = rng.choice(['archive','camera','indexer','ocr'])
        code = rng.choice(['E_DISK_FULL','E_TIMEOUT','E_ACCESS'])
        retries = rng.randrange(1,7)
        lines = ['SIMULATED TERMINAL', '$ labctl status', f'service={service}', f'state=failed code={code}', f'retries={retries}', 'Action required: review logs']
        for y,line in zip(range(50,600,85),lines): draw.text((45,y),line,font=font,fill='white')
        expected = dict(service=service, error_code=code, retries=retries)
        instruction = 'Read the simulated terminal. Return service, error_code, retries (integer). Do not propose actions.'
    elif task == 'chart':
        values = rng.sample(range(10,91,5),4)
        labels = ['A','B','C','D']
        draw.text((60,25),'Synthetic completed jobs per node',font=font,fill='black')
        draw.line((100,100,100,520),fill='black',width=3)
        draw.line((100,520,900,520),fill='black',width=3)
        for n in range(0,101,20):
            y=520-n*4
            draw.line((95,y,900,y),fill='#cccccc',width=1)
            draw.text((35,y-15),str(n),font=font,fill='black')
        for x,label,value in zip([210,390,570,750],labels,values):
            draw.rectangle((x-45,520-value*4,x+45,520),fill='#426b84')
            draw.text((x-15,540),label,font=font,fill='black')
            draw.text((x-20,480-value*4),str(value),font=font,fill='black')
        expected = dict(highest_node=labels[values.index(max(values))], jobs_b=values[1])
        instruction = 'Read the chart. Return highest_node (A/B/C/D), jobs_b (integer).'
    elif task == 'counting':
        circles = rng.randrange(2,9)
        squares = rng.randrange(2,9)
        types = ['circle']*circles+['square']*squares
        rng.shuffle(types)
        draw.text((35,20),'Count the shapes',font=font,fill='black')
        for i,kind in enumerate(types):
            x=110+(i%5)*175+rng.randrange(-10,11)
            y=135+(i//5)*130+rng.randrange(-10,11)
            box=(x-32,y-32,x+32,y+32)
            if kind=='circle': draw.ellipse(box,fill='#456f86',outline='black',width=2)
            else: draw.rectangle(box,fill='#ba8440',outline='black',width=2)
        expected = dict(circles=circles, squares=squares)
        instruction = 'Count all filled shapes. Return circles (integer), squares (integer).'
        variant = 'nonoverlapping-grid'
    else:
        images=[]
        start=rng.randrange(1,80)
        onset=rng.choice([1,2])
        for frame in range(3):
            im,d,f=canvas(font_path,32)
            d.text((40,35),f'Timestamp: {start+frame*2} seconds',font=f,fill='black')
            d.rectangle((280,170,680,480),outline='black',width=4)
            status='ALARM' if frame>=onset else 'NORMAL'
            d.text((390,310),status,font=f,fill='black')
            images.append(im)
        expected = dict(first_alarm_seconds=start+onset*2)
        instruction = 'These frames are chronological. Return first_alarm_seconds (integer), the timestamp of the first frame showing ALARM.'
        variant='three-sampled-frames'
    if task in ['label','document'] and index % 3 == 1:
        images=[im.rotate(3,resample=Image.Resampling.BICUBIC,fillcolor='white').filter(ImageFilter.GaussianBlur(.4)) for im in images]
        variant='rotation-3deg-blur-0.4'
    return images, instruction, expected, variant

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--font',type=Path,required=True)
    p.add_argument('--split',choices=['development','evaluation'],required=True)
    args=p.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    rng=random.Random(34109 if args.split=='evaluation' else 81273)
    cases=[]
    for task in TASKS:
        for index in range(10 if args.split=='evaluation' else 1):
            images,prompt,expected,variant=generate(task,index,rng,args.font)
            case_id=f'{task}-{index:02d}'
            files=[]
            for frame,im in enumerate(images):
                path=args.output/f'{case_id}-{frame}.png'
                im.save(path)
                files.append(dict(path=path.name,sha256=digest(path)))
            cases.append(dict(id=case_id,task=task,variant=variant,images=files,
                prompt=prompt+' Return only one JSON object with exactly those keys. Use null if unreadable.',expected=expected))
    manifest=dict(schema_version=1,split=args.split,provenance='Original synthetic fixtures. No personal data. No real-world representativeness claimed.',
                  generator_sha256=digest(Path(__file__)),font_sha256=digest(args.font),cases=cases)
    (args.output/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(f'Generated {len(cases)} {args.split} cases')

if __name__=='__main__': main()
