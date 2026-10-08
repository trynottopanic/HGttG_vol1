#!/usr/bin/env python3
"""Bounded Deck interface to a separately installed Node Semiotic Engine."""

from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import stat
import sys
import time

NODE_LINK_DIRECTORY = Path("/usr/lib/guideos/node-link")
if str(NODE_LINK_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(NODE_LINK_DIRECTORY))

from guide_node_client import NodeClient, NodeLinkError, validate_node_description


SESSION_FILE = Path("/run/guideos-node-session.json")
INPUT_FILE = Path("/run/guideos-se-input.txt")
SUMMARY_FILE = Path("/run/guideos-se-summary.txt")
UNCERTAINTY_FILE = Path("/run/guideos-se-uncertainty.txt")
cancel_requested = False


def request_cancel(_signal: int, _frame: object) -> None:
    global cancel_requested
    cancel_requested = True


def safe_text(value: object, limit: int = 120) -> str:
    return " ".join(str(value).replace("\0", " ").split())[:limit]


def session_client() -> NodeClient:
    try:
        session = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise NodeLinkError("PAIR WITH A NODE FIRST") from error
    if not isinstance(session, dict) or not isinstance(session.get("token"), str):
        raise NodeLinkError("NODE SESSION IS INVALID")
    client = NodeClient(validate_node_description(session.get("description")))
    client.token = session["token"]
    return client


def status() -> int:
    capabilities = session_client().capabilities().get("capabilities", [])
    engine = next((item for item in capabilities
                   if isinstance(item, dict) and item.get("id") == "semiotic.text"), None)
    if not isinstance(engine, dict):
        raise NodeLinkError("NODE DOES NOT OFFER A SEMIOTIC ENGINE")
    print("GUIDE-SE-STATUS-1")
    print("READY=" + ("YES" if engine.get("available") else "NO"))
    print("STATE=" + safe_text(engine.get("state", "unknown"), 40).upper())
    print("DETAIL=" + safe_text(engine.get("reason", ""), 100).upper())
    return 0


def read_input(path_text: str) -> str:
    if path_text != str(INPUT_FILE):
        raise NodeLinkError("ENGINE INPUT PATH IS NOT PERMITTED")
    try:
        descriptor = os.open(INPUT_FILE, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except OSError as error:
        raise NodeLinkError("ENGINE INPUT IS NOT AVAILABLE") from error
    try:
        details = os.fstat(descriptor)
        if not stat.S_ISREG(details.st_mode) or not 1 <= details.st_size <= 96_000:
            raise NodeLinkError("ENGINE INPUT FILE IS INVALID")
        raw = os.read(descriptor, 96_001)
        if len(raw) != details.st_size:
            raise NodeLinkError("ENGINE INPUT CHANGED WHILE BEING READ")
        text = raw.decode("utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise NodeLinkError("ENGINE INPUT IS NOT READABLE TEXT") from error
    finally:
        os.close(descriptor)
    return text[:32_000]


def write_private_text(path: Path, text: str) -> None:
    temporary = path.with_suffix(path.suffix + ".new")
    try:
        temporary.unlink()
    except FileNotFoundError:
        pass
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                         getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            output.write(text)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def summarize(path_text: str) -> int:
    global cancel_requested
    cancel_requested = False
    previous_term = signal.signal(signal.SIGTERM, request_cancel)
    try:
        client = session_client()
        submitted = client.semiotic_submit(read_input(path_text))
        job_id = str(submitted["job_id"])
        deadline = time.monotonic() + 305
        while time.monotonic() < deadline:
            if cancel_requested:
                client.semiotic_cancel(job_id)
                raise NodeLinkError("ENGINE JOB CANCELLED")
            current = client.semiotic_job(job_id)
            state = current.get("state")
            if state == "complete":
                result = current.get("result", {})
                summary = result.get("text") if isinstance(result, dict) else None
                if not isinstance(summary, str) or len(summary) > 4000:
                    raise NodeLinkError("ENGINE RETURNED INVALID TEXT")
                uncertainty = current.get("uncertainty", "")
                if not isinstance(uncertainty, str):
                    uncertainty = ""
                write_private_text(SUMMARY_FILE, summary)
                write_private_text(UNCERTAINTY_FILE, uncertainty[:500])
                print("GUIDE-SE-SUMMARY-1")
                print("TEXT=/run/guideos-se-summary.txt")
                print("UNCERTAINTY=/run/guideos-se-uncertainty.txt")
                return 0
            if state in {"failed", "cancelled"}:
                raise NodeLinkError(current.get("error", "ENGINE JOB DID NOT COMPLETE"))
            if state not in {"queued", "running"}:
                raise NodeLinkError("ENGINE RETURNED AN UNKNOWN JOB STATE")
            time.sleep(0.15)
        client.semiotic_cancel(job_id)
        raise NodeLinkError("ENGINE JOB EXCEEDED FIVE MINUTES")
    except KeyboardInterrupt:
        if "client" in locals() and "job_id" in locals():
            client.semiotic_cancel(job_id)
        raise
    finally:
        signal.signal(signal.SIGTERM, previous_term)


def main(arguments: list[str] | None = None) -> int:
    args = sys.argv[1:] if arguments is None else arguments
    try:
        if args == ["status"]:
            return status()
        if len(args) == 2 and args[0] == "summarize":
            return summarize(args[1])
        raise NodeLinkError("UNKNOWN SEMIOTIC ENGINE REQUEST")
    except (NodeLinkError, OSError, ValueError, json.JSONDecodeError) as error:
        print("ERROR=" + safe_text(error).upper())
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
