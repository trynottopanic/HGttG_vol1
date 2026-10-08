#!/usr/bin/python3
"""Create offline human/structured reports without inflating evidence into passes."""
import argparse
import html
import json
from pathlib import Path
import re
import shutil


def build(folder):
    def read(name):
        path=folder/name
        return path.read_text(errors='replace') if path.exists() else ''
    app={}
    try: app=json.loads(read('controller-summary.json') or '{}')
    except ValueError: app={'session':'invalid summary; inspect raw logs'}
    kernel=read('kernel.txt').strip()
    dmesg=read('dmesg.txt')
    cube=read('cube.txt')
    samples=[]; sample_errors=0
    for line in read('samples.jsonl').splitlines():
        try: samples.append(json.loads(line))
        except ValueError: sample_errors+=1
    thermal={}
    for sample in samples:
        for sensor in sample.get('thermal',[]):
            try: value=float(sensor['millidegrees_c'])/1000
            except (ValueError,TypeError,KeyError): continue
            key=sensor.get('type') or sensor.get('zone','unknown')
            thermal.setdefault(key,[]).append(value)
    frames=re.findall(r'Rendered (\d+) frames in ([\d.]+) sec \(([\d.]+) fps\)',cube)
    renderer=re.search(r'OpenGL core profile renderer:\s*(.+)',read('egl.txt'))
    features=[]
    def add(name,state,evidence,source):
        features.append(dict(feature=name,state=state,evidence=evidence,source=source))
    add('Boot','observed' if kernel else 'not recorded',kernel or 'Kernel report missing','kernel.txt')
    add('Display registration','observed' if 'connected\n640x480' in read('displays.txt') else 'needs review',
        read('displays.txt').strip() or 'No connector report','displays.txt')
    if frames:
        count,elapsed,fps=frames[-1]
        add('Graphics rendering','measured',f'{count} logged frames in {elapsed} seconds; {fps} FPS. Renderer: '+
            (renderer.group(1) if renderer else 'unknown')+'. Short workload only; not a reliability test.','cube.txt')
    else:
        add('Graphics rendering','not demonstrated', 'No frame statistics found. '+
            ('Renderer initialization: '+renderer.group(1) if renderer else 'No renderer reported.'),'cube.txt')
    warnings=[line for line in dmesg.splitlines() if re.search(r'WARNING:|BUG:|Call trace:',line)]
    add('Kernel warning traces','not recorded' if not dmesg else 'needs review' if warnings else 'none captured',
        'No kernel log is available.' if not dmesg else '\n'.join(warnings[:8]) if warnings else 'No matching trace in this log; this is not proof every subsystem works.','dmesg.txt')
    add('Wi-Fi interface','enumerated' if 'wlan0' in read('network.txt') else 'not observed',
        read('wifi-link.txt').strip() or 'Connection and data transfer have not been tested.','network.txt')
    add('Bluetooth controller','enumerated' if re.search(r'\bhci\d+\b',read('device-nodes.txt')) else 'not observed',
        'Device-node snapshot only. Pairing, audio and stability are not established.','device-nodes.txt')
    add('Audio codec','enumerated' if 'card 0:' in read('audio.txt') else 'not observed',
        'Codec enumeration does not establish audible output or correct routing.','audio.txt')
    add('Passive system samples','recorded' if samples else 'not recorded',
        f'{len(samples)} samples of exposed temperature, power, memory and load data; {sample_errors} unreadable lines. Sensor accuracy is not validated.','samples.jsonl')
    for name,values in thermal.items():
        add('Temperature: '+name,'sensor readings',f'Reported range {min(values):.1f} to {max(values):.1f} C during this run.','samples.jsonl')
    add('Storage inventory','enumerated' if read('storage.txt') else 'not recorded',
        'See device/mount inventory and free space. No write endurance or removable-slot test was performed.','storage.txt')
    add('Shutdown','requested' if 'requesting orderly poweroff' in read('completion.txt') else 'not recorded',
        'The report is saved before shutdown and cannot itself prove poweroff completed.','completion.txt')
    add('Start / Power / Reset','excluded','No exercise or navigation test is requested for these controls.','controller-summary.json')
    latest={}
    for row in app.get('results',[]): latest[(row.get('phase',''),row.get('label',''))]=row
    controls=list(latest.values())
    observations=[r for r in controls if r['phase'] in ('experience','output')]
    needs=[r for r in controls if r.get('outcome') in ('not observed','ambiguous','unavailable','not confirmed','needs review','user-reported issue')]
    # Missing data is visible, not converted to an all-green result.
    return {'schema_version':1,'boot_id':read('boot-id.txt').strip(), 'kernel':kernel,
            'clock_note':'Device calendar may be unset. Use boot ID and monotonic timing to identify this run.',
            'session':app.get('session','no guided-session summary'), 'features':features,
            'missing_artifacts':[name for name in ('kernel.txt','controller-summary.json','controller-events.jsonl','dmesg.txt','cube.txt','completion.txt') if not (folder/name).exists()],
            'sample_count':len(samples),'sample_parse_errors':sample_errors,
            'control_results':controls, 'observations':observations, 'needs_review':needs,
            'mappings':app.get('mapping',{}), 'devices':app.get('devices',[]),
            'not_tested':['USB data/host modes','storage endurance and removable-slot behavior',
                          'charging/discharging accuracy','suspend/resume','network throughput and pairing',
                          'exhaustive button combinations','long-duration load and temperature stability'],
            'files':[p.name for p in sorted(folder.iterdir()) if p.is_file() and not p.name.endswith('.tmp')]}


