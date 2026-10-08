"""Real WebKit process test under a virtual display; no Deck claims."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from gi.repository import GLib
from guide_browser import Browser, WebKit
import guide_transfer_ui
# Exercise the actual transfer/storage implementation; only the private socket
# is replaced by a direct call so this test can run as an ordinary host user.
import sys,tempfile
from pathlib import Path
REPO=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(REPO/'package/guide-transfers'),str(REPO/'package/guide-storage'),str(REPO/'package/guide-installer'),str(REPO/'package/guide-ipc/python')]
from transfers import Transfers
from storage_files import Files
scratch=tempfile.TemporaryDirectory()
files=Files(Path(scratch.name)/'card',Path(scratch.name)/'files')
transfers=Transfers(Path(scratch.name)/'jobs',files.dispatch)
def transfer_request(op,**args):
    assert op=='offer'
    return transfers.offer(args['source'],args['name'],cookies=args.get('cookies'))
guide_transfer_ui.request=transfer_request

class Fixture(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        if self.path == '/download':
            self.send_header('Content-Type', 'application/octet-stream')
            self.send_header('Content-Disposition', 'attachment; filename=fixture.bin')
            body = b'guide-browser-fixture'
        else:
            self.send_header('Content-Type', 'text/html')
            body = b'<html><head><style>body{margin:32px;font-size:12px}</style></head><body><input id="note" value="owner draft"><input id="pin" type="password"><textarea id="multiline"></textarea><p>Guide browser fixture</p></body></html>'
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass  # Expected when WebKit cancels the intercepted download.
    def log_message(self, *_): pass

server = ThreadingHTTPServer(('127.0.0.1', 0), Fixture)
threading.Thread(target=server.serve_forever, daemon=True).start()
base = 'http://127.0.0.1:' + str(server.server_port)
app = Browser(base)
def destination_selected(job):
    transfers.start(job['id'],'internal','ask')
    def completed():
        row=transfers.jobs[job['id']]
        if row['state']=='completed':
            assert (Path(scratch.name)/'files'/row['name']).read_bytes()==b'guide-browser-fixture'
            results.append('browser-download-through-transfer-owner');app.quit();return False
        if row['state']=='failed':fail(row['reason']);return False
        return True
    GLib.timeout_add(50,completed)
app.show_transfers=destination_selected
results = []
failed = []

def fail(exc):
    failed.append(str(exc))
    app.quit()

def js(script, callback):
    def done(view, result, *_):
        try:
            value = view.evaluate_javascript_finish(result)
            callback(json.loads(value.to_string()))
        except Exception as exc: fail(exc)
    app.view.evaluate_javascript(script, -1, None, None, None, done, None)

snapshot = 'JSON.stringify({margin:getComputedStyle(document.body).marginLeft,note:document.getElementById("note").value})'

def original(value):
    assert value['margin'] == '32px', value
    results.append('original-render')
    app.mode.set_active(True)
    GLib.timeout_add(150, lambda: (js(snapshot, adapted), False)[1])

def adapted(value):
    assert value == {'margin':'8px', 'note':'owner draft'}, value
    results.append('adapted-with-form-preserved')
    app.mode.set_active(False)
    GLib.timeout_add(150, lambda: (js(snapshot, restored), False)[1])

def restored(value):
    assert value == {'margin':'32px', 'note':'owner draft'}, value
    results.append('original-restored-without-reload')
    js('document.getElementById("note").focus(); JSON.stringify(true)', keyboard_test)

def keyboard_test(_value):
    original=app.entry.get_text()
    app.open_keyboard('address')
    app.native_keyboard.keyboard.handle('insert',text='changed')
    app.command(dict(action='keyboard-input',token=app.native_keyboard.token,events=[dict(code=304,value=1)]))
    assert app.entry.get_text()==original
    results.append('native-address-cancel-preserves-address')
    app.open_keyboard('page')
    token=app.native_keyboard.token
    from unittest.mock import patch
    neutral = dict(action='keyboard-input', token=token,
                   events=[dict(sticks=dict(left=[0,0],right=[0,0],generation=1))])
    with patch.object(app, 'draw_keyboard', wraps=app.draw_keyboard) as redraw:
        for sequence in range(100):app.command(dict(neutral, sequence=sequence))
        assert redraw.call_count == 0, redraw.call_count
    app.command(dict(action='keyboard-input',token='stale',events=[dict(code=305,value=1)]))
    assert app.native_keyboard.keyboard.session.text==''
    press = dict(action='keyboard-input',token=token,sequence=100,events=[dict(code=305,value=1)])
    app.command(press)
    app.command(press)  # An ambiguous reply/retry must not insert twice.
    assert app.native_keyboard.keyboard.session.text=='q'
    app.native_keyboard.keyboard.handle('insert',text=' edited')
    app.commit_keyboard()
    GLib.timeout_add(150, lambda: (js(snapshot, keyboard_result), False)[1])

def keyboard_result(value):
    assert ' edited' in value['note'], value
    results.append('keyboard-inserts-into-page-field')
    js('document.getElementById("pin").focus(); JSON.stringify(true)',password_test)

def password_test(_value):
    app.open_keyboard('page')
    app.native_keyboard.keyboard.handle('insert',text='fixture-secret')
    assert app.native_keyboard.keyboard.session.display_text()=='•'*14
    app.commit_keyboard()
    GLib.timeout_add(150,lambda:(js('JSON.stringify(document.getElementById("pin").value)',password_result),False)[1])

def password_result(value):
    assert value=='fixture-secret'
    results.append('native-keyboard-password-insertion')
    js('document.getElementById("multiline").focus(); JSON.stringify(true)',multiline_test)

def multiline_test(_value):
    app.open_keyboard('page')
    app.native_keyboard.keyboard.handle('insert',text='line one\n<b>literal text</b>')
    app.commit_keyboard()
    GLib.timeout_add(150,lambda:(js('JSON.stringify(document.getElementById("multiline").value)',multiline_result),False)[1])

def multiline_result(value):
    assert value=='line one\n<b>literal text</b>'
    results.append('native-keyboard-multiline-literal-insertion')
    app.session.connect('download-started', download_observed)
    app.view.download_uri(base + '/download')

def download_observed(_session, download):
    # Cancellation is asynchronous; observe the actual engine completion.
    download.connect('failed', download_failed)

def download_failed(download, error):
    try:
        assert download.get_destination() is None
        results.append('download-intercepted-no-destination')
    except Exception as exc: fail(exc)

started = False

def loaded(view, event):
    global started
    if event == WebKit.LoadEvent.FINISHED and not started:
        started = True
        js(snapshot, original)

def activated(*_):
    app.view.connect('load-changed', loaded)

app.connect('activate', activated)
GLib.timeout_add_seconds(25, lambda: (fail('integration timeout'), False)[1])
try:
    app.run([])
finally:
    server.shutdown()
    transfers.close();files.close();scratch.cleanup()
print(json.dumps({'passed':results, 'errors':failed}))
raise SystemExit(0 if len(results) == 9 and not failed else 1)
