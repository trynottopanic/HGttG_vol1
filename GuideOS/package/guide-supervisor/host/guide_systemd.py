# SPDX-License-Identifier: AGPL-3.0-or-later
"""Trusted, single-caller development adapter for the systemd user manager.

No application-facing API or privilege boundary. Agreements and checkpoint
evidence must already be authorized by Guide. Never use this as a root daemon.
The C policy component remains responsible for deciding when to unload.
"""
from dataclasses import dataclass
from pathlib import Path
import math
import re
import subprocess
import uuid


class HostError(RuntimeError):
    pass


@dataclass(frozen=True)
class InstalledAgreement:
    application: str
    revision: int
    tier: int
    cpu_weight: int
    memory_high_bytes: int
    tasks_max: int
    stop_timeout_ms: int
    needs_checkpoint: bool

    def validate(self):
        if not re.fullmatch(r"[0-9]{1,64}", self.application):
            raise ValueError("application identity must be a numeric string")
        for value in (self.revision, self.cpu_weight, self.memory_high_bytes,
                      self.tasks_max, self.stop_timeout_ms):
            if type(value) is not int or not 0 < value < 2**63:
                raise ValueError("agreement values must be positive bounded integers")
        if type(self.tier) is not int or not 0 <= self.tier <= 4:
            raise ValueError("invalid tier")
        if self.cpu_weight > 10000 or type(self.needs_checkpoint) is not bool:
            raise ValueError("invalid weight or checkpoint requirement")


@dataclass(frozen=True)
class UnloadAuthorization:
    """Trusted Supervisor output, not a receipt accepted from an application.

    The caller must validate the policy action, checkpoint generation/durability,
    and continuing quiescence. These booleans do not authenticate those facts.
    """
    instance: str
    revision: int
    episode: int
    sequence: int
    checkpoint_durable: bool
    quiescent: bool


@dataclass(frozen=True)
class Observation:
    instance: str
    invocation: str
    active: str
    substate: str
    result: str
    populated: bool | None
    memory_bytes: int | None
    tasks: int | None
    cpu_usage_usec: int | None
    controls_verified: bool
    # Empty containment is not proof of a saved checkpoint or globally free RAM.


@dataclass
class _Instance:
    agreement: InstalledAgreement
    argv: tuple[str, ...]
    unit: str
    start_attempted: bool = False
    invocation: str = ""
    cgroup: Path | None = None
    stop_attempted: tuple[int, int] | None = None


