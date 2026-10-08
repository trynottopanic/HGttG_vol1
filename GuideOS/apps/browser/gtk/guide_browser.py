#!/usr/bin/env python3
"""Isolated WebKitGTK prototype, not yet a Deck application host."""
import argparse
import json
import signal
import sys
from pathlib import Path
from urllib.parse import urlsplit
from guide_browser_metrics import emit
emit('before-toolkit')
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
gi.require_version('WebKit', '6.0')
from gi.repository import Gdk, Gio, GLib, Gtk, WebKit
emit('toolkit-imported')

ADAPTED_CSS = '''
html { overflow-wrap: anywhere !important; }
body { margin: 8px !important; min-width: 0 !important;
       max-width: 100% !important; font-size: 18px !important; }
img, video, svg { max-width: 100% !important; height: auto !important; }
pre { white-space: pre-wrap !important; overflow-wrap: anywhere !important; }
'''

def web_address(value):
    value = value.strip()
    if not value or any(ord(c) < 32 for c in value):
        raise ValueError('Enter a web address')
    if '://' not in value:
        value = 'https://' + value
    parsed = urlsplit(value)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname:
        raise ValueError('This prototype opens HTTP and HTTPS addresses')
    if parsed.username is not None or parsed.password is not None:
        raise ValueError('Do not put credentials in the address')
    return value

