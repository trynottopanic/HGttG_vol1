# SPDX-License-Identifier: AGPL-3.0-or-later
"""Bounded Supervisor-owned process-to-instance resolution for Envelope 0."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import os, re

_TOKEN=re.compile(r"[A-Za-z0-9_.@-]{1,96}")
_INSTANCE=re.compile(r"[0-9a-f]{32}")

class ResolutionError(RuntimeError): pass

@dataclass(frozen=True)
class InstanceContext:
    instance_id: str
    generation: int
    package_id: str
    component: str
    unit: str
    cgroup: Path
    uid: int
    agreement_revision: int

@dataclass(frozen=True)
class ResolvedPeer:
    context: InstanceContext
    pid: int
    uid: int
    gid: int
    pidfd: int

class InstanceRegistry:
    """Trusted bounded registry. Callers own and must close returned pidfds."""
    def __init__(self, *, max_instances=32, proc_root=Path("/proc"), cgroup_root=Path("/sys/fs/cgroup"), pidfd_open=os.pidfd_open):
        if type(max_instances) is not int or not 0 < max_instances <= 1024: raise ValueError("invalid instance bound")
        self.max_instances=max_instances; self.proc_root=Path(proc_root); self.cgroup_root=Path(cgroup_root)
        self._pidfd_open=pidfd_open; self._records={}; self._reconciled=False

    def set_reconciled(self, value: bool):
        if type(value) is not bool: raise ValueError("boolean required")
        self._reconciled=value

    def register(self, context: InstanceContext):
        if not isinstance(context,InstanceContext) or not _INSTANCE.fullmatch(context.instance_id): raise ValueError("invalid instance")
        if type(context.generation) is not int or not 0 < context.generation < 2**64: raise ValueError("invalid generation")
        if not _TOKEN.fullmatch(context.package_id) or not _TOKEN.fullmatch(context.component) or not _TOKEN.fullmatch(context.unit): raise ValueError("invalid identity token")
        if type(context.uid) is not int or context.uid < 0 or type(context.agreement_revision) is not int or context.agreement_revision <= 0: raise ValueError("invalid identity metadata")
        cg=context.cgroup.resolve(strict=False); root=self.cgroup_root.resolve(strict=False)
        if cg == root or root not in cg.parents: raise ValueError("instance cgroup must be beneath cgroup root")
        if cg.name != context.unit: raise ValueError("unit and cgroup identity differ")
        if context.instance_id not in self._records and len(self._records) >= self.max_instances: raise ResolutionError("instance registry full")
        old=self._records.get(context.instance_id)
        if old and context.generation <= old.generation: raise ResolutionError("generation must advance")
        self._records[context.instance_id]=InstanceContext(context.instance_id,context.generation,context.package_id,context.component,context.unit,cg,context.uid,context.agreement_revision)

    def retire(self, instance_id: str, generation: int):
        current=self._records.get(instance_id)
        if not current or current.generation != generation: raise ResolutionError("stale instance retirement")
        del self._records[instance_id]

    def _process_identity(self,pid:int):
        try:
            status=(self.proc_root/str(pid)/"status").read_text(encoding="ascii")
            uid_line=next(line for line in status.splitlines() if line.startswith("Uid:"))
            process_uid=int(uid_line.split()[1])
            rows=(self.proc_root/str(pid)/"cgroup").read_text(encoding="ascii").splitlines()
            unified=[row.split(":",2)[2] for row in rows if row.startswith("0::")]
            if len(unified) != 1: raise ResolutionError("peer has no unique unified cgroup")
            relative=Path(unified[0].lstrip("/"))
            if ".." in relative.parts: raise ResolutionError("invalid peer cgroup")
            cgroup=(self.cgroup_root/relative).resolve(strict=False)
            return process_uid,cgroup
        except (OSError,ValueError,StopIteration) as exc:
            raise ResolutionError("unable to inspect live peer") from exc

    def resolve(self,pid:int,uid:int,gid:int)->ResolvedPeer:
        if not self._reconciled: raise ResolutionError("Supervisor registry is not reconciled")
        if any(type(v) is not int or v < 0 for v in (pid,uid,gid)) or pid == 0: raise ResolutionError("invalid peer credentials")
        process_uid,cgroup=self._process_identity(pid)
        if process_uid != uid: raise ResolutionError("peer uid changed")
        matches=[r for r in self._records.values() if r.uid == uid and (cgroup == r.cgroup or r.cgroup in cgroup.parents)]
        if len(matches) != 1: raise ResolutionError("peer is not in one registered instance")
        try: pidfd=self._pidfd_open(pid,0)
        except OSError as exc: raise ResolutionError("unable to pin peer process") from exc
        return ResolvedPeer(matches[0],pid,uid,gid,pidfd)

def current_cgroup(pid=os.getpid(), *, proc_root=Path("/proc"), cgroup_root=Path("/sys/fs/cgroup")):
    rows=(Path(proc_root)/str(pid)/"cgroup").read_text(encoding="ascii").splitlines()
    unified=[row.split(":",2)[2] for row in rows if row.startswith("0::")]
    if len(unified)!=1: raise ResolutionError("no unique unified cgroup")
    return (Path(cgroup_root)/unified[0].lstrip("/")).resolve(strict=False)
