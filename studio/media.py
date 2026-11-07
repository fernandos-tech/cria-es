"""Local FFmpeg operations. No shell, external API or credentials required."""
import json
import math
import re
import subprocess
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
    return dict(duration=duration, width=video['width'], height=video['height'],
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
    return dict(start=start, end=end, layout=layout, preset=preset, crf=int(crf),
                normalize=bool(raw.get('normalize', True)), watermark=watermark,
                template=templates.settings(raw.get('template', {})))


def watermark_settings(raw):
    if not isinstance(raw, dict):
        raise ValueError('Configuração de marca d’água inválida.')
    enabled = bool(raw.get('enabled', False))
    kind = raw.get('type', 'text')
    position = raw.get('position', 'top-right')
    if kind not in ('text', 'logo') or position not in ('top-left', 'top-right', 'bottom-left', 'bottom-right'):
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


def export(source, output, options, cues=(), watermark_path=None):
    start, end = options['start'], options['end']
    filters = []
    template = options.get('template', {'id': 'none'})
    templated = template['id'] != 'none'
    prefix = templates.filters(template, output, end-start) if templated else ''
    if templated:
        filters += ['null']
    elif options['layout'] == 'fit':
        filters += ['scale=1080:1920:force_original_aspect_ratio=decrease:force_divisible_by=2',
                    'pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black', 'setsar=1']
    elif options['layout'] == 'crop':
        filters += ['scale=1080:1920:force_original_aspect_ratio=increase:force_divisible_by=2',
                    'crop=1080:1920', 'setsar=1']
    else:
        filters += ['scale=trunc(iw/2)*2:trunc(ih/2)*2', 'setsar=1']
    subtitle = clip_srt(cues, start, end)
    if subtitle:
        # Relative, generated filename: no user-controlled path in filter syntax.
        Path(output).with_suffix('.srt').write_text(subtitle, encoding='utf-8')
        filters.append("subtitles=" + Path(output).with_suffix('.srt').name + ":force_style='FontName=DejaVu Sans,FontSize=20,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=0,Alignment=2,MarginV=55'")
    watermark = options.get('watermark', {})
    logo = watermark.get('enabled') and watermark['type'] == 'logo'
    if watermark.get('enabled'):
        width, height = 1080, 1920
        if options['layout'] == 'original' and not templated:
            info = probe(source)
            width, height = info['width'] // 2 * 2, info['height'] // 2 * 2
        margin_x, margin_y = max(2, round(width * .035)), max(2, round(height * .05))
        position = watermark['position']
        if logo:
            if watermark_path is None or not Path(watermark_path).is_file():
                raise ValueError('Logo não encontrado. Envie o arquivo novamente.')
            x = str(margin_x) if position.endswith('left') else f'W-w-{margin_x}'
            y = str(margin_y) if position.startswith('top') else f'H-h-{margin_y}'
            logo_width = max(2, round(width * watermark['size'] / 100))
            logo_height = max(2, round(height * .25))
            input_label = '[templated]' if templated else '[0:v]'
            complex_filter = (prefix + ';' if templated else '') + input_label + ','.join(filters) + '[base];[1:v]scale=' + str(logo_width) + ':' + str(logo_height) + ':force_original_aspect_ratio=decrease,format=rgba,colorchannelmixer=aa=' + str(watermark['opacity']) + '[logo];[base][logo]overlay=x=' + x + ':y=' + y + ':shortest=1[out]'
        else:
            textfile = Path(output).with_suffix('.watermark.txt')
            textfile.write_text(watermark['text'], encoding='utf-8')
            fontsize = max(6, min(round(height * watermark['size'] / 100), round(width * .84 / max(1, len(watermark['text'])) / .65)))
            x = str(margin_x) if position.endswith('left') else f'w-tw-{margin_x}'
            y = str(margin_y) if position.startswith('top') else f'h-th-{margin_y}'
            filters.append(f'drawtext=font=DejaVu Sans:textfile={textfile.name}:expansion=none:fontsize={fontsize}:fontcolor=white@{watermark["opacity"]}:shadowcolor=black@0.6:shadowx=1:shadowy=1:x={x}:y={y}')
    args = ['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
            '-threads', '2', '-ss', str(start), '-i', str(Path(source).resolve())]
    if logo:
        args += ['-loop', '1', '-i', str(Path(watermark_path).resolve())]
    args += ['-t', str(end-start), '-sn', '-dn', '-map_metadata', '-1', '-filter_threads', '2']
    if logo:
        args += ['-filter_complex_threads', '2', '-filter_complex', complex_filter, '-map', '[out]']
    elif templated:
        args += ['-filter_complex_threads', '2', '-filter_complex', prefix + ';[templated]' + ','.join(filters) + '[out]', '-map', '[out]']
    else:
        args += ['-vf', ','.join(filters), '-map', '0:v:0']
    args += ['-map', '0:a:0?', '-r', '30',
            '-c:v', 'libx264', '-preset', 'medium', '-crf', str(options['crf']),
            '-pix_fmt', 'yuv420p', '-threads', '2', '-c:a', 'aac', '-b:a', '192k', '-ar', '48000']
    if options['normalize']:
        args += ['-af', 'loudnorm=I=-16:TP=-1.5:LRA=11']
    args += ['-movflags', '+faststart', Path(output).name]
    result = subprocess.run(args, cwd=Path(output).parent, capture_output=True, text=True, timeout=7200)
    if result.returncode:
        Path(output).unlink(missing_ok=True)
        raise ValueError('Falha ao exportar. ' + result.stderr[-1600:])
