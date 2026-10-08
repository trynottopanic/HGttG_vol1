#!/usr/bin/python3
"""First supervised Debian Guide Shell integration slice.
The shell owns display/input and exposes optional media providers only when
their integration is enabled for the installed image.
SPDX-License-Identifier: AGPL-3.0-or-later
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import sys
import subprocess
import time
from guide_telemetry import emit, Timings
from guide_status_bar import StatusBar, StatusSink
from guide_platform_rg35xxh import DeckInputs, Framebuffer, EV_KEY
from guide_wifi_panel import WiFiPanel
from guide_nearby_panel import NearbyPanel
from guide_input import TextEntryManager, draw_menu_pointer
from guide_menu_input import MenuInput
from guide_unicode import ImageCanvas, UnicodeText
UP, DOWN, A, B, MENU = 544, 545, 305, 304, 316
WIFI_DISCOVERY_ENABLED = os.environ.get("GUIDE_WIFI_DISCOVERY", "0") == "1"
WIFI_CONTROL_ENABLED = os.environ.get("GUIDE_WIFI_CONTROL", "0") == "1"
AUDIO_ENABLED = os.environ.get("GUIDE_AUDIO", "0") == "1"
STORAGE_ENABLED = os.environ.get("GUIDE_STORAGE", "0") == "1"
OPERATIONS_ENABLED = os.environ.get("GUIDE_OPERATIONS", "0") == "1"
# Owner-paused integration: image environment flags cannot re-enable this release.
BROWSER_ENABLED = False
PAGES = (("media", "status") + (("wifi",) if WIFI_DISCOVERY_ENABLED else ()) +
         (("storage",) if STORAGE_ENABLED else ()) +
         (("files", "transfers", "updates") if OPERATIONS_ENABLED else ()) +
         (("browser",) if BROWSER_ENABLED else ()) + ("power", "applications"))
CHOICES = ((("MEDIA" if AUDIO_ENABLED else "MEDIA FOUNDATION"), "SYSTEM STATUS") +
           ((("WI-FI",) if WIFI_CONTROL_ENABLED else ("WI-FI DISCOVERY",)) if WIFI_DISCOVERY_ENABLED else ()) +
           (("EXTERNAL CARD",) if STORAGE_ENABLED else ()) +
           (("FILES", "TRANSFERS", "UPDATES") if OPERATIONS_ENABLED else ()) +
           (("BROWSER",) if BROWSER_ENABLED else ()) + ("POWER OFF", "APPLICATIONS"))
BUILD_ID = os.environ.get("GUIDE_BUILD_ID", "source")
BG, PANEL, INK, MUTED, GOLD, GREEN = "#101c2c", "#203047", "#f1f5fa", "#9cacbf", "#ffd166", "#63e6b0"

class BootFramebuffer:
    """Initialize Home before acquiring the animation's display surface."""
    def __init__(self, factory, runtime):
        self.factory, self.runtime, self.surface = factory, Path(runtime), None
        self.last_metrics = {}
    def show(self, image, dirty=None):
        if self.surface is None:
            console = self.runtime / 'console.json'
            deadline = time.monotonic() + 26
            while console.exists() and not (self.runtime / 'display-released').exists():
                if time.monotonic() >= deadline:
                    raise RuntimeError('Boot animation did not release the display')
                time.sleep(.025)
            self.surface = self.factory()
            # Inherit the pre-animation mode rather than saving KD_GRAPHICS as
            # the terminal's eventual cleanup mode. The boot helper remains the
            # recovery owner until the first actual Home write succeeds.
            if console.exists():
                original = json.loads(console.read_text())['mode']
                if original not in (0, 1, 2):
                    raise ValueError('Invalid boot console mode')
                self.surface.old_mode = original
            self.surface.show(image)
            if console.exists():
                (self.runtime / 'home-presented').touch()
        else:
            self.surface.show(image, dirty=dirty)
        self.last_metrics = getattr(self.surface, 'last_metrics', {})
    def invalidate(self):
        if self.surface is not None and hasattr(self.surface, 'invalidate'):
            self.surface.invalidate()
    @property
    def supports_layers(self):return getattr(self.factory,'supports_layers',False)
    def show_layers(self,image,layers=()):
        if self.surface is None:
            from guide_gpu_framebuffer import compose
            self.show(compose(image,layers))
        self.surface.show_layers(image,layers)
        self.last_metrics=getattr(self.surface,'last_metrics',{})
    def suspend(self,image=None):
        return self.surface.suspend(image) if self.surface is not None and hasattr(self.surface,'suspend') else True
    def resume(self):
        if self.surface is not None and hasattr(self.surface,'resume'):self.surface.resume()
    def close(self):
        return self.surface.close() if self.surface is not None else []

