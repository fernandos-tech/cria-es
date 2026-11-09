"""Local FFmpeg operations. No shell, external API or credentials required."""
import json
import math
import re
import subprocess
import sys
import os
import hashlib
from pathlib import Path
from . import templates


def run(args, timeout=120):
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise ValueError('Falha no processamento do vídeo. ' + result.stderr[-1600:])
    return result.stdout


def probe(path):
    data = json.loads(run(['ffprobe', '-v', 'error', '-show_format', '-show_streams', '-of', 'json', str(path)]))
    video = next((s for s in data['streams'] if s['codec_type'] == 'video' and not s.get('disposition', {}).get('attached_pic')), None)
    if not video:
        raise ValueError('O arquivo precisa conter uma faixa de vídeo.')
    duration = float(data.get('format', {}).get('duration', video.get('duration', 0)))
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError('Não foi possível determinar a duração do vídeo.')
    width, height = video['width'], video['height']
    rotation = next((side.get('rotation', 0) for side in video.get('side_data_list', [])
                     if side.get('side_data_type') == 'Display Matrix'), video.get('tags', {}).get('rotate', 0))
    try:
        if abs(float(rotation) % 180 - 90) < 1:
            width, height = height, width
    except (ValueError, TypeError):
        pass
    return dict(duration=duration, width=width, height=height,
                has_audio=any(s['codec_type'] == 'audio' for s in data['streams']))


def number(value, name, low, high):
    try:
        value = float(value)
    except (ValueError, TypeError):
        raise ValueError(f'{name}: informe um número válido.') from None
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f'{name}: use um valor entre {low:g} e {high:g}.')
    return value


def settings(raw, duration):
    start = number(raw.get('start', 0), 'Início', 0, duration)
    end = number(raw.get('end', duration), 'Fim', 0, duration)
    if end - start < 0.1:
        raise ValueError('O fim deve estar pelo menos 0,1 segundo após o início.')
    layout = raw.get('layout', 'fit')
    if layout not in ('fit', 'crop', 'original'):
        raise ValueError('Enquadramento inválido.')
    preset = raw.get('preset', 'custom')
    if preset not in ('tiktok', 'reels', 'shorts', 'custom'):
        raise ValueError('Preset inválido.')
    crf = number(raw.get('crf', 18), 'Qualidade CRF', 16, 28)
    watermark = watermark_settings(raw.get('watermark', {}))
    template = templates.settings(raw.get('template', {}))
    if watermark['enabled'] and watermark['position'] == 'title' and (template['id'] != 'impact' or watermark['type'] != 'text'):
        raise ValueError('A posição abaixo do título exige texto e o template Referência 1.')
    return dict(start=start, end=end, layout=layout, preset=preset, crf=int(crf),
                normalize=bool(raw.get('normalize', True)), watermark=watermark,
                template=template)


def watermark_settings(raw):
    if not isinstance(raw, dict):
        raise ValueError('Configuração de marca d’água inválida.')
    enabled = bool(raw.get('enabled', False))
    kind = raw.get('type', 'text')
    position = raw.get('position', 'top-right')
    if kind not in ('text', 'logo') or position not in ('top-left', 'top-right', 'bottom-left', 'bottom-right', 'custom', 'title'):
        raise ValueError('Tipo ou posição da marca d’água inválido.')
    text = raw.get('text', '')
    if not isinstance(text, str) or len(text) > 80 or any(ord(c) < 32 for c in text):
        raise ValueError('A marca d’água deve ter até 80 caracteres, em uma linha.')
    logo_id = raw.get('logo_id', '')
    if not isinstance(logo_id, str) or (logo_id and not re.fullmatch(r'[a-f0-9]{32}', logo_id)):
        raise ValueError('Logo inválido.')
    if enabled and ((kind == 'text' and not text.strip()) or (kind == 'logo' and not logo_id)):
        raise ValueError('Digite o texto ou envie o logo para ativar a marca d’água.')
    return dict(enabled=enabled, type=kind, position=position, text=text, logo_id=logo_id,
                x=number(raw.get('x', 50), 'Posição horizontal', 0, 100),
                y=number(raw.get('y', 50), 'Posição vertical', 0, 100),
                opacity=number(raw.get('opacity', .8), 'Opacidade', .1, 1),
                size=number(raw.get('size', 4 if kind == 'text' else 20), 'Tamanho', 2, 30))


