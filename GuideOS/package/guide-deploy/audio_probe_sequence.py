"""Fixed, bounded hardware-format comparisons for the explicit speaker probe."""
import hashlib
import math
import re
from pathlib import Path
import struct
import subprocess
import tempfile
import time

RATE = 48000
FRAMES = RATE * 4

def buffer_summary(raw):
    prefix=raw[:4096]
    checksum=2166136261
    for value in prefix:checksum=((checksum ^ value)*16777619) & 0xffffffff
    return dict(bytes=len(prefix),nonzero_bytes=sum(value!=0 for value in prefix),fnv1a32=checksum)

def buffer_evidence(command, expected):
    result=command(['amixer','-c','Codec','cget','name=DAC Buffer Evidence'])
    if not result.get('available'):return dict(available=False)
    match=re.search(r': values=([0-9,]+)',result.get('text',''))
    if not match:return dict(available=False)
    values=[int(value) for value in match[1].split(',')]
    if len(values)!=11 or values[0]!=1:return dict(available=False,reason='not-captured')
    actual=dict(bytes=values[1],nonzero_bytes=values[2],fnv1a32=values[3] | (values[4]<<16))
    return dict(available=True,expected=expected,actual=actual,matches=actual==expected,
                sample_bits=values[5],channels=values[6],configured_dma_destination=values[7],
                rate=values[8],dma_buffer_bytes=values[9],configured_dma_width=values[10])


def make_signal(path, sample_format, silent=False, higher=False):
    if sample_format not in ('S16_LE', 'S32_LE'):
        raise ValueError('unsupported probe format')
    raw = bytearray()
    peak = 0
    for n in range(FRAMES):
        fade = min(1, n / 2400, (FRAMES - 1 - n) / 2400)
        value = 0 if silent else int((0.24 if higher else 0.12) * 32767 * fade * math.sin(2 * math.pi * 440 * n / RATE))
        peak = max(peak, abs(value))
        # Same normalized waveform, with 16 valid bits left-aligned in S32.
        raw.extend(struct.pack('<hh', value, value) if sample_format == 'S16_LE'
                   else struct.pack('<ii', value << 16, value << 16))
    Path(path).write_bytes(raw)
    return dict(format=sample_format, frames=FRAMES, rate=RATE, channels=2,
                normalized_peak=peak / 32768, bytes=len(raw),
                sha256=hashlib.sha256(raw).hexdigest(), silent=silent)


def run_stage(path, sample_format, label, snapshot):
    """No plug layer; retain unsupported-format/EIO output and bounded cleanup."""
    started = time.monotonic()
    result = dict(label=label, format=sample_format, started_monotonic=started,
                  snapshots=[], timed_out=False)
    argv = ['aplay', '-D', 'hw:CARD=Codec,DEV=0', '-t', 'raw', '-f',
            sample_format, '-r', str(RATE), '-c', '2', str(path)]
    with tempfile.TemporaryFile() as output:
        player = subprocess.Popen(argv, stdout=output, stderr=subprocess.STDOUT)
        try:
            for offset in (1.5, 2.5):
                time.sleep(max(0, started + offset - time.monotonic()))
                poll = player.poll()
                result['snapshots'].append(dict(elapsed=time.monotonic()-started,
                    player_returncode=poll, board=snapshot()))
                if poll is not None and label != 'internal-sine':
                    break
            if label == 'internal-sine':
                # The oscillator can remain audible after the PCM writer fails.
                time.sleep(max(0, started + 4 - time.monotonic()))
            try:
                result['returncode'] = player.wait(timeout=max(0.1, started + 7 - time.monotonic()))
            except subprocess.TimeoutExpired:
                result['timed_out'] = True
                player.kill()
                result['returncode'] = player.wait()
        finally:
            if player.poll() is None:
                player.kill()
                player.wait()
            result['exit_observed_elapsed'] = time.monotonic() - started
            output.seek(0)
            result['aplay'] = output.read(8192).decode(errors='replace')
    result['state'] = 'complete' if result['returncode'] == 0 and not result['timed_out'] else 'failed'
    return result


def sequence(state, command, snapshot, save_progress, selected=None, announce=None, probe_buffer=False):
    """Three independent streams; never change source under an active player."""
    if selected not in (None,'file-s16','file-s32','internal-sine','file-s16-higher'):
        raise ValueError('unsupported tone')
    stages = []
    for label, fmt, source, gain in (
        ('file-s16', 'S16_LE', 'Normal', '58'),
        ('file-s32', 'S32_LE', 'Normal', '58'),
        ('file-s16-higher', 'S16_LE', 'Normal', '58'),
        ('internal-sine', 'S16_LE', 'Sine', '48'),
    ):
        if label == 'file-s16-higher' and selected != label:continue
        if selected is not None and selected != label:continue
        try:
            path = Path(state) / (label + '.raw')
            signal = make_signal(path, fmt, silent=source != 'Normal',
                                 higher=label == 'file-s16-higher')
            expected=buffer_summary(path.read_bytes()) if probe_buffer else None
            if announce:announce(label)
            for control, value in (('DAC Playback Volume', gain), ('DAC Diagnostic Source', source)):
                if not command(['amixer', '-c', 'Codec', 'cset', 'name='+control, value])['available']:
                    raise RuntimeError('stage-mixer-set-failed: '+control)
            if probe_buffer and not command(['amixer','-c','Codec','cset','name=DAC Buffer Probe','on'])['available']:
                raise RuntimeError('buffer-probe-arm-failed')
            stage = run_stage(path, fmt, label, snapshot)
            stage['signal'] = signal
            if probe_buffer:stage['buffer_evidence']=buffer_evidence(command,expected)
            stages.append(stage)
            save_progress(stages)
        finally:
            disarmed = not probe_buffer or command(['amixer','-c','Codec','cset','name=DAC Buffer Probe','off'])['available']
            # run_stage has reaped its player before this source change.
            reset = command(['amixer', '-c', 'Codec', 'cset', 'name=DAC Diagnostic Source', 'Normal'])
            if not reset['available']:
                raise RuntimeError('diagnostic-source-reset-failed')
            if not disarmed:raise RuntimeError('buffer-probe-disarm-failed')
        time.sleep(1)
    return stages
