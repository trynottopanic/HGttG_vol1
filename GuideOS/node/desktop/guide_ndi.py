"""GuideOS NDI: a fresh desktop interface over the current GuideOS transports.

The UI owns connection presentation and background jobs. NodeRuntime owns
Deck-facing services; the pinned deployment transport owns diagnostic/update
authority. No prototype UI or free-form remote command interface is used.
"""
from __future__ import annotations

import ipaddress
import json
import os
from pathlib import Path
import queue
import socket
import subprocess
import sys
import threading
import time
import zipfile
import tkinter as tk
from tkinter import filedialog, ttk

from guide_node_core import NodeState
from guide_node_server import NodeRuntime
from diagnostic_suite import DiagnosticSuiteRunner, SuiteStep
from prepare_deck_video import HandBrakeJob, handbrake_cli, DEFAULT_PRESET

VERSION = '1.0.4'
SETTINGS = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'GuideNDI' / 'settings.json'
NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


def private_ipv4(value: str) -> str:
    address = ipaddress.IPv4Address(value.strip())
    if not (address.is_private or address.is_link_local) or address.is_loopback or address.is_unspecified:
        raise ValueError('Enter the Deck’s local Wi-Fi address.')
    return str(address)


def project_directory() -> Path:
    candidates = [Path(__file__).resolve().parents[2]]
    if getattr(sys, 'frozen', False):
        executable = Path(sys.executable).resolve()
        candidates.extend([executable.parent / 'GuideOS', executable.parent.parent / 'HGttG_vol1' / 'GuideOS'])
    candidates.append(Path('E:/DGttG/HGttG_vol1/GuideOS'))
    return next((path for path in candidates if (path / 'package/guide-deploy/guide_deploy.py').is_file()), candidates[-1])


def update_directory(project: Path, fallback: Path) -> Path:
    """Choose the latest local signed package by sequence, never label sorting.

    This is a picker starting folder, not signature or compatibility approval.
    Both legacy candidate/wifi-rN folders and release-0.4.2.xx folders work.
    """
    choices=[]
    folders=[fallback]
    folders.extend(path for path in (project/'build').glob('release-*/*')
        if path.is_dir() and (path.name=='candidate' or path.name.startswith('wifi-') or
            (path.name.startswith('candidate-v') and not any(word in path.name for word in ('-before-','-pre-','-failed')))))
    for folder in folders:
        for package in folder.glob('*.guide-release'):
            try:
                if not 0<package.stat().st_size<=100_000_000:continue
                with zipfile.ZipFile(package) as archive:
                    entry=archive.getinfo('manifest.json')
                    if entry.file_size>128_000:continue
                    manifest=json.loads(archive.read(entry))
                if manifest.get('format')!='GUIDE-SIGNED-BUNDLE-1':continue
                profile=manifest['profile']['manifest'];sequence=profile['releaseSequence']
                if type(sequence) is not int or not 1<=sequence<=2**63-1:continue
                choices.append((sequence,str(folder),folder))
            except (OSError,ValueError,KeyError,TypeError,zipfile.BadZipFile):continue
    return max(choices,key=lambda row:row[:2])[2] if choices else fallback


class GuideTransport:
    """Use the installed developer profile; never import secrets into UI state."""
    def __init__(self, project: Path):
        self.project = project

    def command(self, address: str, operation: str, package: Path | None = None) -> list[str]:
        address = private_ipv4(address)
        project = self.project.resolve()
        if not (project / 'package/guide-deploy/guide_deploy.py').is_file():
            raise ValueError('Select the current GuideOS source folder under Connection details.')
        if len(project.drive) != 2 or not project.drive.endswith(':'):
            raise ValueError('The GuideOS source folder must be on a local drive.')
        linux = '/mnt/' + project.drive[0].lower() + project.as_posix()[2:]
        command = ['wsl.exe', '-d', 'Ubuntu', '-u', 'root', '--', 'env',
                   'PYTHONDONTWRITEBYTECODE=1', 'python3', linux + '/package/guide-deploy/guide_deploy.py',
                   '--profile', '/home/hacker/guideos-private/deploy0/profile.json', '--host', address, operation]
        if package is not None:
            package = package.resolve(strict=True)
            if package.suffix != '.guide-release' or len(package.drive) != 2:
                raise ValueError('Choose a signed .guide-release file on a local drive.')
            command.append('/mnt/' + package.drive[0].lower() + package.as_posix()[2:])
        return command

    def request(self, address: str, operation: str = 'status', package: Path | None = None) -> dict:
        result = subprocess.run(self.command(address, operation, package), capture_output=True,
                                text=True, encoding='utf-8', errors='replace',
                                timeout=180 if package else 20, creationflags=NO_WINDOW)
        if result.returncode:
            detail = result.stderr.strip().splitlines()
            raise ConnectionError(detail[-1][:240] if detail else 'The Deck did not answer the saved diagnostic connection.')
        return json.loads(result.stdout)


