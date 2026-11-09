"""Layouts traced from the three user references, with a fixed photo below the title."""
import re
import unicodedata
import json
import subprocess
import sys
from pathlib import Path
from collections import Counter

CATALOG=('none','impact','compare','red')
FONT=Path(__file__).parent/'web'/'fonts'/'Montserrat.ttf'
STOP=set('a o as os um uma de da do das dos e em no na nos nas para por com sem que qual como esse essa isso mais muito voce sobre aqui porque quando onde entao tambem este esta eles elas nosso nossa pelo pela tem ser uma sao nao sim tudo gente vai foi vou isto coisa'.split())


def settings(raw):
    if not isinstance(raw,dict) or raw.get('id','none') not in CATALOG:raise ValueError('Template inválido.')
    title,highlight,topic=(raw.get(key,'') for key in ('title','highlight','topic'))
    for value,limit in ((title,120),(highlight,80),(topic,160)):
        if not isinstance(value,str) or len(value)>limit or any(ord(c)<32 for c in value):raise ValueError('Texto inválido no template.')
    return dict(id=raw.get('id','none'),title=title,highlight=highlight,topic=topic)


def normalize(text):
    return unicodedata.normalize('NFKD',text).encode('ascii','ignore').decode().lower()


def choices(topic,cues,start,end,preset):
    excerpt=' '.join(re.sub(r'\s+',' ',text).strip() for a,b,text in cues if b>start and a<end)
    if not excerpt and not topic.strip():return []
    phrases=[p.strip(' .!?') for p in re.split(r'(?<=[.!?])\s+|\n+',excerpt) if len(p.strip())>8]
    if len(phrases)<3:
        words=excerpt.split()
        phrases += [' '.join(words[i:i+12]) for i in range(0,len(words),12) if len(words[i:i+12])>=3]
    if topic.strip():phrases.insert(0,topic.strip())
    phrases=list(dict.fromkeys(p[:100].strip() for p in phrases if p))[:3]
    if not phrases:phrases=[excerpt[:100]]
    counts=Counter(w for w in re.findall(r'[\wÀ-ÿ]+',normalize(topic+' '+excerpt)) if len(w)>3 and w not in STOP)
    tags=['#'+w for w,_ in counts.most_common(4)]+['#cortes',{'reels':'#reels','shorts':'#shorts','tiktok':'#tiktok'}.get(preset,'#video')]
    result=[]
    for i,phrase in enumerate(phrases):
        highlights=[word for word in phrase.split() if len(normalize(word.strip(',.!?')))>4 and normalize(word.strip(',.!?')) not in STOP][-3:]
        result.append(dict(id=str(i+1),title=phrase,highlight='|'.join(highlights)[:80],caption=phrase+'\n\n'+excerpt[:400],hashtags=list(dict.fromkeys(tags)),source='Opção extraída da fala transcrita do corte.' if excerpt else 'Opção baseada no tema informado.'))
    return result


def suggestion(topic,cues,start,end,preset):
    options=choices(topic,cues,start,end,preset)
    if not options:return dict(title='',caption='',hashtags=[],choices=[],source='Aguardando transcrição automática do corte.')
    return dict(options[0],choices=options)


def font(size):
    from PIL import ImageFont
    result=ImageFont.truetype(str(FONT),size)
    try:result.set_variation_by_name('Black')
    except (ValueError,OSError):pass
    return result


def lines_for(title,size,max_width=1000):
    f=font(size);lines=[];line=''
    for word in title.split():
        candidate=(line+' '+word).strip()
        if f.getlength(candidate)>max_width and line:lines.append(line);line=word
        else:line=candidate
    if line:lines.append(line)
    return lines


