"""Ready-to-render split-screen templates and transparent local copy suggestions."""
import re
import textwrap
import unicodedata
from pathlib import Path

CATALOG = ('none', 'impact', 'compare', 'red')


def settings(raw):
    if not isinstance(raw, dict) or raw.get('id', 'none') not in CATALOG:
        raise ValueError('Template inválido.')
    title = raw.get('title', '')
    highlight = raw.get('highlight', '')
    topic = raw.get('topic', '')
    for value, limit in ((title, 120), (highlight, 40), (topic, 160)):
        if not isinstance(value, str) or len(value) > limit or any(ord(c) < 32 for c in value):
            raise ValueError('Use texto em uma linha e respeite o limite do template.')
    return dict(id=raw.get('id', 'none'), title=title, highlight=highlight, topic=topic)


def suggestion(topic, cues, start, end, preset):
    excerpt = ' '.join(re.sub(r'\s+', ' ', text).strip() for a, b, text in cues if b > start and a < end)
    title = topic.strip() or excerpt[:90].strip()
    if not title:
        return dict(title='', caption='', hashtags=[], source='Informe um tema ou importe SRT para gerar uma sugestão contextual.')
    normalized = unicodedata.normalize('NFKD', topic or excerpt).encode('ascii', 'ignore').decode().lower()
    words = re.findall(r'[a-z]{4,}', normalized)
    stop = {'para','como','esse','essa','isso','mais','muito','voce','sobre','aqui','porque','quando','onde','entao','tambem','qual','isso','este','esta','eles','elas','nosso','nossa','pelo','pela'}
    tags = list(dict.fromkeys('#'+w for w in words if w not in stop))[:4]
    tags += ['#cortes', {'reels':'#reels', 'shorts':'#shorts', 'tiktok':'#tiktok'}.get(preset, '#video')]
    caption = f'{topic.strip()}. ' if topic.strip() else ''
    if excerpt:
        caption += excerpt[:240].rstrip() + ('…' if len(excerpt) > 240 else '') + '\n\n'
    caption += 'Qual é a sua opinião? Conte nos comentários.'
    return dict(title=title[:120], caption=caption, hashtags=list(dict.fromkeys(tags)),
                source='Sugestão local baseada no tema e no SRT; revise antes de publicar. Sem análise semântica do vídeo.')


def ass_text(text):
    return text.replace('\\', '').replace('{', '').replace('}', '')


def title_ass(path, template, duration):
    title = template['title'].strip().upper()
    columns = 18
    lines = textwrap.wrap(title, width=columns, break_long_words=True)
    while len(lines) > 3:
        columns += 1
        lines = textwrap.wrap(title, width=columns, break_long_words=True)
    fontsize = max(30, round(80 * 18 / columns))
    highlight = ass_text(template['highlight'].upper().strip())
    content = r'\N'.join(ass_text(line) for line in lines)
    if highlight:
        content = content.replace(highlight, r'{\c&H00DDFF&}' + highlight + r'{\c&HFFFFFF&}')
    total = round(duration * 100)
    finish = f'{total//360000}:{total//6000%60:02}:{total//100%60:02}.{total%100:02}'
    Path(path).write_text('[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\nWrapStyle: 2\n'
        '[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n'
        f'Style: Title,DejaVu Sans,{fontsize},&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,-1,0,1,0,0,5,20,20,0,1\n'
        '[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n'
        f'Dialogue: 0,0:00:00.00,{finish},Title,,0,0,0,,{{\\pos(540,960)}}{content}\n', encoding='utf-8')


def filters(template, output, duration):
    """Two synchronized crops, with a center title band; compare uses three crops."""
    def view(source, destination, width, height, focus=.5, zoom=1):
        w, h = round(width*zoom), round(height*zoom)
        return f'[{source}]scale={w}:{h}:force_original_aspect_ratio=increase,crop={width}:{height}:x=(iw-ow)*{focus}:y=(ih-oh)*0.5,setsar=1,fps=30[{destination}]'
    if template['id'] == 'compare':
        graph = ['[0:v]split=3[a][b][c]', view('a','top',1080,820), view('b','left',540,820,.25),
                 view('c','right',540,820,.75), '[left][right]hstack=inputs=2[bottom]']
    else:
        graph = ['[0:v]split=2[a][b]', view('a','top',1080,820), view('b','bottom',1080,820,.5,1.5)]
    color = '0xc60013' if template['id'] == 'red' else 'black'
    graph += [f'color=c={color}:s=1080x280:r=30:d={duration}[band]', '[top][band][bottom]vstack=inputs=3[splitout]']
    titlefile = Path(output).with_suffix('.template.ass')
    title_ass(titlefile, template, duration)
    graph += [f'[splitout]subtitles={titlefile.name}[templated]']
    return ';'.join(graph)
