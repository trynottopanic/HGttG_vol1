#!/usr/bin/python3
"""GStreamer audio-only adapter behind the Media Session engine protocol."""
from buffer_policy import BufferController, LOCAL_AUDIO, policy


class GStreamerAudioAdapter:
    def __init__(self, backend, *, policy_class=LOCAL_AUDIO):
        self.backend = backend
        self.buffer = BufferController(policy(policy_class))
        self.position_ms = 0; self.duration_ms = None
        self.requested_play = False; self.ready = False

    def open(self, descriptor, position_ms):
        self.backend.open_descriptor(descriptor, position_ms,
                                     max_buffer_bytes=self.buffer.policy.max_bytes)
        self.position_ms = position_ms
        self.duration_ms = self.backend.duration_ms()

    def poll(self):
        status = self.backend.status()
        self.position_ms = status["position_ms"]
        self.duration_ms = status.get("duration_ms", self.duration_ms)
        if status.get("ended"):
            self.ready=False
            return {"ready":False,"ended":True,"buffered_ms":0}
        self.ready = self.buffer.update(status["buffered_ms"],
                                        requested_play=self.requested_play,
                                        input_complete=status.get("input_complete",False))
        self.backend.set_presenting(self.ready)
        return {"ready": self.ready, "buffered_ms": status["buffered_ms"],
                "underruns": self.buffer.underruns}

    def play(self):
        self.requested_play = True
        return self.poll()["ready"]
    def pause(self): self.requested_play=False; self.backend.set_presenting(False)
    def seek(self, value):
        self.backend.seek(value); self.position_ms=value
        self.buffer = BufferController(self.buffer.policy)
        if self.requested_play: self.poll()
    def select_audio(self, value): raise ValueError("audio-only source has one selected stream")
    def select_subtitle(self, value): raise ValueError("audio-only source has no subtitles")
    def set_output(self, value): self.backend.set_output(value)
    def stop(self): self.requested_play=False; self.backend.stop()