class Browser(Gtk.Application):
    def __init__(self, address=None, control=None, fullscreen=False):
        super().__init__(application_id='org.hhgtg.BrowserPrototype',
                         flags=Gio.ApplicationFlags.NON_UNIQUE)
        self.address = address
        self.control_path, self.fullscreen = control, fullscreen
        self.control = None
        self.failed_load = False
        self.load_state = 'idle'
        self.keyboard_target = None
        self.keyboard_page = 0
        self.native_keyboard=None
        self.connect('shutdown', self.cleanup)
        self.connect('activate', self.activate_browser)

    def activate_browser(self, *_):
        self.window = Gtk.ApplicationWindow(application=self, title='Guide Browser prototype')
        self.window.set_default_size(640, 480)
        # Reclaim page/network caches before the whole-session guard intervenes.
        # Keep WebKit's process-kill threshold disabled; Guide owns recovery.
        pressure = WebKit.MemoryPressureSettings.new()
        pressure.set_memory_limit(256)
        pressure.set_conservative_threshold(.5)
        pressure.set_strict_threshold(.75)
        pressure.set_poll_interval(2)
        WebKit.NetworkSession.set_memory_pressure_settings(pressure)
        self.session = WebKit.NetworkSession.new_ephemeral()
        self.session.connect('download-started', self.download_started)
        # One view with navigation: avoid the general multi-tab browser cache.
        self.web_context = WebKit.WebContext(memory_pressure_settings=pressure)
        self.web_context.set_cache_model(WebKit.CacheModel.DOCUMENT_BROWSER)
        self.view = WebKit.WebView(network_session=self.session, web_context=self.web_context)
        emit('webview-created')
        self.content = self.view.get_user_content_manager()
        self.style = WebKit.UserStyleSheet.new(
            ADAPTED_CSS, WebKit.UserContentInjectedFrames.TOP_FRAME,
            WebKit.UserStyleLevel.USER, None, None)
        self.view.connect('notify::uri', self.uri_changed)
        self.view.connect('load-changed', self.load_changed)
        self.view.connect('load-failed', self.load_failed)
        self.view.connect('web-process-terminated', self.process_terminated)
        self.view.connect('decide-policy', self.decide_policy)
        self.view.connect('permission-request', self.permission_requested)
        self.view.connect('run-file-chooser', self.file_chooser_requested)
        self.view.get_settings().set_enable_media_stream(False)
        layout = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        bar = Gtk.Box(spacing=4)
        for label, callback in [('Back', lambda *_: self.view.go_back()),
                                ('Forward', lambda *_: self.view.go_forward()),
                                ('Reload', lambda *_: self.view.reload())]:
            button = Gtk.Button(label=label)
            button.connect('clicked', callback)
            bar.append(button)
        self.mode = Gtk.ToggleButton(label='Adapted')
        self.mode.connect('toggled', self.set_adapted)
        bar.append(self.mode)
        transfers = Gtk.Button(label='Transfers')
        transfers.connect('clicked', lambda *_: self.show_transfers())
        bar.append(transfers)
        keyboard = Gtk.Button(label='Page keys')
        keyboard.connect('clicked', lambda *_: self.open_keyboard('page'))
        bar.append(keyboard)
        close = Gtk.Button(label='Close')
        close.connect('clicked', lambda *_: self.quit())
        bar.append(close)
        self.entry = Gtk.Entry(placeholder_text='Web address')
        self.entry.connect('activate', self.navigate)
        self.entry.set_max_length(4096)
        address_bar = Gtk.Box(spacing=4)
        address_button = Gtk.Button(label='Address')
        address_button.connect('clicked', lambda *_: self.open_keyboard('address'))
        self.entry.set_hexpand(True)
        go = Gtk.Button(label='Go')
        go.connect('clicked', self.navigate)
        for child in (address_button,self.entry,go):address_bar.append(child)
        self.status = Gtk.Label(label='Choose Address to open a website.', xalign=0)
        self.status.set_wrap(True)
        for child in (bar, address_bar, self.status, self.view):
            layout.append(child)
        self.keyboard_box = Gtk.Picture()
        self.keyboard_box.set_can_shrink(True)
        self.keyboard_box.set_hexpand(True);self.keyboard_box.set_vexpand(True)
        self.keyboard_box.set_halign(Gtk.Align.FILL);self.keyboard_box.set_valign(Gtk.Align.FILL)
        self.keyboard_box.set_visible(False)
        self.view.set_vexpand(True)
        overlay=Gtk.Overlay();overlay.set_child(layout);overlay.add_overlay(self.keyboard_box)
        self.window.set_child(overlay)
        controller = Gtk.EventControllerKey()
        controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        controller.connect('key-pressed', self.shortcut)
        self.window.add_controller(controller)
        if self.fullscreen:
            self.window.fullscreen()
        self.window.present()
        emit('window-presented')
        self.memory_timer = GLib.timeout_add_seconds(10, self.memory_sample)
        if self.control_path:
            from guide_browser_control import ControlServer
            self.control = ControlServer(self.control_path, self.command)
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, self.quit_signal)
        if self.address:
            self.entry.set_text(self.address)
            self.navigate()
        else:
            # A blank page has no page field to type into. Make the initial
            # destination explicit instead of inferring it after button focus.
            GLib.idle_add(self.initial_address)

    def initial_address(self):
        self.open_keyboard('address')
        return False

    def memory_sample(self):
        emit('periodic')
        return True

    def navigate(self, *_):
        if self.keyboard_target == 'address':
            self.entry.set_text(self.native_keyboard.keyboard.session.text)
            self.close_keyboard()
        try:
            self.view.load_uri(web_address(self.entry.get_text()))
        except ValueError as exc:
            self.status.set_text(str(exc))

    def uri_changed(self, *_):
        self.entry.set_text(self.view.get_uri() or '')

    def set_adapted(self, *_):
        self.content.remove_all_style_sheets()
        if self.mode.get_active():
            self.content.add_style_sheet(self.style)
        self.status.set_text('Adapted view' if self.mode.get_active() else 'Original view')

    def load_changed(self, _view, event):
        if event == WebKit.LoadEvent.STARTED:
            emit('navigation-started')
            self.failed_load = False
            self.load_state = 'loading'
            if self.view.get_uri() not in (None,'about:blank'):self.close_keyboard()
            self.status.set_text('Loading...')
        elif event == WebKit.LoadEvent.FINISHED and not self.failed_load:
            emit('navigation-finished')
            self.load_state = 'finished'
            self.status.set_text('Choose Address to open a website.' if self.view.get_uri() in (None,'about:blank') else
                                 'Adapted view' if self.mode.get_active() else 'Original view')

    def load_failed(self, _view, _event, _uri, error):
        self.failed_load = True
        self.load_state = 'failed'
        # Fixed diagnostic fields only: no address, page text or error body.
        print('GUIDE_BROWSER_EVENT '+json.dumps(dict(phase='load-failed',
              domain=str(error.domain)[:80],code=error.code)),flush=True)
        self.status.set_text('Page could not load. Check the address or connection, then Reload.')
        return True

    def process_terminated(self, *_):
        self.load_state = 'terminated'
        print('GUIDE_BROWSER_EVENT '+json.dumps(dict(phase='page-terminated')),flush=True)
        self.status.set_text('Browser page stopped. Reload to try again.')

    def cleanup(self, *_):
        emit('shutdown')
        if getattr(self, 'memory_timer', None):
            GLib.source_remove(self.memory_timer)
            self.memory_timer = None
        self.close_keyboard()
        if self.control:
            self.control.close()
            self.control = None

    def quit_signal(self):
        self.quit()
        return False

    def command(self, request):
        action = request.get('action')
        if action == 'open':
            uri = web_address(request['uri'])
            if len(uri) > 4096:
                raise ValueError('Address too long')
            self.view.load_uri(uri)
        elif action == 'back': self.view.go_back()
        elif action == 'forward': self.view.go_forward()
        elif action == 'reload': self.view.reload()
        elif action == 'stop': self.view.stop_loading()
        elif action == 'adapted':
            if type(request.get('enabled')) is not bool:
                raise ValueError('Expected boolean')
            self.mode.set_active(request['enabled'])
        elif action == 'keyboard': self.open_keyboard()
        elif action == 'address': self.open_keyboard('address')
        elif action == 'keyboard-input':
            if self.native_keyboard and request.get('token')==self.native_keyboard.token:
                sequence = request.get('sequence')
                if sequence is not None and (type(sequence) is not int or not 0 <= sequence <= 2**53):
                    raise ValueError('Invalid keyboard sequence')
                if sequence is None or sequence > self.native_keyboard.last_sequence:
                    if sequence is not None:self.native_keyboard.last_sequence = sequence
                    if self.native_keyboard.input(request.get('events')):
                        self.finish_keyboard_event()
        elif action == 'close': GLib.idle_add(self.quit_signal)
        elif action != 'status': raise ValueError('Unknown action')
        return {'ready': True, 'loading': self.view.is_loading(),
                'adapted': self.mode.get_active(), 'keyboard': self.keyboard_target is not None,
                'keyboard_target': self.keyboard_target, 'load_state': self.load_state,
                'keyboard_token':self.native_keyboard.token if self.native_keyboard else None,
                'can_back': self.view.can_go_back(), 'can_forward': self.view.can_go_forward()}

    def shortcut(self, _controller, key, _code, _modifiers):
        if self.native_keyboard and key not in (Gdk.KEY_F10,Gdk.KEY_F6,Gdk.KEY_F4):
            actions={Gdk.KEY_Up:'up',Gdk.KEY_Down:'down',Gdk.KEY_Left:'left',Gdk.KEY_Right:'right',
                     Gdk.KEY_Return:'activate',Gdk.KEY_KP_Enter:'activate',Gdk.KEY_Escape:'cancel',
                     Gdk.KEY_BackSpace:'backspace',Gdk.KEY_Delete:'delete',Gdk.KEY_Home:'home',Gdk.KEY_End:'end'}
            action=actions.get(key)
            if action:self.native_keyboard.keyboard.handle(action)
            elif not (_modifiers & (Gdk.ModifierType.CONTROL_MASK|Gdk.ModifierType.ALT_MASK)):
                character=Gdk.keyval_to_unicode(key)
                if character>=32:self.native_keyboard.keyboard.handle('insert',text=chr(character))
            self.finish_keyboard_event()
            return True
        if key == Gdk.KEY_F10:
            self.quit()
        elif key == Gdk.KEY_F6:
            self.open_keyboard('address')
        elif key == Gdk.KEY_F4:
            self.open_keyboard()
        elif key == Gdk.KEY_Escape:
            if self.keyboard_target: self.close_keyboard()
            else: self.view.go_back()
        else:
            return False
        return True

    def close_keyboard(self):
        was_open = self.native_keyboard is not None
        self.keyboard_target = None
        if self.native_keyboard:self.native_keyboard.close();self.native_keyboard=None
        if hasattr(self, 'keyboard_box'):
            self.keyboard_box.set_visible(False)
            self.keyboard_box.set_paintable(None)
        if was_open: emit('keyboard-closed')

    def open_keyboard(self, target=None):
        if self.keyboard_target and target is None:
            self.close_keyboard()
            return
        focused=self.window.get_focus()
        address_focus=focused is not None and (focused==self.entry or focused.is_ancestor(self.entry))
        selected = target or ('address' if address_focus or not self.view.get_uri() or self.view.get_uri()=='about:blank' else 'page')
        if selected not in ('address','page'):raise ValueError('Unknown keyboard target')
        self.close_keyboard()
        emit('keyboard-before')
        from guide_browser_keyboard import NativeKeyboard
        self.native_keyboard=NativeKeyboard(selected,self.entry.get_text() if selected=='address' else '')
        self.keyboard_target = selected
        self.keyboard_page = 0
        self.draw_keyboard()
        emit('keyboard-after')

    def draw_keyboard(self, initial=None):
        if not self.native_keyboard:return
        image=self.native_keyboard.renderer.render(self.native_keyboard.keyboard)
        self.keyboard_box.set_paintable(Gdk.MemoryTexture.new(image.width,image.height,
            Gdk.MemoryFormat.R8G8B8,GLib.Bytes.new(image.tobytes()),image.width*3))
        self.keyboard_box.set_visible(True)

    def finish_keyboard_event(self):
        if not self.native_keyboard:return
        state=self.native_keyboard.keyboard.session.state
        if state=='submitted':self.commit_keyboard()
        elif state=='cancelled':self.close_keyboard()
        else:self.draw_keyboard()

    def next_keyboard_page(self):
        if self.native_keyboard:
            self.native_keyboard.keyboard.handle('next-layer');self.draw_keyboard()

    def commit_keyboard(self):
        if not self.native_keyboard:return
        keyboard=self.native_keyboard.keyboard
        if keyboard.session.state=='editing':keyboard.handle('submit')
        result=keyboard.take_result()
        if result is None or result.state!='submitted':self.draw_keyboard();return
        text, target = result.text, self.keyboard_target
        self.close_keyboard()
        if target == 'address':
            self.entry.set_text(text)
            self.navigate()
        else:
            self.view.grab_focus()
            self.view.execute_editing_command_with_argument('InsertText', text)

    def file_chooser_requested(self, _view, request):
        request.cancel()
        self.status.set_text('File selection requires the Guide storage integration')
        return True

    def permission_requested(self, _view, request):
        request.deny()
        self.status.set_text('Website permission requests are not enabled in this prototype')
        return True

    def decide_policy(self, _view, decision, kind):
        if kind in (WebKit.PolicyDecisionType.NAVIGATION_ACTION,
                    WebKit.PolicyDecisionType.NEW_WINDOW_ACTION):
            uri = decision.get_navigation_action().get_request().get_uri()
            if urlsplit(uri).scheme not in ('http', 'https', 'about'):
                decision.ignore()
                self.status.set_text('This link requires another application')
                return True
            if kind == WebKit.PolicyDecisionType.NEW_WINDOW_ACTION:
                decision.ignore()
                self.status.set_text('New windows are not enabled in this prototype')
                return True
        return False

    def show_transfers(self, job=None):
        from guide_transfer_ui import TransferWindow
        TransferWindow(self.window,job).present()

    def download_started(self, _session, download):
        download.connect('decide-destination',self.download_destination)

    def download_destination(self, download, suggested):
        # Refetch GET through the independent transfer owner, preserving scoped
        # cookies. POST/blob downloads are explicit unsupported prototype cases.
        request=download.get_request()
        uri=request.get_uri()
        method=request.get_http_method()
        download.cancel()
        if method!='GET' or urlsplit(uri).scheme not in ('http','https'):
            self.status.set_text('This download type is not supported yet (GET links only)')
            return True
        name=suggested or 'download'
        if '/' in name or '\\' in name or len(name.encode())>180:
            self.status.set_text('Download filename is not supported')
            return True
        manager=self.session.get_cookie_manager()
        def cookies_ready(manager,result,*_):
            try:
                cookies=manager.get_cookies_finish(result)
                records=[dict(name=c.get_name(),value=c.get_value(),domain=c.get_domain(),path=c.get_path(),secure=c.get_secure()) for c in cookies]
                from guide_transfer_ui import request as transfer_request
                # Keep network/service waits off GTK's input loop.
                from concurrent.futures import ThreadPoolExecutor
                pool=ThreadPoolExecutor(max_workers=1)
                future=pool.submit(transfer_request,'offer',source={'url':uri},name=name,cookies=records)
                def complete(f):
                    def present():
                        try:self.show_transfers(f.result());self.status.set_text('Choose a download destination')
                        except Exception:self.status.set_text('Download service unavailable; retry the link')
                        return False
                    GLib.idle_add(present);pool.shutdown(wait=False)
                future.add_done_callback(complete)
            except Exception:
                self.status.set_text('Download could not be prepared; retry the link')
        manager.get_cookies(uri,None,cookies_ready,None)
        return True

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('address', nargs='?')
    parser.add_argument('--control')
    parser.add_argument('--fullscreen', action='store_true')
    args = parser.parse_args()
    raise SystemExit(Browser(args.address, args.control, args.fullscreen).run([]))
