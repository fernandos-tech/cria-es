import http.client
import json
import os
from pathlib import Path
import socket
import secrets
import subprocess
import tempfile
import time
import unittest

from studio import media, templates, auth


class EditingRules(unittest.TestCase):
    def test_sessions_expiration_and_limits(self):
        password=secrets.token_urlsafe(32)+'çã'
        sessions=auth.Sessions(password,username='usuarioadmin',lifetime=-1)
        token=sessions.login('usuarioadmin',password,'owner')
        self.assertFalse(sessions.valid(token))
        sessions=auth.Sessions(password,username='usuarioadmin')
        for _ in range(6):
            with self.assertRaises(auth.InvalidCredentials):sessions.login('usuarioadmin','wrong','attacker')
        with self.assertRaises(auth.TooManyAttempts):sessions.login('usuarioadmin',password,'attacker')
        token=sessions.login('usuarioadmin',password,'owner')
        self.assertTrue(sessions.valid(token));sessions.logout(token);self.assertFalse(sessions.valid(token))

    def test_session_survives_process_restart_and_logout(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'sessions.json';password=secrets.token_urlsafe(24)
            first=auth.Sessions(password);first.attach_storage(path);token=first.login('studio',password,'owner')
            second=auth.Sessions(password);second.attach_storage(path);self.assertTrue(second.valid(token))
            self.assertNotIn(token,path.read_text());second.logout(token)
            third=auth.Sessions(password);third.attach_storage(path);self.assertFalse(third.valid(token))
            changed=auth.Sessions(password+'changed');changed.attach_storage(path);self.assertFalse(changed.valid(token))

    def test_choices_are_derived_from_spoken_content(self):
        cues=[(0,2,'Este perfume tem notas cítricas.'),(2,4,'A duração dele é muito boa.'),(4,6,'Prefiro o segundo perfume para o verão.')]
        options=templates.choices('',cues,0,6,'reels')
        self.assertGreaterEqual(len(options),2)
        for option in options:
            self.assertTrue(option['title']);self.assertIn('#reels',option['hashtags'])
        self.assertEqual(templates.choices('',[],0,2,'reels'),[])
    def test_watermark_validation_and_title_suggestions(self):
        for wm in ({'enabled':True,'text':''},{'position':'somewhere'},{'opacity':float('nan')},{'text':'a\nb'}):
            with self.subTest(wm=wm),self.assertRaises(ValueError):media.watermark_settings(wm)
        response=templates.suggestion('Perfumes e aromas',[(0,1,'Um aroma cítrico.'),(5,6,'Trecho fora do corte.')],0,2,'reels')
        self.assertIn('cítrico',response['caption'])
        self.assertNotIn('fora do corte',response['caption'])
        self.assertIn('#perfumes',response['hashtags'])
        self.assertEqual(templates.suggestion('',[],0,1,'shorts')['title'],'')

    def test_invalid_ranges_and_numbers(self):
        for raw in ({'end': 0}, {'start': -1}, {'end': 99}, {'start': float('nan')}, {'layout': 'unknown'}):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                media.settings(raw, 10)

    def test_batch_preserves_remainder(self):
        self.assertEqual(media.segments(2, 10, 3), [(2, 5), (5, 8), (8, 10)])
        with self.assertRaises(ValueError):
            media.segments(0, 1000, 1)

    def test_subtitles_are_trimmed_and_rebased(self):
        cues = media.parse_srt('1\r\n00:00:01,000 --> 00:00:04,000\r\nOlá, mundo!\r\n\r\n2\r\n00:00:05,000 --> 00:00:06,000\r\nFim\r\n')
        clipped = media.clip_srt(cues, 2, 5.5)
        self.assertIn('00:00:00,000 --> 00:00:02,000', clipped)
        self.assertIn('00:00:03,000 --> 00:00:03,500', clipped)
        with self.assertRaises(ValueError):
            media.parse_srt('not an SRT')


class FullWorkflow(unittest.TestCase):
    def test_missing_speech_does_not_lose_video_or_photo(self):
        source=self.directory/'silent-fallback.mp4'
        media.run(['ffmpeg','-v','error','-f','lavfi','-i','color=c=blue:s=160x90:r=30','-t','0.5','-c:v','libx264','-threads','1',str(source)])
        status,_,body=self.request('POST','/api/upload',source.read_bytes(),{'X-Filename':'silent.mp4'})
        self.assertEqual(status,201);asset=json.loads(body)
        status,_,body=self.request('POST','/api/export',json.dumps(dict(asset_id=asset['id'],end=.5,template=dict(id='impact'))))
        self.assertEqual(status,202,body);job=self.wait_job(json.loads(body)['jobs'][0]['id'])
        self.assertEqual(job['options']['template']['id'],'none');self.assertEqual(job['requested_template']['id'],'impact')
        self.assertFalse(job['publication']['choices']);self.assertTrue(job['warnings'])
        self.assertEqual(self.request('GET',job['photo'])[0],200);self.assertEqual(self.request('GET',job['download'])[0],200)

    def wait_job(self,job_id):
        deadline=time.monotonic()+90
        while time.monotonic()<deadline:
            status,_,body=self.request('GET','/api/jobs')
            job=next(j for j in json.loads(body)['jobs'] if j['id']==job_id)
            if job['status'] in ('done','error'):
                self.assertEqual(job['status'],'done',job)
                return job
            time.sleep(.15)
        self.fail('Export did not complete')

    def test_templates_revision_and_logo(self):
        status,_,body=self.request('POST','/api/upload',self.source.read_bytes(),{'X-Filename':'original.mp4'})
        self.assertEqual(status,201,body);asset=json.loads(body)
        base=dict(asset_id=asset['id'],start=0,end=.6,layout='original',crf=24)
        status,_,body=self.request('POST','/api/export',json.dumps(base))
        self.assertEqual(status,202,body);parent=self.wait_job(json.loads(body)['jobs'][0]['id'])
        logo=self.directory/'red-logo.png'
        media.run(['ffmpeg','-hide_banner','-loglevel','error','-f','lavfi','-i','color=c=red:s=64x32',
                   '-frames:v','1','-threads','2',str(logo)])
        status,_,body=self.request('POST','/api/watermark',logo.read_bytes())
        self.assertEqual(status,201,body);logo_info=json.loads(body)
        for template in ['impact','compare','red']:
            options=dict(base,reedit_of=parent['id'],template=dict(id=template,title='QUAL É MELHOR?',highlight='MELHOR',topic='Comparação de perfumes'),
                         watermark=dict(enabled=True,type='logo',logo_id=logo_info['id'],position='top-right',size=20,opacity=1))
            status,_,body=self.request('POST','/api/export',json.dumps(options))
            self.assertEqual(status,202,body);job=self.wait_job(json.loads(body)['jobs'][0]['id'])
            self.assertEqual(job['parent_id'],parent['id']);self.assertEqual(job['asset_id'],asset['id'])
            self.assertEqual(self.request('GET',job['photo'])[0],200)
            self.assertEqual(self.request('GET',job['cover'])[0],200)
            self.assertIn('#perfumes',job['publication']['hashtags'])
            output=self.directory/'data'/'exports'/(job['id']+'.mp4')
            info=media.probe(output);self.assertEqual((info['width'],info['height']),(1080,1920))
            # Sample the center band away from text and the red logo center.
            pixels=subprocess.run(['ffmpeg','-v','error','-i',str(output),'-frames:v','1','-pix_fmt','rgb24','-threads','2','-f','rawvideo','-'],capture_output=True,check=True).stdout
            def pixel(x,y):return tuple(pixels[(y*1080+x)*3:(y*1080+x)*3+3])
            r,g,b=pixel(930,140);self.assertGreater(r,180);self.assertLess(g,70);self.assertLess(b,70)
            r,g,b=pixel(10,960)
            if template=='red':self.assertGreater(r,140);self.assertLess(g,50)
            else:self.assertLess(max(r,g,b),30)
        self.assertTrue((self.directory/'data'/'exports'/(parent['id']+'.mp4')).is_file())
        # Untrusted watermark text stays literal, including filter punctuation.
        options=dict(base,watermark=dict(enabled=True,text="@marca: 100% 'teste'",size=8,opacity=1,position='top-left'))
        status,_,body=self.request('POST','/api/export',json.dumps(options));self.assertEqual(status,202,body)
        self.wait_job(json.loads(body)['jobs'][0]['id'])
        self.assertEqual(self.request('POST','/api/watermark',b'not an image')[0],400)
        self.assertEqual(self.request('GET','/api/assets/'+asset['id'])[0],200)

    def test_template_uses_a_static_photo_and_automatic_title(self):
        status,_,body=self.request('POST','/api/upload',self.source.read_bytes(),{'X-Filename':'automatic.mp4'})
        self.assertEqual(status,201);asset=json.loads(body)
        raw=dict(asset_id=asset['id'],start=0,end=1,template=dict(id='impact',title='',highlight='',topic=''),
                 subtitles='1\n00:00:00,000 --> 00:00:01,000\nEste perfume tem notas cítricas. A duração dele é excelente. Prefiro usar no verão.\n')
        status,_,body=self.request('POST','/api/export',json.dumps(raw));self.assertEqual(status,202,body)
        job=self.wait_job(json.loads(body)['jobs'][0]['id']);self.assertTrue(job['options']['template']['title'])
        self.assertGreaterEqual(len(job['publication']['choices']),2)
        video=self.directory/'data'/'exports'/(job['id']+'.mp4')
        # The lower photograph is fixed while the source video keeps moving above it.
        data=subprocess.run(['ffmpeg','-v','error','-i',str(video),'-vf',r'select=eq(n\,0)+eq(n\,20),crop=240:160:400:1350',
             '-vsync','0','-frames:v','2','-threads','1','-pix_fmt','rgb24','-f','rawvideo','-'],capture_output=True,check=True).stdout
        length=240*160*3;self.assertEqual(len(data),length*2)
        error=sum(abs(a-b) for a,b in zip(data[:length],data[length:]))/length
        self.assertLess(error,3)
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.directory = Path(cls.temp.name)
        cls.source = cls.directory / 'sample.mp4'
        media.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-f', 'lavfi', '-i',
                   'testsrc2=size=320x180:rate=30', '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000',
                   '-t', '3', '-c:v', 'libx264', '-threads', '2', '-pix_fmt', 'yuv420p', '-c:a', 'aac', str(cls.source)])
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            cls.port = sock.getsockname()[1]
        cls.log = (cls.directory / 'server.log').open('w')
        cls.process = subprocess.Popen(['python3', '-m', 'studio.server', '--port', str(cls.port)],
                                       env=dict(os.environ, STUDIO_DATA_DIR=str(cls.directory / 'data'), AUTO_TRANSCRIBE='0'),
                                       stdout=cls.log, stderr=cls.log)
        for _ in range(100):
            try:
                if cls.request('GET', '/api/health')[0] == 200:
                    return
            except OSError:
                pass
            if cls.process.poll() is not None:
                break
            time.sleep(.1)
        raise RuntimeError('Server failed to start')

    @classmethod
    def tearDownClass(cls):
        cls.process.terminate()
        cls.process.wait(timeout=10)
        cls.log.close()
        cls.temp.cleanup()

    @classmethod
    def request(cls, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', cls.port, timeout=30)
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        connection.close()
        return result

    def test_upload_batch_render_and_download(self):
        status, _, data = self.request('POST', '/api/upload', self.source.read_bytes(), {'X-Filename': 'sample.mp4'})
        self.assertEqual(status, 201, data)
        asset = json.loads(data)
        self.assertTrue(asset['has_audio'])
        status, headers, part = self.request('GET', asset['url'], headers={'Range': 'bytes=0-99'})
        self.assertEqual(status, 206)
        self.assertEqual(len(part), 100)
        self.assertTrue(headers['Content-Range'].startswith('bytes 0-99/'))
        options = dict(asset_id=asset['id'], start=0, end=3, batch=True, length=2,
                       layout='crop', preset='shorts', normalize=True, crf=24,
                       subtitles='1\n00:00:01,000 --> 00:00:02,500\nTeste de legenda\n')
        status, _, body = self.request('POST', '/api/export', json.dumps(options), {'Content-Type': 'application/json'})
        self.assertEqual(status, 202, body)
        self.assertEqual(len(json.loads(body)['jobs']), 2)
        selected_ids = {job['id'] for job in json.loads(body)['jobs']}
        deadline = time.monotonic() + 100
        while time.monotonic() < deadline:
            _, _, body = self.request('GET', '/api/jobs')
            jobs = [job for job in json.loads(body)['jobs'] if job['id'] in selected_ids]
            if all(j['status'] in ('done', 'error') for j in jobs):
                break
            time.sleep(.2)
        self.assertEqual([j['status'] for j in jobs], ['done', 'done'], jobs)
        for job, duration in zip(jobs, (2, 1)):
            status, _, content = self.request('GET', job['download'])
            self.assertEqual(status, 200)
            downloaded = self.directory / (job['id'] + '.mp4')
            downloaded.write_bytes(content)
            info = media.probe(downloaded)
            self.assertEqual((info['width'], info['height']), (1080, 1920))
            self.assertTrue(info['has_audio'])
            self.assertAlmostEqual(info['duration'], duration, delta=.15)
            streams = json.loads(media.run(['ffprobe', '-v', 'error', '-show_streams', '-of', 'json', str(downloaded)]))['streams']
            video = next(s for s in streams if s['codec_type'] == 'video')
            self.assertEqual(video['codec_name'], 'h264')
            self.assertEqual(video['pix_fmt'], 'yuv420p')
            self.assertEqual(video['avg_frame_rate'], '30/1')
        second_srt = self.directory / 'data' / 'exports' / (jobs[1]['id'] + '.srt')
        self.assertIn('00:00:00,000 --> 00:00:00,500', second_srt.read_text())
        options['end'] = 999
        self.assertEqual(self.request('POST', '/api/export', json.dumps(options))[0], 400)

    def test_rejects_non_video_and_bad_ranges(self):
        status, _, _ = self.request('POST', '/api/upload', b'not a video')
        self.assertEqual(status, 400)
        self.assertEqual(self.request('GET', '/media/../../etc/passwd')[0], 404)
        self.assertEqual(self.request('POST', '/api/export', '{}', {'Sec-Fetch-Site': 'cross-site'})[0], 403)

    def test_silent_source_original_and_fit(self):
        source = self.directory / 'silent.mp4'
        media.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-f', 'lavfi', '-i', 'color=c=blue:s=160x90:r=30',
                   '-t', '0.3', '-c:v', 'libx264', '-threads', '2', str(source)])
        for layout, dimensions in [('fit', (1080, 1920)), ('original', (160, 90))]:
            target = self.directory / (layout + '.mp4')
            media.export(source, target, media.settings(dict(end=.3, layout=layout, crf=24), .3))
            info = media.probe(target)
            self.assertEqual((info['width'], info['height']), dimensions)
            self.assertFalse(info['has_audio'])


