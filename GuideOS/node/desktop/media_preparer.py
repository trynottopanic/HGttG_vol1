"""Prepare conservative, cached video copies for the first GuideOS Deck."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import queue
import glob
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import replace
from typing import Callable
from urllib.parse import quote

from media_library import MediaRecord


TARGET_WIDTH = 640
TARGET_HEIGHT = 360
VIDEO_BITRATE_KBPS = 1200
AUDIO_BITRATE_KBPS = 128
CONVERSION_REVISION = "deck-video-640x360-v5-audio-tracks"
TEXT_SUBTITLE_CODECS = {
    "ass", "ssa", "subrip", "srt", "text", "mov_text", "webvtt", "microdvd",
}
_ENCODER_LOCK = threading.Lock()
_ENCODER_CACHE: dict[str, str | None] = {}


def _winget_program(name: str) -> str | None:
    """Find a WinGet-installed FFmpeg even before this process sees PATH changes."""
    found = shutil.which(name)
    if found:
        return found
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        return None
    links = Path(local) / "Microsoft" / "WinGet" / "Links" / f"{name}.exe"
    if links.is_file():
        return str(links)
    pattern = str(Path(local) / "Microsoft" / "WinGet" / "Packages" /
                  "Gyan.FFmpeg_*" / "ffmpeg-*" / "bin" / f"{name}.exe")
    matches = sorted(glob.glob(pattern), reverse=True)
    return matches[0] if matches else None


def _subtitle_tracks(path: Path) -> tuple[str, ...]:
    ffprobe = _winget_program("ffprobe")
    if not ffprobe:
        return ()
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    try:
        result = subprocess.run(
            [ffprobe, "-v", "error", "-select_streams", "s", "-show_entries",
             "stream=index:stream_tags=language,title", "-of", "json", str(path)],
            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30,
            creationflags=flags, check=False,
        )
        payload = json.loads(result.stdout) if result.returncode == 0 else {}
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return ()
    tracks = []
    for number, stream in enumerate(payload.get("streams", [])):
        tags = stream.get("tags", {}) if isinstance(stream, dict) else {}
        language = str(tags.get("language", "")).strip().upper()
        title = str(tags.get("title", "")).strip()
        label = title or language or f"TRACK {number + 1}"
        tracks.append(" ".join(label.split())[:32])
    return tuple(tracks[:8])


def default_cache_path() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / "GuideNode" / "media-cache"
    return Path.home() / ".guide-node" / "media-cache"


def _file_uri(path: Path) -> str:
    return "file:///" + quote(path.resolve().as_posix(), safe="/:[]()'")


def _hardware_encoders(ffmpeg: str) -> tuple[str, ...]:
    """Prefer a remembered winner, otherwise try common Windows encoders in order."""
    with _ENCODER_LOCK:
        if ffmpeg in _ENCODER_CACHE:
            winner = _ENCODER_CACHE[ffmpeg]
            return (winner,) if winner else ()
    return ("h264_amf", "h264_nvenc", "h264_qsv") if sys.platform == "win32" else ()


class DeckMediaPreparer:
    """One bounded worker that never alters an owner's original media."""

    def __init__(self, cache_path: Path | None = None,
                 backend: Callable[[Path, Path], tuple[bool, str]] | None = None) -> None:
        self.cache_path = cache_path or default_cache_path()
        self._backend = backend
        self._lock = threading.RLock()
        self._states: dict[str, tuple[str, str]] = {}
        self._outputs: dict[str, Path] = {}
        self._subtitles: dict[str, tuple[str, ...]] = {}
        self._keys: dict[str, str] = {}
        self._queue: queue.Queue[MediaRecord | None] = queue.Queue(maxsize=10_000)
        self._stop = threading.Event()
        self._process: subprocess.Popen | None = None
        self._subtitle_lock = threading.Lock()
        self._active_id = ""
        self._thread = threading.Thread(target=self._work, name="guide-media-preparer", daemon=True)
        self._thread.start()

    @staticmethod
    def _key(record: MediaRecord) -> str:
        identity = (str(record.path.resolve()) + "\0" + str(record.size) + "\0" +
                    str(record.modified_ns) + "\0" + CONVERSION_REVISION).encode("utf-8")
        return hashlib.sha256(identity).hexdigest()

    def synchronize(self, records: list[MediaRecord]) -> None:
        current = {record.media_id for record in records if record.kind == "video"}
        cancel = None
        with self._lock:
            for media_id in list(self._states):
                if media_id not in current:
                    self._states.pop(media_id, None)
                    self._outputs.pop(media_id, None)
                    self._subtitles.pop(media_id, None)
                    self._keys.pop(media_id, None)
            for record in records:
                if record.kind != "video":
                    continue
                key = self._key(record)
                output = self.cache_path / (key + ".mp4")
                if output.is_file() and output.stat().st_size > 1024:
                    self._states[record.media_id] = ("ready", "")
                    self._outputs[record.media_id] = output
                    self._subtitles[record.media_id] = _subtitle_tracks(output)
                    self._keys[record.media_id] = key
                elif (self._keys.get(record.media_id) != key or
                      record.media_id not in self._states or
                      self._states[record.media_id][0] == "error"):
                    self._states[record.media_id] = ("queued", "")
                    self._keys[record.media_id] = key
                    self._queue.put_nowait(record)
            if self._active_id and self._active_id not in current:
                cancel = self._process
        if cancel and cancel.poll() is None:
            cancel.terminate()

    def prepared(self, record: MediaRecord) -> MediaRecord | None:
        if record.kind != "video":
            return record
        with self._lock:
            state = self._states.get(record.media_id, ("queued", ""))[0]
            output = self._outputs.get(record.media_id)
            subtitles = self._subtitles.get(record.media_id, ())
        if state != "ready" or output is None:
            return None
        try:
            information = output.stat()
            if not output.is_file() or information.st_size <= 1024:
                return None
        except OSError:
            return None
        return replace(record, path=output, content_type="video/mp4",
                       size=information.st_size, modified_ns=information.st_mtime_ns,
                       subtitle_tracks=subtitles)

    def subtitle(self, record: MediaRecord, track: int) -> MediaRecord | None:
        """Materialize one small text subtitle beside the prepared video."""
        prepared = self.prepared(record)
        if (prepared is None or track < 0 or track >= len(prepared.subtitle_tracks) or
                prepared.path.parent != self.cache_path):
            return None
        output = prepared.path.with_name(prepared.path.name + f".subtitle-{track}.srt")
        with self._subtitle_lock:
            try:
                if not output.is_file() or output.stat().st_size == 0:
                    ffmpeg = _winget_program("ffmpeg")
                    if not ffmpeg:
                        return None
                    temporary = output.with_suffix(output.suffix + ".partial")
                    temporary.unlink(missing_ok=True)
                    flags = ((getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) |
                              getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0x00004000))
                             if sys.platform == "win32" else 0)
                    result = subprocess.run(
                        [ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                         "-i", str(prepared.path), "-map", f"0:s:{track}", "-c:s", "srt",
                         "-f", "srt", str(temporary)],
                        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL, timeout=120, creationflags=flags,
                        check=False)
                    if result.returncode != 0 or not temporary.is_file() or temporary.stat().st_size == 0:
                        temporary.unlink(missing_ok=True)
                        return None
                    os.replace(temporary, output)
                information = output.stat()
            except (OSError, subprocess.TimeoutExpired):
                return None
        return replace(prepared, path=output,
                       name=f"{prepared.name} - {prepared.subtitle_tracks[track]}.srt",
                       kind="subtitle", content_type="application/x-subrip",
                       size=information.st_size, modified_ns=information.st_mtime_ns,
                       subtitle_tracks=())

    def summary(self) -> dict[str, object]:
        with self._lock:
            counts = {name: 0 for name in ("queued", "preparing", "ready", "error")}
            errors = []
            for state, detail in self._states.values():
                counts[state] = counts.get(state, 0) + 1
                if state == "error" and detail:
                    errors.append(detail)
        return {**counts, "last_error": errors[-1] if errors else ""}

    def wait_for_idle(self, timeout: float = 5.0) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            summary = self.summary()
            if not summary["queued"] and not summary["preparing"]:
                return True
            time.sleep(0.02)
        return False

    def close(self) -> None:
        self._stop.set()
        try:
            self._queue.put_nowait(None)
        except queue.Full:
            pass
        with self._lock:
            process = self._process
        if process and process.poll() is None:
            process.terminate()
        self._thread.join(timeout=3)

    def _work(self) -> None:
        while not self._stop.is_set():
            try:
                record = self._queue.get(timeout=0.25)
            except queue.Empty:
                continue
            if record is None:
                return
            with self._lock:
                if self._states.get(record.media_id, ("", ""))[0] != "queued":
                    continue
                self._states[record.media_id] = ("preparing", "")
                self._active_id = record.media_id
            output = self.cache_path / (self._key(record) + ".mp4")
            temporary = output.with_suffix(".part.mp4")
            try:
                self.cache_path.mkdir(parents=True, exist_ok=True)
                temporary.unlink(missing_ok=True)
                okay, detail = (self._backend or self._convert)(record.path, temporary)
                if not okay or not temporary.is_file() or temporary.stat().st_size <= 1024:
                    raise OSError(detail or "The video converter did not produce a usable file")
                if self._backend is None:
                    okay, detail = self._validate_output(temporary)
                    if not okay:
                        raise OSError(detail)
                os.replace(temporary, output)
                with self._lock:
                    if self._keys.get(record.media_id) == self._key(record):
                        self._outputs[record.media_id] = output
                        self._subtitles[record.media_id] = _subtitle_tracks(output)
                        self._states[record.media_id] = ("ready", "")
            except OSError as error:
                temporary.unlink(missing_ok=True)
                self._write_error_report(record, error)
                with self._lock:
                    message = " ".join(str(error).split())
                    self._states[record.media_id] = (
                        "error", f"{record.name}: {message}"[:300])
            finally:
                with self._lock:
                    self._active_id = ""

    def _write_error_report(self, record: MediaRecord, error: OSError) -> None:
        """Keep one useful local report without exposing paths to a Deck."""
        try:
            report = self.cache_path / "last-conversion-error.txt"
            temporary = report.with_suffix(".new")
            temporary.write_text(
                f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"File: {record.path}\n"
                f"Reason: {' '.join(str(error).split())}\n",
                encoding="utf-8",
            )
            os.replace(temporary, report)
        except OSError:
            pass

    @staticmethod
    def _probe(path: Path) -> dict[str, object] | None:
        ffprobe = _winget_program("ffprobe")
        if not ffprobe:
            return None
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        try:
            result = subprocess.run(
                [ffprobe, "-v", "error", "-show_entries",
                 "stream=index,codec_type,codec_name,width,height,pix_fmt:"
                 "stream_disposition=attached_pic:"
                 "stream_tags=language,title:"
                 "format=duration", "-of", "json", str(path)],
                stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60,
                creationflags=flags, check=False,
            )
            value = json.loads(result.stdout) if result.returncode == 0 else None
            return value if isinstance(value, dict) else None
        except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
            return None

    @staticmethod
    def _stream_index(streams: list[object], kind: str) -> int | None:
        for value in streams:
            if not isinstance(value, dict) or value.get("codec_type") != kind:
                continue
            disposition = value.get("disposition", {})
            if kind == "video" and isinstance(disposition, dict) and disposition.get("attached_pic"):
                continue
            index = value.get("index")
            if isinstance(index, int):
                return index
        return None

    @staticmethod
    def _error_tail(value: str, fallback: str) -> str:
        lines = [" ".join(line.split()) for line in value.splitlines() if line.strip()]
        return (lines[-1] if lines else fallback)[:260]

    def _run_converter(self, arguments: list[str]) -> tuple[bool, str]:
        flags = 0
        if sys.platform == "win32":
            flags = (getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) |
                     getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0x00004000))
        try:
            with self._lock:
                self._process = subprocess.Popen(
                    arguments, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE, text=True, errors="replace", creationflags=flags)
                process = self._process
            _, errors = process.communicate()
            return process.returncode == 0, self._error_tail(errors or "", "Video conversion failed")
        except OSError as error:
            return False, str(error)
        finally:
            with self._lock:
                self._process = None

    def _ffmpeg_arguments(self, ffmpeg: str, source: Path, destination: Path,
                          probe: dict[str, object] | None, subtitles: bool,
                          tolerant: bool = False, encoder: str = "libx264") -> list[str]:
        streams = probe.get("streams", []) if isinstance(probe, dict) else []
        streams = streams if isinstance(streams, list) else []
        video_index = self._stream_index(streams, "video")
        audio_index = self._stream_index(streams, "audio")
        audio_indices=[s['index'] for s in streams if isinstance(s,dict) and
                       s.get('codec_type')=='audio' and type(s.get('index')) is int][:8]
        subtitle_indices = []
        if subtitles:
            for value in streams:
                if (isinstance(value, dict) and value.get("codec_type") == "subtitle" and
                        value.get("codec_name") in TEXT_SUBTITLE_CODECS and
                        isinstance(value.get("index"), int)):
                    subtitle_indices.append(int(value["index"]))
        before_input = [ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                        "-fflags", "+genpts+discardcorrupt"]
        if tolerant:
            before_input += ["-err_detect", "ignore_err"]
        if subtitle_indices:
            before_input += ["-fix_sub_duration"]
        arguments = before_input + ["-i", str(source)]
        silent_audio = audio_index is None and bool(streams)
        if silent_audio:
            arguments += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
        arguments += ["-map", f"0:{video_index}" if video_index is not None else "0:v:0"]
        if silent_audio:
            arguments += ["-map", "1:a:0", "-shortest"]
        elif audio_index is not None:
            for index in audio_indices:arguments += ["-map", f"0:{index}"]
        else:
            arguments += ["-map", "0:a:0?"]
        for index in subtitle_indices[:8]:
            arguments += ["-map", f"0:{index}"]
        for output_index,index in enumerate(audio_indices):
            source_track=next(s for s in streams if isinstance(s,dict) and s.get('index')==index)
            tags=source_track.get('tags',{})
            if isinstance(tags,dict):
                for tag in ('language','title'):
                    value=tags.get(tag)
                    if isinstance(value,str):
                        arguments += [f'-metadata:s:a:{output_index}',f'{tag}={value[:128]}']
            arguments += [f'-disposition:a:{output_index}','default' if output_index==0 else '0']
        pixel_format = "nv12" if encoder != "libx264" else "yuv420p"
        arguments += [
            "-vf", "scale=640:360:force_original_aspect_ratio=decrease:"
                   "force_divisible_by=2,pad=640:360:(ow-iw)/2:(oh-ih)/2,"
                   f"setsar=1,fps=30,format={pixel_format}",
            "-c:v", encoder,
        ]
        if encoder == "h264_amf":
            arguments += ["-usage", "transcoding", "-quality", "speed", "-rc", "cbr"]
        elif encoder == "h264_nvenc":
            arguments += ["-preset", "p2", "-tune", "ll"]
        elif encoder == "h264_qsv":
            arguments += ["-preset", "veryfast"]
        else:
            cpu_threads = min(8, max(2, (os.cpu_count() or 4) // 2))
            arguments += ["-preset", "veryfast", "-threads", str(cpu_threads)]
        arguments += [
            "-pix_fmt", "yuv420p", "-profile:v", "main", "-level:v", "3.1",
            "-filter_threads", "2", "-b:v", f"{VIDEO_BITRATE_KBPS}k",
            "-maxrate", "1600k", "-bufsize", "3200k", "-g", "60",
            "-c:a", "aac", "-b:a", f"{AUDIO_BITRATE_KBPS}k", "-ac", "2",
            "-ar", "48000", "-af", "aresample=48000:async=1:first_pts=0",
        ]
        if subtitle_indices:
            arguments += ["-c:s", "mov_text"]
        arguments += ["-map_metadata", "-1", "-map_chapters", "-1",
                      "-max_muxing_queue_size", "4096", "-avoid_negative_ts", "make_zero",
                      "-movflags", "+faststart", str(destination)]
        return arguments

    def _validate_output(self, path: Path) -> tuple[bool, str]:
        value = self._probe(path)
        if value is None:
            return True, ""
        streams = value.get("streams", [])
        if not isinstance(streams, list):
            return False, "Converted file could not be inspected"
        video = next((item for item in streams if isinstance(item, dict) and
                      item.get("codec_type") == "video"), None)
        audio = next((item for item in streams if isinstance(item, dict) and
                      item.get("codec_type") == "audio"), None)
        if not video or video.get("codec_name") != "h264":
            return False, "Converted file does not contain compatible H.264 video"
        width, height = video.get("width"), video.get("height")
        if ((isinstance(width, int) and width > TARGET_WIDTH) or
                (isinstance(height, int) and height > TARGET_HEIGHT) or
                video.get("pix_fmt") not in (None, "yuv420p")):
            return False, "Converted video does not meet the Deck display profile"
        if not audio or audio.get("codec_name") != "aac":
            return False, "Converted file does not contain compatible AAC audio"
        return True, ""

    def _convert(self, source: Path, destination: Path) -> tuple[bool, str]:
        ffmpeg = _winget_program("ffmpeg")
        if ffmpeg:
            probe = self._probe(source)
            if probe is not None:
                streams = probe.get("streams", [])
                if (not isinstance(streams, list) or
                        self._stream_index(streams, "video") is None):
                    return False, "No playable video stream was found"
            hardware = _hardware_encoders(ffmpeg)
            encoders = (*hardware, "libx264")
            errors = []
            for encoder in encoders:
                for subtitles, tolerant in ((True, False), (False, True)):
                    arguments = self._ffmpeg_arguments(
                        ffmpeg, source, destination, probe, subtitles, tolerant,
                        encoder=encoder)
                    destination.unlink(missing_ok=True)
                    okay, detail = self._run_converter(arguments)
                    if okay:
                        if encoder != "libx264":
                            with _ENCODER_LOCK:
                                _ENCODER_CACHE[ffmpeg] = encoder
                        elif hardware:
                            with _ENCODER_LOCK:
                                _ENCODER_CACHE[ffmpeg] = None
                        return True, ""
                    errors.append(detail)
            if len(errors) > 1:
                return False, f"Primary: {errors[0]}; safe retry: {errors[-1]}"[:300]
            return False, errors[-1] if errors else "Video conversion failed"
        else:
            program_files = Path(os.environ.get("ProgramFiles", "C:/Program Files"))
            vlc = shutil.which("vlc") or str(program_files / "VideoLAN" / "VLC" / "vlc.exe")
            if not Path(vlc).is_file():
                return False, "Install VLC or FFmpeg to prepare videos for the Deck"
            transcode = (
                f"#transcode{{vcodec=h264,vb={VIDEO_BITRATE_KBPS},width={TARGET_WIDTH},"
                f"height={TARGET_HEIGHT},acodec=mp4a,ab={AUDIO_BITRATE_KBPS},channels=2,"
                "samplerate=48000}:std{access=file,mux=mp4,dst='" +
                str(destination).replace("'", "\\'") + "'}"
            )
            arguments = [vlc, "-I", "dummy", "--dummy-quiet", _file_uri(source),
                         "--sout", transcode, "vlc://quit"]
        return self._run_converter(arguments)
