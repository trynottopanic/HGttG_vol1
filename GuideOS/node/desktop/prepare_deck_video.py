"""Desktop-only HandBrake conversion. Preserve originals and publish on success."""
from pathlib import Path
import argparse,json,os,shutil,subprocess,threading,time,uuid

PRESET_NAME='GuideOS Deck 480p30'
DEFAULT_PRESET=Path(__file__).resolve().parent/'presets/GuideOS-Deck-480p30.json'
NO_WINDOW=getattr(subprocess,'CREATE_NO_WINDOW',0)

def handbrake_cli():
    candidates=[shutil.which('HandBrakeCLI')]
    if os.environ.get('LOCALAPPDATA'):
        candidates.append(str(Path(os.environ['LOCALAPPDATA'])/'Programs/HandBrakeCLI/HandBrakeCLI.exe'))
    return next((value for value in candidates if value and Path(value).is_file()),None)

class HandBrakeJob:
    def __init__(self):
        self.cancelled=threading.Event();self.lock=threading.Lock();self.process=None

    def cancel(self):
        self.cancelled.set()
        with self.lock:
            process=self.process
            if process is not None and process.poll() is None:
                process.terminate()
                try:process.wait(timeout=2)
                except subprocess.TimeoutExpired:process.kill();process.wait(timeout=1)

    def run(self,source,output,preset,log):
        source=Path(source).resolve(strict=True);output=Path(output).resolve()
        preset=Path(preset).resolve(strict=True);log=Path(log)
        cli=handbrake_cli()
        if not cli:raise RuntimeError('Install HandBrakeCLI to prepare Deck videos.')
        if not source.is_file() or output.suffix.lower()!='.mp4' or output==source:
            raise ValueError('Choose a video and a different MP4 destination.')
        if output.exists():raise FileExistsError('The destination already exists. Choose a new filename.')
        if not output.parent.is_dir():raise ValueError('The destination folder is unavailable.')
        # Media discovery cannot mistake an unfinished encode for a video.
        temporary=output.with_name(output.stem+'.guideos-'+uuid.uuid4().hex+'.partial')
        assert temporary.parent==output.parent
        log.parent.mkdir(parents=True,exist_ok=True)
        try:
            with log.open('x',encoding='utf-8') as transcript:
                with self.lock:
                    if self.cancelled.is_set():raise RuntimeError('Video preparation cancelled.')
                    self.process=subprocess.Popen([cli,'--preset-import-file',str(preset),
                        '-Z',PRESET_NAME,'-f','av_mp4','-i',str(source),'-o',str(temporary)],
                        stdin=subprocess.DEVNULL,stdout=transcript,stderr=subprocess.STDOUT,
                        creationflags=NO_WINDOW)
                deadline=time.monotonic()+6*60*60
                while self.process.poll() is None:
                    if self.cancelled.wait(.2):raise RuntimeError('Video preparation cancelled.')
                    if time.monotonic()>deadline:raise TimeoutError('Video preparation timed out.')
                if self.process.returncode:raise RuntimeError('HandBrake could not prepare this video. See '+str(log))
            if not temporary.is_file() or not temporary.stat().st_size:
                raise RuntimeError('HandBrake did not produce a video.')
            # Publishing cannot replace an existing owner file. Windows rename
            # rejects an occupied destination; other hosts use an exclusive link.
            with self.lock:
                if self.cancelled.is_set():raise RuntimeError('Video preparation cancelled.')
                if os.name=='nt':os.rename(temporary,output)
                else:os.link(temporary,output);temporary.unlink()
            return dict(output=str(output),bytes=output.stat().st_size,preset=PRESET_NAME,log=str(log))
        finally:
            if self.process is not None and self.process.poll() is None:
                self.cancel()
            if temporary.exists():temporary.unlink()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('source',type=Path)
    parser.add_argument('output',type=Path);parser.add_argument('--preset',type=Path,
        default=DEFAULT_PRESET)
    parser.add_argument('--log',type=Path,required=True);args=parser.parse_args()
    print(json.dumps(HandBrakeJob().run(args.source,args.output,args.preset,args.log),indent=2))
