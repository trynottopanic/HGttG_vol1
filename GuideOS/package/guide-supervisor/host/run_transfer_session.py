"""Run a recorded two-transfer scheduling acceptance session on a Linux host.

The manifest supplies a synthetic capacity schedule. This is provider acceptance,
not a video player or an inferred measurement of available Wi-Fi bandwidth.
"""
import argparse
import json
import os
from pathlib import Path
import signal
import threading
import time
import uuid

from guide_transfers import RangeTransfer, Source, TransferAgreement, TransferScheduler, sync_directory


def run(planner, manifest, output):
    config = json.loads(Path(manifest).read_text())
    if config.get("version") != 1:
        raise ValueError("unsupported session manifest")
    profile = dict(config["agreement"])
    profile["weights"] = tuple(profile["weights"])
    agreement = TransferAgreement(**profile)
    agreement.validate()
    schedule = config["capacity_schedule"]
    if (not schedule or len(schedule) > 100
            or any(type(s["intervals"]) is not int or not 0 < s["intervals"] <= 10000
                   or type(s["capacity_bytes"]) is not int or s["capacity_bytes"] < 0 for s in schedule)):
        raise ValueError("invalid finite capacity schedule")
    destination = Path(output)
    destination.mkdir(parents=True, exist_ok=True)
    instance = uuid.uuid4().hex
    cancelled = threading.Event()
    previous_handlers = {s: signal.signal(s, lambda *_: cancelled.set())
                         for s in (signal.SIGINT, signal.SIGTERM)}
    workers = []
    summary = {"instance": instance, "agreement_revision": agreement.revision,
               "evidence": "real HTTP transfers; synthetic capacity schedule; no video decoder",
               "outcome": "failed"}
    try:
        for name in ("stream", "download"):
            workers.append(RangeTransfer(Source(**config["sources"][name]), destination / name,
                                         chunk_bytes=config["chunk_bytes"],
                                         request_timeout=config["request_timeout"]))
        scheduler = TransferScheduler(Path(planner), agreement, *workers)
        with (destination / f"events-{instance}.jsonl").open("x", encoding="utf-8") as log:
            started = time.monotonic()
            tick = 0
            for phase in schedule:
                for _ in range(phase["intervals"]):
                    if cancelled.wait(max(0, scheduler._next - time.monotonic())):
                        break
                    report = scheduler.tick(phase["capacity_bytes"], reserve_bytes=config["reserve_bytes"])
                    tick += 1
                    report.update(instance=instance, tick=tick, elapsed=time.monotonic() - started)
                    log.write(json.dumps(report) + "\n")
                    log.flush()
                    if any(w.snapshot()["state"] == "failed" for w in workers):
                        raise RuntimeError("transfer failed; inspect session observations")
                if cancelled.is_set():
                    break
            # Observe the last allowance before closing workers.
            cancelled.wait(max(0, scheduler._next - time.monotonic()))
            os.fsync(log.fileno())
        summary["outcome"] = "cancelled" if cancelled.is_set() else "schedule-finished"
    except Exception as error:
        summary["error"] = type(error).__name__
    finally:
        for worker in workers:
            try:
                worker.close()
            except TimeoutError:
                summary["outcome"] = "stop-unconfirmed"
        summary["transfers"] = [w.snapshot() for w in workers]
        summary["all_content_verified"] = len(workers) == 2 and all(
            w.snapshot()["state"] == "complete" for w in workers)
        with (destination / f"summary-{instance}.json").open("x", encoding="utf-8") as saved:
            json.dump(summary, saved, indent=2)
            saved.flush()
            os.fsync(saved.fileno())
        sync_directory(destination)
        for sig, handler in previous_handlers.items():
            signal.signal(sig, handler)
    print(json.dumps(summary, indent=2))
    return 0 if summary["all_content_verified"] and summary["outcome"] == "schedule-finished" else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--planner", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", required=True, help="Private session directory; reuse to resume partial files")
    args = parser.parse_args()
    raise SystemExit(run(args.planner, args.manifest, args.output))