def segments(start, end, length):
    length = number(length, 'Duração', 1, 600)
    count = math.ceil((end - start) / length)
    if count > 30:
        raise ValueError('Máximo de 30 cortes por lote. Aumente a duração ou reduza o intervalo.')
    return [(start + i * length, min(end, start + (i + 1) * length)) for i in range(count)
            if min(end, start + (i + 1) * length) - (start + i * length) >= 0.1]


SRT_TIME = re.compile(r'(\d{2,}):(\d{2}):(\d{2}),(\d{3})')


def timestamp(raw):
    match = SRT_TIME.fullmatch(raw.strip())
    if not match:
        raise ValueError('Tempo inválido no SRT. Use HH:MM:SS,mmm.')
    h, m, s, ms = map(int, match.groups())
    if m > 59 or s > 59:
        raise ValueError('Tempo inválido no SRT.')
    return h * 3600 + m * 60 + s + ms / 1000


def parse_srt(text):
    if not text.strip():
        return []
    if len(text.encode('utf-8')) > 500_000:
        raise ValueError('A legenda deve ter no máximo 500 KB.')
    cues = []
    for block in re.split(r'\n\s*\n', text.lstrip('\ufeff').replace('\r\n', '\n').strip()):
        lines = block.splitlines()
        if lines and lines[0].strip().isdigit():
            lines = lines[1:]
        if len(lines) < 2 or ' --> ' not in lines[0]:
            raise ValueError('Arquivo SRT inválido.')
        times = lines[0].split(' --> ')
        if len(times) != 2:
            raise ValueError('Arquivo SRT inválido.')
        start, end = map(timestamp, times)
        if end <= start:
            raise ValueError('Intervalo inválido no SRT.')
        # Plain text only: prevent subtitle markup from controlling the renderer.
        caption = re.sub(r'<[^>]*>|\{[^}]*\}', '', '\n'.join(lines[1:])).replace('\\', '')
        cues.append((start, end, caption))
    return cues


def srt_time(seconds):
    ms = round(seconds * 1000)
    return f'{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}'


def clip_srt(cues, start, end):
    out = []
    for a, b, caption in cues:
        if b <= start or a >= end:
            continue
        out.append(f'{len(out)+1}\n{srt_time(max(a, start)-start)} --> {srt_time(min(b, end)-start)}\n{caption}\n')
    return '\n'.join(out)


def prepare_top(source, output, options):
    height=900 if options['template']['id']=='red' else 960
    target=Path(output).with_suffix('.top.mkv')
    try:
        run(['ffmpeg','-nostdin','-v','error','-y','-threads','1','-ss',str(options['start']),'-i',str(Path(source).resolve()),
             '-t',str(options['end']-options['start']),'-map','0:v:0','-map','0:a:0?','-sn','-dn',
             '-filter_threads','1','-vf',templates.crop_filter(1080,height),'-pix_fmt','yuv420p',
             '-c:v','libx264','-crf','0','-preset','ultrafast','-tune','zerolatency','-threads','1','-bf','0',
             '-c:a','pcm_s16le',str(target)],timeout=7200)
        return target
    except Exception:
        target.unlink(missing_ok=True)
        raise


