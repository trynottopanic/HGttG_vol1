"""One admission check per open; the existing media service owns the decoder.

Device discovery is availability evidence only. mpv's observed hwdec-current
property remains the authority for whether decoding actually used hardware.
"""
from __future__ import annotations
import hashlib,json,os,platform,re,stat
from pathlib import Path

RUNTIME=Path('/usr/lib/guideos/media/cedrus-runtime')
REQUIRED_LIBRARIES={'lib/libavcodec.so.63','lib/libavformat.so.63','lib/libavutil.so.61',
                    'lib/libavfilter.so.12','lib/libswscale.so.10','lib/libswresample.so.7'}

def select_decoder(*, runtime=RUNTIME, sysfs=Path('/sys/class'), dev=Path('/dev'),
                   kernel_release=None, access=os.access):
    fallback=dict(executable='/usr/bin/mpv',hwdec='no',reason='runtime-unavailable')
    try:
        manifest=runtime/'manifest.json'
        if manifest.stat().st_size>65536:return fallback
        record=json.loads(manifest.read_text())
        if (not isinstance(record,dict) or record.get('schema')!=1 or record.get('hwdec')!='v4l2request-copy'
                or record.get('codecs')!=['h264']):return fallback
        if record.get('kernel_release')!=(kernel_release or platform.release()):
            return dict(fallback,reason='kernel-mismatch')
        files=record['files']
        if not isinstance(files,dict) or not 2<=len(files)<=64:return fallback
        if not ({'bin/mpv','bin/mpv-guide'}|REQUIRED_LIBRARIES).issubset(files):return fallback
        base=runtime.resolve(strict=True)
        verified={}
        for name,digest in files.items():
            if not isinstance(name,str) or not re.fullmatch(r'[A-Za-z0-9_./+-]{1,160}',name):return fallback
            relative=Path(name)
            if relative.is_absolute() or '..' in relative.parts:return fallback
            target=(base/relative).resolve(strict=True)
            if not target.is_relative_to(base) or not target.is_file():return fallback
            if not isinstance(digest,str) or not re.fullmatch(r'[0-9a-f]{64}',digest):return fallback
            if not access(target,os.R_OK):return fallback
            # SONAME aliases share one file. Hash each actual library once.
            if target not in verified:
                with target.open('rb') as stream:verified[target]=hashlib.file_digest(stream,'sha256').hexdigest()
            if verified[target]!=digest:return dict(fallback,reason='runtime-incomplete')
        if not all(access(base/'bin'/name,os.X_OK) for name in ('mpv','mpv-guide')):return fallback
    except (OSError,ValueError,KeyError,TypeError):return fallback

    # A video node alone might be a camera. Both nodes must belong to the
    # same Cedrus platform device and be usable by the unprivileged player.
    def devices(subsystem,prefix):
        result={}
        for entry in sorted((sysfs/subsystem).glob(prefix+'[0-9]*'))[:64]:
            if not re.fullmatch(prefix+r'[0-9]+',entry.name):continue
            try:
                parent=(entry/'device').resolve(strict=True)
                if (parent/'driver').resolve(strict=True).name!='cedrus':continue
                compatible=(parent/'of_node/compatible').read_bytes()
                if b'allwinner,sun50i-h616-video-engine' not in compatible.split(b'\x00'):continue
                node=dev/entry.name
                if not stat.S_ISCHR(node.stat().st_mode) or not access(node,os.R_OK|os.W_OK):continue
                result[parent]=str(node)
            except OSError:continue
        return result
    media=devices('media','media');video=devices('video4linux','video')
    shared=sorted(set(media)&set(video))
    if not shared:return dict(fallback,reason='cedrus-unavailable')
    return dict(executable=str(base/'bin/mpv-guide'),hwdec='v4l2request-copy',
                reason='cedrus-admitted')