def overlay(template,path,photo_path=None):
    from PIL import Image,ImageDraw,ImageFilter
    image=Image.new('RGBA',(1080,1920));draw=ImageDraw.Draw(image)
    red=template['id']=='red';center=1080 if red else 960
    if red:
        # Fixed torn-paper contour following reference 03; white exposed paper at edges.
        points=[(0,938),(82,925),(145,934),(210,916),(370,925),(490,914),(650,928),(805,921),(966,933),(1072,946),(1079,978),(1067,1015),(1077,1054),(1065,1110),(1080,1150),(1066,1203),(946,1214),(818,1206),(667,1221),(506,1211),(330,1224),(192,1210),(52,1217),(9,1200),(18,1163),(1,1120),(12,1083),(2,1044),(17,1008),(0,971)]
        paper=[(max(0,min(1079,x+(8 if i%3==0 else -6))),y+(-10 if y<1000 else 9)) for i,(x,y) in enumerate(points)]
        shadow=Image.new('RGBA',image.size);ImageDraw.Draw(shadow).polygon([(x,y+9) for x,y in paper],fill=(0,0,0,180));image.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(9)))
        draw=ImageDraw.Draw(image);draw.polygon(paper,fill=(242,240,230,255));draw.polygon(points,fill=(218,0,10,255))
        tint=Image.new('RGBA',image.size);td=ImageDraw.Draw(tint)
        for offset in range(0,250,2):
            alpha=int(28*abs(offset-125)/125);td.line([(28,945+offset),(1052,945+offset)],fill=(80,0,0,alpha),width=2)
        image.alpha_composite(tint);draw=ImageDraw.Draw(image)
    else:
        half=160 if template['id']=='compare' else 132
        for y in range(center-half,center+half):
            alpha=int(255*min(1,(half-abs(y-center))/45))
            draw.line([(0,y),(1080,y)],fill=(0,0,0,alpha))
    title=template['title'].strip().upper();size=82
    while size>30:
        lines=lines_for(title,size)
        if len(lines)<=3 and len(lines)*size*1.08<=230:break
        size-=2
    f=font(size);highlights={normalize(w.strip(',.!?')) for w in template.get('highlight','').replace('|',' ').split()}
    line_height=round(size*1.08);top=center-len(lines)*line_height/2
    for index,line in enumerate(lines):
        x=(1080-f.getlength(line))/2;y=top+index*line_height
        for word in re.findall(r'\S+\s*',line):
            color=(255,220,0,255) if not red and normalize(word.strip(' ,.?!')) in highlights else (255,255,255,255)
            draw.text((x,y),word,font=f,fill=color,anchor='lt',stroke_width=0);x+=f.getlength(word)
    if template.get('brand') and template['id']=='impact':
        brand_layer=Image.new('RGBA',image.size);draw=ImageDraw.Draw(brand_layer)
        brand=template['brand'];brand_size=28;small=font(brand_size)
        while small.getlength(brand)>940 and brand_size>10:
            brand_size-=1;small=font(brand_size)
        alpha=round(255*template.get('brand_opacity',1))
        x=(1080-small.getlength(brand))/2;y=center+len(lines)*line_height/2+9
        draw.text((x,y),brand,font=small,fill=(245,245,245,alpha),anchor='lt',stroke_width=1,stroke_fill=(0,0,0,alpha))
        for icon_x in (x-28,x+small.getlength(brand)+8):
            draw.ellipse((icon_x,y+2,icon_x+20,y+22),fill=(255,255,255,alpha))
            draw.rounded_rectangle((icon_x+3,y+7,icon_x+17,y+17),radius=2,fill=(255,0,10,alpha))
            draw.polygon([(icon_x+8,y+9),(icon_x+8,y+15),(icon_x+13,y+12)],fill=(255,255,255,alpha))
        image.alpha_composite(brand_layer)
    if photo_path is not None:
        background=Image.new('RGBA',(1080,1920))
        with Image.open(photo_path) as source:
            source=source.convert('RGB')
            def put(x,y,width,height,focus=.5,zoom=1):
                iw,ih=source.size
                crop_w=max(2,int(min(iw,ih*width/height)/zoom)//2*2)
                crop_h=max(2,int(min(ih,iw*height/width)/zoom)//2*2)
                left=round((iw-crop_w)*focus);top=round((ih-crop_h)/2)
                region=source.crop((left,top,left+crop_w,top+crop_h)).resize((width,height),Image.Resampling.LANCZOS)
                background.paste(region,(x,y))
            if template['id']=='red':put(0,984,1080,852,.5,1.25)
            elif template['id']=='compare':put(0,960,540,960,.25);put(540,960,540,960,.75)
            else:put(0,960,1080,960,.5,1.5)
        background.alpha_composite(image)
        image=background
    image.save(path)


def crop_filter(width,height,focus=.5,zoom=1):
    ratio=width/height
    return f"crop=w='trunc(min(iw,ih*{ratio})/{zoom}/2)*2':h='trunc(min(ih,iw/{ratio})/{zoom}/2)*2':x=(iw-ow)*{focus}:y=(ih-oh)*0.5,scale={width}:{height},setsar=1,fps=30"


def filters(template,output,duration,direct=False):
    y=84 if template['id']=='red' else 0
    height=900 if template['id']=='red' else 960
    source=crop_filter(1080,height)+',' if direct else ''
    graph=[f'[0:v]{source}pad=1080:1920:0:{y}:black[composition]',
           '[composition][1:v]overlay=0:0:shortest=1,format=yuv420p[templated]']
    result=subprocess.run([sys.executable,str(Path(__file__).resolve()),str(Path(output).with_suffix('.template.png').resolve()),str(Path(output).with_suffix('.photo.jpg').resolve())],
                          input=json.dumps(template,ensure_ascii=False),capture_output=True,text=True,timeout=60)
    if result.returncode:
        raise ValueError('Não foi possível gerar o gráfico do template. '+result.stderr[-400:])
    return ';'.join(graph)


if __name__=='__main__':
    overlay(json.load(sys.stdin),sys.argv[1],sys.argv[2] if len(sys.argv)>2 else None)
