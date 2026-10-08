# SPDX-License-Identifier: AGPL-3.0-or-later
"""Cooperating range-transfer provider, driven by Guide's existing C policy.

This moves bounded payload bytes; it is not a kernel bandwidth shaper, media
decoder, capability broker or automatic link-capacity estimator. Sources and
destinations are selected by the trusted caller. No redirects or proxy discovery.
"""
from dataclasses import dataclass
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import subprocess
import threading
import time
from urllib.parse import urlsplit


def sync_directory(path):
    """Commit newly created/renamed entries on the Linux target filesystem."""
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


@dataclass(frozen=True)
class Source:
    url: str
    size: int
    sha256: str

    def validate(self):
        parsed = urlsplit(self.url)
        if (parsed.scheme not in ("http", "https") or not parsed.hostname
                or parsed.username or parsed.password or parsed.fragment
                or type(self.size) is not int or self.size <= 0
                or not re.fullmatch(r"[0-9a-f]{64}", self.sha256)):
            raise ValueError("explicit HTTP(S) source, positive size and SHA-256 required")


@dataclass(frozen=True)
class TransferAgreement:
    revision: int
    interval_seconds: float
    stream_ceiling: int
    stream_floor: int
    download_ceiling: int
    download_floor: int
    weights: tuple[int, int, int, int]

    def validate(self):
        if type(self.revision) is not int or self.revision <= 0:
            raise ValueError("positive agreement revision required")
        if not 0 < self.interval_seconds <= 60:
            raise ValueError("invalid accounting interval")
        for ceiling, floor in ((self.stream_ceiling, self.stream_floor),
                               (self.download_ceiling, self.download_floor)):
            if (type(ceiling) is not int or type(floor) is not int
                    or not 0 < floor <= ceiling < 2**63):
                raise ValueError("invalid installed transfer limits")
        if (len(self.weights) != 4 or any(type(w) is not int for w in self.weights)
                or not 10000 >= self.weights[0] > self.weights[1] > self.weights[2] > self.weights[3] > 0):
            raise ValueError("four descending tier weights required")