def export(source, output, options, cues=(), watermark_path=None):
    start, end = options['start'], options['end']
    filters = []
    template = dict(options.get('template', {'id': 'none'}))
    watermark = options.get('watermark', {})
    centered_brand = template['id'] == 'impact' and watermark.get('enabled') and watermark['type'] == 'text' and watermark['position'] == 'title'
    if centered_brand:
        template.update(brand=watermark['text'], brand_opacity=watermark['opacity'])
    templated = template['id'] != 'none'
    photo_path = Path(output).with_suffix('.photo.jpg')
    if templated and not photo_path.is_file():
        photo(source, start, end, photo_path)
    info = probe(source) if templated or options['layout'] == 'original' else None
    direct = templated and info['width'] * info['height'] <= 1920 * 1080
    prefix = templates.filters(template, output, end-start, direct=direct) if templated else ''
    if templated:
        filters += ['null']
    elif options['layout'] == 'fit':
        filters += ['scale=1080:1920:force_original_aspect_ratio=decrease:force_divisible_by=2',
                    'pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black', 'setsar=1']
    elif options['layout'] == 'crop':
        filters += [templates.crop_filter(1080,1920)]
    else:
        filters += ["scale=w='min(1920,iw)':h='min(1920,ih)':force_original_aspect_ratio=decrease:force_divisible_by=2", 'setsar=1']
    subtitle = clip_srt(cues, start, end)
    if subtitle:
        # Relative, generated filename: no user-controlled path in filter syntax.
        Path(output).with_suffix('.srt').write_text(subtitle, encoding='utf-8')
        filters.append("subtitles=" + Path(output).with_suffix('.srt').name + ":force_style='FontName=DejaVu Sans,FontSize=20,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=0,Alignment=2,MarginV=55'")
    logo = watermark.get('enabled') and watermark['type'] == 'logo'
    if watermark.get('enabled') and not centered_brand:
        width, height = 1080, 1920
        if options['layout'] == 'original' and not templated:
            factor=min(1,1920/max(info['width'],info['height']))
            width, height = int(info['width']*factor)//2*2, int(info['height']*factor)//2*2
        margin_x, margin_y = max(2, round(width * .035)), max(2, round(height * .05))
        position = watermark['position']
        if logo:
            if watermark_path is None or not Path(watermark_path).is_file():
                raise ValueError('Logo não encontrado. Envie o arquivo novamente.')
            x = str(margin_x) if position.endswith('left') else f'W-w-{margin_x}'
            y = str(margin_y) if position.startswith('top') else f'H-h-{margin_y}'
            if position == 'custom':
                x, y = f'(W-w)*{watermark["x"]/100}', f'(H-h)*{watermark["y"]/100}'
            logo_width = max(2, round(width * watermark['size'] / 100))
            logo_height = max(2, round(height * .25))
            input_label = '[templated]' if templated else '[0:v]'
            logo_input = '2:v' if templated else '1:v'
            complex_filter = (prefix + ';' if templated else '') + input_label + ','.join(filters) + '[base];[' + logo_input + ']scale=' + str(logo_width) + ':' + str(logo_height) + ':force_original_aspect_ratio=decrease,format=rgba,colorchannelmixer=aa=' + str(watermark['opacity']) + '[logo];[base][logo]overlay=x=' + x + ':y=' + y + ':shortest=1[out]'
        else:
            textfile = Path(output).with_suffix('.watermark.txt')
            textfile.write_text(watermark['text'], encoding='utf-8')
            fontsize = max(6, min(round(height * watermark['size'] / 100), round(width * .84 / max(1, len(watermark['text'])) / .65)))
            x = str(margin_x) if position.endswith('left') else f'w-tw-{margin_x}'
            y = str(margin_y) if position.startswith('top') else f'h-th-{margin_y}'
            if position == 'custom':
                x, y = f'(w-tw)*{watermark["x"]/100}', f'(h-th)*{watermark["y"]/100}'
            filters.append(f'drawtext=font=DejaVu Sans:textfile={textfile.name}:expansion=none:fontsize={fontsize}:fontcolor=white@{watermark["opacity"]}:shadowcolor=black@0.6:shadowx=1:shadowy=1:x={x}:y={y}')
    normalized=prepare_top(source,output,options) if templated and not direct else None
    args = ['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
            '-threads', '1', '-ss', '0' if normalized else str(start), '-i', str(normalized.resolve() if normalized else Path(source).resolve())]
    if templated:
        for image in (Path(output).with_suffix('.template.png'),):
            args += ['-threads', '1', '-framerate', '1', '-loop', '1', '-i', str(image.resolve())]
    if logo:
        args += ['-threads', '1', '-framerate', '1', '-loop', '1', '-i', str(Path(watermark_path).resolve())]
    args += ['-t', str(end-start), '-sn', '-dn', '-map_metadata', '-1', '-filter_threads', '1']
    if logo:
        args += ['-filter_complex_threads', '1', '-filter_complex', complex_filter, '-map', '[out]']
    elif templated:
        args += ['-filter_complex_threads', '1', '-filter_complex', prefix + ';[templated]' + ','.join(filters) + '[out]', '-map', '[out]']
    else:
        args += ['-vf', ','.join(filters), '-map', '0:v:0']
    args += ['-map', '0:a:0?', '-r', '30',
            '-c:v', 'libx264', '-preset', 'veryfast', '-tune', 'zerolatency', '-rc-lookahead', '0', '-bf', '0', '-crf', str(options['crf']),
            '-pix_fmt', 'yuv420p', '-threads', '1', '-c:a', 'aac', '-b:a', '192k', '-ar', '48000']
    if options['normalize']:
        args += ['-af', 'loudnorm=I=-16:TP=-1.5:LRA=11']
    args += ['-movflags', '+faststart', Path(output).name]
    try:
        result = subprocess.run(args, cwd=Path(output).parent, capture_output=True, text=True, timeout=7200)
    finally:
        if normalized:
            normalized.unlink(missing_ok=True)
    if result.returncode:
        Path(output).unlink(missing_ok=True)
        raise ValueError('Falha ao exportar. ' + result.stderr[-1600:])


