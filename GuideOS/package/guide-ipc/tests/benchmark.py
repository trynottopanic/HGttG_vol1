#!/usr/bin/env python3
from __future__ import annotations
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
import guide_ipc as ipc

payload_object = {0: 1, 1: {0: "notepad", 1: True}, 2: 1 << 40}
encoded = ipc.encode_payload(payload_object)
iterations = 100_000

start = time.perf_counter_ns()
for _ in range(iterations):
    ipc.validate_cbor(encoded)
validate_ns = time.perf_counter_ns() - start

start = time.perf_counter_ns()
for _ in range(iterations):
    ipc.decode_payload(encoded)
decode_ns = time.perf_counter_ns() - start

start = time.perf_counter_ns()
for _ in range(iterations):
    ipc.encode_payload(payload_object)
encode_ns = time.perf_counter_ns() - start

print(f"PY_PROFILE_BENCH iterations={iterations} bytes={len(encoded)} "
      f"validate_us={validate_ns / iterations / 1000:.2f} "
      f"decode_us={decode_ns / iterations / 1000:.2f} "
      f"encode_us={encode_ns / iterations / 1000:.2f}")
