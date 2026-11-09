"""Single-user editing studio. Run: python3 -m studio.server"""
import argparse
import copy
import json
import mimetypes
import os
import re
import shutil
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http.cookies import SimpleCookie, CookieError
from pathlib import Path
from urllib.parse import unquote, urlsplit

from . import media, templates, auth

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get('STUDIO_DATA_DIR', ROOT.parent / '.studio')).resolve()
MAX_UPLOAD = 2 * 1024**3
POOL = ThreadPoolExecutor(max_workers=1)
LOCK = threading.Lock()
JOBS = {}
AUTH = auth.Sessions(os.environ.get('STUDIO_PASSWORD', ''), os.environ.get('STUDIO_USERNAME', 'studio'))


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-f0-9]{32}', value):
        raise ValueError('Identificador inválido.')
    return value


def save_json(path, data):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    temporary.replace(path)


def work(job_id, source, options, cues):
    with LOCK:
        JOBS[job_id]['status'] = 'processing'
    try:
        warnings = []
        if not cues and os.environ.get('AUTO_TRANSCRIBE', '1') == '1' and media.probe(source)['has_audio']:
            with LOCK:
                JOBS[job_id]['stage'] = 'Transcrevendo a fala para sugerir títulos e legendas…'
            try:
                cues = media.transcribe(source, options['start'], options['end'], DATA / 'exports' / (job_id+'.transcript.json'))
            except (ValueError, TimeoutError) as error:
                warnings.append(str(error))
        publication = templates.suggestion(options['template']['topic'], cues, options['start'], options['end'], options['preset'])
        selected = next((choice for choice in publication.get('choices', []) if choice['title'] == options['template']['title']), None)
        if selected:
            publication = dict(selected, choices=publication['choices'])
        with LOCK:
            JOBS[job_id].update(publication=publication, subtitles=media.clip_srt(cues, 0, 1e12), stage='Montando corte e foto automática…')
        if options['template']['id'] != 'none' and not options['template']['title'].strip():
            if publication['title']:
                options['template'].update(title=publication['title'], highlight=publication.get('highlight', ''))
            else:
                with LOCK:
                    JOBS[job_id]['requested_template'] = copy.deepcopy(options['template'])
                options['template']['id'] = 'none'
                if options['watermark']['position'] == 'title':
                    options['watermark']['position'] = 'top-right'
                warnings.append('O corte e a foto foram gerados sem o template porque não há fala reconhecida para criar o título. Aplique o template novamente após obter a transcrição.')
        if not publication['title']:
            publication['source'] = 'Não há fala transcrita disponível para sugerir título e legenda neste corte.'
        media.photo(source, options['start'], options['end'], DATA / 'exports' / (job_id+'.photo.jpg'))
        wm = options.get('watermark', {})
        logo = DATA / 'watermarks' / (wm['logo_id'] + '.png') if wm.get('enabled') and wm['type'] == 'logo' else None
        media.export(source, DATA / 'exports' / (job_id + '.mp4'), options, cues, watermark_path=logo)
        media.cover(DATA / 'exports' / (job_id + '.mp4'), DATA / 'exports' / (job_id + '.jpg'))
        with LOCK:
            JOBS[job_id].update(status='done', download=f'/exports/{job_id}.mp4', cover=f'/covers/{job_id}.jpg',
                               photo=f'/photos/{job_id}.jpg', warnings=warnings, stage='Concluído')
    except Exception as error:
        with LOCK:
            JOBS[job_id].update(status='error', error=str(error))
    finally:
        with LOCK:
            save_json(DATA / 'exports' / (job_id + '.json'), JOBS[job_id])


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def setup(self):
        super().setup()
        self.connection.settimeout(300)

    def json(self, data, status=200, headers=None):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)

    def body(self):
        size = int(self.headers.get('Content-Length', '0'))
        if not 0 < size <= 1_000_000:
            raise ValueError('Requisição inválida ou muito grande.')
        data = json.loads(self.rfile.read(size))
        if not isinstance(data, dict):
            raise ValueError('Envie um objeto JSON.')
        return data

    def session_token(self):
        try:
            cookie = SimpleCookie(self.headers.get('Cookie', ''))
            return cookie['cria_session'].value if 'cria_session' in cookie else ''
        except CookieError:
            return ''

    def signed_in(self):
        return not AUTH.required or AUTH.valid(self.session_token())

    def redirect(self, destination):
        self.send_response(303)
        self.send_header('Location', destination)
        self.send_header('Content-Length', '0')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Connection', 'close')
        self.end_headers()
        self.close_connection = True

    def authenticate(self):
        if self.signed_in():
            return True
        self.close_connection = True
        if urlsplit(self.path).path == '/':
            self.redirect('/login')
        else:
            self.json({'error': 'Sua sessão expirou. Entre novamente.', 'login': '/login'}, 401)
        return False

    def cookie_header(self, token, expires=False):
        secure = '; Secure' if self.headers.get('X-Forwarded-Proto', '').split(',')[0].strip() == 'https' else ''
        age = 0 if expires else AUTH.lifetime
        return f'cria_session={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age={age}{secure}'

    def login(self):
        if self.headers.get('Content-Type', '').split(';')[0].strip() != 'application/json':
            self.close_connection = True
            return self.json({'error': 'Envie o login pela página de entrada.'}, 415)
        try:
            raw = self.body()
            if any(not isinstance(raw.get(key), str) or len(raw[key]) > 1024 for key in ('username', 'password')):
                raise ValueError('Informe usuário e senha.')
            token = AUTH.login(raw['username'].strip(), raw['password'], self.client_address[0])
            return self.json({'ok': True}, headers={'Set-Cookie': self.cookie_header(token)})
        except auth.InvalidCredentials:
            return self.json({'error': 'Usuário ou senha não conferem. Use a senha de STUDIO_PASSWORD no Render.'}, 401)
        except auth.TooManyAttempts:
            return self.json({'error': 'Muitas tentativas. Aguarde um minuto e tente novamente.'}, 429, {'Retry-After': '60'})
        except (ValueError, TypeError):
            self.close_connection = True
            return self.json({'error': 'Informe usuário e senha válidos.'}, 400)

    def do_POST(self):
        # This service is intended for a trusted, single-user environment.
        # Block cross-site browser submissions; no CORS access is granted.
        if self.headers.get('Sec-Fetch-Site') == 'cross-site':
            self.close_connection = True
            return self.json({'error': 'Origem não permitida.'}, 403)
        if urlsplit(self.path).path == '/api/auth/login':
            return self.login()
        if not self.authenticate():
            return
        if urlsplit(self.path).path == '/api/auth/logout':
            AUTH.logout(self.session_token())
            self.close_connection = True
            return self.json({'ok': True}, headers={'Set-Cookie': self.cookie_header('', expires=True)})
        try:
            path = urlsplit(self.path).path
            if path == '/api/upload':
                return self.upload()
            if path == '/api/watermark':
                return self.upload_watermark()
            if path == '/api/suggest':
                raw = self.body()
                template = templates.settings(raw.get('template', {}))
                cues = media.parse_srt(raw.get('subtitles', ''))
                start = media.number(raw.get('start', 0), 'Início', 0, 1e8)
                end = media.number(raw.get('end', 1e8), 'Fim', start, 1e8)
                return self.json(templates.suggestion(template['topic'], cues, start, end, raw.get('preset', 'custom')))
            if path == '/api/export':
                raw = self.body()
                asset_id = identifier(raw.get('asset_id'))
                metadata = DATA / 'uploads' / (asset_id + '.json')
                if not metadata.is_file():
                    return self.json({'error': 'Vídeo não encontrado.'}, 404)
                info = json.loads(metadata.read_text())
                options = media.settings(raw, info['duration'])
                wm = options['watermark']
                if wm['enabled'] and wm['type'] == 'logo' and not (DATA / 'watermarks' / (wm['logo_id'] + '.png')).is_file():
                    raise ValueError('Logo não encontrado. Envie o arquivo novamente.')
                parent_id = raw.get('reedit_of')
                if parent_id:
                    identifier(parent_id)
                    with LOCK:
                        parent = JOBS.get(parent_id)
                        if not parent or parent.get('asset_id') != asset_id or parent['status'] != 'done':
                            raise ValueError('Corte original não encontrado para edição.')
                cues = media.parse_srt(raw.get('subtitles', ''))
                publication = templates.suggestion(options['template']['topic'], cues, options['start'], options['end'], options['preset'])
                ranges = [(options['start'], options['end'])]
                if raw.get('batch'):
                    ranges = media.segments(options['start'], options['end'], raw.get('length', 30))
                with LOCK:
                    if sum(j['status'] in ('queued', 'processing') for j in JOBS.values()) + len(ranges) > 30:
                        return self.json({'error': 'A fila está cheia. Aguarde as exportações atuais.'}, 429)
                    jobs = []
                    for index, (start, end) in enumerate(ranges):
                        job_id = uuid.uuid4().hex
                        opts = dict(copy.deepcopy(options), start=start, end=end)
                        name = f'{parent["name"]} · nova versão' if parent_id else f'Corte {index+1:02}'
                        job = dict(id=job_id, name=name, status='queued', options=opts,
                                   asset_id=asset_id, parent_id=parent_id, subtitles=raw.get('subtitles', ''),
                                   publication=templates.suggestion(options['template']['topic'], cues, start, end, options['preset']))
                        JOBS[job_id] = job
                        save_json(DATA / 'exports' / (job_id + '.json'), job)
                        jobs.append(dict(job))
                        POOL.submit(work, job_id, DATA / 'uploads' / (asset_id + '.media'), opts, cues)
                return self.json({'jobs': jobs}, 202)
            self.json({'error': 'Rota não encontrada.'}, 404)
        except (ValueError, TypeError, OSError) as error:
            self.close_connection = True
            self.json({'error': str(error)}, 400)
        except Exception:
            self.close_connection = True
            self.json({'error': 'Não foi possível processar a requisição.'}, 500)

    def upload(self):
        size = int(self.headers.get('Content-Length', '0'))
        if not 0 < size <= MAX_UPLOAD:
            self.close_connection = True
            return self.json({'error': 'Envie um vídeo de até 2 GB.'}, 413)
        asset_id = uuid.uuid4().hex
        target = DATA / 'uploads' / (asset_id + '.media')
        try:
            with target.open('xb') as output:
                remaining = size
                while remaining:
                    block = self.rfile.read(min(1024 * 1024, remaining))
                    if not block:
                        raise ValueError('Envio interrompido. Tente novamente.')
                    output.write(block)
                    remaining -= len(block)
            info = media.probe(target)
            name = Path(unquote(self.headers.get('X-Filename', 'video'))).name[:200]
            info.update(id=asset_id, name=name, url=f'/media/{asset_id}')
            save_json(target.with_suffix('.json'), info)
            self.json(info, 201)
        except Exception:
            target.unlink(missing_ok=True)
            raise

    def upload_watermark(self):
        size = int(self.headers.get('Content-Length', '0'))
        if not 0 < size <= 5 * 1024**2:
            self.close_connection = True
            return self.json({'error': 'O logo deve ter até 5 MB.'}, 413)
        logo_id = uuid.uuid4().hex
        raw = DATA / 'watermarks' / (logo_id + '.upload')
        target = raw.with_suffix('.png')
        try:
            body = self.rfile.read(size)
            if len(body) != size:
                raise ValueError('Envio de logo interrompido.')
            raw.write_bytes(body)
            data = json.loads(media.run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(raw)]))
            streams = data.get('streams', [])
            image = streams[0] if len(streams) == 1 else {}
            if image.get('codec_name') not in ('png', 'mjpeg') or data.get('format', {}).get('format_name') not in ('png_pipe', 'jpeg_pipe', 'image2'):
                raise ValueError('Envie uma imagem PNG ou JPEG estática.')
            if not 0 < image.get('width', 0) * image.get('height', 0) <= 16_000_000:
                raise ValueError('O logo deve ter até 16 megapixels.')
            media.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-i', str(raw),
                       '-frames:v', '1', '-pix_fmt', 'rgba', '-threads', '2', str(target)])
            return self.json({'id': logo_id, 'url': f'/watermarks/{logo_id}.png'}, 201)
        except Exception:
            target.unlink(missing_ok=True)
            raise
        finally:
            raw.unlink(missing_ok=True)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == '/api/auth/status':
            return self.json({'required': AUTH.required, 'authenticated': self.signed_in(), 'username': AUTH.username})
        public = {'/login': 'login.html', '/login.js': 'login.js', '/login.css': 'login.css',
                  '/fonts/space-grotesk-latin.woff2': 'fonts/space-grotesk-latin.woff2'}
        if path in public:
            if path == '/login' and self.signed_in():
                return self.redirect('/')
            return self.file(ROOT / 'web' / public[path], private=True)
        if path != '/api/health' and not self.authenticate():
            return
        try:
            path = urlsplit(self.path).path
            if path == '/api/health':
                return self.json({'status': 'ok', 'ffmpeg': bool(shutil.which('ffmpeg') and shutil.which('ffprobe'))})
            if path == '/api/jobs':
                with LOCK:
                    jobs = [dict(j) for j in JOBS.values()]
                return self.json({'jobs': jobs})
            if path.startswith('/api/assets/'):
                asset_id = identifier(path[len('/api/assets/'):])
                metadata = DATA / 'uploads' / (asset_id + '.json')
                if not metadata.is_file():
                    return self.json({'error': 'Vídeo original não encontrado.'}, 404)
                return self.json(json.loads(metadata.read_text()))
            if path.startswith('/watermarks/') and path.endswith('.png'):
                logo_id = identifier(path[len('/watermarks/'):-4])
                return self.file(DATA / 'watermarks' / (logo_id + '.png'))
            if path.startswith('/media/'):
                asset_id = identifier(path[7:])
                metadata = DATA / 'uploads' / (asset_id + '.json')
                if not metadata.is_file():
                    return self.json({'error': 'Vídeo não encontrado.'}, 404)
                name = json.loads(metadata.read_text())['name']
                content_type = mimetypes.guess_type(name)[0] or 'application/octet-stream'
                return self.file(DATA / 'uploads' / (asset_id + '.media'), content_type=content_type)
            if path.startswith('/exports/') and path.endswith('.mp4'):
                return self.file(DATA / 'exports' / (identifier(path[9:-4]) + '.mp4'), download=True)
            if path.startswith('/covers/') and path.endswith('.jpg'):
                return self.file(DATA / 'exports' / (identifier(path[8:-4]) + '.jpg'))
            if path.startswith('/photos/') and path.endswith('.jpg'):
                return self.file(DATA / 'exports' / (identifier(path[8:-4]) + '.photo.jpg'))
            static = {'/': 'index.html', '/app.js': 'app.js', '/style.css': 'style.css',
                      '/motion.js': 'motion.js', '/fonts/space-grotesk-latin.woff2': 'fonts/space-grotesk-latin.woff2'}
            static['/template-render.js'] = 'template-render.js'
            static['/fonts/Montserrat.ttf'] = 'fonts/Montserrat.ttf'
            if path in static:
                return self.file(ROOT / 'web' / static[path])
            self.json({'error': 'Não encontrado.'}, 404)
        except (ValueError, OSError):
            self.json({'error': 'Arquivo não encontrado.'}, 404)

    def do_HEAD(self):
        self.do_GET()

    def file(self, path, download=False, content_type=None, private=False):
        if not path.is_file():
            return self.json({'error': 'Arquivo não encontrado.'}, 404)
        size = path.stat().st_size
        start, end = 0, size - 1
        range_header = self.headers.get('Range')
        if range_header:
            match = re.fullmatch(r'bytes=(\d*)-(\d*)', range_header)
            if not match or not any(match.groups()):
                return self.json({'error': 'Intervalo inválido.'}, 416)
            a, b = match.groups()
            if a:
                start, end = int(a), min(int(b), end) if b else end
            else:
                start = max(0, size-int(b))
            if start > end or start >= size:
                self.send_response(416)
                self.send_header('Content-Range', f'bytes */{size}')
                self.send_header('Content-Length', '0')
                self.end_headers()
                return
        self.send_response(206 if range_header else 200)
        self.send_header('Content-Type', content_type or mimetypes.guess_type(str(path))[0] or 'application/octet-stream')
        self.send_header('Content-Length', str(end-start+1))
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('X-Content-Type-Options', 'nosniff')
        if private or AUTH.required:
            self.send_header('Cache-Control', 'no-store')
        if range_header:
            self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
        if download:
            self.send_header('Content-Disposition', f'attachment; filename="corte-{path.stem[:8]}.mp4"')
        self.end_headers()
        if self.command == 'HEAD':
            return
        try:
            with path.open('rb') as source:
                source.seek(start)
                remaining = end-start+1
                while remaining:
                    block = source.read(min(256*1024, remaining))
                    if not block:
                        break
                    self.wfile.write(block)
                    remaining -= len(block)
        except (BrokenPipeError, ConnectionResetError):
            pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()
    if args.host not in ('127.0.0.1', 'localhost', '::1') and not os.environ.get('STUDIO_PASSWORD'):
        parser.error('Defina STUDIO_PASSWORD para expor o servidor fora da interface local.')
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
        parser.error('Instale FFmpeg e ffprobe antes de iniciar.')
    for name in ('uploads', 'exports', 'watermarks'):
        (DATA / name).mkdir(parents=True, exist_ok=True)
    AUTH.attach_storage(DATA / '.sessions.json')
    for path in (DATA / 'exports').glob('*.json'):
        if not re.fullmatch(r'[a-f0-9]{32}', path.stem):
            continue
        job = json.loads(path.read_text())
        if job['status'] in ('queued', 'processing', 'transcribing'):
            job.update(status='error', error='O serviço reiniciou durante este processamento. Gere novamente a partir do vídeo original.')
        JOBS[job['id']] = job
    print(f'Cria Studio iniciado na porta {args.port}', flush=True)
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == '__main__':
    main()
