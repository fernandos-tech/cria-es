import http.client
import base64
import json
import os
from pathlib import Path
import socket
import secrets
import subprocess
import tempfile
import time
import unittest

from studio import media, templates


class EditingRules(unittest.TestCase):
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
                                       env=dict(os.environ, STUDIO_DATA_DIR=str(cls.directory / 'data')),
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
            with socket.socket() as sock:
                sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
            password=secrets.token_urlsafe(32)
            with (Path(temporary)/'hosted.log').open('w') as log:
                process=subprocess.Popen(['python3','-m','studio.server','--port',str(port)],
                    env=dict(os.environ,STUDIO_DATA_DIR=temporary,STUDIO_PASSWORD=password),stdout=log,stderr=log)
                try:
                    def request(path,authorization=None,method='GET'):
                        connection=http.client.HTTPConnection('127.0.0.1',port,timeout=5)
                        headers={'Authorization':authorization} if authorization else {}
                        connection.request(method,path,headers=headers)
                        response=connection.getresponse();data=response.read();status=response.status;connection.close()
                        return status,data
                    for _ in range(100):
                        try:
                            if request('/api/health')[0]==200:break
                        except OSError:pass
                        time.sleep(.1)
                    self.assertEqual(request('/')[0],401)
                    self.assertEqual(request('/api/jobs')[0],401)
                    self.assertEqual(request('/api/upload',method='POST')[0],401)
                    self.assertEqual(request('/media/'+'a'*32)[0],401)
                    self.assertEqual(request('/','Basic invalid!')[0],401)
                    valid='Basic '+base64.b64encode(('studio:'+password).encode()).decode()
                    self.assertEqual(request('/',valid)[0],200)
                    self.assertEqual(request('/api/jobs',valid)[0],200)
                    self.assertEqual(request('/api/health')[0],200)
                finally:
                    process.terminate();process.wait(timeout=10)


if __name__ == '__main__':
    unittest.main()
