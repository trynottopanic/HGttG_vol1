"""Validation and bounded deterministic work for Semiotic Engine Protocol 0."""

from __future__ import annotations

import re
import secrets
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from queue import Empty, Queue


PROTOCOL = "guide-se/0"
MAX_TEXT_CHARS = 32_000
MAX_INSTRUCTION_CHARS = 1_000
MAX_OUTPUT_CHARS = 4_000
MAX_JOBS = 16
JOB_TTL_SECONDS = 15 * 60
REQUEST_KEYS = {"protocol", "request_id", "task", "context", "limits", "policy"}


class RequestProblem(ValueError):
    pass


class BackendProblem(RuntimeError):
    pass


def _exact_keys(value: object, keys: set[str], label: str) -> dict:
    if not isinstance(value, dict) or set(value) != keys:
        raise RequestProblem(f"{label} has missing or unknown fields")
    return value


def validate_request(value: object) -> dict:
    request = _exact_keys(value, REQUEST_KEYS, "request")
    if request["protocol"] != PROTOCOL:
        raise RequestProblem("unsupported protocol")
    request_id = request["request_id"]
    if not isinstance(request_id, str) or not re.fullmatch(r"[0-9a-f]{32}", request_id):
        raise RequestProblem("request_id must be 32 lowercase hexadecimal characters")

    task = _exact_keys(request["task"], {"kind", "instruction", "output_format"}, "task")
    if task["kind"] != "text.summarize" or task["output_format"] != "guide-summary/0":
        raise RequestProblem("unsupported task or output format")
    instruction = task["instruction"]
    if not isinstance(instruction, str) or not 1 <= len(instruction) <= MAX_INSTRUCTION_CHARS:
        raise RequestProblem("instruction length is outside the supported range")

    context = request["context"]
    if not isinstance(context, list) or len(context) != 1:
        raise RequestProblem("Protocol 0 requires exactly one context item")
    item = _exact_keys(context[0], {"id", "media_type", "content", "source"}, "context item")
    if not isinstance(item["id"], str) or not re.fullmatch(r"[A-Za-z0-9._:-]{1,64}", item["id"]):
        raise RequestProblem("context id is invalid")
    if item["media_type"] != "text/plain":
        raise RequestProblem("Protocol 0 accepts plain text only")
    if not isinstance(item["content"], str) or not 1 <= len(item["content"]) <= MAX_TEXT_CHARS:
        raise RequestProblem("context text length is outside the supported range")
    source = _exact_keys(item["source"], {"label"}, "source")
    if not isinstance(source["label"], str) or not 1 <= len(source["label"]) <= 120:
        raise RequestProblem("source label is invalid")

    limits = _exact_keys(request["limits"], {"deadline_ms", "max_output_chars", "retention"}, "limits")
    if type(limits["deadline_ms"]) is not int or not 1 <= limits["deadline_ms"] <= 300_000:
        raise RequestProblem("deadline_ms is outside the supported range")
    if type(limits["max_output_chars"]) is not int or not 1 <= limits["max_output_chars"] <= MAX_OUTPUT_CHARS:
        raise RequestProblem("max_output_chars is outside the supported range")
    if limits["retention"] != "none":
        raise RequestProblem("Protocol 0 permits no durable request retention")

    policy = _exact_keys(request["policy"], {"tools", "network", "additional_context"}, "policy")
    if any(policy[name] is not False for name in policy):
        raise RequestProblem("Protocol 0 provides no tools, network, or additional context")
    return request


def summarize(text: str, limit: int) -> str:
    """Return a predictable extractive summary without pretending to be a model."""
    normalized = " ".join(text.split())
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", normalized) if part.strip()]
    selected = " ".join(sentences[:3]) if sentences else normalized
    if len(selected) <= limit:
        return selected
    if limit <= 1:
        return selected[:limit]
    cut = selected[: limit - 1].rsplit(" ", 1)[0]
    return (cut or selected[: limit - 1]) + "…"


class EngineBackend:
    """Replaceable computation behind the stable Semiotic Engine boundary."""

    implementation = "unknown"
    capabilities = ("text.summarize",)

    def run(self, request: dict, cancel: threading.Event) -> tuple[str, str]:
        raise NotImplementedError

    def close(self) -> None:
        return

    def diagnostics(self) -> dict[str, object]:
        return {}


class DeterministicBackend(EngineBackend):
    implementation = "deterministic-reference/0"

    def run(self, request: dict, cancel: threading.Event) -> tuple[str, str]:
        if cancel.is_set():
            raise BackendProblem("cancelled")
        text = request["context"][0]["content"]
        result = summarize(text, request["limits"]["max_output_chars"])
        return result, "Extractive prototype: no claims were added or independently verified."