class ShellState:
    def __init__(self):
        self.page = "home"
        self.selection = 0
        self.status_selection = 0
        self.power_selection = 0
        self.home_slide_enabled = False
        self.home_slide = None
        self.home_slide_progress = 0.0
        from guide_v3_ui import HomeState
        self.v3_home = HomeState()
        self.settings_selection = 0
        self.unavailable_message = ''
        self.v3_next_world = 0.0
        self.navigation_stack = []
        self.update_notice_id = None
        self.update_notice_dismissed = None
        self.shutdown_requested = False
        self.revision = 0
        self.pointer_revision = 0
        self.wifi = {"state": "idle", "message": "Ready to scan.", "networks": []}
        self.wifi_scroll = 0
        self.scan_requested = False
        self.text_entries = TextEntryManager()
        self.wifi_panel = WiFiPanel(text_entries=self.text_entries) if WIFI_CONTROL_ENABLED else None
        self.nearby_panel = NearbyPanel(text_entries=self.text_entries)
        from guide_nodes_panel import NodesPanel
        self.nodes_panel = NodesPanel(self.text_entries)
        self.application_panel = None
        from guide_quick_find import QuickFind
        self.quick_find = QuickFind(self.text_entries)
        self.planegotchi = None
        self.installer_panel = None
        self.audio_panel = None
        if AUDIO_ENABLED:
            from guide_audio_panel import AudioPanel
            if os.environ.get('GUIDE_MEDIA_PLAYERS') == '1':
                from guide_media_panel import MediaPanel
                self.audio_panel = MediaPanel()
            else:self.audio_panel = AudioPanel()
        self.storage_panel = None
        if STORAGE_ENABLED:
            from guide_storage_panel import StoragePanel
            self.storage_panel = StoragePanel()
        self.operations = None
        if OPERATIONS_ENABLED:
            if "/usr/lib/guideos/ui" not in sys.path:sys.path.append("/usr/lib/guideos/ui")
            from guide_operations_frontend import OperationsPages
            self.operations = OperationsPages()
            self.operations.pages['files'].media_available=callable(getattr(self.audio_panel,'open_path',None))
        self.pages, self.choices = PAGES, CHOICES
        self.menu_input = MenuInput(self)
    def enter_page(self, destination, parent=None):
        if destination == self.page:
            return False
        previous = self.page
        self.cancel_media_navigation(destination)
        self.navigation_stack.append(previous if parent is None else parent)
        self.page = destination
        if destination == 'nodes' and self.nodes_panel.view == 'list':self.nodes_panel.scan()
        emit('UI_NAVIGATION', transition='open', page=destination)
        return True
    def go_home(self):
        changed = self.page != 'home' or bool(self.navigation_stack)
        self.cancel_media_navigation('home')
        self.page = 'home'
        self.navigation_stack.clear()
        if changed:emit('UI_NAVIGATION', transition='home', page='home')
        return changed
    def go_back(self, fallback='home'):
        destination = self.navigation_stack.pop() if self.navigation_stack else fallback
        changed = self.page != destination
        self.cancel_media_navigation(destination)
        self.page = destination
        if changed:emit('UI_NAVIGATION', transition='back', page=destination)
        return changed
    def cancel_media_navigation(self, destination):
        if self.page == 'nearby' and destination != self.page:
            self.nearby_panel.leave()
        if self.page == 'find' and destination != self.page:
            self.quick_find.leave()
        if self.page == 'planegotchi' and destination != self.page and self.planegotchi:
            self.planegotchi.deactivate()
        if self.page in ('media','audio') and destination != self.page and self.audio_panel:
            cancel=getattr(self.audio_panel,'cancel_pending_launch',None)
            if cancel:cancel()
    def sync_update_notice(self):
        previous = self.update_notice_id
        transaction = ((self.operations.pages['updates'].status.get('transaction') or {})
                       if self.operations else {})
        self.update_notice_id = transaction.get('id') if transaction.get('state') in ('validated','queued') else None
        return previous != self.update_notice_id
    def dismiss_update_notice(self):
        if self.update_notice_id is None:return False
        self.update_notice_dismissed=self.update_notice_id;self.update_notice_id=None
        return True
    def tick_v3(self, now=None, visible=True):
        now = time.monotonic() if now is None else now
        changed = False
        if self.planegotchi and self.planegotchi.poll_background():changed=True
        if self.page == 'home' and self.v3_home.tick(now):
            changed = True
        if self.page == 'planegotchi' and self.planegotchi:
            if not visible:self.planegotchi.suspend()
            elif self.planegotchi.tick(now):changed=True
        if self.operations:
            if self.operations.pages['updates'].poll():changed=True
            changed=self.sync_update_notice() or changed
        if changed:
            self.revision += 1
        return changed
    def show_unavailable(self,message,replace_current=False):
        self.unavailable_message=message
        if replace_current:self.page='unavailable'
        else:self.enter_page('unavailable')
        self.menu_input.sync_focus();self.revision += 1
        return True
    def open_v3_destination(self, destination):
        if destination == 'planegotchi':
            try:
                from guide_planegotchi import StaticViewer,WorldUnavailable
            except ModuleNotFoundError as exc:
                if exc.name != 'guide_planegotchi':raise
                return self.show_unavailable('The world application is not installed in this build.')
            try:
                if self.planegotchi is None:self.planegotchi=StaticViewer()
                self.planegotchi.suspend()
            except (WorldUnavailable,OSError) as exc:
                return self.show_unavailable(str(exc))
            self.enter_page('planegotchi')
            self.planegotchi.activate_runtime()
            self.menu_input.pointer.close_context()
            if not self.menu_input.pointer.visible:self.menu_input.pointer.move_to(210,252)
        elif destination == 'media':
            if not self.audio_panel:return self.show_unavailable('Media playback is not installed in this build.')
            self.audio_panel.view='library';self.audio_panel.cursor=0
            self.audio_panel.notice=''
            if hasattr(self.audio_panel,'view_stack'):self.audio_panel.view_stack.clear()
            self.enter_page('media')
        elif destination == 'files':
            if not self.operations:return self.show_unavailable('File browser is not installed in this build.')
            self.enter_page('files');self.operations.open('files')
        elif destination == 'applications':
            self.enter_page('installer');self.open_installer('installed')
        elif destination == 'find':
            self.enter_page('find');self.quick_find.open()
        elif destination == 'settings':
            self.enter_page('settings')
        elif destination == 'browser':
            if not BROWSER_ENABLED:return self.show_unavailable('Web browsing is paused for now.')
            self.enter_page('browser')
        elif destination == 'nodes':
            self.enter_page('nodes')
        elif destination == 'storage':
            if not self.storage_panel:return self.show_unavailable('Storage controls are not installed in this build.')
            self.enter_page('storage')
        else:
            return self.show_unavailable('This Home destination is not available.')
        self.menu_input.sync_focus();self.revision += 1
        return True
    def open_v3_setting(self, setting):
        destination = {'audio':'audio','connections':'wifi','nearby':'nearby','storage':'storage',
                       'power':'power','updates':'updates',
                       'diagnostics':'diagnostics','about':'about'}.get(setting)
        if destination == 'wifi' and not self.wifi_panel:
            return self.show_unavailable('Wi-Fi controls are not installed in this build.')
        if destination == 'storage' and not self.storage_panel:
            return self.show_unavailable('Storage controls are not installed in this build.')
        if destination == 'audio' and not self.audio_panel:
            return self.show_unavailable('Audio controls are not installed in this build.')
        if destination == 'updates' and not self.operations:
            return self.show_unavailable('Update controls are not installed in this build.')
        if destination is None:
            return self.show_unavailable('This Settings destination is not available.')
        self.enter_page(destination)
        if destination == 'nearby': self.nearby_panel.open()
        if destination == 'audio':
            self.audio_panel.view='audio';self.audio_panel.cursor=0
            self.audio_panel.notice=''
            if hasattr(self.audio_panel,'view_stack'):self.audio_panel.view_stack.clear()
        if destination == 'updates':self.operations.open('updates')
        if destination == 'power':self.power_selection = 0
        self.menu_input.sync_focus();self.revision += 1
        return True
    def tick_home_slide(self, now=None):
        if self.home_slide is None:
            return False
        now = time.monotonic() if now is None else now
        self.home_slide_progress = max(0.0, min(1.0, (now-self.home_slide[2])/.20))
        if self.home_slide_progress >= 1 or self.page != 'home':
            self.home_slide = None
            self.menu_input.sync_focus()
        self.revision += 1
        return True
    def open_installer(self,view):
        if self.installer_panel is None:
            from guide_installer_panel import InstallerPanel
            self.installer_panel=InstallerPanel(self)
        self.installer_panel.open(view);self.revision+=1
    def open_application(self,code):
        if self.application_panel and not (self.application_panel.finished or self.application_panel.failed):
            raise RuntimeError('An application is already active.')
        if self.application_panel:self.application_panel.shutdown()
        from guide_application_panel import ApplicationPanel
        self.application_panel=ApplicationPanel(code,self.text_entries)
        self.enter_page('application');self.revision+=1
    def open_find_result(self, result):
        if result['kind']=='app':
            try:self.open_application(result['code'])
            except (RuntimeError,ValueError):
                self.quick_find.notice='Finish the active application before opening another.';return False
            return True
        if not self.operations:
            self.quick_find.notice='File Browser is unavailable.';return False
        panel=self.operations.pages['files']
        if panel.busy:
            self.quick_find.notice='File Browser is busy. Try opening again.';return False
        panel.location=result['location'];panel.path=list(result['parts'])
        offer=panel.media_offer(result['entry'])
        if offer and self.audio_panel and self.audio_panel.open_path(offer):
            self.enter_page('media');return True
        panel.folder=result['folder'];panel.offset=result['offset']
        panel.history=[(None,0,None,())];panel.listing={'items':[]}
        panel.show_details(result['entry'])
        panel.submit('folder',2,folder=panel.folder,offset=panel.offset,revision=result['revision'])
        self.operations.current='files';self.operations.focus['files']=result['id']
        self.enter_page('files');return True
    @property
    def keyboard_active(self):
        return bool((self.page == 'nearby' and self.nearby_panel.editor) or (self.page == 'find' and self.quick_find.editor) or (self.page == 'wifi' and self.wifi_panel and self.wifi_panel.editor) or (self.page == 'application' and self.application_panel and self.application_panel.editor) or (self.page == 'nodes' and self.nodes_panel and self.nodes_panel.editor))
    def sticks(self, sample, now=None):
        # Input ownership stays with the shell. Route normalized samples to
        # the active editor or menu; no axes/cursor positions are logged.
        if self.home_slide is not None:
            return False
        if not isinstance(sample, dict):
            return False
        if self.page == 'planegotchi' and self.planegotchi:
            pointer=self.menu_input.pointer;before=pointer.position
            changed,_=pointer.update(left=sample.get('left'),right=None,generation=sample.get('generation',0),right_click=False,now=now)
            if pointer.position!=before:
                changed=self.planegotchi.pointer_moved() or changed
            if changed:self.revision+=1
            return changed
        if self.page == 'nodes' and self.nodes_panel and self.nodes_panel.editor:
            changed=self.nodes_panel.sticks(sample, now=now)
            if changed:self.revision+=1
            return changed
        if self.keyboard_active:
            panel=self.nearby_panel if self.page=='nearby' else self.quick_find if self.page=='find' else self.application_panel if self.page=='application' else self.wifi_panel
            changed = panel.sticks(sample, now=now)
            if not self.keyboard_active:
                self.menu_input.sync_focus()
        else:
            before_revision = self.revision
            changed = self.menu_input.update(sample, now=now)
            if changed and self.revision == before_revision:
                self.pointer_revision += 1
        if changed:
            self.revision += 1
            return True
        return False
    def key(self, code, value):
        if self.page == 'planegotchi' and self.planegotchi and code in (312,313):
            changed=self.planegotchi.key(code,self.menu_input.pointer.position,value=value)
            if changed:self.revision+=1
            return bool(changed)
        if value != 1:
            return False
        if self.home_slide is not None:
            if code == MENU:self.home_slide = None
            else:return False
        if self.audio_panel and code in (114, 115):
            self.audio_panel.activate('quieter' if code == 114 else 'louder')
            self.revision += 1
            return True
        if self.page == 'planegotchi' and self.planegotchi:
            if code == MENU:self.go_home();changed=True
            elif code == 116:self.enter_page('power');self.power_selection=0;changed=True
            else:
                changed=self.planegotchi.key(code,self.menu_input.pointer.position)
                if changed=='close':self.go_back();changed=True
            if changed:self.revision+=1
            return bool(changed)
        if self.page in ('media','audio') and self.audio_panel and code == 116:
            if getattr(self.audio_panel,'video_busy',False):self.audio_panel.video_key(code)
            self.enter_page('power');self.power_selection=0
            self.menu_input.sync_focus();self.revision+=1
            return True
        if self.audio_panel and getattr(self.audio_panel,'video_busy',False):
            video_action=self.audio_panel.video_key(code)
            if code == MENU:self.go_home()
            elif code == B and video_action!='options':
                if not self.audio_panel.back_view():self.go_back()
                self.menu_input.sync_focus()
            elif code == 116:self.enter_page('power');self.power_selection=0
            self.revision+=1
            return True
        if self.page in ('media','audio') and self.audio_panel and code == B:
            back_view=getattr(self.audio_panel,'back_view',None)
            if not (back_view and back_view()):self.go_back()
            self.menu_input.sync_focus();self.revision += 1
            return True
        if (self.page == 'media' and self.audio_panel and
                getattr(self.audio_panel,'view',None) == 'player' and
                getattr(self.audio_panel,'player_key',lambda code:False)(code)):
            self.menu_input.sync_focus();self.revision += 1
            return True
        if self.keyboard_active:
            changed = self._key(code, value)
            if not self.keyboard_active:
                self.menu_input.sync_focus()
            return changed
        changed = self.menu_input.key(code)
        if changed:
            self.revision += 1
        return changed
    def _key(self, code, value):
        if value != 1:  # ignore release and kernel repeat
            return False
        if self.page=='find':
            if code==MENU:self.go_home()
            elif code==B and self.quick_find.editor is None:self.go_back()
            else:self.quick_find.key(code)
            self.revision+=1;return True
        if self.page == 'installer' and self.installer_panel:
            self.installer_panel.key(code);self.revision+=1;return True
        if self.page == 'storage' and code == A:
            self.enter_page('installer');self.open_installer('cartridges');return True
        if self.page == 'application' and self.application_panel:
            if self.application_panel.failed and code in (B,MENU):
                self.go_home() if code == MENU else self.go_back()
            else:self.application_panel.key(code)
            self.revision+=1;return True
        if self.page in ('media','audio') and self.audio_panel:
            if self.audio_panel.key(code) == 'home':
                self.go_home() if code == MENU else self.go_back()
            self.revision += 1
            return True
        if self.operations and self.page in self.operations.pages:
            if code == MENU:
                self.operations.current = None
                self.go_home()
            elif code == B:
                if self.page=='files' and self.navigation_stack and self.navigation_stack[-1]=='find':
                    self.operations.current=None;self.go_back();self.revision+=1;return True
                destination = self.operations.back()
                if destination == 'home':self.go_back()
                else:self.page = destination
            elif code in (UP, DOWN):
                self.operations.move(-1 if code == UP else 1)
            elif code == A:
                self.page = self.operations.activate() or 'home'
            else:
                return False
            self.revision += 1
            return True
        if self.page == 'browser' and code in (B, MENU):
            self.go_home() if code == MENU else self.go_back()
            self.revision += 1
            return True
        if self.page == 'settings':
            if code == B:
                self.go_back()
            elif code in (UP, DOWN):
                from guide_v3_ui import SETTINGS
                self.settings_selection = (self.settings_selection + (1 if code == DOWN else -1)) % len(SETTINGS)
            elif code == A:
                from guide_v3_ui import SETTINGS
                return self.open_v3_setting(SETTINGS[self.settings_selection][0])
            else:
                return False
            self.revision += 1
            return True
        if self.page == 'nodes' and self.nodes_panel:
            result=self.nodes_panel.key(code)
            if result=='home':self.go_home() if code==MENU else self.go_back()
            self.revision+=1;return True
        if self.page == 'nearby':
            if self.nearby_panel.key(code) == 'home': self.go_back()
            self.revision += 1
            return True
        if self.page == 'wifi' and self.wifi_panel:
            if self.wifi_panel.key(code) == 'home':
                self.go_home() if code == MENU else self.go_back()
            self.revision += 1
            return True
        if self.page == 'status' and self.audio_panel:
            if code == A:
                self.audio_panel.activate('test')
                self.revision += 1
                return True
            if code in (UP, DOWN) and self.menu_input.targets():
                self.status_selection = (self.status_selection + (1 if code == DOWN else -1)) % len(self.menu_input.targets())
                self.revision += 1
                return True
        before = (self.page, self.selection, self.shutdown_requested, self.wifi_scroll, self.scan_requested)
        if code == MENU:
            self.go_home()
        elif self.page == "home":
            if code == UP:
                self.selection = (self.selection - 1) % len(CHOICES)
            elif code == DOWN:
                self.selection = (self.selection + 1) % len(CHOICES)
            elif code == A:
                self.enter_page(self.pages[self.selection])
                if self.operations and self.page in self.operations.pages:self.operations.open(self.page)
                if self.page == "applications":self.open_installer("installed")
                if self.page == "wifi" and not self.wifi_panel:
                    self.scan_requested = True
        elif self.page == "power":
            if code == A:
                self.shutdown_requested = True
            elif code == B:
                self.go_back()
        elif self.page == "wifi":
            if code == B:
                self.go_back()
            elif code == A and self.wifi['state'] != 'scanning':
                self.scan_requested = True
            elif code == DOWN:
                self.wifi_scroll = min(max(0, len(self.wifi['networks']) - 5), self.wifi_scroll + 1)
            elif code == UP:
                self.wifi_scroll = max(0, self.wifi_scroll - 1)
        elif code == B:
            self.go_back()
        changed = before != (self.page, self.selection, self.shutdown_requested, self.wifi_scroll, self.scan_requested)
        if changed:
            self.revision += 1
        return changed

