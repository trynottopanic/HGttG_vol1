"""Serve exactly two synthetic files for the physical transfer-provider check.

Run on the personal computer. This standalone fixture does not use Node trust
or AT Field settings and serves no personal files. Default: loopback only.
"""
import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re


PAYLOADS = {"/stream": bytes(range(256)) * 512,
            "/download": bytes(reversed(range(256))) * 1024}


class FixtureHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        payload = PAYLOADS.get(self.path)
        match = re.fullmatch(r"bytes=(\d+)-(\d+)", self.headers.get("Range", ""))
        if payload is None or not match:
            self.send_error(404)
            return
        start, end = map(int, match.groups())
        if not 0 <= start <= end < len(payload):
            self.send_error(416)
            return
        self.send_response(206)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Content-Range", f"bytes {start}-{end}/{len(payload)}")
        self.end_headers()
        try:
            self.wfile.write(payload[start:end + 1])
        except (OSError, ConnectionError):
            pass

    def log_message(self, *args):
        pass


def manifest(base):
    return {"version": 1,
            "agreement": {"revision": 1, "interval_seconds": 0.2,
                          "stream_ceiling": 8192, "stream_floor": 6144,
                          "download_ceiling": 16384, "download_floor": 2048,
                          "weights": [8, 4, 2, 1]},
            "reserve_bytes": 1024, "chunk_bytes": 2048, "request_timeout": 2,
            "sources": {name[1:]: {"url": base + name, "size": len(data),
                                    "sha256": hashlib.sha256(data).hexdigest()}
                        for name, data in PAYLOADS.items()},
            "capacity_schedule": [{"intervals": 5, "capacity_bytes": 24576},
                                  {"intervals": 8, "capacity_bytes": 7168},
                                  {"intervals": 40, "capacity_bytes": 24576}]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=14367)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.bind, args.port), FixtureHandler)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest(f"http://{args.bind}:{server.server_port}"), indent=2))
    print(f"Synthetic transfer source ready; manifest: {args.manifest}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
