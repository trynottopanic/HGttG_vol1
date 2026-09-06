#!/usr/bin/env python3
"""Request, resume, verify, and store an official English Wikipedia dump."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import urllib.error
import urllib.request


BASE_URL = "https://dumps.wikimedia.org/enwiki/latest/"
CHECKSUM_NAME = "enwiki-latest-sha1sums.txt"
ARTICLE_NAME = "enwiki-latest-pages-articles-multistream.xml.bz2"
INDEX_NAME = "enwiki-latest-pages-articles-multistream-index.txt.bz2"
WANTED = (ARTICLE_NAME, INDEX_NAME)
USER_AGENT = "GuideOS-Wikipedia-Library/0.1 (https://github.com/trynottopanic/HGttG_vol1)"
BUFFER_SIZE = 4 * 1024 * 1024


class DumpError(RuntimeError):
    """A safe, user-presentable dump operation failure."""


def _request(url: str, *, method="GET", headers=None):
    request_headers = {"User-Agent": USER_AGENT}
    request_headers.update(headers or {})
    return urllib.request.Request(url, method=method, headers=request_headers)


def fetch_bytes(url: str, limit: int = 2 * 1024 * 1024, opener=urllib.request.urlopen) -> bytes:
    try:
        with opener(_request(url), timeout=30) as response:
            body = response.read(limit + 1)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as error:
        raise DumpError(f"Could not read {url}") from error
    if len(body) > limit:
        raise DumpError("Wikimedia metadata exceeded its safe size limit")
    return body


def parse_checksums(document: str) -> dict[str, str]:
    checksums = {}
    for line in document.splitlines():
        match = re.fullmatch(r"([0-9a-fA-F]{40})\s+([^/\\]+)", line.strip())
        if match:
            checksums[match.group(2)] = match.group(1).lower()
    return checksums


def dated_name(latest_name: str, checksum_names) -> str:
    suffix = latest_name.removeprefix("enwiki-latest-")
    candidates = [name for name in checksum_names if re.fullmatch(r"enwiki-\d{8}-" + re.escape(suffix), name)]
    if len(candidates) != 1:
        raise DumpError(f"Could not identify the dated file for {latest_name}")
    return candidates[0]


def remote_size(url: str, opener=urllib.request.urlopen) -> int:
    try:
        with opener(_request(url, method="HEAD"), timeout=30) as response:
            value = response.headers.get("Content-Length")
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as error:
        raise DumpError(f"Could not inspect {url}") from error
    if value is None or not value.isdigit():
        raise DumpError(f"Wikimedia did not report a valid size for {url}")
    return int(value)


def discover(opener=urllib.request.urlopen) -> dict:
    checksum_url = BASE_URL + CHECKSUM_NAME
    try:
        checksums = parse_checksums(fetch_bytes(checksum_url, opener=opener).decode("ascii"))
    except UnicodeDecodeError as error:
        raise DumpError("Wikimedia returned an unreadable checksum list") from error
    files = []
    for latest_name in WANTED:
        source_name = dated_name(latest_name, checksums)
        url = BASE_URL + latest_name
        files.append({
            "name": source_name,
            "latest_alias": latest_name,
            "url": url,
            "size": remote_size(url, opener),
            "sha1": checksums[source_name],
        })
    snapshot_match = re.search(r"enwiki-(\d{8})-", files[0]["name"])
    return {
        "format": "guide.wikipedia.dump-manifest.v1",
        "project": "enwiki",
        "contents": "current article pages; no edit history or media files",
        "snapshot": snapshot_match.group(1) if snapshot_match else "unknown",
        "schema_namespace": "http://www.mediawiki.org/xml/export-0.10/",
        "checksum_source": checksum_url,
        "files": files,
    }


def _human_size(value: int) -> str:
    units = ("B", "KiB", "MiB", "GiB", "TiB")
    size = float(value)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.1f} {unit}"
        size /= 1024
    return str(value)


def print_plan(manifest: dict, destination: Path) -> None:
    total = sum(item["size"] for item in manifest["files"])
    space_probe = destination
    while not space_probe.exists() and space_probe != space_probe.parent:
        space_probe = space_probe.parent
    free = shutil.disk_usage(space_probe).free
    print(f"Wikipedia snapshot: {manifest['snapshot']}")
    print(f"Download size: {_human_size(total)}")
    print(f"Available space: {_human_size(free)}")
    print(f"Storage folder: {destination}")
    for item in manifest["files"]:
        print(f"  {item['name']}: {_human_size(item['size'])}")
    if free < total + 5 * 1024**3:
        raise DumpError("The destination needs the download size plus at least 5 GiB of working room")


def hash_file(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(BUFFER_SIZE), b""):
            digest.update(block)
    return digest.hexdigest()


def download_file(item: dict, destination: Path, opener=urllib.request.urlopen) -> Path:
    final_path = destination / item["name"]
    partial_path = final_path.with_name(final_path.name + ".partial")
    if final_path.exists():
        if final_path.stat().st_size == item["size"] and hash_file(final_path) == item["sha1"]:
            print(f"Already verified: {final_path.name}")
            return final_path
        raise DumpError(f"An unverified completed file already exists: {final_path}")

    offset = partial_path.stat().st_size if partial_path.exists() else 0
    headers = {"Range": f"bytes={offset}-"} if offset else {}
    try:
        response = opener(_request(item["url"], headers=headers), timeout=60)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as error:
        raise DumpError(f"Could not download {item['name']}") from error
    status = getattr(response, "status", None)
    if status is None:
        status = response.getcode()
    if offset and status != 206:
        response.close()
        offset = 0
        try:
            response = opener(_request(item["url"]), timeout=60)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as error:
            raise DumpError(f"Could not restart {item['name']}") from error
    mode = "ab" if offset else "wb"
    with response, partial_path.open(mode) as target:
        copied = offset
        while True:
            block = response.read(BUFFER_SIZE)
            if not block:
                break
            target.write(block)
            copied += len(block)
            print(f"\r{item['name']}: {_human_size(copied)} / {_human_size(item['size'])}", end="", flush=True)
    print()
    if partial_path.stat().st_size != item["size"]:
        raise DumpError(f"Download stopped early; run download again to resume {item['name']}")
    if hash_file(partial_path) != item["sha1"]:
        raise DumpError(f"Checksum failed for {item['name']}; the partial file was retained for diagnosis")
    os.replace(partial_path, final_path)
    print(f"Verified: {final_path.name}")
    return final_path


def save_manifest(manifest: dict, destination: Path) -> None:
    temporary = destination / "guide-wikipedia-manifest.json.new"
    final = destination / "guide-wikipedia-manifest.json"
    temporary.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, final)


def verify(manifest: dict, destination: Path) -> bool:
    good = True
    for item in manifest["files"]:
        path = destination / item["name"]
        if not path.exists():
            print(f"MISSING: {path.name}")
            good = False
        elif path.stat().st_size != item["size"] or hash_file(path) != item["sha1"]:
            print(f"FAILED: {path.name}")
            good = False
        else:
            print(f"VERIFIED: {path.name}")
    return good


def status(manifest: dict, destination: Path) -> None:
    for item in manifest["files"]:
        final = destination / item["name"]
        partial = final.with_name(final.name + ".partial")
        if final.exists():
            label, amount = "COMPLETE (NOT CHECKED)", final.stat().st_size
        elif partial.exists():
            label, amount = "PARTIAL", partial.stat().st_size
        else:
            label, amount = "NOT STARTED", 0
        print(f"{label}: {final.name} ({_human_size(amount)} / {_human_size(item['size'])})")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="GuideOS English Wikipedia backup manager")
    parser.add_argument("command", choices=("plan", "download", "status", "verify"))
    parser.add_argument("destination", type=Path, help="folder that will hold the Wikipedia library")
    args = parser.parse_args(argv)
    try:
        manifest_path = args.destination / "guide-wikipedia-manifest.json"
        if args.command in ("status", "verify") and manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        else:
            manifest = discover()
        print_plan(manifest, args.destination)
        if args.command == "download":
            args.destination.mkdir(parents=True, exist_ok=True)
            for item in manifest["files"]:
                download_file(item, args.destination)
            save_manifest(manifest, args.destination)
        if args.command == "status":
            status(manifest, args.destination)
        if args.command == "verify" and not verify(manifest, args.destination):
            return 1
        return 0
    except (DumpError, OSError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
