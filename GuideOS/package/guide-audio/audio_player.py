"""GStreamer audio-only worker. Never owns display, input or global shutdown."""
import gi
import time
import faulthandler
import os
import signal
from guide_telemetry import emit
gi.require_version('Gst', '1.0')
from gi.repository import Gst
Gst.init(None)

BUFFER_TIME_NS = 1000 * Gst.MSECOND
BUFFER_START_NS = 750 * Gst.MSECOND
BUFFER_BYTES = 2 * 1024 * 1024


def audio_queue():
    """Decode ahead without dropping samples or changing output ownership."""
    queue = Gst.ElementFactory.make('queue', 'guide-audio-buffer')
    if queue is None:
        raise ValueError('Audio buffer component is unavailable')
    queue.set_property('max-size-time', BUFFER_TIME_NS)
    queue.set_property('max-size-bytes', BUFFER_BYTES)
    queue.set_property('max-size-buffers', 0)
    queue.set_property('min-threshold-time', BUFFER_START_NS)
    queue.set_property('leaky', 0)
    queue.set_property('flush-on-eos', False)
    queue.set_property('silent', True)
    return queue


def buffered_sink(sink):
    queue = audio_queue()
    output = Gst.Bin.new('guide-buffered-output')
    output.add(queue)
    output.add(sink)
    if not queue.link(sink):
        raise ValueError('Could not attach the audio buffer')
    if not output.add_pad(Gst.GhostPad.new('sink', queue.get_static_pad('sink'))):
        raise ValueError('Could not expose the audio buffer')
    return output


class GstPlayer:
    def __init__(self):
        self.pipeline = None
        self.state = 'stopped'
        self.message = 'Choose an output and a file.'
        self.position = 0
        self.path = None
        self.output = None
        self.volume = 20
        self.seek_pending = 0
        self.deadline = 0
        self.queue_empty_events = 0

    def stop_pipeline(self):
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
            self.pipeline = None

    def play(self, path, output, resume=0):
        self.stop_pipeline()
        self.path, self.output = path, output
        sink = Gst.ElementFactory.make('pipewiresink')
        pipeline = Gst.ElementFactory.make('playbin')
        if sink is None or pipeline is None:
            raise ValueError('Audio components are unavailable')
        sink.set_property('target-object', output)
        properties = Gst.Structure.new_empty('props')
        properties.set_value('node.dont-reconnect', True)
        properties.set_value('node.dont-fallback', True)
        properties.set_value('media.role', 'Music')
        sink.set_property('stream-properties', properties)
        queue = audio_queue()
        queue.set_property('silent', False)
        self.queue_empty_events = 0
        queue.connect('underrun', self.queue_underrun)
        pipeline.set_property('audio-filter', queue)
        pipeline.set_property('audio-sink', sink)
        pipeline.set_property('flags', 2 | 16)  # audio + software volume; no video/text
        pipeline.set_property('uri', path.as_uri())
        pipeline.set_property('volume', 0 if resume else self.volume / 100)
        self.pipeline = pipeline
        self.seek_pending = max(0, resume)
        self.position = resume
        self.state = 'starting'
        self.deadline = time.monotonic() + 10
        self.message = 'Opening audio...'
        if pipeline.set_state(Gst.State.PAUSED) == Gst.StateChangeReturn.FAILURE:
            self.stop_pipeline()
            self.state = 'failed'
            raise ValueError('Could not open this audio file or output')

    def queue_underrun(self, _queue):
        self.queue_empty_events += 1

    def pause(self, message='Paused'):
        if self.pipeline:
            self.pipeline.set_state(Gst.State.PAUSED)
        self.state, self.message = 'paused', message

    def resume(self):
        if not self.pipeline:
            raise ValueError('Choose a file to play')
        result = self.pipeline.set_state(Gst.State.PLAYING)
        self.state, self.message = ('playing', 'Playing') if result == Gst.StateChangeReturn.SUCCESS else ('starting', 'Resuming...')
        self.deadline = time.monotonic() + 10

    def stop(self):
        self.stop_pipeline()
        self.state, self.message, self.position = 'stopped', 'Stopped', 0

    def set_volume(self, volume):
        self.volume = max(0, min(100, int(volume)))
        if self.pipeline:
            self.pipeline.set_property('volume', 0 if self.seek_pending else self.volume / 100)

    def tick(self):
        if not self.pipeline:
            return
        if self.state == 'starting' and time.monotonic() >= self.deadline:
            self.stop_pipeline()
            self.state, self.message = 'failed', 'Opening audio timed out'
            return
        bus = self.pipeline.get_bus()
        for _ in range(32):
            event = bus.pop()
            if event is None:
                break
            if event.type == Gst.MessageType.ERROR:
                error, _debug = event.parse_error()
                emit('AUDIO_DECODE_ERROR', backend_code=error.code, backend_domain=error.domain)
                self.stop_pipeline()
                self.state, self.message = 'failed', 'Playback failed. Check the file and selected output.'
                return
            if event.type == Gst.MessageType.EOS:
                self.stop()
                self.message = 'Playback finished'
                return
            if event.type == Gst.MessageType.STATE_CHANGED and event.src == self.pipeline:
                _old, current, _pending = event.parse_state_changed()
                if current == Gst.State.PLAYING:
                    if self.seek_pending:
                        # Avoid PipeWire's flush path on a queued stream. A
                        # running, muted stream can drain its bounded queue
                        # before a non-flushing seek installs the new segment.
                        target = self.seek_pending
                        if not self.pipeline.seek_simple(Gst.Format.TIME,
                                Gst.SeekFlags.KEY_UNIT,
                                int(target * Gst.SECOND)):
                            self.stop_pipeline()
                            self.state, self.message = 'failed', 'Could not restore playback position'
                            return
                        self.seek_pending = 0
                        self.pipeline.set_property('volume', self.volume / 100)
                    self.state, self.message = 'playing', 'Playing'
            if event.type == Gst.MessageType.ASYNC_DONE and self.state == 'starting':
                if self.pipeline.set_state(Gst.State.PLAYING) == Gst.StateChangeReturn.FAILURE:
                    self.stop_pipeline()
                    self.state, self.message = 'failed', 'Could not start audio playback'
                    return
                # Confirm PLAYING only from the pipeline state-change message.
        ok, position = self.pipeline.query_position(Gst.Format.TIME)
        if ok and not self.seek_pending:
            self.position = position / Gst.SECOND