@dataclass
class Job:
    job_id: str
    request_id: str
    submitted: float
    state: str = "queued"
    started: float | None = None
    finished: float | None = None
    request: dict | None = None
    response: dict | None = None
    error: str = ""
    cancel: threading.Event = field(default_factory=threading.Event)

    def public(self) -> dict[str, object]:
        value: dict[str, object] = {
            "protocol": PROTOCOL,
            "request_id": self.request_id,
            "job_id": self.job_id,
            "state": self.state,
        }
        if self.response:
            return dict(self.response)
        if self.error:
            value["error"] = self.error
        return value


class JobManager:
    def __init__(self, backend: EngineBackend | None = None) -> None:
        self.backend = backend or DeterministicBackend()
        self._jobs: OrderedDict[str, Job] = OrderedDict()
        self._lock = threading.RLock()
        self._queue: Queue[Job | None] = Queue(maxsize=MAX_JOBS)
        self._closed = False
        self._worker = threading.Thread(target=self._work, name="guide-se-worker", daemon=True)
        self._worker.start()

    def submit(self, value: object) -> Job:
        request = validate_request(value)
        with self._lock:
            self._expire()
            if self._closed or len(self._jobs) >= MAX_JOBS:
                raise RequestProblem("Engine work queue is full")
            job = Job(secrets.token_hex(16), request["request_id"], time.monotonic(), request=request)
            self._jobs[job.job_id] = job
            self._queue.put_nowait(job)
            return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            self._expire()
            return self._jobs.get(job_id)

    def cancel(self, job_id: str) -> Job | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job and job.state in {"queued", "running"}:
                job.cancel.set()
            return job

    def cancel_active(self) -> int:
        """Cancel all queued/running work without exposing internal job records."""
        cancelled = 0
        with self._lock:
            for job in self._jobs.values():
                if job.state in {"queued", "running"}:
                    job.cancel.set()
                    cancelled += 1
        return cancelled

    def status(self) -> dict[str, object]:
        with self._lock:
            self._expire()
            counts = {name: 0 for name in ("queued", "running", "complete", "failed", "cancelled")}
            for job in self._jobs.values():
                counts[job.state] += 1
            return {"protocol": PROTOCOL, "ready": not self._closed,
                    "implementation": self.backend.implementation, "jobs": counts,
                    "backend": self.backend.diagnostics()}

    def about(self) -> dict[str, object]:
        return {
            "protocol": PROTOCOL,
            "name": "Guide Semiotic Engine",
            "implementation": self.backend.implementation,
            "capabilities": list(self.backend.capabilities),
            "authority": {"tools": False, "network": False, "files": False},
        }

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            for job in self._jobs.values():
                if job.state in {"queued", "running"}:
                    job.cancel.set()
        self._queue.put(None)
        self._worker.join(timeout=2)
        self.backend.close()

    def _expire(self) -> None:
        now = time.monotonic()
        expired = [key for key, job in self._jobs.items()
                   if job.finished is not None and now - job.finished > JOB_TTL_SECONDS]
        for key in expired:
            self._jobs.pop(key, None)

    def _work(self) -> None:
        while True:
            try:
                job = self._queue.get(timeout=0.5)
            except Empty:
                if self._closed:
                    return
                continue
            if job is None:
                return
            if job.cancel.is_set():
                job.state, job.finished, job.request = "cancelled", time.monotonic(), None
                continue
            job.state, job.started = "running", time.monotonic()
            try:
                request = job.request or {}
                deadline = job.submitted + request["limits"]["deadline_ms"] / 1000
                if job.cancel.is_set() or time.monotonic() > deadline:
                    job.state = "cancelled" if job.cancel.is_set() else "failed"
                    job.error = "cancelled" if job.cancel.is_set() else "deadline expired"
                else:
                    result, uncertainty = self.backend.run(request, job.cancel)
                    finished = time.monotonic()
                    if job.cancel.is_set():
                        raise BackendProblem("cancelled")
                    job.response = {
                        "protocol": PROTOCOL,
                        "request_id": job.request_id,
                        "job_id": job.job_id,
                        "state": "complete",
                        "result": {"format": "guide-summary/0", "text": result},
                        "uncertainty": uncertainty[:500],
                        "provenance": [request["context"][0]["id"]],
                        "proposed_actions": [],
                        "timing": {
                            "queued_ms": max(0, int(((job.started or job.submitted) - job.submitted) * 1000)),
                            "work_ms": max(0, int((finished - (job.started or finished)) * 1000)),
                        },
                    }
                    job.state = "complete"
            except BackendProblem as error:
                if str(error) == "cancelled" or job.cancel.is_set():
                    job.state, job.error = "cancelled", "cancelled"
                else:
                    job.state, job.error = "failed", str(error)[:300]
            except Exception:
                job.state, job.error = "failed", "Engine backend failed"
            finally:
                job.finished = time.monotonic()
                job.request = None
