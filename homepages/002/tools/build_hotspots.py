#!/usr/bin/env python3
"""Compile locally exported hotspots.md to config/hotspots.json. No dependencies."""
import json, re, sys
from pathlib import Path

def convert(source):
    entries=[]
    for block in re.split(r'^## ',source,flags=re.M)[1:]:
        lines=block.splitlines()
        item={'label':lines[0].strip()}
        keys={'ID':'id','REGION':'region','X':'x','Y':'y','ACTION':'action','URL':'url','CONTENT':'content','MIN_ZOOM':'minZoom','REVEAL':'reveal'}
        for line in lines[1:]:
            m=re.match(r'^([A-Z_]+):\s*(.*)$',line)
            if m and m.group(1) in keys:item[keys[m.group(1)]]=m.group(2).replace('\\n','\n')
        for k in ('x','y'):item[k]=int(item[k])
        for k in ('minZoom','reveal'):item[k]=float(item.get(k,1.5 if k=='minZoom' else .9))
        if not re.fullmatch(r'x-?\d+_y-?\d+',item.get('region','')):raise ValueError('Invalid REGION: '+item.get('region',''))
        if not 0<=item['x']<4096 or not 0<=item['y']<4096:raise ValueError('Invalid local pixel coordinates')
        if item.get('action') not in ('link','modal'):raise ValueError('Invalid ACTION')
        entries.append(item)
    return entries

if __name__=='__main__':
    root=Path(__file__).resolve().parent.parent
    inputfile=Path(sys.argv[1]) if len(sys.argv)>1 else root/'hotspots.md'
    outputfile=root/'config'/'hotspots.json'
    records=convert(inputfile.read_text(encoding='utf8'))
    outputfile.write_text(json.dumps(records,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    print(f'Created {outputfile} with {len(records)} hotspot(s).')
