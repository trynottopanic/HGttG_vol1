"""Bounded normal-path tone; no mixer changes or persistent media selection."""
from pathlib import Path
import math
import struct
import time
import wave

RATE, SECONDS, PEAK = 48000, 5, 0.5


def write_tone(path):
    # Half-scale peak leaves headroom; the ordinary software volume still applies.
    samples = bytearray()
    for n in range(RATE * SECONDS):
        fade = min(1.0, n / (RATE * .05), (RATE * SECONDS - 1 - n) / (RATE * .05))
        value = int(32767 * PEAK * fade * math.sin(2 * math.pi * 440 * n / RATE))
        samples.extend(struct.pack('<hh', value, value))
    with wave.open(str(path), 'wb') as output:
        output.setparams((2, 2, RATE, 0, 'NONE', 'not compressed'))
        output.writeframes(samples)


class AudioTest:
    def __init__(self, player, runtime):
        self.player = player
        self.path = Path(runtime) / 'system-test.wav'
        self.active = False
        self.message = ''
        self.output = None
        self.deadline = 0

    def start(self, outputs, selected, volume, media_state, prepare_output=None):
        if self.active:
            self.stop()
            return
        if media_state in ('playing', 'starting'):
            raise ValueError('Pause music before starting the audio test.')
        available = {row['id'] for row in outputs}
        output = selected if selected in available else None
        if selected and output is None:
            raise ValueError('Selected output unavailable. Choose an audio output.')
        if output is None:
            output = next((row['id'] for row in outputs
                           if row['id'].startswith('alsa_output.platform-5096000.codec.')), None)
        if output is None:
            raise ValueError('No audio output available. Choose an output in Audio.')
        write_tone(self.path)
        self.player.set_volume(volume)
        try:
            if prepare_output:
                prepare_output(output)
            self.player.play(self.path, output)
        except Exception:
            self.player.close()
            self.path.unlink(missing_ok=True)
            raise
        self.output, self.active = output, True
        self.deadline = time.monotonic() + 17  # bounded startup plus five seconds
        self.message = 'Audio test: opening at current volume'

    def tick(self):
        if not self.active:
            return
        self.player.tick()
        if self.player.state == 'failed':
            self.stop('Audio test failed. Check the selected output.')
        elif self.player.state == 'stopped':
            self.stop('Audio test complete')
        elif time.monotonic() >= self.deadline:
            self.stop('Audio test timed out')
        else:
            self.message = 'Audio test: playing at current volume' if self.player.state == 'playing' else 'Audio test: opening at current volume'

    def stop(self, message='Audio test stopped'):
        self.player.close()
        self.active = False
        self.path.unlink(missing_ok=True)
        self.message = message
