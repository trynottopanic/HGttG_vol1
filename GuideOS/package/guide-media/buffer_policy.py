#!/usr/bin/python3
"""Shared bounded prebuffer policy for Guide media engine adapters."""
from dataclasses import dataclass

LOCAL_AUDIO, LOCAL_VIDEO, NODE_MEDIA, ONLINE_MEDIA = range(1, 5)


@dataclass(frozen=True)
class BufferPolicy:
    start_ms: int
    low_ms: int
    resume_ms: int
    max_bytes: int


POLICIES = {
    LOCAL_AUDIO: BufferPolicy(750, 250, 750, 2 * 1024 * 1024),
    LOCAL_VIDEO: BufferPolicy(2000, 750, 2000, 16 * 1024 * 1024),
    NODE_MEDIA: BufferPolicy(5000, 2000, 5000, 24 * 1024 * 1024),
    ONLINE_MEDIA: BufferPolicy(8000, 3000, 8000, 32 * 1024 * 1024),
}


class BufferController:
    def __init__(self, policy: BufferPolicy):
        self.policy = policy
        self.started = False
        self.buffering = True
        self.underruns = 0

    def update(self, buffered_ms: int, *, requested_play: bool, input_complete: bool = False) -> bool:
        if type(buffered_ms) is not int or buffered_ms < 0:
            raise ValueError("invalid buffered duration")
        if not requested_play:
            self.buffering = True
            return False
        # End of a finite input cannot fill a larger high-water target. Drain
        # the remainder at normal speed rather than buffering indefinitely.
        if input_complete:
            self.buffering = False; self.started = True
            return True
        threshold = self.policy.resume_ms if self.started else self.policy.start_ms
        if self.buffering:
            if buffered_ms >= threshold:
                self.buffering = False; self.started = True
        elif buffered_ms < self.policy.low_ms:
            self.buffering = True; self.underruns += 1
        return not self.buffering


def policy(kind: int) -> BufferPolicy:
    try: return POLICIES[kind]
    except KeyError as exc: raise ValueError("unknown media buffer class") from exc