class NDI:
    def __init__(self, window: tk.Tk):
        self.window = window
        self.events: queue.Queue = queue.Queue()
        self.settings = self.load_settings()
        self.project = Path(self.settings.get('project', str(project_directory())))
        self.transport = GuideTransport(self.project)
        self.state: NodeState | None = None
        self.runtime: NodeRuntime | None = None
        self.peers: list[dict] = []
        self.selected_id = ''
        self.address = str(self.settings.get('deck_address', ''))
        self.verified_address = ''
        self.remote_status: dict = {}
        self.probing = False
        self.next_probe = 0.0
        self.busy = False
        self.video_job = None
        self.runner: DiagnosticSuiteRunner | None = None
        self.last_capture: Path | None = None
        self.closed = False
        self.snapshot_pending = False
        self.starting = True
        self.last_peer_signature = ''
        self.last_code = ''
        self.vars = {name: tk.StringVar() for name in ('connection', 'remembered', 'code', 'pairing',
                    'diagnostic', 'release', 'updates', 'notice', 'computer', 'address', 'source', 'identity')}
        self.build_ui()
        self.vars['computer'].set(socket.gethostname())
        self.vars['notice'].set('Starting the computer’s GuideOS services…')
        self.vars['diagnostic'].set('Waiting for a Deck')
        self.vars['release'].set('Not yet read from the Deck')
        self.vars['updates'].set('Choose a signed GuideOS release to send to the Deck.')
        self.vars['source'].set(str(self.project))
        self.manual_address.set(self.address)
        self.background('start', self.start_services)
        self.window.after(200, self.tick)

    @staticmethod
    def load_settings():
        try:
            if SETTINGS.stat().st_size > 32768:
                return {}
            value = json.loads(SETTINGS.read_text(encoding='utf-8'))
            return value if isinstance(value, dict) else {}
        except (OSError, ValueError):
            return {}

    def save_settings(self):
        self.settings.update(project=str(self.project), deck_address=self.address)
        try:
            SETTINGS.parent.mkdir(parents=True, exist_ok=True)
            temporary = SETTINGS.with_suffix('.new')
            temporary.write_text(json.dumps(self.settings, indent=2), encoding='utf-8')
            os.replace(temporary, SETTINGS)
        except OSError:
            self.vars['notice'].set('The connection works, but its address could not be saved on this computer.')

    def build_ui(self):
        root = self.window
        root.title('GuideOS NDI')
        root.geometry('820x720')
        root.minsize(700, 620)
        root.protocol('WM_DELETE_WINDOW', self.close)
        style = ttk.Style(root)
        style.theme_use('clam')
        style.configure('.', font=('Segoe UI', 11), background='#f3f4f1', foreground='#202924')
        style.configure('TFrame', background='#f3f4f1')
        style.configure('TLabel', background='#f3f4f1')
        style.configure('Title.TLabel', font=('Segoe UI', 25, 'bold'))
        style.configure('Heading.TLabel', font=('Segoe UI', 14, 'bold'))
        style.configure('Code.TLabel', font=('Consolas', 30, 'bold'), foreground='#315d4b')
        style.configure('TButton', padding=(14, 8))
        style.configure('TNotebook.Tab', padding=(18, 10))
        outer = ttk.Frame(root, padding=24)
        outer.pack(fill='both', expand=True)
        ttk.Label(outer, text='GuideOS NDI', style='Title.TLabel').pack(anchor='w')
        ttk.Label(outer, textvariable=self.vars['computer']).pack(anchor='w', pady=(2, 16))
        tabs = ttk.Notebook(outer)
        tabs.pack(fill='both', expand=True)
        self.deck_page = ttk.Frame(tabs, padding=20)
        sharing = ttk.Frame(tabs, padding=20)
        details = ttk.Frame(tabs, padding=20)
        tabs.add(self.deck_page, text='Deck')
        tabs.add(sharing, text='Shared media')
        tabs.add(details, text='Connection details')
        self.peer_choice = ttk.Combobox(self.deck_page, state='readonly')
        self.peer_choice.bind('<<ComboboxSelected>>', self.select_peer)
        self.label(self.deck_page, 'connection', 'Heading.TLabel')
        self.label(self.deck_page, 'remembered')
        self.pair_box = ttk.Frame(self.deck_page)
        self.pair_box.pack(fill='x', pady=(14, 10))
        ttk.Label(self.pair_box, text='On the Deck, open Nodes and select this computer.').pack(anchor='w')
        ttk.Label(self.pair_box, text='Enter this code, then choose Remember this computer.').pack(anchor='w', pady=(2, 8))
        self.label(self.pair_box, 'code', 'Code.TLabel')
        self.label(self.pair_box, 'pairing')
        self.retry = ttk.Button(self.pair_box, text='Retry starting NDI', command=self.retry_start)
        cards = ttk.Frame(self.deck_page)
        self.cards = cards
        cards.pack(fill='both', expand=True, pady=(16, 0))
        cards.columnconfigure(0, weight=1, uniform='cards')
        cards.columnconfigure(1, weight=1, uniform='cards')
        diagnostics = ttk.Frame(cards, padding=(0, 0, 16, 0))
        updates = ttk.Frame(cards, padding=(16, 0, 0, 0))
        diagnostics.grid(row=0, column=0, sticky='nsew')
        updates.grid(row=0, column=1, sticky='nsew')
        ttk.Label(diagnostics, text='Diagnostics', style='Heading.TLabel').pack(anchor='w')
        self.label(diagnostics, 'diagnostic')
        diagnostic_buttons = ttk.Frame(diagnostics)
        diagnostic_buttons.pack(anchor='w', pady=10)
        self.run_button = ttk.Button(diagnostic_buttons, text='Run diagnostics', command=self.run_diagnostics, state='disabled')
        self.run_button.pack(side='left')
        self.cancel_button = ttk.Button(diagnostic_buttons, text='Cancel', command=self.cancel_diagnostics, state='disabled')
        self.cancel_button.pack(side='left', padx=8)
        self.capture_button = ttk.Button(diagnostics, text='Open saved capture folder', command=self.open_capture, state='disabled')
        self.capture_button.pack(anchor='w', pady=4)
        ttk.Label(updates, text='GuideOS updates', style='Heading.TLabel').pack(anchor='w')
        self.label(updates, 'release')
        self.label(updates, 'updates')
        self.send_button = ttk.Button(updates, text='Send update…', command=self.send_update, state='disabled')
        self.send_button.pack(anchor='w', pady=10)

        ttk.Label(sharing, text='Media available to your Deck', style='Heading.TLabel').pack(anchor='w')
        ttk.Label(sharing, text='Choose folders on this computer. The Deck browses them through its Media screen.',
                  wraplength=660).pack(anchor='w', pady=(6, 14))
        self.folders = tk.Listbox(sharing, font=('Segoe UI', 11), height=10, selectmode='browse',
                                  relief='flat', background='white', activestyle='none')
        self.folders.pack(fill='both', expand=True)
        controls = ttk.Frame(sharing)
        controls.pack(fill='x', pady=12)
        self.add_button = ttk.Button(controls, text='Add folder…', command=self.add_folder, state='disabled')
        self.add_button.pack(side='left')
        self.remove_button = ttk.Button(controls, text='Remove folder', command=self.remove_folder, state='disabled')
        self.remove_button.pack(side='left', padx=8)
        self.scan_button = ttk.Button(controls, text='Refresh media', command=self.refresh_media, state='disabled')
        self.scan_button.pack(side='left')
        self.media_notice = tk.StringVar(value='No folders loaded yet.')
        ttk.Label(sharing, textvariable=self.media_notice, wraplength=660).pack(anchor='w')
        preparation = ttk.Frame(sharing)
        preparation.pack(fill='x', pady=(12, 4))
        self.prepare_button = ttk.Button(preparation, text='Prepare video…', command=self.prepare_video)
        self.prepare_button.pack(side='left')
        self.prepare_cancel = ttk.Button(preparation, text='Cancel preparation', command=self.cancel_video)
        self.video_notice = tk.StringVar(value='Create a smaller copy for the Deck. Original videos stay intact.')
        ttk.Label(sharing, textvariable=self.video_notice, wraplength=660).pack(anchor='w')

        ttk.Label(details, text='Current connection', style='Heading.TLabel').pack(anchor='w')
        self.label(details, 'address')
        self.label(details, 'identity')
        ttk.Label(details, text='If automatic connection is unavailable, enter the Deck’s Wi-Fi address:',
                  wraplength=660).pack(anchor='w', pady=(20, 6))
        address_row = ttk.Frame(details)
        address_row.pack(fill='x')
        self.manual_address = tk.StringVar()
        ttk.Entry(address_row, textvariable=self.manual_address, width=24).pack(side='left')
        ttk.Button(address_row, text='Check connection', command=self.use_address).pack(side='left', padx=8)
        ttk.Label(details, text='Remembered Decks', style='Heading.TLabel').pack(anchor='w', pady=(22, 8))
        self.remembered = ttk.Combobox(details, state='readonly')
        self.remembered.pack(fill='x')
        ttk.Button(details, text='Forget selected Deck', command=self.forget_deck).pack(anchor='w', pady=8)
        ttk.Label(details, text='Connection policy', style='Heading.TLabel').pack(anchor='w', pady=(12, 6))
        self.policy = ttk.Combobox(details, values=('Open', 'Familiar', 'Closed'), state='readonly', width=18)
        self.policy.pack(anchor='w')
        self.policy.bind('<<ComboboxSelected>>', self.set_policy)
        ttk.Label(details, text='Open offers introductions. Familiar accepts remembered Decks and code pairing. '
                  'Closed declines incoming connections. Existing sessions continue.', wraplength=660).pack(anchor='w', pady=6)
        ttk.Label(details, text='GuideOS source folder', style='Heading.TLabel').pack(anchor='w', pady=(12, 4))
        self.label(details, 'source')
        ttk.Button(details, text='Choose folder…', command=self.choose_project).pack(anchor='w', pady=6)
        self.label(outer, 'notice')

    def label(self, parent, name, style='TLabel'):
        label = ttk.Label(parent, textvariable=self.vars[name], style=style, wraplength=660)
        label.configure(width=1)
        label.bind('<Configure>', lambda event: label.configure(wraplength=max(120, event.width)))
        label.pack(anchor='w', fill='x', pady=3)
        return label

    def background(self, event, function):
        def work():
            try:
                self.events.put((event, function(), None))
            except Exception as error:
                self.events.put((event, None, str(error)[:400]))
        threading.Thread(target=work, name='ndi-' + event, daemon=True).start()

    def retry_start(self):
        if not self.starting:
            self.starting = True
            self.retry.pack_forget()
            self.background('start', self.start_services)

    def snapshot(self):
        if time.time() >= self.state.pairing_expires:
            self.state.rotate_pairing_code()
        return (self.state.connected_decks(), self.state.pairing_code,
                self.state.pairing_expires, self.state.trusted_decks())

    def start_services(self):
        if self.runtime and self.runtime.running:
            return self.state, self.runtime
        state = NodeState(name=socket.gethostname(), auto_prepare=True)
        runtime = NodeRuntime(state)
        try:
            runtime.start()
            with state._lock:
                state._save_trust()  # A stable computer identity exists before its first pairing.
        except Exception:
            runtime.stop()
            state.close()
            raise
        if self.closed:
            runtime.stop()
            state.close()
        return state, runtime

    def tick(self):
        if self.closed:
            return
        while True:
            try:
                event, value, error = self.events.get_nowait()
            except queue.Empty:
                break
            self.handle_event(event, value, error)
        if self.state and not self.snapshot_pending:
            self.snapshot_pending = True
            self.background('snapshot', self.snapshot)
        if self.address and not self.probing and not self.busy and time.monotonic() >= self.next_probe:
            self.probe()
        self.window.after(500, self.tick)

    def handle_event(self, event, value, error):
        if event == 'start':
            self.starting = False
            if error:
                self.vars['notice'].set('NDI could not start: ' + error + '. Close any other NDI and retry.')
                self.retry.pack(anchor='w', pady=8)
                return
            self.state, self.runtime = value
            self.retry.pack_forget()
            self.vars['computer'].set(self.state.name)
            self.policy.set(self.state.at_field.mode.value.title())
            self.vars['notice'].set('NDI is ready. Connect from Nodes on your Deck.')
            self.render_connection()
            self.render_media()
        elif event == 'snapshot':
            self.snapshot_pending = False
            if error:
                self.vars['notice'].set(error)
                return
            peers, code, expires, choices = value
            signature = json.dumps(peers, sort_keys=True)
            if signature != self.last_peer_signature:
                self.last_peer_signature = signature
                self.peers = peers
                self.render_connection()
            if code != self.last_code:
                self.last_code = code
                self.vars['code'].set(code[:3] + ' ' + code[3:])
            pairing_text = 'Code renews in ' + str(max(0, int(expires - time.time()))) + ' seconds.'
            if self.vars['pairing'].get() != pairing_text:
                self.vars['pairing'].set(pairing_text)
            if choices != getattr(self, 'trusted_choices', []):
                self.trusted_choices = choices
                self.remembered.configure(values=[name for _, name in choices])
                if choices:
                    self.remembered.current(0)
                else:
                    self.remembered.set('No remembered Decks')
        elif event == 'probe':
            self.probing = False
            address, status = value if not error else ('', {})
            if error or address != self.address:
                self.verified_address = ''
                self.vars['identity'].set('Deck identity has not been verified at this address.')
                self.vars['release'].set('Installed version is unavailable while the Deck is disconnected.')
                self.vars['diagnostic'].set('Saved diagnostic connection unavailable. ' + (error or 'The selected Deck changed.'))
            else:
                self.verified_address = address
                self.remote_status = status
                active = status.get('active', {})
                self.vars['identity'].set('Verified Deck: ' + str(status.get('device', '')))
                self.vars['release'].set('Installed: ' + str(active.get('version', 'Unknown')))
                self.vars['diagnostic'].set('Ready — saved Deck identity verified')
                transaction = status.get('transaction')
                if transaction and transaction.get('state') in ('validated', 'queued', 'activating', 'trial'):
                    self.vars['updates'].set('Update ' + str(transaction['state']) + '. For a staged update, open Settings → Updates on the Deck.')
                self.save_settings()
            self.update_buttons()
        elif event == 'prepared-video':
            self.video_job = None
            self.prepare_button.configure(state='normal')
            self.prepare_cancel.pack_forget()
            self.video_notice.set(error or ('Deck copy saved: ' + Path(value['output']).name))
        elif event in ('capture', 'update', 'media'):
            self.busy = False
            self.runner = None
            self.cancel_button.configure(state='disabled')
            if error:
                self.vars['notice'].set(error)
                if event == 'capture':
                    self.vars['diagnostic'].set('Diagnostics failed. ' + error)
            elif event == 'capture':
                result = value[0]
                compatibility = 'Compatibility diagnostic capture:' in result.detail
                self.vars['diagnostic'].set(('Diagnostic snapshot saved (compatibility mode).' if compatibility else 'Diagnostics saved.') if result.outcome == 'passed' else 'Diagnostics ' + result.outcome + '.')
                if result.outcome == 'passed':
                    line = next((line for line in reversed(result.detail.splitlines()) if line.startswith(('Full capture saved: ', 'Diagnostic capture saved: '))), '')
                    if line:
                        self.last_capture = Path(line.partition(': ')[2])
                        self.capture_button.configure(state='normal')
                    self.vars['notice'].set(line or 'Diagnostic capture complete.')
                elif result.outcome == 'cancelled':
                    self.vars['notice'].set('Diagnostic capture cancelled.')
                else:
                    self.vars['notice'].set('The capture could not finish. Check the Deck is awake and connected. Details are saved in the NDI operation log.')
                self.save_operation_log('capture', DiagnosticSuiteRunner.bundle(value))
            elif event == 'update':
                self.vars['updates'].set('Update ' + str(value.get('state', 'staged')) + '. Open Settings → Updates on the Deck to install it.')
                self.vars['notice'].set('The signed update is on the Deck. Installation restarts its shell.')
                self.next_probe = 0
            else:
                self.render_media()
                self.vars['notice'].set('Shared media refreshed.')
            self.update_buttons()
        elif event == 'policy':
            if error:
                self.vars['notice'].set(error)
                self.policy.set(self.state.at_field.mode.value.title())
            else:
                self.vars['notice'].set('Connection policy saved; current sessions continue.')
        elif error:
            self.vars['notice'].set(error)

    def render_connection(self):
        peer = next((peer for peer in self.peers if peer['id'] == self.selected_id), None)
        if peer is None and self.peers:
            peer = self.peers[0]
        if len(self.peers) > 1:
            self.peer_choice.configure(values=[peer['name'] + ' · ' + peer['address'] for peer in self.peers])
            self.peer_choice.pack(before=self.deck_page.winfo_children()[1], fill='x', pady=(0, 10))
            self.peer_choice.current(self.peers.index(peer))
        else:
            self.peer_choice.pack_forget()
        if peer:
            self.selected_id = str(peer['id'])
            self.vars['connection'].set(str(peer['name']) + ' — Node session open')
            self.vars['remembered'].set('Remembered — reconnect without a code' if peer['remembered'] else 'Session connection — choose Remember this computer on the Deck')
            self.pair_box.pack_forget()
            if peer['address'] and self.address != peer['address']:
                try:
                    self.address = private_ipv4(str(peer['address']))
                except ValueError:
                    self.vars['notice'].set('This Deck session has no usable Wi-Fi address.')
                    return
                self.verified_address = ''
                self.manual_address.set(self.address)
                self.next_probe = 0
        else:
            self.vars['connection'].set('Connect your Deck')
            self.vars['remembered'].set('Remembered connections resume when you open Nodes on the Deck.')
            if not self.pair_box.winfo_manager():
                self.pair_box.pack(before=self.cards, fill='x', pady=(14, 10))
        self.vars['address'].set('Deck Wi-Fi address: ' + (self.address or 'Waiting for connection'))
        self.update_buttons()

    def select_peer(self, _event=None):
        if self.busy or self.probing:
            return
        index = self.peer_choice.current()
        if 0 <= index < len(self.peers):
            self.selected_id = str(self.peers[index]['id'])
            self.render_connection()

    def probe(self):
        self.probing = True
        self.next_probe = time.monotonic() + 20
        address = self.address
        self.background('probe', lambda: (address, self.transport.request(address)))

    def update_buttons(self):
        ready = bool(self.verified_address and self.verified_address == self.address and not self.busy)
        for button in (self.run_button, self.send_button):
            button.configure(state='normal' if ready else 'disabled')
        for button in (self.add_button, self.remove_button, self.scan_button):
            button.configure(state='normal' if self.state and not self.busy else 'disabled')
        self.peer_choice.configure(state='disabled' if self.busy else 'readonly')

    def run_diagnostics(self):
        if self.busy or self.verified_address != self.address:
            return
        script = self.project / 'build/Guide-Link.ps1'
        if not script.is_file():
            self.vars['notice'].set('The current GuideOS source folder does not contain the diagnostic helper.')
            return
        self.busy = True
        self.runner = DiagnosticSuiteRunner(script, self.address, (SuiteStep('deck.capture', 'Capture', 240),))
        runner = self.runner
        self.vars['diagnostic'].set('Saving the Deck’s current-boot diagnostics…')
        self.vars['notice'].set('Diagnostics are running. You can continue using the Deck.')
        self.cancel_button.configure(state='normal')
        self.update_buttons()
        self.background('capture', runner.run)

    def cancel_diagnostics(self):
        if self.runner:
            self.runner.cancel()
            self.vars['diagnostic'].set('Cancelling the capture…')
            self.cancel_button.configure(state='disabled')

    def save_operation_log(self, operation, results):
        try:
            logs = SETTINGS.parent / 'operations'
            logs.mkdir(parents=True, exist_ok=True)
            filename = operation + '-' + str(time.time_ns()) + '.json'
            (logs / filename).write_text(json.dumps({'address': self.address, 'results': results}, indent=2), encoding='utf-8')
        except OSError:
            self.vars['notice'].set('The operation finished, but its local log could not be saved.')

    def open_capture(self):
        if self.last_capture and self.last_capture.is_file():
            os.startfile(str(self.last_capture.parent))
        else:
            self.vars['notice'].set('The saved capture is no longer at its original location.')

    def send_update(self):
        if self.busy or self.verified_address != self.address:
            return
        fallback=Path(sys.executable).parent if getattr(sys,'frozen',False) else self.project/'build'
        initial=update_directory(self.project,fallback)
        value = filedialog.askopenfilename(title='Send signed GuideOS update', initialdir=str(initial), filetypes=[('GuideOS signed release', '*.guide-release')])
        if not value:
            return
        self.busy = True
        address = self.address
        self.vars['updates'].set('Sending and validating ' + Path(value).name + '…')
        self.vars['notice'].set('The Deck will check the signature and release compatibility.')
        self.update_buttons()
        self.background('update', lambda: self.transport.request(address, 'stage', Path(value)))

    def use_address(self):
        if self.busy or self.probing:
            self.vars['notice'].set('Wait for the current operation to finish.')
            return
        try:
            self.address = private_ipv4(self.manual_address.get())
        except ValueError as error:
            self.vars['notice'].set(str(error))
            return
        self.verified_address = ''
        self.vars['address'].set('Deck Wi-Fi address: ' + self.address)
        self.vars['diagnostic'].set('Checking the saved Deck identity…')
        self.next_probe = 0
        self.update_buttons()

    def forget_deck(self):
        index = self.remembered.current()
        if not self.state or not 0 <= index < len(getattr(self, 'trusted_choices', [])):
            return
        identity, name = self.trusted_choices[index]
        self.background('forget', lambda: self.state.revoke_trust(identity))
        self.vars['notice'].set(name + ' will need the displayed code to connect again.')

    def set_policy(self, _event=None):
        if self.state:
            mode = self.policy.get().lower()
            self.background('policy', lambda: self.state.set_at_field(mode))

    def choose_project(self):
        if self.busy or self.probing:
            self.vars['notice'].set('Wait for the current operation to finish.')
            return
        value = filedialog.askdirectory(title='Current GuideOS source folder')
        if value:
            project = Path(value)
            if not (project / 'package/guide-deploy/guide_deploy.py').is_file():
                self.vars['notice'].set('This folder does not contain the GuideOS deployment service.')
                return
            self.project = project
            self.transport = GuideTransport(project)
            self.vars['source'].set(str(project))
            self.save_settings()
            self.next_probe = 0

    def render_media(self):
        self.folders.delete(0, 'end')
        for folder in self.state.media.folders:
            self.folders.insert('end', str(folder))
        self.media_notice.set(str(len(self.state.media.records())) + ' media items indexed. ' + self.state.media.last_error)

    def media_job(self, action):
        if not self.state or self.busy:
            return
        self.busy = True
        self.vars['notice'].set('Refreshing shared media…')
        self.update_buttons()
        def work():
            with self.state._lock:
                action()
                self.state.prepare_media()
        self.background('media', work)

    def add_folder(self):
        value = filedialog.askdirectory(title='Share a media folder with your Deck')
        if value:
            self.media_job(lambda: self.state.media.add_folder(value))

    def remove_folder(self):
        selected = self.folders.curselection()
        if selected:
            index = selected[0]
            self.media_job(lambda: self.state.media.remove_folder(index))

    def refresh_media(self):
        self.media_job(self.state.media.scan)

    def prepare_video(self):
        if self.video_job is not None:return
        if not handbrake_cli():
            self.video_notice.set('Install HandBrakeCLI on this computer to prepare Deck videos.')
            return
        source = filedialog.askopenfilename(title='Choose a video to prepare for the Deck',
            filetypes=[('Video files', '*.mp4 *.mkv *.mov *.avi *.webm'), ('All files', '*.*')])
        if not source:return
        source = Path(source)
        destination = filedialog.asksaveasfilename(title='Save the Deck video copy',
            initialdir=str(source.parent), initialfile=source.stem+' - Deck.mp4',
            defaultextension='.mp4', filetypes=[('MP4 video', '*.mp4')])
        if not destination:return
        job = self.video_job = HandBrakeJob()
        self.prepare_button.configure(state='disabled')
        self.prepare_cancel.pack(side='left', padx=8)
        self.video_notice.set('Preparing the Deck copy…')
        self.background('prepared-video', lambda:job.run(source, destination,
            DEFAULT_PRESET,
            SETTINGS.parent/'conversions'/('handbrake-'+str(time.time_ns())+'.log')))

    def cancel_video(self):
        if self.video_job is not None:
            self.video_job.cancel()
            self.video_notice.set('Cancelling video preparation…')

    def close(self):
        self.closed = True
        if self.video_job is not None:self.video_job.cancel()
        if self.runner:
            self.runner.cancel()
        def stop():
            if self.runtime:
                self.runtime.stop()
            if self.state:
                self.state.close()
        threading.Thread(target=stop, daemon=True).start()
        self.window.destroy()


def main():
    if sys.platform == 'win32':
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (OSError, AttributeError):
            pass
    window = tk.Tk()
    NDI(window)
    window.mainloop()


if __name__ == '__main__':
    main()
