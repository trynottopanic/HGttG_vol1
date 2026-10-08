"""Bake the video transition once using the current GuideOS UI face."""
from pathlib import Path
import argparse
from PIL import Image,ImageDraw,ImageFont

def generate(font,output):
    image=Image.new('RGB',(640,480),'#06111d')
    draw=ImageDraw.Draw(image);face=ImageFont.truetype(str(font),48)
    text='Opening Video';left,top,right,bottom=draw.textbbox((0,0),text,font=face)
    draw.text(((640-(right-left))/2-left,(480-(bottom-top))/2-top),
              text,font=face,fill='#edf5fb')
    Path(output).parent.mkdir(parents=True,exist_ok=True)
    image.save(output,optimize=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--font',type=Path,required=True)
    parser.add_argument('output',type=Path);args=parser.parse_args()
    generate(args.font,args.output)