def cover(video, target):
    info = probe(video)
    run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y', '-threads', '1',
         '-ss', str(min(info['duration']*.4, max(0, info['duration']-.05))), '-i', str(video),
         '-frames:v', '1', '-vf', 'scale=360:640:force_original_aspect_ratio=decrease,pad=360:640:(ow-iw)/2:(oh-ih)/2',
         '-filter_threads', '1', '-threads', '1', '-q:v', '2', str(target)])


def photo(source, start, end, target):
    run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-threads', '1', '-ss', str(start+(end-start)*.5),
         '-i', str(Path(source).resolve()), '-frames:v', '1', '-vf', 'scale=min(1920\\,iw):-2',
         '-filter_threads', '1', '-threads', '1', '-q:v', '2', str(target)])


def transcribe(source, start, end, target):
    source = Path(source).resolve()
    stat = source.stat()
    key = hashlib.sha256(json.dumps([str(source), stat.st_size, stat.st_mtime_ns, float(start), float(end),
                                    os.environ.get('STUDIO_WHISPER_MODEL', 'tiny'), 'pt-v1']).encode()).hexdigest()
    cache_dir = source.parent / 'transcripts'
    cache = cache_dir / (key + '.json')
    try:
        cues = json.loads(cache.read_text())
        if not isinstance(cues, list) or any(not isinstance(c, list) or len(c) != 3 or
                not isinstance(c[2], str) or not all(isinstance(t, (int, float)) and math.isfinite(t) for t in c[:2]) or
                c[1] <= c[0] for c in cues):
            raise ValueError('Cache inválido.')
        return cues
    except (OSError, ValueError, TypeError):
        pass
    env = dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', HF_HUB_DISABLE_XET='1', HF_HUB_DOWNLOAD_TIMEOUT='120')
    try:
        result = subprocess.run([sys.executable, '-m', 'studio.speech', str(source), str(start), str(end), str(target)],
                                capture_output=True, text=True, timeout=1800, env=env)
    except subprocess.TimeoutExpired:
        raise ValueError('A transcrição demorou demais. O corte será gerado; tente a transcrição novamente depois.') from None
    if result.returncode:
        raise ValueError('Não foi possível transcrever automaticamente. Verifique o acesso ao modelo de fala e tente novamente.')
    cues = json.loads(Path(target).read_text())
    cache_dir.mkdir(exist_ok=True)
    temporary = cache.with_suffix('.tmp')
    temporary.write_text(json.dumps(cues, ensure_ascii=False))
    temporary.replace(cache)
    return cues