class SystemdUserHost:
    """Bounded command adapter. Serialize calls from the Supervisor event loop.

    Unique unit names are never reused. No automatic restart, retry after an
    uncertain mutation, or fallback to a different instance. Records are kept
    in memory: recovery across Supervisor restart is deliberately unsupported.
    """
    def __init__(self, *, command_timeout: float, max_instances: int):
        if not math.isfinite(command_timeout) or command_timeout <= 0:
            raise ValueError("finite positive command timeout required")
        if type(max_instances) is not int or max_instances <= 0:
            raise ValueError("positive instance bound required")
        self.timeout = command_timeout
        self.max_instances = max_instances
        self._instances = {}

    def _run(self, argv, *, check=True):
        try:
            result = subprocess.run(argv, stdin=subprocess.DEVNULL,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    text=True, timeout=self.timeout, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise HostError("host command failed or timed out; reconcile before retry") from exc
        if check and result.returncode:
            # Do not copy arbitrary application command arguments into errors.
            raise HostError(f"host command returned {result.returncode}; reconcile instance")
        return result

    def reserve(self, agreement: InstalledAgreement, argv: list[str]) -> str:
        agreement.validate()
        if len(self._instances) >= self.max_instances:
            raise HostError("instance record capacity exhausted")
        if (not argv or len(argv) > 128 or not Path(argv[0]).is_absolute()
                or any(not isinstance(arg, str) or "\0" in arg for arg in argv)
                or sum(len(arg) for arg in argv) > 32768):
            raise ValueError("bounded argument vector with absolute executable required")
        identity = uuid.uuid4().hex
        self._instances[identity] = _Instance(
            agreement, tuple(argv), f"guide-app-{identity}.service")
        return identity

    def _get(self, instance):
        try:
            return self._instances[instance]
        except KeyError as exc:
            raise HostError("unknown instance") from exc

    def start(self, instance):
        record = self._get(instance)
        if record.start_attempted:
            raise HostError("instance start already attempted; observe it instead")
        a = record.agreement
        properties = [
            "Type=exec", "ExitType=cgroup", "RemainAfterExit=yes", "Restart=no",
            "KillMode=control-group", "SendSIGKILL=no", "Delegate=no",
            "StandardInput=null", "StandardOutput=null", "StandardError=null",
            f"TimeoutStopSec={a.stop_timeout_ms}ms", "MemoryAccounting=yes",
            "TasksAccounting=yes", f"CPUWeight={a.cpu_weight}",
            f"MemoryHigh={a.memory_high_bytes}", f"TasksMax={a.tasks_max}",
        ]
        command = ["/usr/bin/systemd-run", "--user", "--quiet",
                   "--expand-environment=no", f"--unit={record.unit}",
                   "--description=Guide application instance"]
        command += [f"--property={p}" for p in properties]
        command += ["--", *record.argv]
        record.start_attempted = True  # A timeout does not prove creation failed.
        self._run(command)
        return self.observe(instance)

    def _properties(self, record):
        names = ("LoadState", "InvocationID", "ActiveState", "SubState", "Result",
                 "ControlGroup", "CPUWeight", "MemoryHigh", "TasksMax",
                 "SendSIGKILL", "KillMode", "Restart")
        result = self._run(["/usr/bin/systemctl", "--user", "show", record.unit,
                            "--property=" + ",".join(names)], check=False)
        props = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
        if props.get("LoadState") == "not-found" and record.invocation:
            return props
        if result.returncode:
            raise HostError("unable to observe instance")
        if props.get("LoadState") != "loaded":
            raise HostError("instance unit unavailable; release is unverified")
        invocation = props.get("InvocationID", "")
        if invocation:
            if not re.fullmatch(r"[0-9a-f]{32}", invocation):
                raise HostError("invalid host invocation identity")
            if record.invocation and invocation != record.invocation:
                raise HostError("host invocation changed; refusing replacement instance")
            record.invocation = invocation
        elif props.get("ActiveState") not in ("inactive", "failed"):
            raise HostError("running instance has no invocation identity")
        group = props.get("ControlGroup", "")
        if group:
            path = Path("/sys/fs/cgroup") / group.lstrip("/")
            if ".." in path.parts or path.name != record.unit:
                raise HostError("unexpected application containment path")
            if record.cgroup and path != record.cgroup:
                raise HostError("application containment changed")
            record.cgroup = path
        return props

    def observe(self, instance) -> Observation:
        record = self._get(instance)
        if not record.start_attempted:
            raise HostError("instance has not been started")
        props = self._properties(record)
        values = {}
        if record.cgroup:
            for name in ("cgroup.events", "memory.current", "pids.current", "cpu.stat",
                         "cpu.weight", "memory.high", "pids.max"):
                try:
                    values[name] = (record.cgroup / name).read_text().strip()
                except FileNotFoundError:
                    pass  # Missing accounting is unknown, never zero consumption.
        events = dict(line.split() for line in values.get("cgroup.events", "").splitlines())
        cpu = dict(line.split() for line in values.get("cpu.stat", "").splitlines())
        a = record.agreement
        controls = (
            values.get("cpu.weight") == str(a.cpu_weight)
            and values.get("memory.high") == str(a.memory_high_bytes)
            and values.get("pids.max") == str(a.tasks_max)
            and props.get("SendSIGKILL") == "no"
            and props.get("KillMode") == "control-group"
            and props.get("Restart") == "no")
        def number(value):
            return int(value) if value is not None else None
        populated = events.get("populated") == "1" if "populated" in events else None
        if (record.cgroup and not record.cgroup.exists()
                and (props.get("ActiveState") in ("inactive", "failed")
                     or (props.get("ActiveState") == "active" and props.get("SubState") == "exited"))):
            populated = False  # Known containment has been removed by the host.
        return Observation(instance, record.invocation, props.get("ActiveState", "unknown"),
                           props.get("SubState", "unknown"), props.get("Result", "unknown"),
                           populated,
                           number(values.get("memory.current")), number(values.get("pids.current")),
                           number(cpu.get("usage_usec")), controls)

    def unload(self, authorization: UnloadAuthorization):
        record = self._get(authorization.instance)
        a = record.agreement
        if (authorization.revision != a.revision
                or type(authorization.episode) is not int or authorization.episode <= 0
                or type(authorization.sequence) is not int or authorization.sequence <= 0):
            raise HostError("stale or invalid unload authorization")
        if a.needs_checkpoint and not (
                authorization.checkpoint_durable is True and authorization.quiescent is True):
            raise HostError("unload requires a durable checkpoint and continuing quiescence")
        key = (authorization.episode, authorization.sequence)
        if record.stop_attempted:
            if record.stop_attempted != key:
                raise HostError("stop already attempted; reconcile before another action")
            return False  # Idempotent acknowledgement; no repeated signal.
        observation = self.observe(authorization.instance)
        if observation.active != "active" or not observation.invocation:
            raise HostError("instance is not active; reconcile before unloading")
        if not observation.controls_verified:
            raise HostError("host controls unverified; refusing unload")
        record.stop_attempted = key
        self._run(["/usr/bin/systemctl", "--user", "--no-block", "stop", record.unit])
        return True  # Request accepted, NOT a claim of stop or resource release.

    def retire(self, instance):
        record = self._get(instance)
        if record.start_attempted and self.observe(instance).populated is not False:
            raise HostError("cannot retire an instance without observed empty containment")
        if record.start_attempted:
            props = self._properties(record)
            if props.get("LoadState") == "loaded" and props.get("ActiveState") == "active":
                # RemainAfterExit preserves evidence. Release that empty unit too.
                self._run(["/usr/bin/systemctl", "--user", "stop", record.unit])
        del self._instances[instance]