def _worker(connection):
    faulthandler.register(signal.SIGUSR1, all_threads=False)
    player = GstPlayer()
    sequence = 0
    next_report = 0
    last_state = None
    try:
        while True:
            if connection.poll(.1):
                sequence, operation, args = connection.recv()
                if operation == 'close':
                    break
                try:
                    getattr(player, operation)(*args)
                except Exception:
                    player.state, player.message = 'failed', 'Audio worker could not complete the request'
            player.tick()
            if player.state != last_state:
                emit('AUDIO_STATE', state=player.state, position=player.position)
                last_state = player.state
            if time.monotonic() >= next_report and player.pipeline:
                queue = player.pipeline.get_property('audio-filter')
                emit('AUDIO_QUEUE', state=player.state, position=player.position,
                     volume=player.volume, queue_empty_events=player.queue_empty_events,
                     buffer_ms=queue.get_property('current-level-time')/Gst.MSECOND,
                     buffer_bytes=queue.get_property('current-level-bytes'))
                next_report = time.monotonic()+5
            connection.send(dict(sequence=sequence, state=player.state, message=player.message,
                                 position=player.position, volume=player.volume,
                                 attached=player.pipeline is not None))
    finally:
        player.stop()
        connection.close()


class Player:
    """Bound the native decoder in its own process, including calls that stall."""
    def __init__(self):
        self.process = self.connection = None
        self.state, self.message = 'stopped', 'Choose an output and a file.'
        self.position, self.volume = 0, 20
        self.path = self.output = None
        self.pipeline = False
        self.sequence = self.acknowledged = 0
        self.last_reply = self.deadline = 0

    def _start(self):
        import multiprocessing
        context = multiprocessing.get_context('spawn')
        self.connection, child = context.Pipe()
        self.process = context.Process(target=_worker, args=(child,))
        self.process.start()
        child.close()
        self.sequence = self.acknowledged = 0
        self.last_reply = time.monotonic()

    def _send(self, operation, *args):
        if not self.process or not self.process.is_alive():
            self.close()
            self._start()
        if self.sequence - self.acknowledged >= 8:
            raise ValueError('Audio worker is busy')
        self.sequence += 1
        self.connection.send((self.sequence, operation, args))
        if self.sequence - self.acknowledged == 1:
            self.deadline = time.monotonic() + 12

    def play(self, path, output, resume=0):
        self.path, self.output = path, output
        self._send('set_volume', self.volume)
        self._send('play', path, output, resume)
        self.state, self.message = 'starting', 'Opening audio...'

    def pause(self, message='Paused'):
        self.state, self.message = 'paused', message
        if self.process:
            self._send('pause', message)

    def resume(self):
        self._send('resume')

    def stop_pipeline(self):
        # An unavailable sink can stall native teardown behind queued audio.
        # Release the isolated worker rather than enqueue more work behind it.
        # Position is retained for an explicit Resume on the chosen output.
        self.close()

    def stop(self):
        if self.process:
            self._send('stop')
        self.state, self.message, self.position = 'stopped', 'Stopped', 0

    def set_volume(self, value):
        self.volume = max(0, min(100, int(value)))
        if self.process:
            self._send('set_volume', self.volume)

    def tick(self):
        if not self.process:
            return
        try:
            for _ in range(32):
                if not self.connection.poll():
                    break
                status = self.connection.recv()
                self.last_reply = time.monotonic()
                self.acknowledged = status['sequence']
                if self.acknowledged == self.sequence:
                    for name in ('state','message','position','volume'):
                        setattr(self, name, status[name])
                    self.pipeline = status['attached']
        except (EOFError, OSError):
            self.last_reply = 0
        waiting = self.sequence != self.acknowledged
        if (not self.process.is_alive() or
                (waiting and time.monotonic() >= self.deadline) or
                time.monotonic() - self.last_reply > 12):
            emit('AUDIO_WORKER_TIMEOUT', position=self.position)
            if self.process.is_alive() and isinstance(self.process.pid, int):
                try:
                    os.kill(self.process.pid, signal.SIGUSR1)
                    time.sleep(.1)
                except ProcessLookupError:
                    pass
            self.close()
            self.state, self.message = 'failed', 'Audio worker timed out or stopped; playback position retained.'

    def close(self):
        if self.process:
            self.process.terminate()
            self.process.join(timeout=.5)
            if self.process.is_alive():
                self.process.kill()
                self.process.join(timeout=.5)
            self.process.close()
            self.process = None
        if self.connection:
            self.connection.close()
            self.connection = None
        self.pipeline = False