class RangeTransfer:
    """One worker, one bounded request in flight, no unbounded byte queue.

    Allowances never accumulate. A new grant replaces unused credit. Requests
    already in flight can finish after a grant changes; pause is acknowledged
    only once they have closed and their data is durably recorded.
    """
    def __init__(self, source: Source, destination: Path, *, chunk_bytes: int,
                 request_timeout: float):
        source.validate()
        if not 0 < chunk_bytes <= 1024 * 1024 or not 0 < request_timeout <= 60:
            raise ValueError("bounded chunk and request timeout required")
        self.source, self.destination = source, Path(destination)
        self.chunk_bytes, self.request_timeout = chunk_bytes, request_timeout
        self.part = self.destination.with_name(self.destination.name + ".part")
        self.metadata = self.destination.with_name(self.destination.name + ".source.json")
        self.destination.parent.mkdir(parents=True, exist_ok=True)
        completed = self.destination.exists()
        descriptor = {"size": source.size, "sha256": source.sha256}
        # Content identity, not a possibly temporary ticket URL, binds recovery.
        if self.part.exists() and not completed:
            if json.loads(self.metadata.read_text()) != descriptor:
                raise ValueError("partial transfer belongs to different content")
        else:
            with self.metadata.open("w", encoding="utf-8") as record:
                json.dump(descriptor, record)
                record.flush()
                os.fsync(record.fileno())
            sync_directory(self.metadata.parent)
        existing = self.destination if completed else self.part
        self.offset = existing.stat().st_size if existing.exists() else 0
        if self.offset > source.size:
            raise ValueError("partial transfer exceeds declared content size")
        self._digest = hashlib.sha256()
        if existing.exists():
            with existing.open("rb") as previous:
                while block := previous.read(chunk_bytes):
                    self._digest.update(block)
        if completed and (self.offset != source.size or self._digest.hexdigest() != source.sha256):
            raise ValueError("existing destination is not the expected completed content")
        self._condition = threading.Condition()
        self._credits = 0
        self._expires = 0.0
        self._generation = 0
        self._paused = True
        self._busy = False
        self._closing = False
        self._state = "complete" if completed else "paused"
        self._error = ""
        self._thread = threading.Thread(target=self._work, name="guide-range-transfer", daemon=True)
        if not completed:
            self._thread.start()

    def grant(self, amount: int, *, valid_until: float):
        if type(amount) is not int or amount < 0 or not time.monotonic() < valid_until < float("inf"):
            raise ValueError("nonnegative allowance with future expiry required")
        with self._condition:
            self._generation += 1
            self._credits, self._expires = amount, valid_until
            self._paused = amount == 0
            if self._state not in ("complete", "failed", "stopped"):
                self._state = "pausing" if self._paused and self._busy else (
                    "paused" if self._paused else "running")
            self._condition.notify_all()

    def snapshot(self):
        with self._condition:
            return {"state": self._state, "bytes": self.offset,
                    "in_flight": self._busy, "generation": self._generation,
                    "error": self._error}

    def close(self):
        with self._condition:
            self._closing = True
            self._condition.notify_all()
        if self._thread.ident is None:
            return
        self._thread.join(self.request_timeout + 1)
        if self._thread.is_alive():
            raise TimeoutError("transfer worker still stopping; no stop acknowledgement")

    def _fetch(self, start, length):
        parsed = urlsplit(self.source.url)
        kind = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
        connection = kind(parsed.hostname, parsed.port, timeout=self.request_timeout)
        deadline = time.monotonic() + self.request_timeout
        target = parsed.path or "/"
        if parsed.query:
            target += "?" + parsed.query
        try:
            connection.request("GET", target, headers={
                "Range": f"bytes={start}-{start + length - 1}",
                "Accept-Encoding": "identity", "Connection": "close"})
            response = connection.getresponse()
            if (response.status != 206 or response.getheader("Content-Range") !=
                    f"bytes {start}-{start + length - 1}/{self.source.size}"
                    or response.getheader("Content-Length") != str(length)
                    or response.getheader("Content-Encoding", "identity") != "identity"):
                raise ValueError("source did not honor the exact range")
            output = bytearray()
            while len(output) < length:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("range request deadline exceeded")
                if connection.sock:
                    connection.sock.settimeout(remaining)
                block = response.read1(min(65536, length - len(output)))
                if not block:
                    raise ValueError("source ended before the range completed")
                output.extend(block)
            return output
        finally:
            connection.close()

    def _work(self):
        try:
            with self.part.open("ab") as output:
                sync_directory(self.part.parent)
                while True:
                    with self._condition:
                        if self._closing:
                            self._state = "stopped"
                            return
                        if self.offset == self.source.size:
                            break
                        if self._credits == 0 or time.monotonic() >= self._expires:
                            self._state = "paused" if self._paused else "waiting"
                            self._condition.wait(0.1)
                            continue
                        length = min(self.chunk_bytes, self._credits, self.source.size - self.offset)
                        start = self.offset
                        self._credits -= length
                        self._busy = True
                    block = self._fetch(start, length)
                    output.write(block)
                    output.flush()
                    os.fsync(output.fileno())
                    with self._condition:
                        self._digest.update(block)
                        self.offset += len(block)
                        self._busy = False
                        self._state = "paused" if self._paused else "running"
            if self._digest.hexdigest() != self.source.sha256:
                raise ValueError("completed content checksum mismatch; partial file retained")
            os.replace(self.part, self.destination)
            sync_directory(self.destination.parent)
            with self._condition:
                self._state = "complete"
        except Exception as error:
            with self._condition:
                self._busy = False
                self._state = "failed"
                # Error class only: URLs may contain private ticket credentials.
                self._error = type(error).__name__


class TransferScheduler:
    def __init__(self, planner: Path, agreement: TransferAgreement,
                 stream: RangeTransfer, download: RangeTransfer):
        agreement.validate()
        self.planner, self.agreement = str(planner), agreement
        self.stream, self.download = stream, download
        self._next = 0.0

    def tick(self, capacity_bytes: int, *, reserve_bytes=0):
        if any(type(v) is not int or not 0 <= v < 2**63 for v in (capacity_bytes, reserve_bytes)):
            raise ValueError("capacity and reserve must be nonnegative integer bytes")
        now = time.monotonic()
        if now < self._next:
            raise ValueError("accounting interval has not elapsed")
        a = self.agreement
        self._next = now + a.interval_seconds
        observations = [t.snapshot() for t in (self.stream, self.download)]
        demands = [0 if s["state"] in ("complete", "failed", "stopped") else ceiling
                   for s, ceiling in zip(observations, (a.stream_ceiling, a.download_ceiling))]
        values = (capacity_bytes, reserve_bytes, demands[0], a.stream_ceiling,
                  a.stream_floor, demands[1], a.download_ceiling, a.download_floor, *a.weights)
        result = subprocess.run([self.planner, *map(str, values)], capture_output=True,
                                text=True, timeout=min(a.interval_seconds, 5), check=False)
        plan = json.loads(result.stdout)
        if result.returncode not in (0, 1) or plan.get("status") not in ("ok", "shortfall"):
            raise RuntimeError("planner rejected the installed profile")
        # No catch-up burst if planning missed its interval.
        expiry = self._next
        if expiry <= time.monotonic():
            raise TimeoutError("planning missed the accounting interval")
        allocations = (plan["stream"], plan["download"]) if plan["status"] == "ok" else (0, 0)
        for transfer, amount in zip((self.stream, self.download), allocations):
            transfer.grant(amount, valid_until=expiry)
        return {"agreement_revision": a.revision, "capacity_bytes": capacity_bytes,
                "plan": plan, "stream": self.stream.snapshot(), "download": self.download.snapshot()}