class HostedAccess(unittest.TestCase):
    def test_password_protects_editor_media_and_uploads(self):
        with tempfile.TemporaryDirectory() as temporary:
            exports=Path(temporary)/'exports';exports.mkdir()
            (exports/('a'*32+'.transcript.json')).write_text('[[0,1,"fala de teste"]]')
            with socket.socket() as sock:
                sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
            password=secrets.token_urlsafe(32)+'Çã@'
            with (Path(temporary)/'hosted.log').open('w') as log:
                process=subprocess.Popen(['python3','-m','studio.server','--port',str(port)],
                    env=dict(os.environ,STUDIO_DATA_DIR=temporary,STUDIO_PASSWORD=password,STUDIO_USERNAME='usuarioadmin'),stdout=log,stderr=log)
                try:
                    def request(path,cookie=None,method='GET',data=None,extra=None):
                        connection=http.client.HTTPConnection('127.0.0.1',port,timeout=5)
                        headers={'Cookie':cookie} if cookie else {}
                        headers.update(extra or {})
                        if data is not None:headers['Content-Type']='application/json'
                        body=json.dumps(data).encode() if data is not None else None
                        connection.request(method,path,body=body,headers=headers)
                        response=connection.getresponse();result=response.read();status=response.status;returned=dict(response.getheaders());connection.close()
                        return status,result,returned
                    for _ in range(100):
                        try:
                            if request('/api/health')[0]==200:break
                        except OSError:pass
                        time.sleep(.1)
                    root=request('/');self.assertEqual(root[0],303);self.assertEqual(root[2]['Location'],'/login')
                    self.assertNotIn('WWW-Authenticate',root[2])
                    self.assertEqual(request('/login')[0],200)
                    self.assertEqual(request('/login.css')[0],200)
                    self.assertEqual(request('/login.js')[0],200)
                    self.assertEqual(request('/api/health',method='HEAD')[0],200)
                    self.assertEqual(request('/api/jobs')[0],401)
                    self.assertEqual(request('/api/upload',method='POST')[0],401)
                    self.assertEqual(request('/media/'+'a'*32)[0],401)
                    self.assertEqual(request('/api/jobs','cria_session=forged')[0],401)
                    bad=request('/api/auth/login',method='POST',data={'username':'usuarioadmin','password':'wrong'})
                    self.assertEqual(bad[0],401);self.assertNotIn('Set-Cookie',bad[2])
                    valid=request('/api/auth/login',method='POST',data={'username':'usuarioadmin','password':password},extra={'X-Forwarded-Proto':'https'})
                    self.assertEqual(valid[0],200,valid[1]);cookie=valid[2]['Set-Cookie']
                    self.assertIn('HttpOnly',cookie);self.assertIn('Secure',cookie);self.assertIn('SameSite=Strict',cookie)
                    token=cookie.split(';')[0]
                    self.assertEqual(request('/',token)[0],200)
                    self.assertEqual(request('/api/jobs',token)[0],200)
                    self.assertEqual(request('/login',token)[0],303)
                    self.assertTrue(json.loads(request('/api/auth/status',token)[1])['authenticated'])
                    cross=request('/api/auth/login',method='POST',data={'username':'usuarioadmin','password':password},extra={'Sec-Fetch-Site':'cross-site'})
                    self.assertEqual(cross[0],403)
                    self.assertEqual(request('/api/auth/logout',token,method='POST',data={})[0],200)
                    self.assertEqual(request('/api/jobs',token)[0],401)
                    self.assertEqual(request('/api/health')[0],200)
                finally:
                    process.terminate();process.wait(timeout=10)


if __name__ == '__main__':
    unittest.main()
