"""Bounded authoritative runtime-grant store for Envelope 0 providers."""
from __future__ import annotations
from dataclasses import dataclass
import secrets, time

class GrantError(RuntimeError): pass

@dataclass(frozen=True)
class GrantRecord:
    grant_id: bytes
    instance_id: str
    generation: int
    provider: str
    interface_major: int
    capability: str
    operations: frozenset[int]
    scope: bytes
    expires_ns: int
    sharing_mode: str
    resource_revision: int
    issued_revision: int

class GrantStore:
    def __init__(self, *, max_grants=128, clock=time.monotonic_ns):
        if type(max_grants) is not int or not 0 < max_grants <= 4096: raise ValueError("invalid grant bound")
        self.max_grants=max_grants; self.clock=clock; self.revision=0; self._records={}; self._revoked=set()

    def _purge_expired(self):
        expired=[key for key,record in self._records.items() if self.clock() >= record.expires_ns]
        for key in expired:
            self._records.pop(key,None); self._revoked.discard(key)
        if expired: self.revision+=1

    def issue(self, context, *, provider, interface_major, capability, operations, scope=b"", lifetime_ns=60_000_000_000, sharing_mode="shared", resource_revision=1):
        self._purge_expired()
        if len(self._records) >= self.max_grants: raise GrantError("grant capacity exhausted")
        if not provider or not capability or sharing_mode not in ("shared","exclusive"): raise ValueError("invalid grant metadata")
        ops=frozenset(operations)
        if not ops or any(type(op) is not int or not 0 < op <= 65535 for op in ops): raise ValueError("invalid operations")
        if type(scope) is not bytes or len(scope)>256 or type(lifetime_ns) is not int or not 0 < lifetime_ns <= 300_000_000_000: raise ValueError("invalid scope or lifetime")
        if type(interface_major) is not int or interface_major<=0 or type(resource_revision) is not int or resource_revision<=0: raise ValueError("invalid version")
        grant_id=secrets.token_bytes(16)
        while grant_id in self._records: grant_id=secrets.token_bytes(16)
        self.revision+=1
        record=GrantRecord(grant_id,context.instance_id,context.generation,provider,interface_major,capability,ops,scope,self.clock()+lifetime_ns,sharing_mode,resource_revision,self.revision)
        self._records[grant_id]=record
        return record

    def validate(self, grant_id, context, *, provider, interface_major, capability, operation, scope=b"", resource_revision=1):
        if type(grant_id) is not bytes or len(grant_id)!=16: raise GrantError("invalid grant reference")
        record=self._records.get(grant_id)
        if not record or grant_id in self._revoked: raise GrantError("unknown or revoked grant")
        if self.clock() >= record.expires_ns:
            self._records.pop(grant_id,None); self._revoked.discard(grant_id); self.revision+=1
            raise GrantError("expired grant")
        checks=(record.instance_id==context.instance_id, record.generation==context.generation, record.provider==provider, record.interface_major==interface_major, record.capability==capability, operation in record.operations, record.scope==scope, record.resource_revision==resource_revision)
        if not all(checks): raise GrantError("grant scope mismatch")
        return record

    def revoke(self, grant_id):
        if grant_id not in self._records: return False
        if grant_id not in self._revoked: self._revoked.add(grant_id); self.revision+=1
        return True

    def release(self, grant_id):
        existed=self._records.pop(grant_id,None) is not None
        self._revoked.discard(grant_id)
        if existed: self.revision+=1
        return existed

    def invalidate_instance(self, instance_id, generation):
        changed=False
        for key,record in list(self._records.items()):
            if record.instance_id==instance_id and record.generation==generation:
                self._records.pop(key); self._revoked.discard(key); changed=True
        if changed: self.revision+=1
        return changed
