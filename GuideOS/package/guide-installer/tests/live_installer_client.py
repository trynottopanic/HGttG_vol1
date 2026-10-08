import json,os,select,shutil,socket,subprocess,sys,tempfile,threading,time,uuid
from pathlib import Path
project=Path(sys.argv[1]);sys.path[:0]=[str(project/'package/guide-installer'),str(project/'package/guide-storage'),str(project/'package/guide-ipc/python'),str(project/'package/guide-foundation/python')]
from guide_install_wire import call,INSTALLER,CATALOG
from cartridge_catalog import Catalog
from guide_installer import supervisor,stop_application
from guide_application_runtime import request

def rpc(op,args=None):
    if op in (6,7,8):
        args=dict(args,expectedGeneration=json.loads((Path('/var/lib/guideos/applications')/args['id']/'installation.json').read_text())['generation'])
    result,fds=call(INSTALLER,op,args or {});assert not fds;return result

def wait():
    until=time.monotonic()+20
    while time.monotonic()<until:
        r=rpc(3)
        if not r['busy']:return r
        time.sleep(.05)
    raise AssertionError('installer timed out')

def install(version):
    listing,fds=call(CATALOG,1,{'offset':0});assert not fds
    item=next(i for i in listing['items'] if i['version']==version)
    selection=dict(epoch=listing['epoch'],generation=listing['generation'],token=item['token'])
    rpc(1,selection);result=wait();assert not result['error'],result;preview=result['preview'];assert preview['unsigned']
    rpc(2,dict(token=preview['token'],requestId=uuid.uuid4().hex,granted=preview['granted'],downgrade=False));return wait()

def shell(code,op=1,args=None):
    with socket.socket(socket.AF_UNIX,socket.SOCK_SEQPACKET) as s:
        s.settimeout(1);s.connect('/run/guideos/apps/'+str(code)+'/shell.sock');return request(s,op,args or {})

with tempfile.TemporaryDirectory(prefix='guide-card-fixture-') as temp:
    card=Path(temp);folder=card/'GUIDE/CARTRIDGES';folder.mkdir(parents=True)
    for p in (project/'build/cartridge-installer-0/cartridges').iterdir():
        if p.suffix in ('.guide','.gde'):shutil.copyfile(p,folder/p.name)
    present=[{'identity':'synthetic-card'}];catalog=Catalog(card,lambda:present[0]);catalog.invalidate(present[0]);catalog.connect(CATALOG);stop=threading.Event()
    def serve():
        while not stop.is_set():
            if select.select([catalog.listener],[],[],.05)[0]:catalog.poll()
    thread=threading.Thread(target=serve);thread.start()
    try:
        result=install('1.0.0');assert result['status']['phase']=='committed' and not result['error'],result
        code=result['status']['code'];ident='org.hhgtg.cartridge-proof'
        print('LIVE_CARTRIDGE_INSTALL_PASS',flush=True)
        present[0]=None;catalog.invalidate();instance=supervisor(1,{0:code})
        until=time.monotonic()+4
        while time.monotonic()<until:
            try:
                if shell(code).get(0):break
            except (OSError,ValueError):pass
            time.sleep(.05)
        shell(code,2,{0:0});time.sleep(.1);shell(code,3,{0:'retained cartridge draft'});stop_application(code)
        before=(Path('/var/lib/guideos/applications')/ident/'private/objects/checkpoint').read_bytes()
        print('LIVE_REMOVE_CARD_LAUNCH_CHECKPOINT_PASS',flush=True)
        present[0]={'identity':'synthetic-card'};catalog.invalidate(present[0])
        result=install('1.1.0');assert result['status']['phase']=='committed',result
        result=install('1.2.0');assert result['status']['phase']=='failed',result
        record=json.loads((Path('/var/lib/guideos/applications')/ident/'installation.json').read_text());assert record['package']['manifest']['version']=='1.1.0'
        assert before==(Path('/var/lib/guideos/applications')/ident/'private/objects/checkpoint').read_bytes()
        print('LIVE_UPDATE_HEALTH_ROLLBACK_PRESERVATION_PASS',flush=True)
        rpc(8,dict(id=ident,version='1.0.0',requestId=uuid.uuid4().hex));assert wait()['status']['phase']=='committed'
        rpc(6,dict(id=ident,requestId=uuid.uuid4().hex));assert wait()['status']['phase']=='committed'
        assert before==(Path('/var/lib/guideos/applications')/ident/'private/objects/checkpoint').read_bytes()
        result=install('1.0.0');assert result['status']['phase']=='committed' and result['status']['code']==code,result
        assert before==(Path('/var/lib/guideos/applications')/ident/'private/objects/checkpoint').read_bytes()
        print('LIVE_ROLLBACK_UNINSTALL_REINSTALL_PASS',flush=True)
        rpc(6,dict(id=ident,requestId=uuid.uuid4().hex));wait();rpc(7,dict(id=ident,requestId=uuid.uuid4().hex));assert wait()['status']['phase']=='committed'
        assert not (Path('/var/lib/guideos/applications')/ident/'private').exists()
        print('LIVE_EXPLICIT_PRIVATE_DELETE_PASS',flush=True)
    finally:stop.set();thread.join();catalog.close()
