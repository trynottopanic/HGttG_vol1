"""Local trusted-shell service; IPC is not a public cartridge capability grant."""
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import time
import selectors
from concurrent.futures import ThreadPoolExecutor
from gi.repository import GLib
from audio_core import atomic_json, catalog, outputs_from_dump, selected_path
from audio_player import Player
from audio_lease import AudioLease
from audio_test import AudioTest
from audio_bluetooth import Bluetooth
from audio_errors import report
from audio_monitor import Monitor
from guide_telemetry import emit, Timings

RUNTIME = Path('/run/guideos-audio')
MEDIA = Path('/data/guideos/media')
STATE = Path('/var/lib/guideos-audio/state.json')

def read_inventory():
    """One bounded I/O job; never mutate the playback owner from this worker."""
    process=subprocess.Popen(['pw-dump'],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
    data=bytearray();deadline=time.monotonic()+2
    try:
        os.set_blocking(process.stdout.fileno(),False)
        with selectors.DefaultSelector() as ready:
            ready.register(process.stdout,selectors.EVENT_READ)
            while time.monotonic()<deadline:
                if not ready.select(max(0,deadline-time.monotonic())):break
                part=os.read(process.stdout.fileno(),65536)
                if not part:
                    if process.wait(timeout=max(.01,deadline-time.monotonic())):raise ValueError('Audio inventory unavailable')
                    value=json.loads(data)
                    if type(value)is not list or any(type(row)is not dict for row in value):raise ValueError('Invalid audio inventory')
                    return value
                data.extend(part)
                if len(data)>4*1024**2:raise ValueError('Audio inventory too large')
        raise TimeoutError('Audio inventory timed out')
    finally:
        if process.poll() is None:process.kill()
        process.wait(timeout=.25);process.stdout.close()


class Service:
    def __init__(self):
        self.player = Player()
        self.playback_lease = AudioLease()
        self.audio_test = AudioTest(Player(), RUNTIME)
        self.bluetooth = Bluetooth()
        self.monitor = Monitor()
        self.rows = catalog(MEDIA)
        self.outputs = []
        self.inventory_worker=ThreadPoolExecutor(max_workers=1,thread_name_prefix='guide-audio-inventory')
        self.inventory_job=None
        self.inventory_state='unknown'
        self.inventory_observed=0
        self.selected = None
        self.track = None
        self.notice = ''
        self.token = ''
        self.next_refresh = 0
        self.position = 0
        self.timings = Timings()
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self.sock.bind(str(RUNTIME / 'control.sock'))
        os.chmod(RUNTIME / 'control.sock', 0o660)
        self.sock.setblocking(False)
        try:
            saved = json.loads(STATE.read_text())
            self.selected = saved.get('output')
            self.player.set_volume(saved.get('volume', 20))
        except (OSError, ValueError, TypeError):
            pass

    def save(self):
        atomic_json(STATE, dict(output=self.selected, volume=self.player.volume,
                                track=self.track, position=self.player.position))

    def refresh(self):
        if self.inventory_job is None:
            self.inventory_job=self.inventory_worker.submit(read_inventory)
        self.bluetooth.refresh()

    def reconcile_inventory(self):
        if self.inventory_job is None or not self.inventory_job.done():return
        job,self.inventory_job=self.inventory_job,None
        try:
            inventory = job.result()
            self.outputs = outputs_from_dump(inventory)
            self.monitor.inventory(inventory, self.selected)
            self.inventory_state='ready';self.inventory_observed=time.monotonic()
        except (OSError, ValueError, TypeError, subprocess.SubprocessError,TimeoutError):
            # A failed observation is not evidence that the pinned sink vanished.
            self.inventory_state='unknown'
            return
        if self.audio_test.active and self.audio_test.output not in {o['id'] for o in self.outputs}:
            self.audio_test.stop('Audio test stopped: output disconnected')
        if self.player.state in ('playing', 'starting', 'failed') and self.track and self.selected not in {o['id'] for o in self.outputs}:
            emit('AUDIO_OUTPUT_LOST', position=self.player.position)
            # Pinning the PipeWire stream prevents migration before this poll.
            self.position = self.player.position
            self.player.pause('Output disconnected. Choose an output, then Resume.')
            self.player.stop_pipeline()

    def prepare_output(self, output):
        # The onboard codec uses fixed UCM gain and software volume. Clear
        # inherited sink mute/attenuation only for this explicitly chosen
        # onboard output; never change another sink or the default route.
        if output.startswith('alsa_output.platform-5096000.codec.'):
            node = next(o.get('node_id') for o in self.outputs if o['id'] == output)
            if type(node) is not int or node < 0:
                raise ValueError('Audio route unavailable. Refresh outputs.')
            for args in (['set-mute',str(node),'0'], ['set-volume',str(node),'1.0']):
                subprocess.run(['wpctl', *args], capture_output=True, timeout=2, check=True)

    def command(self, request):
        action = request['action']
        self.token = str(request.get('token', ''))[:64]
        self.notice = ''
        if action=='test' and self.audio_test.active:
            self.audio_test.stop()
            return
        if action in ('play', 'resume') and self.audio_test.active:
            raise ValueError('Stop the audio test before playing music.')
        if action in ('test','output','play','resume') and (self.inventory_state!='ready' or time.monotonic()-self.inventory_observed>10):
            self.next_refresh=0
            raise ValueError('Audio outputs are being checked. Refresh and try again.')
        if action in ('test','play','resume'):self.playback_lease.acquire()
        if action == 'test':
            self.audio_test.start(self.outputs, self.selected, self.player.volume, self.player.state, self.prepare_output)
        elif action == 'refresh':
            self.rows = catalog(MEDIA)
            self.next_refresh = 0
        elif action == 'output':
            if self.audio_test.active:
                self.audio_test.stop()
            identity = request['id']
            if identity not in {o['id'] for o in self.outputs}:
                raise ValueError('Output no longer available')
            self.position = self.player.position
            self.player.pause('Output selected. Press Resume to continue.')
            self.player.stop_pipeline()
            self.selected = identity
            self.save()
        elif action in ('play', 'resume'):
            if self.selected not in {o['id'] for o in self.outputs}:
                raise ValueError('Choose an available audio output first')
            identity = request['id'] if action == 'play' else self.track
            path = selected_path(self.rows, identity, MEDIA)
            self.prepare_output(self.selected)
            resume = 0 if action == 'play' else self.player.position
            if action == 'resume' and self.player.pipeline and self.player.output == self.selected:
                self.player.resume()
            else:
                self.player.play(path, self.selected, resume)
            self.track = identity
            self.next_refresh = 0
            self.monitor.next_sample = self.monitor.hardware_next = 0
        elif action == 'pause':
            self.player.pause()
            self.save()
        elif action == 'stop':
            self.audio_test.stop()
            self.player.stop()
        elif action == 'volume':
            self.player.set_volume(request['value'])
            if self.audio_test.active:
                self.audio_test.player.set_volume(self.player.volume)
            self.save()
        elif action == 'scan':
            self.bluetooth.scan()
        elif action == 'connect':
            self.bluetooth.connect(request['id'])
        elif action == 'disconnect':
            self.bluetooth.disconnect(request['id'])
            self.next_refresh = 0
        elif action == 'cancel':
            self.bluetooth.cancel()
        else:
            raise ValueError('Unknown audio action')

    def tick(self):
        for _ in range(8):
            request = {}
            try:
                raw = self.sock.recv(4097)
            except BlockingIOError:
                break
            try:
                if len(raw) > 4096:
                    raise ValueError('Request too large')
                request = json.loads(raw)
                if not isinstance(request, dict):
                    raise ValueError('Invalid request')
                started = time.monotonic()
                try:
                    self.command(request)
                finally:
                    self.timings.add('audio_command', time.monotonic()-started)
            except Exception as error:
                action = request.get('action', 'unknown') if isinstance(request, dict) else 'unknown'
                if isinstance(action,str) and action in ('scan','connect','disconnect','cancel'):
                    self.bluetooth.failed(action, error)
                else:
                    report(action, error)
                # No backend paths, addresses or credentials in user messages.
                self.notice = str(error)[:120] if isinstance(error, ValueError) else 'Audio operation failed. Retry or check the device.'
                if action == 'test':
                    self.audio_test.message = self.notice
        self.player.tick()
        self.audio_test.tick()
        if not self.audio_test.active and (self.player.process is None or (not self.player.pipeline and self.player.sequence == self.player.acknowledged)):
            self.playback_lease.release()
        self.bluetooth.tick()
        self.reconcile_inventory()
        if time.monotonic() >= self.next_refresh:
            self.refresh()
            self.next_refresh = time.monotonic() + 3
        self.monitor.sample(self.player, self.outputs, self.selected)
        status = dict(test_active=self.audio_test.active, test_message=self.audio_test.message, observed=time.monotonic(), token=self.token, state=self.player.state,
                      message=self.notice or self.player.message, volume=self.player.volume,
                      position=int(self.player.position), track=self.track, output=self.selected,
                      files=[{k:v for k,v in r.items() if k != 'path'} for r in self.rows],
                      outputs=self.outputs, inventory_state=self.inventory_state,
                      inventory_observed=self.inventory_observed, devices=self.bluetooth.devices,
                      bluetooth_message=self.bluetooth.message,
                      bluetooth_adapters=self.bluetooth.adapter_state,
                      busy=bool(self.bluetooth.pending), scanning=bool(self.bluetooth.scan_adapter))
        atomic_json(RUNTIME / 'status.json', status)
        self.timings.flush()
        return True

    def close(self):
        if self.inventory_job:self.inventory_job.cancel()
        self.inventory_worker.shutdown(wait=True,cancel_futures=True)
        self.timings.flush(force=True)
        self.save()
        self.player.stop()
        self.player.close()
        self.audio_test.stop()
        self.playback_lease.release()
        self.bluetooth.close()
        self.sock.close()
        (RUNTIME / 'control.sock').unlink(missing_ok=True)


def main():
    (RUNTIME / 'control.sock').unlink(missing_ok=True)
    service = Service()
    loop = GLib.MainLoop()
    failed = []
    def tick():
        try:
            return service.tick()
        except Exception as error:
            print('guide-audio fatal=' + type(error).__name__, flush=True)
            failed.append(True)
            loop.quit()
            return False
    GLib.timeout_add(250, tick)
    for sig in (signal.SIGTERM, signal.SIGINT):
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, sig, lambda: (loop.quit(), False)[1])
    try:
        loop.run()
    finally:
        service.close()
    if failed:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
