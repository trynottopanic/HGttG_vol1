"""Read-only bounded signal-path evidence for the paired diagnostic interface."""
import array
import hashlib
import math
import json
from pathlib import Path
import wave
from deploy_diagnostics import head


def board_snapshot(root=Path('/'), budget=24000):
    root=Path(root); files={}; remaining=budget; omitted=False
    paths=[root/'sys/kernel/debug/gpio']
    paths+=sorted((root/'sys/kernel/debug/asoc').glob('*/dapm/*'))
    paths+=sorted((root/'sys/kernel/debug/asoc').glob('*/*/dapm/*'))
    paths+=sorted((root/'sys/kernel/debug/regmap').glob('*5096000*/registers'))
    paths+=sorted((root/'proc/asound').glob('card*/pcm*p/sub*/hw_params'))
    paths+=sorted((root/'proc/asound').glob('card*/pcm*p/sub*/status'))
    paths += [root/'sys/kernel/debug/regulator/regulator_summary',root/'sys/kernel/debug/clk/clk_summary']
    for path in paths[:100]:
        if path.is_dir():continue
        if remaining<=0:omitted=True;break
        limit=min(remaining,8192 if path.name in ('gpio','clk_summary','regulator_summary') else 4096 if path.name=='registers' else 2048)
        if path.name=='clk_summary':
            value=head(path,65536)
            lines=value.get('text','').splitlines()
            text='\n'.join(lines[:3]+[line for line in lines[3:] if any(k in line.lower() for k in ('audio','codec','pll'))])
            value['text']=text[:limit];value['truncated']=value['truncated'] or len(text)>limit
        else:value=head(path,limit)
        remaining-=len(value.get('text','').encode())
        files[str(path.relative_to(root))]=value
    return dict(files=files,budget_bytes=budget,budget_exhausted=omitted,debug_mount=(root/'sys/kernel/debug/asoc').is_dir(),
                codec_registers_found=any('/regmap/' in p for p in files),
                component_dapm_found=any('/dapm/' in p and len(Path(p).parts)>=8 for p in files))


def test_signal(path):
    path=Path(path)
    try:
        if path.stat().st_size>2097152:return dict(available=False,reason='size-limit')
        with wave.open(str(path)) as source:
            channels=source.getnchannels();width=source.getsampwidth();rate=source.getframerate()
            if width!=2 or channels not in (1,2):return dict(available=False,reason='unsupported-test-format')
            raw=source.readframes(source.getnframes())
        samples=array.array('h',raw)
        import sys
        if sys.byteorder!='little':samples.byteswap()
        levels=[]
        for channel in range(channels):
            values=samples[channel::channels]
            levels.append(dict(peak=max((abs(v) for v in values),default=0),rms=round(math.sqrt(sum(v*v for v in values)/max(1,len(values))),3)))
        return dict(available=True,rate=rate,channels=channels,frames=len(samples)//channels,levels=levels,sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    except (OSError,ValueError,wave.Error,EOFError):return dict(available=False,reason='unreadable-test-signal')


def compact_graph(rows, budget=48000):
    result=[]; used=0; truncated=False
    for item in rows:
        kind=item.get('type','').rsplit(':',1)[-1]
        if kind not in ('Node','Port','Link','Device'):continue
        info=item.get('info',{})
        props={k:v for k,v in info.get('props',{}).items() if k.startswith(('audio.','node.','port.','device.','api.alsa.','target.','media.','link.'))}
        value=dict(id=item.get('id'),type=kind,props=props)
        for key in ('state','direction','output-node-id','input-node-id','output-port-id','input-port-id','error'):
            if key in info:value[key]=info[key]
        value['params']={k:v for k,v in info.get('params',{}).items() if k in ('Props','Format','Route','Profile')}
        size=len(json.dumps(value).encode())
        if used+size>budget:truncated=True;continue
        used+=size;result.append(value)
    return dict(available=True,objects=result,truncated=truncated)
