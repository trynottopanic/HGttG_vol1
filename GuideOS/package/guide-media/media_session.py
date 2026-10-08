#!/usr/bin/python3
"""Decoder-independent acknowledged Media Session 1 state machine."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import os
import secrets
from typing import Protocol

RESOLVING, ACQUIRING, OPENING, BUFFERING, PLAYING, PAUSED, SEEKING = range(1, 8)
RECONNECTING, UNAVAILABLE, FAILED, CHECKPOINTING, STOPPING, CLOSED = range(8, 14)

EVENT_STATE_CHANGED = 1
EVENT_POSITION_CHANGED = 2
EVENT_BUFFERING_CHANGED = 3
EVENT_TRACKS_CHANGED = 4
EVENT_SOURCE_LOST = 5
EVENT_OUTPUT_LOST = 6
EVENT_RESNAPSHOT_REQUIRED = 7

EVENT_LIMIT = 16
SESSION_LIMIT = 4


class SessionError(RuntimeError): pass
class SessionNotFound(SessionError): pass
class WrongOwner(SessionError): pass
class StaleSession(SessionError): pass
class InvalidTransition(SessionError): pass
class ResourceDenied(SessionError): pass


class Engine(Protocol):
    position_ms: int
    duration_ms: int | None
    def open(self, descriptor: int, position_ms: int) -> None: ...
    def play(self) -> None: ...
    def pause(self) -> None: ...
    def seek(self, position_ms: int) -> None: ...
    def select_audio(self, track_id: bytes) -> None: ...
    def select_subtitle(self, track_id: bytes | None) -> None: ...
    def set_output(self, output_id: bytes) -> None: ...
    def stop(self) -> None: ...


@dataclass
class Session:
    session_id: bytes
    owner_instance: str
    owner_generation: int
    media_id: bytes
    source_generation: int
    source_class: int
    engine: Engine
    lease: object
    state: int = OPENING
    revision: int = 1
    audio_track: bytes | None = None
    subtitle_track: bytes | None = None
    output_id: bytes | None = None
    failure_class: int | None = None
    events: deque = field(default_factory=lambda: deque(maxlen=EVENT_LIMIT))
    earliest_event_revision: int = 1


class MediaSessionManager:
    def __init__(self, source, engine_factory, admission, checkpoints,
                 *, session_limit=SESSION_LIMIT):
        if not 0 < session_limit <= 32:
            raise ValueError("invalid session limit")
        self.source = source
        self.engine_factory = engine_factory
        self.admission = admission
        self.checkpoints = checkpoints
        self.session_limit = session_limit
        self.sessions: dict[bytes, Session] = {}

    @staticmethod
    def _owner(context):
        return context.instance_id, context.generation

    def _new_id(self) -> bytes:
        value = secrets.token_bytes(16)
        while not any(value) or value in self.sessions:
            value = secrets.token_bytes(16)
        return value

    def _emit(self, session: Session, event: int, body: dict[int, object]) -> None:
        if len(session.events) == session.events.maxlen:
            session.earliest_event_revision = session.events[0][0] + 1
        session.events.append((session.revision, event, body))

    def _state(self, session: Session, state: int) -> None:
        session.state = state
        session.revision += 1
        self._emit(session, EVENT_STATE_CHANGED,
                   {0: session.session_id, 1: state, 2: session.revision})

    def _get(self, context, session_id: bytes) -> Session:
        if type(session_id) is not bytes or len(session_id) != 16:
            raise SessionNotFound("invalid session identity")
        session = self.sessions.get(session_id)
        if session is None:
            raise SessionNotFound("session is unavailable")
        if self._owner(context) != (session.owner_instance, session.owner_generation):
            raise WrongOwner("session belongs to another application instance")
        return session

    @staticmethod
    def _expect(session: Session, revision: int) -> None:
        if type(revision) is not int or revision != session.revision:
            raise StaleSession("state revision is stale")

    def open(self, context, media_id: bytes, source_generation: int,
             *, audio_track=None, subtitle_track=None, output_id=None,
             resume_position_ms=0) -> dict[int, object]:
        # Retain closed records for an immediate final snapshot, but evict the
        # oldest closed record when the next open needs its bounded slot.
        if len(self.sessions) >= self.session_limit:
            for identity, previous in list(self.sessions.items()):
                if previous.state == CLOSED:
                    del self.sessions[identity]
                    break
        if len(self.sessions) >= self.session_limit:
            raise ResourceDenied("session capacity exhausted")
        if type(resume_position_ms) is not int or resume_position_ms < 0:
            raise ValueError("invalid resume position")
        lease = self.admission.acquire(context, media_id, output_id)
        descriptor = None
        try:
            engine = self.engine_factory()
        except Exception:
            self.admission.release(lease)
            raise
        session = Session(self._new_id(), context.instance_id, context.generation,
                          media_id, source_generation, 1, engine, lease,
                          audio_track=audio_track, subtitle_track=subtitle_track,
                          output_id=output_id)
        self.sessions[session.session_id] = session
        try:
            descriptor = self.source.open_local(media_id, source_generation)
            engine.open(descriptor, resume_position_ms)
            if audio_track is not None:
                engine.select_audio(audio_track)
            if subtitle_track is not None:
                engine.select_subtitle(subtitle_track)
            if output_id is not None:
                engine.set_output(output_id)
            self._state(session, PAUSED)
            return {0: session.session_id, 1: session.state, 2: session.revision}
        except Exception:
            try: engine.stop()
            except Exception: pass
            self.admission.release(lease)
            self.sessions.pop(session.session_id, None)
            raise
        finally:
            if descriptor is not None:
                os.close(descriptor)

    def play(self, context, session_id, revision):
        session = self._get(context, session_id); self._expect(session, revision)
        if session.state not in (PAUSED, BUFFERING): raise InvalidTransition("play")
        ready = session.engine.play()
        self._state(session, BUFFERING if ready is False else PLAYING)
        return self._control_result(session)

    def refresh(self, context, session_id):
        """Translate an adapter buffer transition into acknowledged session state."""
        session = self._get(context, session_id)
        poll = getattr(session.engine, "poll", None)
        if poll is None or session.state not in (BUFFERING, PLAYING):
            return self._control_result(session)
        report = poll()
        if report.get("ended"):
            return self.stop(context, session_id)
        ready = bool(report.get("ready"))
        target = PLAYING if ready else BUFFERING
        if target != session.state:
            self._state(session, target)
        self._emit(session, EVENT_BUFFERING_CHANGED,
                   {0: session.session_id, 1: report.get("buffered_ms"),
                    2: session.revision})
        return self._control_result(session)

    def pause(self, context, session_id, revision):
        session = self._get(context, session_id); self._expect(session, revision)
        if session.state not in (PLAYING, BUFFERING, SEEKING): raise InvalidTransition("pause")
        session.engine.pause(); self._state(session, PAUSED)
        return self._control_result(session)

    def seek(self, context, session_id, revision, position_ms):
        session = self._get(context, session_id); self._expect(session, revision)
        if session.state not in (PLAYING, PAUSED): raise InvalidTransition("seek")
        if type(position_ms) is not int or position_ms < 0: raise ValueError("position")
        previous = session.state
        session.engine.seek(position_ms)
        self._state(session, previous)
        self._emit(session, EVENT_POSITION_CHANGED,
                   {0: session.session_id, 1: session.engine.position_ms,
                    2: session.revision})
        return self._control_result(session)

    @staticmethod
    def _active(session):
        if session.state in (STOPPING, CLOSED, FAILED, UNAVAILABLE):
            raise InvalidTransition("session is not active")

    def select_audio(self, context, session_id, revision, track_id):
        session = self._get(context, session_id); self._expect(session, revision)
        self._active(session)
        self._id(track_id); session.engine.select_audio(track_id)
        session.audio_track = track_id; session.revision += 1
        self._emit(session, EVENT_TRACKS_CHANGED,
                   {0: session.session_id, 1: session.revision})
        return self._control_result(session)

    def select_subtitle(self, context, session_id, revision, track_id):
        session = self._get(context, session_id); self._expect(session, revision)
        self._active(session)
        if track_id is not None: self._id(track_id)
        session.engine.select_subtitle(track_id); session.subtitle_track = track_id
        session.revision += 1
        self._emit(session, EVENT_TRACKS_CHANGED,
                   {0: session.session_id, 1: session.revision})
        return self._control_result(session)

    def set_output(self, context, session_id, revision, output_id):
        session = self._get(context, session_id); self._expect(session, revision)
        self._active(session)
        self._id(output_id); session.engine.set_output(output_id)
        session.output_id = output_id; session.revision += 1
        return self._control_result(session)

    def checkpoint(self, context, session_id, revision):
        session = self._get(context, session_id); self._expect(session, revision)
        self._active(session)
        self.checkpoints.save(session.owner_instance, session.media_id,
                              session.engine.position_ms, session.audio_track,
                              session.subtitle_track)
        session.revision += 1
        return self._control_result(session)

    def stop(self, context, session_id, revision=None):
        session = self._get(context, session_id)
        if session.state == CLOSED: return self._control_result(session)
        if revision is not None: self._expect(session, revision)
        self._state(session, STOPPING)
        try:
            session.engine.stop()
        finally:
            try:
                self.admission.release(session.lease)
            finally:
                self._state(session, CLOSED)
        return self._control_result(session)

    def snapshot(self, context, session_id):
        session = self._get(context, session_id)
        return {0: session.state, 1: session.revision,
                2: session.engine.position_ms, 3: session.engine.duration_ms,
                4: None, 5: session.audio_track, 6: session.subtitle_track,
                7: session.output_id, 8: session.source_class,
                9: session.failure_class}

    def events_after(self, context, session_id, revision):
        session = self._get(context, session_id)
        if revision < session.earliest_event_revision - 1:
            return [(session.revision, EVENT_RESNAPSHOT_REQUIRED,
                     {0: session.session_id, 1: session.revision})]
        return [item for item in session.events if item[0] > revision]

    def invalidate_owner(self, instance_id: str, generation: int) -> int:
        targets = [session for session in self.sessions.values()
                   if (session.owner_instance, session.owner_generation) ==
                      (instance_id, generation) and session.state != CLOSED]
        for session in targets:
            class Context: pass
            context = Context(); context.instance_id = instance_id; context.generation = generation
            try: self.stop(context, session.session_id)
            except Exception:
                # stop already releases exactly once, even when the engine fails.
                pass
        return len(targets)

    def invalidate_source(self, source_generation: int) -> int:
        """Stop pinned sources before their storage generation is unmounted."""
        targets = [session for session in self.sessions.values()
                   if session.source_generation == source_generation and
                   session.state != CLOSED]
        for session in targets:
            from types import SimpleNamespace
            context = SimpleNamespace(instance_id=session.owner_instance,
                                      generation=session.owner_generation)
            try:
                self.stop(context, session.session_id)
            except Exception:
                pass
        return len(targets)

    @staticmethod
    def _id(value):
        if type(value) is not bytes or len(value) != 16 or not any(value):
            raise ValueError("invalid opaque identity")

    @staticmethod
    def _control_result(session):
        return {0: session.state, 1: session.revision,
                2: session.engine.position_ms}
