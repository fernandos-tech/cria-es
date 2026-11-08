"""Transcribe in an isolated process so model RAM is released before FFmpeg renders."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def transcribe(source,start,end):
    from faster_whisper import WhisperModel
    with tempfile.TemporaryDirectory() as directory:
        wav=Path(directory)/'audio.wav'
        subprocess.run(['ffmpeg','-nostdin','-v','error','-threads','1','-ss',str(start),'-i',str(source),'-t',str(end-start),'-vn','-ac','1','-ar','16000',str(wav)],check=True,capture_output=True)
        cache=os.environ.get('STUDIO_MODEL_DIR', str(Path(__file__).resolve().parents[1]/'.studio'/'models'))
        model=WhisperModel(os.environ.get('STUDIO_WHISPER_MODEL','tiny'),device='cpu',compute_type='int8',cpu_threads=1,num_workers=1,download_root=cache)
        segments,_=model.transcribe(str(wav),language='pt',beam_size=1,best_of=1,vad_filter=True,condition_on_previous_text=False)
        return [(start+s.start,start+s.end,s.text.strip()) for s in segments if s.text.strip()]


if __name__=='__main__':
    source,start,end,target=sys.argv[1:]
    Path(target).write_text(json.dumps(transcribe(source,float(start),float(end)),ensure_ascii=False),encoding='utf-8')
