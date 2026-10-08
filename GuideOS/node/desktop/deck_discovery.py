"""Bounded discovery of one local GuideOS Deck diagnostic endpoint."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import ipaddress
import socket


def _local_networks() -> set[ipaddress.IPv4Network]:
    networks: set[ipaddress.IPv4Network] = set()
    for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
        try:
            address = ipaddress.IPv4Address(info[4][0])
        except (IndexError, ipaddress.AddressValueError):
            continue
        if address.is_loopback or address.is_link_local or address.is_unspecified:
            continue
        networks.add(ipaddress.ip_network(f"{address}/24", strict=False))
    return networks


def _probe(address: str, port: int, timeout: float) -> str | None:
    try:
        with socket.create_connection((address, port), timeout=timeout):
            return address
    except OSError:
        return None


def discover_decks(port: int = 2222, timeout: float = 0.15,
                   max_hosts: int = 512) -> list[str]:
    """Return local candidates with the existing Guide-Link SSH endpoint open."""
    hosts: list[str] = []
    for network in sorted(_local_networks(), key=str):
        hosts.extend(str(host) for host in network.hosts())
    hosts = hosts[:max_hosts]
    found: list[str] = []
    with ThreadPoolExecutor(max_workers=32, thread_name_prefix="deck-scan") as pool:
        futures = [pool.submit(_probe, host, port, timeout) for host in hosts]
        for future in as_completed(futures):
            address = future.result()
            if address:
                found.append(address)
    return sorted(set(found), key=lambda value: tuple(int(part) for part in value.split(".")))
