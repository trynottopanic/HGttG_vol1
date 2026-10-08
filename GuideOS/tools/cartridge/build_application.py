import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'package/guide-installer'))
from guide_cartridge import build
p=argparse.ArgumentParser();p.add_argument('source');p.add_argument('output');p.add_argument('--id',required=True);p.add_argument('--name',required=True);p.add_argument('--version',required=True);p.add_argument('--summary',required=True);p.add_argument('--module',required=True);p.add_argument('--capability',action='append',default=[]);a=p.parse_args()
m=dict(format='GUIDE-CARTRIDGE-1',id=a.id,name=a.name,version=a.version,summary=a.summary,kind='application',installAction='application.install.v0',capabilities=a.capability,entrypoint=dict(runtime='guide.python-application',interfaceMajor=1,module=a.module,callable='application'))
result=build(a.source,m,a.output);print(json.dumps(result))