def render(data):
    esc=lambda value:html.escape(str(value),quote=True)
    def table(rows):
        return '<table><thead><tr><th>Check</th><th>Finding</th><th>Evidence</th></tr></thead><tbody>'+''.join(
            '<tr><td>'+esc(name)+'</td><td>'+esc(state)+'</td><td>'+esc(evidence)+'</td></tr>'
            for name,state,evidence in rows)+'</tbody></table>'
    features=table((r['feature'],r['state'],r['evidence']) for r in data['features'])
    controls=table((r['label'],r['outcome'],r['phase']+': '+str(r.get('reason',r.get('note','See structured summary for values and timing.')))) for r in data['control_results'])
    links=' '.join('<a href="'+esc(name)+'">'+esc(name)+'</a>' for name in data['files'])
    return '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>GuideOS diagnostic results</title><style>
body{font:17px/1.55 system-ui,sans-serif;max-width:1100px;margin:32px auto;padding:0 24px;color:#14263b;background:#f4f7fa}
h1,h2{line-height:1.15}table{width:100%;border-collapse:collapse;background:white;margin:20px 0}td,th{padding:12px;text-align:left;border-bottom:1px solid #ccd7e0;vertical-align:top;white-space:pre-line}th{background:#e2eaf0}td:first-child{min-width:150px}a{display:inline-block;margin:5px;color:#135fa3}.note{padding:18px;background:#fff0cf;border-radius:8px}code{overflow-wrap:anywhere}
</style><h1>GuideOS diagnostic results</h1><p>Boot <code>'''+esc(data['boot_id'])+'''</code></p>
<p class="note">This report separates measured behavior, device detection, and user observations. It does not give the whole deck a blanket pass.</p>
<p>Guided session: <strong>'''+esc(data['session'])+'</strong>. '+esc(data['clock_note'])+'''</p>
<h2>Artifact completeness</h2><p>'''+esc(', '.join(data['missing_artifacts']) or 'Expected core artifacts are present.')+'''</p>
<h2>Hardware evidence</h2>'''+features+'<h2>Controls and experience</h2>'+controls+'''
<h2>Not tested by this run</h2><ul>'''+''.join('<li>'+esc(x)+'</li>' for x in data['not_tested'])+'''
</ul><h2>Raw evidence</h2><p>Keep these files alongside this page. No network connection is needed to read them.</p>'''+links+'</html>'


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('folder',type=Path); parser.add_argument('--mirror',type=Path)
    args=parser.parse_args(); data=build(args.folder)
    (args.folder/'results.json').write_text(json.dumps(data,indent=2))
    (args.folder/'results.html').write_text(render(data))
    if args.mirror:
        args.mirror.mkdir(parents=True,exist_ok=True)
        for file in args.folder.iterdir():
            if file.is_file() and not file.name.endswith('.tmp'): shutil.copyfile(file,args.mirror/file.name)
        runs=[p for p in sorted(args.mirror.parent.iterdir()) if p.is_dir() and (p/'results.html').exists()]
        index='<!doctype html><meta charset="utf-8"><title>GuideOS diagnostic runs</title><h1>GuideOS diagnostic runs</h1><p>Latest run: '+html.escape(args.mirror.name)+'</p><ul>'
        index+=''.join('<li><a href="'+html.escape(p.name,quote=True)+'/results.html">'+html.escape(p.name)+'</a></li>' for p in runs)+'</ul>'
        (args.mirror.parent/'index.html').write_text(index)


if __name__=='__main__': main()
