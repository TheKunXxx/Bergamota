#!/usr/bin/env python3
"""Fit splash to native panel, including upscaling; preserve aspect ratio."""
import argparse, struct, hashlib
from pathlib import Path
from PIL import Image
p=argparse.ArgumentParser();p.add_argument('source');p.add_argument('output');p.add_argument('--align-bottom',action='store_true');a=p.parse_args()
im=Image.open(a.source).convert('RGB');scale=min(1080/im.width,2248/im.height)
size=(round(im.width*scale),round(im.height*scale))
im=im.resize(size,Image.Resampling.LANCZOS)
canvas=Image.new('RGB',(1080,2248));canvas.paste(im,((1080-im.width)//2,(2248-im.height) if a.align_bottom else (2248-im.height)//2))
q=canvas.quantize(colors=256,method=Image.Quantize.MEDIANCUT,dither=Image.Dither.NONE)
pal=q.getpalette();data=q.tobytes();out=bytearray(struct.pack('<4sHHHH',b'EQSP',1080,2248,256,0))
for i in range(256):
 r,g,b=pal[i*3:i*3+3];out+=struct.pack('<I',0xff000000|r<<16|g<<8|b)
last=data[0];run=0
for c in data:
 if c==last and run<65535:run+=1
 else:out+=struct.pack('<HB',run,last);last=c;run=1
out+=struct.pack('<HB',run,last)
path=Path(a.output);path.write_bytes(out)
path.with_suffix('.sha256').write_text(hashlib.sha256(out).hexdigest()+'  '+path.name+'\n')
print('Source fitted to',size,'on 1080x2248; bytes',len(out))
