"""Fixed local protocol, authenticated by the separately configured SSH gateway."""
import argparse
import base64
import binascii
import fcntl
import grp
import json
import os
from pathlib import Path
import pwd
import socket
import struct
from deploy_core import Store, Rejected, canonical, require
from deploy_host import Host

BASE = Path('/opt/guideos/deploy')
SOCKET = '/run/guideos-deploy/control.sock'
WIRE_LIMIT = 360000

def open_store():
    from deploy_core import read_json
    if read_json(BASE/'config.json').get('signed_updates'):
        from signed_store import SignedStore
        return SignedStore(BASE,Host())
    return Store(BASE,Host())

def dispatch(store, request):
    require(isinstance(request, dict), 'bad-request')
    op = request.get('op')
    if op=='authorize':
        require(set(request)=={'op','id','downgrade'} and hasattr(store,'authorize'),'bad-request')
        return store.authorize(request['id'],request['downgrade'])
    if op=='import-file':
        require(set(request)=={'op','entry'} and hasattr(store,'import_descriptor'),'bad-request')
        import sys
        sys.path[:0]=['/usr/lib/guideos/installer','/usr/lib/guideos/ipc']
        from guide_install_wire import call
        _,fds=call('/run/guideos-storage/files.sock',3,{'entry':request['entry']})
        try:return store.import_descriptor(fds[0])
        finally:
            for fd in fds:os.close(fd)

    if op in ('tf2-observe','tf2-hold-awake','tf2-result'):
        require(set(request)=={'op'},'bad-request')
        from tf2_probe import start, result
        return result() if op=='tf2-result' else start(op=='tf2-hold-awake')
    tones={'tone-internal':'internal-sine','tone-s16':'file-s16','tone-s32':'file-s32','tone-s16-higher':'file-s16-higher'}
    if op in tones:
        require(set(request)=={'op'},'bad-request')
        from deploy_board_diagnostics import start_probe
        return start_probe(tones[op])
    if op=='capture-begin':
        require(set(request)=={'op'},'bad-request')
        from deploy_board_diagnostics import begin_full_capture
        return begin_full_capture()
    if op=='capture-chunk':
        require(set(request)=={'op','id','offset','length'},'bad-request')
        from deploy_board_diagnostics import full_capture_chunk
        return full_capture_chunk(request['id'],request['offset'],request['length'])
    if op=='capture-finish':
        require(set(request)=={'op','id'},'bad-request')
        from deploy_board_diagnostics import finish_full_capture
        return finish_full_capture(request['id'])
    fields = {'audio-path': (), 'probe-result': (), 'inspect': (), 'speaker-probe': (), 'health': (), 'report': (), 'status': (), 'begin': ('id', 'bytes', 'base'), 'chunk': ('id', 'offset', 'data'),
              'validate': ('id',), 'activate': ('id',), 'cancel': ('id',), 'rollback': ()}
    require(op in fields and set(request) == {'op', *fields[op]}, 'bad-request')
    if op in ('audio-path','probe-result'):
        from deploy_board_diagnostics import audio_path, probe_status
        return audio_path() if op=='audio-path' else probe_status()
    if op in ('inspect','speaker-probe'):
        from deploy_board_diagnostics import inspect, start_probe
        return inspect() if op=='inspect' else start_probe()
    if op in ('health','report'):
        from deploy_diagnostics import health, report
        return health() if op=='health' else report()
    if op == 'status':
        result = store.status()
        try:
            result['shell'] = store.host.heartbeat()
        except Rejected as exc:
            result['shell'] = dict(ready=False, reason=str(exc))
        return result
    if op == 'begin':
        return store.begin(request['id'], request['bytes'], request['base'])
    if op == 'chunk':
        try:
            data = base64.b64decode(request['data'], validate=True)
        except (ValueError, TypeError, binascii.Error):
            raise Rejected('bad-chunk') from None
        return dict(received=store.chunk(request['id'], request['offset'], data))
    if op == 'rollback':
        return store.rollback()
    return {'validate': store.validate, 'activate': store.queue, 'cancel': store.cancel}[op](request['id'])

def serve():
    allowed = {0, pwd.getpwnam('guide-deploy').pw_uid}
    Path(SOCKET).unlink(missing_ok=True)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
        listener.bind(SOCKET)
        os.chown(SOCKET, 0, grp.getgrnam('guide-deploy').gr_gid)
        os.chmod(SOCKET, 0o660)
        listener.listen(4)
        while True:
            connection, _ = listener.accept()
            with connection:
                connection.settimeout(5)
                try:
                    _, uid, _ = struct.unpack('3i', connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                    require(uid in allowed, 'unauthorized-peer')
                    with connection.makefile('rb') as reader:
                        raw = reader.readline(WIRE_LIMIT + 1)
                    require(len(raw) <= WIRE_LIMIT and raw.endswith(b'\n'), 'request-limit')
                    request = json.loads(raw)
                    if isinstance(request,dict) and request.get('op')=='capture-begin':connection.settimeout(180)
                    with open(BASE / 'lock', 'a') as lock:
                        # Status remains available while the detached worker applies.
                        if not (isinstance(request, dict) and request.get('op') in ('status','health','report','inspect','audio-path','probe-result','tf2-result','capture-begin','capture-chunk','capture-finish')):
                            try:
                                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                            except BlockingIOError:
                                raise Rejected('controller-busy') from None
                        store=open_store()
                        if store.config.get('signed_updates') and request.get('op') in ('authorize','activate','rollback','import-file'):
                            require(uid==0,'local-owner-action-required')
                        result = dispatch(store, request)
                    response = dict(ok=True, result=result)
                except Rejected as exc:
                    response = dict(ok=False, reason=str(exc))
                except Exception:
                    response = dict(ok=False, reason='invalid-request-or-local-failure')
                try:
                    wire=canonical(response)+b'\n'
                    if len(wire)>WIRE_LIMIT:
                        wire=b'{"ok":false,"reason":"response-size-limit"}\n'
                    connection.sendall(wire)
                except OSError:
                    pass

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['serve', 'apply', 'recover', 'rescue', 'enable', 'disable'])
    args = parser.parse_args()
    os.umask(0o077)
    if args.mode == 'serve':
        return serve()
    with open(BASE / 'lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        store = open_store()
        if args.mode in ('enable', 'disable'):
            from deploy_core import atomic_json
            store.config['enabled'] = args.mode == 'enable'
            atomic_json(BASE / 'config.json', store.config)
        else:
            getattr(store, args.mode)()

if __name__ == '__main__':
    main()
