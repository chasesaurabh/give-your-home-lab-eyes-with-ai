"""Original diagram fixtures with editable SVG and explicit graph ground truth."""
import argparse,hashlib,html,json,math
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont

PROMPT = ('Transcribe only the visible diagram. Return JSON with nodes (node IDs), directed_edges '
    '(strings X->Y), undirected_edges (strings X--Y with endpoints alphabetically ordered), '
    'dashed_edges (same notation as the corresponding directed or undirected edge), '
    'group_membership (strings X=Zone using each visible node ID and its group label), '
    'dashed_meaning (exact meaning word in the legend, or none when no dashed edges), '
    'and tls_labeled (boolean: whether any connector visibly has the label TLS). '
    'All first five fields are arrays of strings, sorted alphabetically with no duplicates. '
    'Count only drawn node boxes; group borders and connector crossings are not nodes. '
    'A connector without arrowheads is undirected. Do not invent edges at a crossing. '
    'Do not infer security properties beyond the visible TLS label. Return no extra keys.')
SCHEMA=dict(type='object',properties={**{key:dict(type='array',items=dict(type='string')) for key in
    ['nodes','directed_edges','undirected_edges','dashed_edges','group_membership']},
    'dashed_meaning':dict(type='string'),'tls_labeled':dict(type='boolean')},
    required=['nodes','directed_edges','undirected_edges','dashed_edges','group_membership','dashed_meaning','tls_labeled'],additionalProperties=False)


def generate(font_path, variant, development=False):
    image=Image.new('RGB',(1280,800),'white');draw=ImageDraw.Draw(image)
    font=ImageFont.truetype(str(font_path),28);big=ImageFont.truetype(str(font_path),34)
    svg=['<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="800" viewBox="0 0 1280 800">',
         '<rect width="1280" height="800" fill="white"/>']
    def rect(box,fill='white',outline='#51616a',width=2):
        draw.rectangle(box,fill=fill,outline=outline,width=width)
        x,y,r,b=box;svg.append(f'<rect x="{x}" y="{y}" width="{r-x}" height="{b-y}" fill="{fill}" stroke="{outline}" stroke-width="{width}"/>')
    def text(x,y,value,large=False):
        draw.text((x,y),value,font=big if large else font,fill='#15232d')
        svg.append(f'<text x="{x}" y="{y+28 if not large else y+34}" font-family="Arial,sans-serif" font-size="{34 if large else 28}" fill="#15232d">{html.escape(value)}</text>')
    def line(start,end,dashed=False,arrow=True):
        x,y=start;u,v=end;length=math.hypot(u-x,v-y);dx=(u-x)/length;dy=(v-y)/length
        if dashed:
            for k in range(0,math.ceil(length),24):
                stop=min(k+14,length);draw.line((x+dx*k,y+dy*k,x+dx*stop,y+dy*stop),fill='#172f40',width=4)
        else:draw.line((*start,*end),fill='#172f40',width=4)
        attr=' stroke-dasharray="14 10"' if dashed else ''
        svg.append(f'<line x1="{x}" y1="{y}" x2="{u}" y2="{v}" stroke="#172f40" stroke-width="4"{attr}/>')
        if arrow:
            points=[(u,v),(u-dx*20-dy*10,v-dy*20+dx*10),(u-dx*20+dy*10,v-dy*20-dx*10)]
            draw.polygon(points,fill='#172f40')
            svg.append('<polygon points="'+' '.join(f'{a},{b}' for a,b in points)+'" fill="#172f40"/>')
    text(50,35,'Synthetic process diagram',True)
    if development:
        positions={'X':(330,350),'Y':(950,350)};groups={'X':'Source','Y':'Sink'}
        bounds=[('Source',(50,150,610,650)),('Sink',(670,150,1230,650))]
        directed=[('Y','X')];undirected=[];dashed={('Y','X')};meaning='optional';tls=False
    else:
        positions=dict(zip('ABCDEF',[(190,280),(640,280),(1090,280),(190,570),(640,570),(1090,570)]))
        groups={key:group for key,group in zip('ABCDEF',['Ingress','Worker','Store','Ingress','Worker','Store'])}
        bounds=[('Ingress',(35,140,350,650)),('Worker',(485,140,800,650)),('Store',(935,140,1250,650))]
        directed=[('A','B'),('B','C'),('D','E'),('E','F'),('B','E')];undirected=[];dashed=set();meaning='none';tls=False
        if variant=='reverse':directed=[(target,source) for source,target in directed]
        elif variant=='crossing':directed=[('A','E'),('D','B'),('B','C'),('E','F'),('B','E')]
        elif variant=='dashed':dashed={('B','C'),('D','E')};meaning='telemetry'
        elif variant=='undirected':directed.remove(('B','E'));undirected=[('B','E')]
        elif variant=='annotated':dashed={('D','E')};meaning='optional';tls=True
    for group,box in bounds:rect(box,fill='#f5f7f8',outline='#9da9af');text(box[0]+18,box[1]+18,group)
    def endpoint(source,target):
        x,y=positions[source];u,v=positions[target];dx=u-x;dy=v-y
        factor=min(80/abs(dx) if dx else float('inf'),40/abs(dy) if dy else float('inf'))
        return x+dx*factor,y+dy*factor
    for source,target in directed+undirected:
        line(endpoint(source,target),endpoint(target,source),(source,target) in dashed,(source,target) in directed)
    for node,(x,y) in positions.items():rect((x-80,y-40,x+80,y+40),outline='#172f40',width=3);text(x-12,y-20,node,True)
    if tls:text(835,220,'TLS')
    if meaning!='none':text(50,710,f'Legend: dashed = {meaning}')
    else:text(50,710,'Legend: arrows show direction; plain lines have no direction')
    svg.append('</svg>')
    edge=lambda pair:pair[0]+('->' if pair in directed else '--')+pair[1]
    expected=dict(nodes=sorted(positions),directed_edges=sorted(edge(pair) for pair in directed),
        undirected_edges=sorted(edge(pair) for pair in undirected),dashed_edges=sorted(edge(pair) for pair in dashed),
        group_membership=sorted(node+'='+group for node,group in groups.items()),dashed_meaning=meaning,tls_labeled=tls)
    return image,'\n'.join(svg),expected


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--font',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--development',action='store_true')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    cases=[]
    for variant in (['development'] if args.development else ['forward','reverse','crossing','dashed','undirected','annotated']):
        image,svg,expected=generate(args.font,variant,args.development)
        (args.output/f'{variant}.svg').write_text(svg,encoding='utf-8')
        for width in ([1280] if args.development else [1280,640]):
            pixels=image if width==1280 else image.resize((640,400),Image.Resampling.LANCZOS)
            name=f'{variant}-{width}.png';pixels.save(args.output/name)
            cases.append(dict(id=f'{variant}-{width}',task=variant,prompt=PROMPT,schema=SCHEMA,expected=expected,
                images=[dict(path=name,sha256=hashlib.sha256((args.output/name).read_bytes()).hexdigest())],
                dimensions=list(pixels.size),paired_design=variant))
    manifest=dict(split='development' if args.development else 'fixed_synthetic_diagrams',
        provenance='Original generated six-node diagrams; paired resolutions are not independent designs. No real system or personal image.',
        font_file=args.font.name,font_sha256=hashlib.sha256(args.font.read_bytes()).hexdigest(),
        generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),cases=cases)
    (args.output/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    (args.output/'generator.py').write_bytes(Path(__file__).read_bytes())
    print(json.dumps(dict(cases=len(cases),split=manifest['split'])))


if __name__=='__main__':main()
