"""Reproducible internal-draft preview cartridge and external-card index."""
import argparse,json,sys,tempfile,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'package/guide-installer'))
from guide_cartridge import build
source=ROOT/'apps/notepad/cartridge'
manifest=json.loads((source.parent/'manifest.source.json').read_text(encoding='utf-8'))
parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT/'build/notepad-0/cartridges')
out=parser.parse_args().output;out.mkdir(parents=True,exist_ok=True)
archive=out/(manifest['id']+'-'+manifest['version']+'.guide')
with tempfile.TemporaryDirectory() as temp:
    clean=Path(temp)/'source';shutil.copytree(source,clean,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    result=build(clean,manifest,archive)
    repeat=build(clean,manifest,Path(temp)/'repeat.guide');assert result['sha256']==repeat['sha256']
lines=['GUIDE-CARTRIDGE-INDEX-1']+[k+'='+v for k,v in [('ID',manifest['id']),('NAME',manifest['name']),('VERSION',manifest['version']),('KIND','application'),('SUMMARY',manifest['summary']),('FILE',archive.name),('BYTES',str(result['archiveBytes'])),('SHA256',result['sha256'])]]+['CAPABILITY='+c for c in manifest['capabilities']]+['ACTION=application.install.v0']
archive.with_suffix('.gde').write_text('\n'.join(lines)+'\n',encoding='ascii')
(out/'validation.json').write_text(json.dumps(dict(deterministic=True,installed=False,physicalAcceptance=False,package=result),indent=2)+'\n',encoding='utf-8')
print('NOTEPAD_CARTRIDGE_BUILT',result['sha256'])
