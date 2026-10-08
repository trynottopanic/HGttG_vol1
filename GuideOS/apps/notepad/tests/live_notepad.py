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

def until(fn):
    end=time.monotonic()+8
    while time.monotonic()<end:
        try:
            value=fn()
            if value:return value
        except (OSError,ValueError,KeyError,TypeError):pass
        time.sleep(.03)
    raise AssertionError('Notepad live operation timed out')

def action(label):
    view=until(lambda:shell(code).get(1))
    shell(code,2,{0:view[2].index(label)})

def view_has(label):return until(lambda:(r:=shell(code).get(1)) and label in r[2] and r)
def submit_text(value):
    until(lambda:shell(code).get(2) is not None);shell(code,3,{0:value})
    until(lambda:shell(code).get(2) is None)

with tempfile.TemporaryDirectory(prefix='guide-notepad-card-') as temp:
    card=Path(temp);folder=card/'GUIDE/CARTRIDGES';folder.mkdir(parents=True)
    for path in (project/'build/notepad-0/cartridges').iterdir():
        if path.suffix in ('.guide','.gde'):shutil.copyfile(path,folder/path.name)
    present=[{'identity':'notepad-fixture-card'}];catalog=Catalog(card,lambda:present[0]);catalog.invalidate(present[0]);catalog.connect(CATALOG);stop=threading.Event()
    def serve():
        while not stop.is_set():
            if select.select([catalog.listener],[],[],.05)[0]:catalog.poll()
    thread=threading.Thread(target=serve);thread.start()
    try:
        result=install('0.1.0-preview.1');assert not result['error'] and result['status']['phase']=='committed',result
        code=result['status']['code'];ident='org.hhgtg.notepad'
        print('NOTEPAD_LIVE_CARTRIDGE_INSTALL_HEALTH_PASS',flush=True)
        present[0]=None;catalog.invalidate()
        for path in folder.iterdir():path.unlink()
        supervisor(1,{0:code});view_has('New note')
        action('New note');view_has('Edit text');action('Edit text');submit_text('A draft after cartridge removal.')
        until(lambda:'Unsaved changes' in shell(code)[1][1]);action('Save internal draft');submit_text('First note')
        until(lambda:'Saved internal draft' in shell(code)[1][1]);stop_application(code)
        objects=Path('/var/lib/guideos/applications')/ident/'private/objects'
        assert (objects/'draft-0').read_text()=='TEXT1\nA draft after cartridge removal.'
        supervisor(1,{0:code});view_has('Restore recovery');action('Restore recovery');view_has('Edit text')
        assert 'Recovered unsaved' in shell(code)[1][1]
        stop_application(code)
        print('NOTEPAD_LIVE_CARD_ABSENT_EDIT_SAVE_RELAUNCH_PASS',flush=True)
        # Exercise the actual shared keyboard and Home/stop adapter.
        sys.path[:0]=[str(project/'board/rg35xxh/debian/shell0'),str(project/'package/guide-input'),str(project/'package/guide-ui')]
        from guide_application_panel import ApplicationPanel
        from guide_input import TextEntryManager
        panel=ApplicationPanel(code,TextEntryManager())
        def panel_until(fn):
            return until(lambda:(panel.poll(),fn())[1])
        panel_until(lambda:panel.view and 'Restore recovery' in panel.view[2])
        panel.action(panel.view[2].index('Restore recovery'))
        panel_until(lambda:panel.view and 'Edit text' in panel.view[2])
        panel.action(panel.view[2].index('Edit text'));panel_until(lambda:panel.editor is not None)
        panel.editor.handle('end');panel.editor.handle('insert',text=' Work kept on Home.')
        panel.key(316);panel_until(lambda:panel.finished or panel.failed);assert panel.finished,panel.notice
        panel.executor.shutdown(wait=True)
        sys.path.insert(0,str(project/'apps/notepad/cartridge/application'))
        from notepad import decode_checkpoint
        assert decode_checkpoint((objects/'checkpoint').read_text())['text'].endswith(' Work kept on Home.')
        print('NOTEPAD_LIVE_KEYBOARD_HOME_RECOVERY_PASS',flush=True)
        rpc(6,dict(id=ident,requestId=uuid.uuid4().hex));assert wait()['status']['phase']=='committed'
        assert (objects/'draft-0').read_text()=='TEXT1\nA draft after cartridge removal.'
        print('NOTEPAD_LIVE_UNINSTALL_RETAINS_DRAFT_PASS',flush=True)
    finally:stop.set();thread.join();catalog.close()