class WiFiScan:
    """Keep network waits outside the input/display loop; cancellation owns the child."""
    MAX_OUTPUT = 64 * 1024
    def __init__(self):
        self.process = None
        self.deadline = 0
        self.output = bytearray()
        self.eof = False
    def start(self):
        self.cancel()
        self.process = subprocess.Popen(
            ["/usr/bin/python3", "/usr/lib/guideos/connectivity/guide_wifi_discovery.py"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        try:
            os.set_blocking(self.process.stdout.fileno(), False)
        except OSError:
            self.cancel()
            raise
        self.deadline = time.monotonic() + 15
    def cancel(self):
        if self.process:
            if self.process.poll() is None:
                self.process.kill()
            self.process.wait(timeout=1)
            self.process.stdout.close()
            self.process = None
        self.output.clear()
        self.eof = False
    @staticmethod
    def failed():
        return dict(state='failed', message='Scan failed.', networks=[])
    def poll(self):
        if not self.process:
            return None
        if time.monotonic() >= self.deadline:
            self.cancel()
            return dict(state='timeout', message='Scan timed out.', networks=[])
        try:
            # Drain while the child runs, bounded per frame and in total. Waiting
            # for exit first deadlocks when a dense result fills its output pipe.
            for _ in range(4):
                try:
                    block = os.read(self.process.stdout.fileno(), min(8192, self.MAX_OUTPUT + 1 - len(self.output)))
                except BlockingIOError:
                    break
                if not block:
                    self.eof = True
                    break
                self.output.extend(block)
                if len(self.output) > self.MAX_OUTPUT:
                    self.cancel()
                    return self.failed()
        except OSError:
            self.cancel()
            return self.failed()
        if self.process.poll() is None or not self.eof:
            return None
        output = bytes(self.output)
        returncode = self.process.returncode
        self.cancel()
        try:
            result = json.loads(output)
            if returncode or not isinstance(result, dict):
                raise ValueError('Failed scan process')
            if result.get('state') not in {'ready', 'cached', 'blocked', 'off', 'no-adapter', 'unavailable'}:
                raise ValueError('Invalid scan state')
            if not isinstance(result.get('message'), str) or len(result['message']) > 200:
                raise ValueError('Invalid scan message')
            if not isinstance(result.get('networks'), list) or len(result['networks']) > 128:
                raise ValueError('Invalid scan response')
            for row in result['networks']:
                if not isinstance(row, dict):
                    raise ValueError('Invalid network row')
                if any(not isinstance(row.get(key), str) or not row[key].isprintable() or len(row[key]) > limit
                       for key, limit in (('ssid', 64), ('security', 32))):
                    raise ValueError('Invalid network text')
                if type(row.get('signal')) is not int or not 0 <= row['signal'] <= 100:
                    raise ValueError('Invalid signal')
            return result
        except (ValueError, AttributeError):
            return self.failed()

class Report:
    def __init__(self, data_root, boot_root):
        boot_id = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
        self.folders = [Path(data_root) / boot_id, Path(boot_root) / boot_id]
        self.events = []
        self.started = time.monotonic()
        self.saved_destinations = 0
        self.last_errors = []
        self.shell_sha256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    def event(self, name, **details):
        self.events.append(dict(event=name, monotonic=time.monotonic(), **details))
        self.events = self.events[-256:]
        if name in {"shell_started", "shell_ready", "shell_error", "cleanup",
                    "wifi_scan_started", "wifi_scan_result", "wifi_scan_cancelled"}:
            # systemd retains these even when a report mirror is unavailable.
            try:
                print("GUIDE_BOOT_STAGE " + json.dumps(dict(stage=name, build_id=BUILD_ID, **details)), flush=True)
            except OSError:
                pass
    def save(self, state, phase, cleanup_errors=()):
        document = {
            "version": "guide-shell-smoke-0",
            "build_id": BUILD_ID,
            "shell_sha256": self.shell_sha256,
            "kernel": os.uname().release,
            "phase": phase,
            "page": state.page,
            "selection": state.selection,
            "shutdown_requested": state.shutdown_requested,
            "elapsed_seconds": time.monotonic() - self.started,
            "cleanup_errors": list(cleanup_errors),
            "previous_report_errors": self.last_errors,
            "events": self.events,
        }
        errors = []
        saved = 0
        for folder in self.folders:
            try:
                # A failed mirror must not prevent the shell or the other copy.
                # Retry on later saves in case a mount becomes writable again.
                folder.mkdir(parents=True, exist_ok=True)
                target = folder / "guide-shell.json"
                temporary = target.with_suffix(".json.tmp")
                with temporary.open("w", encoding="utf-8") as output:
                    json.dump(document, output, indent=2)
                    output.flush()
                    os.fsync(output.fileno())
                temporary.replace(target)
                fd = os.open(folder, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)
                saved += 1
            except OSError as exc:
                errors.append(str(folder) + ": " + str(exc))
        self.saved_destinations = saved
        self.last_errors = errors
        return errors

class Screen:
    def __init__(self, sink):
        from PIL import Image, ImageDraw, ImageFont
        self.statusbar = StatusBar()
        self.Image, self.Draw, self.sink = Image, ImageDraw, StatusSink(sink,self.statusbar)
        font = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        self.fonts = {size: ImageFont.truetype(font, size) for size in (12, 14, 16, 18, 22, 28)}
        self.unicode = UnicodeText()
        self._menu_base = None
        if '/usr/lib/guideos/ui' not in sys.path:sys.path.append('/usr/lib/guideos/ui')
        from guide_v3_ui import V3UI
        self.schema=V3UI()
        # Immutable release asset: no typography rasterization during handoff.
        with Image.open(Path(__file__).resolve().parents[1]/'assets/opening-video.png') as graphic:
            if graphic.size != (640,480):raise ValueError('Invalid video opening graphic')
            self.video_opening=graphic.convert('RGB')
        self._regions=()
        self._regions_page=None
        self._region_signature=()
        self._pointer_box=None
        self.last_metrics={}
    def _v3_layout(self,state,status=None):
        from guide_field_ui import field_model
        if state.page == 'home':return self.schema.render_home(state,layered=self.sink.supports_layers)
        if state.page == 'planegotchi' and state.planegotchi:return state.planegotchi.layout(layered=self.sink.supports_layers)
        if state.page == 'nearby':return state.nearby_panel.layout(self.schema)
        if status is not None:self._v3_status=status
        if state.page=='installer' and state.installer_panel:model=state.installer_panel.model()
        elif state.page=='find':model=state.quick_find.model()
        elif state.page=='application' and state.application_panel:model=state.application_panel.model()
        elif state.operations and state.page in state.operations.pages:model=state.operations.model()
        elif state.page=='settings':model=self.schema.settings_model(state)
        else:model=field_model(state,getattr(self,'_v3_status',None))
        if model!=getattr(self,'_v3_model',None) or self.schema.text.scrolling:
            self._v3_result=self.schema.render(model);self._v3_model=model
        if model.pattern=='application-document':
            state.application_panel.scroll_limit=self.schema.application_views.max_scroll
            state.application_panel.document_scroll=min(state.application_panel.document_scroll,state.application_panel.scroll_limit)
        return self._v3_result
    def _schema_targets(self,state):
        return self._regions if self._regions_page == state.page else ()
    def _present_menu(self, image, draw, state):
        if self.sink.supports_layers:
            self._menu_base=image
            self._present_layers(state)
            return
        # One bounded RGB frame, never keyboard text or a history of screens.
        self._menu_base = image.copy()
        self._menu_overlay(image, draw, state)
        self.sink.show(image)
        self._pointer_box=self._cursor_box(state)
    def _present_layers(self,state):
        from guide_gpu_framebuffer import Layer, compose
        pointer=state.menu_input.pointer
        layers=getattr(self,'_menu_layers',())
        if pointer.context is not None:
            # Context labels retain the existing bounded software rasterizer.
            image=compose(self._menu_base,layers)
            self._menu_overlay(image,ImageCanvas(image),state)
            self.sink.show_layers(image)
        else:
            if pointer.visible:
                x=max(0,min(639,round(pointer.position[0])))
                y=max(0,min(479,round(pointer.position[1])))
                if state.page=='planegotchi' and state.planegotchi:
                    layers=tuple(layers)+(Layer(state.planegotchi.cursor(pointer.position),x,y,cache_key='planegotchi-cursor'),)
                else:
                    from guide_pointer_view import _DOT, CURSOR_RADIUS
                    layers=tuple(layers)+(Layer(_DOT,x-CURSOR_RADIUS,y-CURSOR_RADIUS),)
            self.sink.show_layers(self._menu_base,layers)
    @staticmethod
    def _cursor_box(state):
        pointer=state.menu_input.pointer
        if not pointer.visible:return None
        x,y=map(round,pointer.position);radius=8
        if state.page=='planegotchi':return (x,y,min(640,x+15),min(480,y+19))
        return (x-radius,y-radius,x+radius+1,y+radius+1)
    def _text(self, draw, xy, value, size=18, color=INK):
        if not value.isascii() and self.unicode.available:
            from PIL import ImageColor
            self.unicode.draw(draw, xy, value, size, ImageColor.getrgb(color))
            return
        draw.text(xy, value, font=self.fonts[size], fill=color)
    def text_width(self, value, size):
        if not value.isascii() and self.unicode.available:
            return self.unicode.measure(value, size)[0]
        return self.fonts[size].getlength(value)
    def _menu_overlay(self, image, draw, state):
        menu = state.menu_input
        if state.page=='planegotchi' and state.planegotchi:
            if menu.pointer.visible:
                tile=state.planegotchi.cursor(menu.pointer.position)
                image.paste(tile,tuple(map(round,menu.pointer.position)),tile)
            return
        hovered=menu.hovered()
        draw_menu_pointer(image,menu.pointer,self.fonts,hover=hovered.rect if hovered else None)
    def notice_image(self,title,notice):
        from guide_ui_model import ScreenModel
        return self.schema.render(ScreenModel('v3-list',title,notice=notice)).image
    def draw(self, state, status=None, pointer_only=False):
        self.statusbar.pending_update = bool(getattr(state, 'update_notice_id', None))
        started=time.monotonic()
        state.schema_target_provider=lambda:self._schema_targets(state)
        if state.page=='find' and state.quick_find.editor:
            self._menu_base=None;state.quick_find.draw_editor(self.sink);return
        if state.page=='application' and state.application_panel and state.application_panel.editor:
            self._menu_base=None;state.application_panel.draw_editor(self.sink);return
        if state.page == 'nodes' and state.nodes_panel and state.nodes_panel.editor is not None:
            self._menu_base = None
            state.nodes_panel.draw_editor(self.sink)
            return
        if state.page == 'wifi' and state.wifi_panel and state.wifi_panel.editor is not None:
            self._menu_base = None
            state.wifi_panel.draw_editor(self.sink)
            return
        if state.page == 'nearby' and state.nearby_panel.editor is not None:
            self._menu_base = None
            state.nearby_panel.draw_editor(self.sink)
            return
        if state.page == 'status' and state.audio_panel:
            message = state.audio_panel.notice or state.audio_panel.status.get('test_message', '')
            if message:
                status = list(status or [])
                index = next((i for i, row in enumerate(status) if row.startswith('Audio:')), None)
                if index is not None:
                    status[index] = 'Audio: ' + message.removeprefix('Audio test: ')
        if pointer_only and self._menu_base is not None:
            if self.sink.supports_layers:
                self._present_layers(state)
                self.last_metrics={'layout_ms':0.0,'compose_ms':(time.monotonic()-started)*1000,'pointer_only':1}
                return self.last_metrics
            image = self._menu_base.copy()
            self._menu_overlay(image, ImageCanvas(image), state)
            pointer_box=self._cursor_box(state)
            dirty=[box for box in (self._pointer_box,pointer_box) if box is not None]
            self.sink.show(image,dirty=dirty)
            self._pointer_box=pointer_box
            self.last_metrics={'layout_ms':0.0,'compose_ms':(time.monotonic()-started)*1000,
                               'pointer_only':1}
            return self.last_metrics
        layout_started=time.monotonic()
        result=self._v3_layout(state,status)
        layout_done=time.monotonic()
        signature=tuple((r.identity,r.rect.tuple(),r.action) for r in result.regions)
        page_changed=self._regions_page != state.page
        self._regions=result.regions;self._regions_page=state.page
        regions_changed=signature != self._region_signature;self._region_signature=signature
        self._menu_layers=result.layers
        image=result.image if self.sink.supports_layers else result.image.copy()
        if page_changed or not getattr(state,'_schema_ready',False):
            state._schema_ready=True
            state.menu_input.sync_focus()
        self._present_menu(image,ImageCanvas(image),state)
        self.last_metrics={'layout_ms':(layout_done-layout_started)*1000,
                           'compose_ms':(time.monotonic()-layout_done)*1000,
                           'pointer_only':0,'regions_changed':int(regions_changed)}
        return self.last_metrics

def system_status(report=None):
    rows = ["Shell owns display and controls"]
    capacities = sorted(Path("/sys/class/power_supply").glob("*/capacity"))
    if capacities:
        try:
            rows.append("Battery: " + capacities[0].read_text().strip() + "%")
        except OSError:
            rows.append("Battery: reading unavailable")
    else:
        rows.append("Battery: provider unavailable")
    rows.extend(("Kernel: " + os.uname().release,
                 "Audio: local playback and earbud controls" if AUDIO_ENABLED else "Media Controller: not installed",
                 ("Wi-Fi: connection controls available" if WIFI_CONTROL_ENABLED else "Wi-Fi: discovery available; connection not set up") if WIFI_DISCOVERY_ENABLED else "Wi-Fi: not enabled in this revision",
                 "Power key: system-owned"))
    rows.append("GuideOS: "+os.environ.get("GUIDE_BUILD_ID","0.4.2.05"))
    rows.append("Build: " + BUILD_ID)
    if os.environ.get('GUIDE_DEPLOY_RUNTIME'):
        from guide_deploy_shell import status_line
        rows.append(status_line())
    if report is not None:
        rows.append("Reports saved: " + str(report.saved_destinations) + "/2 destinations")
    try:
        v=os.statvfs('/');total=v.f_blocks*v.f_frsize;free=v.f_bavail*v.f_frsize
        storage='%.1f GiB used / %.1f GiB free'%((total-v.f_bfree*v.f_frsize)/2**30,free/2**30)
    except OSError:storage='Unavailable'
    try:
        memory=next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:'))
        memory=str(round(int(memory)/1024))+' MiB available'
    except (OSError,StopIteration,ValueError):memory='Unavailable'
    rows=[rows[1], 'Memory: '+memory,'Storage: '+storage]+[r for r in rows if r.startswith(('Wi-Fi:','Audio:','Power key:','Kernel:','GuideOS:','Build:'))]
    return rows

def run(report, input_factory=DeckInputs, framebuffer_factory=Framebuffer,
        poweroff=lambda: subprocess.run(["systemctl", "poweroff"], check=False)):
    state = ShellState()
    wifi_scan = WiFiScan()
    inputs = framebuffer = None
    cleanup_errors = []
    stopping = False
    scan_id = 0
    scan_started = 0
    bridge = None
    if os.environ.get('GUIDE_DEPLOY_RUNTIME'):
        from guide_deploy_shell import ShellBridge
        bridge = ShellBridge()
    parked = False
    timings = Timings()
    if state.operations and hasattr(state.operations.pages.get('files'), 'timings'):
        state.operations.pages['files'].timings = timings
    pending_navigation = None
    browser = None
    browser_lease = False
    overlay_lease = False
    browser_destination = None
    def stop(*_args):
        nonlocal stopping
        stopping = True
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        inputs = input_factory(lambda row: None)
        boot_runtime = os.environ.get('GUIDE_BOOT_HANDOFF')
        framebuffer = (BootFramebuffer(framebuffer_factory, boot_runtime)
                       if boot_runtime else framebuffer_factory())
        screen = Screen(framebuffer)
        if state.audio_panel and hasattr(state.audio_panel,'video_busy'):
            state.audio_panel.pause_display=lambda:framebuffer.suspend(screen.video_opening) if hasattr(framebuffer,'suspend') else True
        if BROWSER_ENABLED:
            # Pin the controller to the same immutable generation as its shell.
            # A fixed bootstrap import otherwise ignores delivered browser fixes.
            release_browser=Path(__file__).resolve().parent.parent/'browser'
            sys.path.insert(0, str(release_browser) if (release_browser/'guide_browser_frontend.py').is_file() else '/usr/lib/guideos/browser')
            from guide_browser_frontend import BrowserSession
            def pause_browser_display():
                nonlocal browser_lease
                updates = state.operations.pages['updates'] if state.operations else None
                unsafe_update = bool(updates and (updates.display_busy or
                    (updates.status.get('transaction') or {}).get('state') in ('queued', 'activating', 'trial', 'recovering')))
                safe = (not getattr(state.audio_panel, 'video_busy', False) and
                        state.text_entries.active is None and not state.keyboard_active and
                        not state.shutdown_requested and not unsafe_update)
                if not safe:
                    browser.detail = ('An update is restarting the interface.' if unsafe_update else
                        'Video is using the display.' if getattr(state.audio_panel, 'video_busy', False) else
                        'Finish or cancel the active text entry first.' if state.text_entries.active is not None or state.keyboard_active else
                        'Shutdown is in progress.')
                    return False
                if hasattr(framebuffer,'suspend') and not framebuffer.suspend(screen.notice_image('Web browser','Opening browser…')):
                    browser.detail='The interface could not release the display.'
                    return False
                browser_lease = True
                return True
            def resume_browser_display():
                nonlocal browser_lease, browser_destination
                browser_lease = False
                detail = getattr(browser, 'detail', '')
                if detail and detail != 'Browser stopped':
                    state.show_unavailable('Browser unavailable: ' + detail,replace_current=True)
                else:
                    state.page = browser_destination or 'home'
                browser_destination = None
                if hasattr(framebuffer,'resume'):framebuffer.resume()
                if hasattr(framebuffer, 'invalidate'):
                    framebuffer.invalidate()
                state.menu_input.sync_focus()
                state.revision += 1
            browser = BrowserSession(pause_browser_display, resume_browser_display, probe_display=True)
        report.event("shell_started", inputs=[device.name for device in inputs.devices])
        report.save(state, "running")
        last_revision = -1
        last_content_revision = None
        last_draw = float('-inf')
        next_draw = 0.0
        last_report_view = None
        video_was_active = False
        while not stopping:
            if state.shutdown_requested:
                # A running installer owns its transaction beyond this view.
                # Keep controller/Menu input and rendering alive while it settles.
                if state.installer_panel is None:
                    # No installer view existed in this shell session; systemd
                    # still orders and waits for any socket-activated service at
                    # poweroff. Avoid starting a new service just to stop it.
                    break
                if state.installer_panel.prepare_shutdown():break
            state.tick_home_slide()
            state.tick_v3(visible=not (overlay_lease or browser_lease or parked or getattr(state.audio_panel,'video_busy',False)))
            timings.flush()
            if browser:
                if state.page == 'browser' and browser.state == 'idle' and not browser_lease:
                    emit('BROWSER_ATTEMPT', transition='attempt', page='browser')
                    try:
                        if not browser.start():
                            emit('BROWSER_ATTEMPT', transition='failed', page='browser')
                            state.show_unavailable(browser.detail or 'Browser could not take the display.',replace_current=True)
                        else:
                            emit('BROWSER_ATTEMPT', transition='starting', page='browser')
                    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError):
                        emit('BROWSER_ATTEMPT', transition='failed', page='browser')
                        # If the service may have started, keep its display lease
                        # until poll() observes that it has stopped and restores us.
                        if browser.state != 'idle':
                            if not browser.detail:
                                browser.detail = 'Browser startup failed'
                        else:
                            detail = browser.detail or 'Browser failed to start.'
                            state.show_unavailable('Browser unavailable: ' + detail,replace_current=True)
                if browser.state != 'idle':
                    if browser.state=='checking' and state.page!='browser' and not browser_lease:browser.close()
                    previous_browser_state=browser.state
                    timings.measure('poll_browser', browser.poll)
                    if previous_browser_state=='starting' and browser.state=='running':
                        emit('BROWSER_ATTEMPT',transition='ready',page='browser')
                    if browser.state=='idle' and state.page=='browser' and not browser_lease:
                        emit('BROWSER_ATTEMPT',transition='failed',page='browser')
                        state.show_unavailable('Browser unavailable: '+(browser.detail or 'Browser could not take the display.'),replace_current=True)
            if state.installer_panel and timings.measure('poll_installer', state.installer_panel.poll):dirty=True;state.revision+=1
            if state.application_panel and timings.measure('poll_application', state.application_panel.poll):
                if state.application_panel.finished and state.page=='application':
                    state.go_home() if getattr(state.application_panel,'close_destination','back')=='home' else state.go_back()
                state.menu_input.refresh_targets();state.revision+=1
            if state.quick_find.poll():
                if state.page=='find':
                    if not state.keyboard_active:state.menu_input.refresh_targets()
                    state.revision+=1
            if state.page=='find' and state.quick_find.opened:
                result=state.quick_find.opened;state.quick_find.opened=None
                state.open_find_result(result);state.revision+=1
            if timings.measure('poll_statusbar', screen.statusbar.poll):
                state.revision += 1
            if state.storage_panel and timings.measure('poll_storage', state.storage_panel.poll) and state.page == "storage":
                state.revision += 1
            if state.operations and timings.measure('poll_operations', state.operations.poll):
                if state.page in state.operations.pages:
                    state.menu_input.refresh_targets()
                    state.revision += 1
            if state.nodes_panel and timings.measure('poll_nodes', state.nodes_panel.poll):
                if state.page == 'nodes':
                    state.menu_input.refresh_targets()
                    state.revision += 1
            if state.audio_panel and timings.measure('poll_audio', state.audio_panel.poll):
                if state.page in ('media', 'audio', 'status', 'audio-test'):
                    state.menu_input.refresh_targets()
                    state.revision += 1
            video_active = bool(getattr(state.audio_panel,'video_busy',False))
            if (video_was_active or getattr(state.audio_panel,'display_return_pending',False)) and not video_active:
                if hasattr(framebuffer,'resume'):framebuffer.resume()
                if hasattr(framebuffer,'invalidate'):framebuffer.invalidate()
                if state.audio_panel:state.audio_panel.display_return_pending=False
                last_content_revision=None;state.revision+=1
            video_was_active=video_active
            if bridge:
                # Poll completion even away from the Wi-Fi page. A pending
                # connection or private editor must never be discarded to update.
                if state.wifi_panel and timings.measure('poll_wifi', state.wifi_panel.poll):
                    if not state.keyboard_active:
                        state.menu_input.refresh_targets()
                    state.revision += 1
                safe = (not (state.nodes_panel and state.nodes_panel.pending is not None) and not browser_lease and not getattr(state.audio_panel,'video_busy',False) and state.text_entries.active is None and not state.keyboard_active
                        and not state.scan_requested and wifi_scan.process is None
                        and not (state.wifi_panel and (state.wifi_panel.editor is not None
                                 or state.wifi_panel.pending_token or state.wifi_panel.status.get('busy'))))
                if timings.measure('poll_bridge', bridge.poll, safe):
                    if not parked:
                        framebuffer.show(screen.notice_image('Guide update','Applying Guide update…'))
                        parked = True
                    inputs.poll(.05)
                    continue
                if parked:
                    parked = False
                    state.revision += 1
            if state.page == 'nearby' and state.nearby_panel.poll():
                if not state.keyboard_active: state.menu_input.refresh_targets()
                state.revision += 1
            if state.wifi_panel and state.page == 'wifi' and timings.measure('poll_wifi', state.wifi_panel.poll):
                if not state.keyboard_active:
                    state.menu_input.refresh_targets()
                state.revision += 1
            if state.page != 'wifi':
                if wifi_scan.process is not None:
                    report.event('wifi_scan_cancelled', scan_id=scan_id, reason='left_page')
                wifi_scan.cancel()
                state.scan_requested = False
            elif state.scan_requested:
                state.scan_requested = False
                state.wifi_scroll = 0
                try:
                    wifi_scan.start()
                    scan_id += 1
                    scan_started = time.monotonic()
                    report.event('wifi_scan_started', scan_id=scan_id)
                    state.wifi = dict(state='scanning', message='Scanning nearby networks...', networks=[])
                except OSError:
                    state.wifi = dict(state='unavailable', message='Wi-Fi discovery is unavailable.', networks=[])
                    report.event('wifi_scan_result', state='unavailable', networks=0)
                state.revision += 1
            result = timings.measure('poll_wifi_scan', wifi_scan.poll)
            if result is not None:
                report.event('wifi_scan_result', scan_id=scan_id, state=result['state'],
                             networks=len(result['networks']), elapsed_seconds=time.monotonic() - scan_started)
                state.wifi = result
                state.wifi_scroll = 0
                state.revision += 1
            if not overlay_lease and not browser_lease and not getattr(state.audio_panel,'video_busy',False) and state.page!='home' and screen.schema.text.scrolling and time.monotonic()-last_draw>=.1:state.revision+=1
            if not overlay_lease and not browser_lease and not getattr(state.audio_panel,'video_busy',False) and state.revision != last_revision and time.monotonic() >= next_draw:
                draw_started = time.monotonic()
                content_revision = state.revision - state.pointer_revision
                draw_metrics=screen.draw(state, system_status(report) if state.page in ("status","about") else None,
                                         pointer_only=content_revision == last_content_revision)
                last_content_revision = content_revision
                previous_draw=last_draw
                last_draw = time.monotonic()
                next_draw = max(draw_started + 1 / 60, last_draw)
                timings.add('shell_draw', last_draw-draw_started)
                if previous_draw != float('-inf'):timings.add('frame_interval',last_draw-previous_draw)
                for metric in ('layout_ms','compose_ms'):
                    if isinstance(draw_metrics,dict) and metric in draw_metrics:
                        timings.add('frame_'+metric.removesuffix('_ms'),draw_metrics[metric]/1000)
                for metric in ('diff_ms','convert_ms','write_ms','present_ms'):
                    if metric in getattr(framebuffer,'last_metrics',{}):
                        timings.add('framebuffer_'+metric.removesuffix('_ms'),framebuffer.last_metrics[metric]/1000)
                if pending_navigation is not None:
                    timings.add('navigation_submit', last_draw-pending_navigation)
                    pending_navigation = None
                if last_revision == -1:
                    report.event("shell_ready")
                    if bridge:
                        bridge.ready = True
                        bridge.last = 0
                # Signal refresh, pointer motion and password entry must not
                # generate disk writes or reconstructable key/cursor histories.
                report_view = (state.page, state.selection)
                if not (state.text_entries.active is not None or
                        (state.page == 'wifi' and state.wifi_panel)) and report_view != last_report_view:
                    report.event("view", page=state.page, selection=state.selection)
                    report.save(state, "running")
                last_report_view = report_view
                last_revision = state.revision
            active_motion = state.menu_input.pointer.moving and not state.keyboard_active
            active_animation = ((state.page=='home' and
                                (state.v3_home.animating or state.home_slide is not None)) or
                                (state.page=='planegotchi' and state.planegotchi and state.planegotchi.animating) or
                                bool(state.operations and state.operations.animating) or
                                screen.statusbar.volume_frame>0)
            delay = max(0.0, min(1 / 60, next_draw - time.monotonic())) if active_motion or active_animation or state.revision != last_revision else 0.05
            if overlay_lease or browser_lease or getattr(state.audio_panel,'video_busy',False):
                # No shell draw can advance next_draw while another surface owns
                # scanout. A stale deadline must not turn input polling into spin.
                delay=1 / 60
            for event in inputs.poll(delay):
                if getattr(event,'control_prepare',None) is not None:
                    if framebuffer.suspend():
                        overlay_lease=True
                        if browser and browser.controller:browser.controller.release()
                        inputs.display_yielded(event.control_prepare)
                    continue
                if getattr(event,'control_resume',False):
                    if overlay_lease:
                        overlay_lease=False
                        if not browser_lease and not getattr(state.audio_panel,'video_busy',False):framebuffer.resume()
                    state.revision+=1
                input_started = time.monotonic()
                event_time=getattr(event,'timestamp',input_started)
                timings.add('input_queue',max(0.0,input_started-event_time))
                previous_revision = state.revision
                _device, kind, code, value = event
                if browser_lease:
                    if hasattr(event, 'sticks'):
                        browser.input(sticks=event.sticks)
                    elif kind == EV_KEY and code in (114, 115) and value == 1:
                        state.key(code, value)
                    elif kind == EV_KEY and code == 116 and value == 1:
                        browser_destination = 'power'
                        browser.close()
                    elif kind == EV_KEY:
                        browser.input(code=code, value=value)
                    timings.add('input_handler', time.monotonic()-input_started)
                    continue
                if getattr(event,'control_resume',False):
                    state.revision += 1
                    pending_navigation = None
                if hasattr(event, 'sticks'):
                    state.sticks(event.sticks,now=event_time)
                    timings.add('input_handler', time.monotonic()-input_started)
                    if state.revision != previous_revision and pending_navigation is None:
                        pending_navigation = event_time
                    continue
                private_input = (state.text_entries.active is not None or
                                 bool(state.wifi_panel and state.page == 'wifi'))
                if kind == EV_KEY and state.key(code, value):
                    if not private_input:
                        report.event("action", code=code, page=state.page,
                                     selection=state.selection)
                timings.add('input_handler', time.monotonic()-input_started)
                if state.revision != previous_revision and pending_navigation is None:
                    pending_navigation = event_time
            # Evdev produces no new ABS events for a steady held direction.
            # Continue repeats from the latest complete sample, never a partial
            # X/Y update. Frames above also retain fast flicks within one poll.
            snapshot = getattr(inputs, 'stick_snapshot', None)
            if callable(snapshot):
                input_started = time.monotonic()
                previous_revision = state.revision
                if browser_lease:
                    browser.input(sticks=snapshot())
                else:
                    state.sticks(snapshot())
                if state.revision != previous_revision and pending_navigation is None:
                    pending_navigation = input_started
        phase = "shutdown_requested" if state.shutdown_requested else "stopped"
    except Exception as exc:
        emit('SHELL_ERROR', error_number=getattr(exc,'errno',0) or 0)
        # Exception bodies/traceback messages may contain user text from an
        # input adapter. Record the failure class without echoing its payload.
        import traceback
        frames=[]
        for frame,number in traceback.walk_tb(exc.__traceback__):
            module=Path(frame.f_code.co_filename).name
            if module.startswith('guide_') or module=='ImageDraw.py':
                frames.append(dict(module=module,line=number,function=frame.f_code.co_name))
        report.event("shell_error", error_type=type(exc).__name__,page=state.page,source_frames=frames[-6:])
        phase = "failed"
        raise RuntimeError('Guide shell failed; see the recorded error type.') from None
    finally:
        try:
            if state.planegotchi:state.planegotchi.shutdown()
        except Exception as exc:
            cleanup_errors.append('Planegotchi cleanup: '+type(exc).__name__)
        timings.flush(force=True)
        if browser and browser.state != 'idle':
            try:
                browser.close()
                deadline = time.monotonic() + 8
                while browser.state != 'idle' and time.monotonic() < deadline:
                    browser.next_poll = 0
                    browser.poll()
                    time.sleep(.05)
            except Exception as exc:
                cleanup_errors.append('Browser cleanup: ' + type(exc).__name__)
        if browser:browser.shutdown()
        if state.operations:
            state.operations.close()
        if state.audio_panel:
            if hasattr(state.audio_panel,'close'):state.audio_panel.close()
            state.audio_panel.timings.flush(force=True)
        if state.wifi_panel:state.wifi_panel.timings.flush(force=True)
        if state.wifi_panel:
            state.wifi_panel.clear()
        if state.application_panel:state.application_panel.shutdown()
        state.quick_find.close()
        state.nearby_panel.leave()
        if state.installer_panel and not state.installer_panel.shutdown():
            state.shutdown_requested=False
        state.text_entries.teardown()
        try:
            if wifi_scan.process is not None:
                report.event('wifi_scan_cancelled', scan_id=scan_id, reason='shell_stopping')
            wifi_scan.cancel()
        except Exception as exc:
            cleanup_errors.append('Wi-Fi child cleanup: ' + type(exc).__name__)
        if inputs:
            cleanup_errors.extend(inputs.close())
        if framebuffer:
            cleanup_errors.extend(framebuffer.close())
        report.event("cleanup", errors=cleanup_errors)
        report.save(state, phase, cleanup_errors)
        if bridge:
            bridge.publish(False, stopped=True, clean=not cleanup_errors and phase == 'stopped')
    if state.shutdown_requested:
        poweroff()
    return 0

def preview(folder):
    class Sink:
        def show(self, image): self.image = image
    folder.mkdir(parents=True, exist_ok=True)
    sink, state = Sink(), ShellState()
    screen = Screen(sink)
    for page in ("home", "media", "status", "wifi", "power"):
        state.page = page
        if page == 'wifi':
            state.wifi = dict(state='ready', message='Nearby networks', networks=[
                dict(ssid='Example network', signal=85, security='WPA2'),
                dict(ssid='Long network name with enough words to test clipping', signal=42, security='WPA3'),
                dict(ssid='Guest', signal=24, security='Open')])
        screen.draw(state, ["Shell owns display and controls", "Kernel: preview"])
        sink.image.save(folder / (page + ".png"))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, default=Path("/data/guideos/shell-runs"))
    parser.add_argument("--boot-root", type=Path, default=Path("/boot/diagnostics/shell-runs"))
    parser.add_argument("--preview", type=Path)
    args = parser.parse_args()
    if args.preview:
        preview(args.preview)
        return 0
    factory=Framebuffer
    if os.environ.get('GUIDE_UI_GPU')=='1':
        from guide_gpu_framebuffer import GpuFramebuffer
        factory=GpuFramebuffer
    if os.environ.get('GUIDE_CONTROL_SOCKET'):
        from guide_control_client import RemoteDeckInputs
        return run(Report(args.data_root, args.boot_root),input_factory=RemoteDeckInputs,framebuffer_factory=factory)
    return run(Report(args.data_root, args.boot_root),framebuffer_factory=factory)

if __name__ == "__main__":
    raise SystemExit(main())
