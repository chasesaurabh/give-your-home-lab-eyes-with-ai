"""Original fictional 6-second alert clip: no camera feed, people or private data.

Generate frames, then encode them with the supplied FFmpeg command. The reference
event occupies frames22..25 (2.2 <= t < 2.6 at10fps). No event text in other frames.
"""
import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--output',type=Path,required=True)
p.add_argument('--font',type=Path,required=True,help='Local TTF; font binary is not exported')
args=p.parse_args()
args.output.mkdir(parents=True,exist_ok=False)
font=ImageFont.truetype(str(args.font),28)
small=ImageFont.truetype(str(args.font),20)
frames=[]
for n in range(60):
    event=22<=n<26
    im=Image.new('RGB',(640,360),'#f4f6f8');d=ImageDraw.Draw(im)
    d.text((30,25),'FICTIONAL LAB MONITOR',font=font,fill='#183e55')
    d.text((30,80),f'Frame {n:02d}    Relative time {n/10:.1f} s',font=small,fill='#24313a')
    d.rectangle((30,130,610,260),fill='#a12c35' if event else '#315d70')
    d.text((65,170),'ALERT: FAN STOPPED' if event else 'STATUS: NORMAL',font=font,fill='white')
    d.text((30,300),'Original synthetic test clip; no live equipment',font=small,fill='#24313a')
    path=args.output/f'{n:04d}.png';im.save(path)
    frames.append(dict(index=n,timestamp_seconds=n/10,event=event,path=path.name,
        sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
(args.output/'manifest.json').write_text(json.dumps(dict(fps=10,duration_seconds=6,
    event_start_inclusive=2.2,event_end_exclusive=2.6,frames=frames,
    font_sha256=hashlib.sha256(args.font.read_bytes()).hexdigest()),indent=2))
print('Generated 60 fictional frames. Encode lossless FFV1 MKV at10fps; do not claim a camera test.')
