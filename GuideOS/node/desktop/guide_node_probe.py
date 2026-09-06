"""Temporary command-line Deck stand-in used to verify discovery and pairing."""

from __future__ import annotations

import json
import socket
import urllib.request

from guide_node_core import DEFAULT_DISCOVERY_PORT
from guide_node_server import DISCOVERY_REQUEST


def request_json(url: str, method: str = "GET", data: dict | None = None,
                 token: str = "") -> dict:
    body = None if data is None else json.dumps(data).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def discover(timeout: float = 3.0) -> dict:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(timeout)
    try:
        sock.sendto(DISCOVERY_REQUEST, ("255.255.255.255", DEFAULT_DISCOVERY_PORT))
        data, _ = sock.recvfrom(4096)
        return json.loads(data.decode("utf-8"))
    finally:
        sock.close()


def main() -> None:
    print("Looking for Guide Nodes on this network…")
    node = discover()
    print(f"Found: {node['name']} at {node['address']}")
    code = input("Enter the pairing code shown on the Node: ").strip()
    paired = request_json(
        node["address"] + "/guide/v1/pair", "POST",
        {"code": code, "client_name": "Deck probe"},
    )
    status = request_json(node["address"] + "/guide/v1/status", token=paired["token"])
    capabilities = request_json(
        node["address"] + "/guide/v1/capabilities", token=paired["token"]
    )
    print("Paired successfully.")
    print(json.dumps(status, indent=2))
    print(json.dumps(capabilities, indent=2))


if __name__ == "__main__":
    main()
