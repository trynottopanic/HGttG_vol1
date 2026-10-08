"""Build maintained reference, update and deliberately unhealthy test cartridges."""
import json,sys,tempfile,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'package/guide-installer'))
from guide_cartridge import build,canonical
source=ROOT/'apps/runtime_reference/cartridge';manifest=json.loads((source.parent/'manifest.source.json').read_text());output=ROOT/'build/cartridge-installer-0/cartridges';output.mkdir(parents=True,exist_ok=True)
results=[]
for version in ('1.0.0','1.1.0','1.2.0'):
    with tempfile.TemporaryDirectory() as temp:
        copy=Path(temp)/'source';shutil.copytree(source,copy)
        if version=='1.1.0':
            p=copy/'application/reference.py';p.write_text(p.read_text().replace('Application host test','Updated cartridge test'))
        if version=='1.2.0':(copy/'application/reference.py').write_text('import time\ndef application(api):\n while True: time.sleep(.01)\n')
        m=dict(manifest,version=version);target=output/(m['id']+'-'+version+'.guide');result=build(copy,m,target)
        repeat=Path(temp)/'repeat.guide';second=build(copy,m,repeat);assert result['sha256']==second['sha256']
        lines=['GUIDE-CARTRIDGE-INDEX-1']+[k+'='+v for k,v in [('ID',m['id']),('NAME',m['name']),('VERSION',version),('KIND','application'),('SUMMARY',m['summary']),('FILE',target.name),('BYTES',str(result['archiveBytes'])),('SHA256',result['sha256'])]]+['CAPABILITY='+c for c in m['capabilities']]+['ACTION=application.install.v0']
        target.with_suffix('.gde').write_text('\n'.join(lines)+'\n',encoding='ascii');results.append(result)
(output/'validation.json').write_text(json.dumps({'deterministic':True,'physicalAcceptance':False,'packages':results},indent=2)+'\n')
print('REFERENCE_CARTRIDGES_BUILT',len(results))
