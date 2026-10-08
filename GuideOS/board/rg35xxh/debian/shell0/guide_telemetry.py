"""Best-effort numeric diagnostics; never send user text or command arguments."""
import json
import socket
import time

SOCKET = '/run/guideos-diagnostics/events.sock'
BOUNDS_MS = (1, 2, 4, 8, 16, 33, 50, 100, 250, 500, 1000)


def emit(code, **fields):
    try:
        raw = json.dumps(dict(code=code, observed=time.monotonic(), **fields), separators=(',', ':')).encode()
        if len(raw) > 2048:
            return False
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sock:
            sock.setblocking(False)
            sock.sendto(raw, SOCKET)
        return True
    except (OSError, ValueError, TypeError):
        return False


class Timings:
    """Aggregate timings in RAM; no per-key events or reconstructable input trail."""
    def __init__(self):
        self.rows = {}
        self.next_flush = time.monotonic() + 30

    def add(self, metric, seconds):
        value = max(0, seconds * 1000)
        row = self.rows.setdefault(metric, dict(count=0, total_ms=0, max_ms=0, over_100_ms=0, buckets=[0]*(len(BOUNDS_MS)+1)))
        row['count'] += 1
        row['total_ms'] += value
        row['max_ms'] = max(row['max_ms'], value)
        row['over_100_ms'] += value > 100
        bucket = next((index for index, bound in enumerate(BOUNDS_MS) if value <= bound), len(BOUNDS_MS))
        row['buckets'][bucket] += 1

    @staticmethod
    def percentile(row, fraction):
        target = max(1, int(row['count']*fraction + .999999))
        cumulative = 0
        for index, count in enumerate(row['buckets']):
            cumulative += count
            if cumulative >= target:
                return BOUNDS_MS[index] if index < len(BOUNDS_MS) else round(row['max_ms'], 3)
        return round(row['max_ms'], 3)

    def measure(self, metric, function, *args, **kwargs):
        started = time.monotonic()
        try:
            return function(*args, **kwargs)
        finally:
            self.add(metric, time.monotonic()-started)

    def flush(self, force=False):
        if not force and time.monotonic() < self.next_flush:
            return
        for metric, row in self.rows.items():
            emit('TIMING', metric=metric, count=row['count'],
                 mean_ms=round(row['total_ms']/row['count'], 3),
                 p50_ms=self.percentile(row, .50), p95_ms=self.percentile(row, .95),
                 max_ms=round(row['max_ms'], 3), over_100_ms=row['over_100_ms'])
        self.rows.clear()
        self.next_flush = time.monotonic() + 30
