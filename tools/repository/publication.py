#!/usr/bin/env python3
"""Check or export public source without changing Git history or publishing.
SPDX-License-Identifier: AGPL-3.0-or-later
"""
import argparse
import collections
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
LIMIT = 100 * 1024 * 1024
TEXT = {'.py', '.sh', '.ps1', '.cmd', '.bat', '.json', '.toml', '.yaml', '.yml',
        '.md', '.txt', '.conf', '.cfg', '.ini', '.service', '.socket', '.c', '.h',
        '.cpp', '.js', '.ts', '.xml', '.gradle', '.patch', '.in', '.mk'}
PATTERNS = (
    ('OpenAI credential', re.compile(rb'sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{30,}')),
    ('GitHub credential', re.compile(rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})')),
    ('private key', re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----\r?\n[A-Za-z0-9+/=]{30,}')),
)


def git(*args, data=None, cwd=ROOT, okay=(0,)):
    result = subprocess.run(['git', *args], cwd=cwd, input=data,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode not in okay:
        raise RuntimeError(result.stderr.decode('utf-8', 'replace').strip())
    return result.stdout


def source_files():
    raw = git('ls-files', '--cached', '--others', '--exclude-standard', '-z')
    names = sorted(set(name for name in raw.decode('utf-8').split('\0') if name))
    ignored = set(git('check-ignore', '--no-index', '-z', '--stdin',
                      data=('\0'.join(names)+'\0').encode(), okay=(0, 1)).decode().split('\0'))
    selected = []
    excluded = []
    for name in names:
        if name in ignored:
            excluded.append(name)
        else:
            path = ROOT / name
            if path.exists() or path.is_symlink():
                selected.append(name)
    return selected, excluded


def check(selected, excluded):
    problems = []
    groups = collections.defaultdict(lambda: dict(files=0, bytes=0))
    entries = []
    environment_key = os.environ.get('OPENAI_API_KEY', '').encode()
    for name in selected:
        path = ROOT / name
        # Never follow links into owner data or external workspaces.
        if path.is_symlink():
            problems.append(dict(path=name, reason='source symlink requires explicit review'))
            continue
        if not path.is_file():
            problems.append(dict(path=name, reason='not a regular source file'))
            continue
        size = path.stat().st_size
        if size > LIMIT:
            problems.append(dict(path=name, reason='over 100 MiB'))
        if 'planegotchi' in name.lower() or Path(name).name in {
                'guide_settlement.py', 'settlement_grid_runtime.py', 'test_settlement_viewer.py'}:
            problems.append(dict(path=name, reason='excluded application source'))
        if path.suffix.lower() in TEXT and size <= 4 * 1024 * 1024:
            data = path.read_bytes()
            for kind, pattern in PATTERNS:
                if pattern.search(data):
                    problems.append(dict(path=name, reason=kind+' pattern; value withheld'))
            if len(environment_key) >= 20 and environment_key in data:
                problems.append(dict(path=name, reason='environment API key found; value withheld'))
        group = '/'.join(name.split('/')[:2])
        groups[group]['files'] += 1
        groups[group]['bytes'] += size
        entries.append(dict(path=name, bytes=size))
    return dict(status='PASS' if not problems else 'REVIEW_REQUIRED',
                selectedFiles=len(entries), selectedBytes=sum(p['bytes'] for p in entries),
                excludedFiles=len(excluded), groups=dict(sorted(groups.items())),
                problems=problems, files=entries, excluded=excluded,
                limits='Checks file selection, sizes and common credentials; not a runtime or history audit')


def export(selected, destination):
    destination = destination.resolve()
    if destination == ROOT or ROOT in destination.parents:
        raise ValueError('Export must be outside the development checkout')
    if not destination.is_dir() or not (destination / '.git').exists():
        raise ValueError('Create a fresh publication worktree before exporting')
    top = Path(git('rev-parse', '--show-toplevel', cwd=destination).decode().strip()).resolve()
    branch = git('branch', '--show-current', cwd=destination).decode().strip()
    if top != destination or not branch.startswith('publish/'):
        raise ValueError('Export requires the exact publication worktree and a publish/ branch')
    if any(p.name != '.git' for p in destination.iterdir()):
        raise ValueError('Publication worktree must contain only its Git metadata')
    for name in selected:
        source, target = ROOT / name, destination / name
        if source.is_symlink() or not source.is_file():
            raise ValueError('Unsafe export entry: '+name)
        if destination not in target.resolve().parents:
            raise ValueError('Export path escaped the destination')
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        public_document(name, target)


def public_document(name, path):
    if name != 'GuideOS/docs/DESIGN_ALIGNMENT_0.md':
        return
    text = path.read_text(encoding='utf-8-sig')
    marker = '### Planegotchi world viewer, 0.4.3.01'
    if marker in text:
        text = text.split(marker, 1)[0].rstrip()+'\n\n'
        text += '## Public-source scope\n\nPrivate application-specific alignment sections are omitted from this export.\n'
    text = '\n'.join(line for line in text.splitlines()
                     if not (line.startswith('| ') and 'PLANEGOTCHI_' in line))+'\n'
    path.write_text(text, encoding='utf-8', newline='\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='check the current public source selection')
    parser.add_argument('--export', type=Path, help='copy into a fresh publish/ worktree')
    parser.add_argument('--report', type=Path, help='write a local audit outside the source checkout')
    args = parser.parse_args()
    selected, excluded = source_files()
    report = check(selected, excluded)
    if args.report:
        report_path = args.report.resolve()
        if report_path == ROOT or ROOT in report_path.parents:
            raise ValueError('Local audits must stay outside public source')
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k not in ('files', 'excluded', 'groups')}, indent=2))
    if report['problems']:
        return 1
    if args.export:
        export(selected, args.export)
        print('PUBLIC_SOURCE_EXPORTED')
    return 0


if __name__ == '__main__':
    sys.exit(main())
