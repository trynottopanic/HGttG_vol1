#!/usr/bin/env python3
"""Maintain public UTF-8 documentation without publishing or inspecting history.
SPDX-License-Identifier: AGPL-3.0-or-later
"""
import argparse
from collections import Counter, defaultdict
import html
from pathlib import Path
import re
import sys
import textwrap
from urllib.parse import quote, unquote, urlsplit

import publication

ROOT = publication.ROOT
CATALOGUE = 'docs/CATALOG.md'
HANDBOOK = 'docs/HANDBOOK.md'
PLAIN_EDITION = 'docs/HANDBOOK.txt'
GENERATED = {CATALOGUE, PLAIN_EDITION}
NON_PROSE = {'requirements.txt', 'cmakelists.txt'}
GROUPS = (
    'Current project and development guides',
    'Project foundations',
    'Architecture and contracts',
    'Components and reference implementations',
    'Design and artwork references',
    'Historical evidence and investigations',
    'Licensing and third-party notices',
)
# Follow links from maintained entry points, not every dated investigation.
# Their targets and heading anchors are still verified, including older specs.
ENTRY_POINTS = {
    'README.md', 'CONTRIBUTING.md', 'PUBLICATION.md', 'LICENSE.md',
    'GuideOS/README.md', 'GuideOS/docs/README.md',
    'HHG_Foundation/README.md', 'prototypes/README.md',
    'GuideOS/node/desktop/README.md',
    'GuideOS/board/rg35xxh/debian/shell0/README.md',
    'GuideOS/package/guide-media/README.md',
    'GuideOS/design/atlas/README.md',
    'GuideOS/design/ui-theme-drafts/README.md',
    'GuideOS/design/handoff/field-theme-1/README.md',
    'GuideOS/design/notepad-drafts/2026-10-03-v1/README.md',
    'GuideOS/docs/FILE_BROWSER_UI_0.md',
    'GuideOS/docs/FILE_BROWSER_FOLDER_UI_0.md',
    'GuideOS/docs/FILE_BROWSER_LOCATIONS_UI_0.md',
    'GuideOS/docs/RELEASE_0_3_7_HANDOFF.md',
    'GuideOS/docs/RELEASE_0_3_9_HANDOFF.md',
}
HISTORY = re.compile(
    r'(?:^BUILD_|^RELEASE_|^DEBIAN_|^README_HISTORY|^BASELINE|^BUILDING|'
    r'BACKLOG|HANDOFF|EVIDENCE|AUDIT|INVESTIGATION|PHYSICAL|CAPTURE|'
    r'FAILURE|RESULT|FOLLOWUP|_TEST|_TESTS|^EVIDENCE_|'
    r'\d{4}[-_]\d{2}[-_]\d{2}|_0_[34]_\d|^DIAGNOSTIC[^S_]|'
    r'^DIAGNOSTIC3|^ANBERNIC_FAILSAFE|^AUDIO_(?:CAUSE|CODEC|FORMAT|FIFO|FLOW|'
    r'BUFFER|DMA|MUTE|OUTPUT)|^BOOT_ANIMATION_(?:TIMING|INTEGRATION)|'
    r'^EXTERNAL_CARD_RECOGNITION|^UI_SCHEMA_AUDIO|^WINDOWS_UI_KNOWN|'
    r'^SUPERVISOR_CAPABILITY_IMPLEMENTATION_EVIDENCE)', re.I)
FENCE = re.compile(r'^ {0,3}(`{3,}|~{3,})(.*)$')
INLINE_CODE = re.compile(r'(`+)(.+?)\1', re.S)
DEFINITION = re.compile(r'^ {0,3}\[([^\]]+)\]:\s*(\S+)(?:\s+.*)?$', re.M)


def prose_file(name):
    path = Path(name)
    return path.suffix.lower() in {'.md', '.txt'} and path.name.lower() not in NON_PROSE


def read_prose(selected):
    documents, problems = {}, []
    for name in selected:
        if not prose_file(name):
            continue
        path = ROOT / name
        if path.is_symlink() or not path.is_file() or ROOT.resolve() not in path.resolve().parents:
            problems.append(name + ': not a regular file within the public checkout')
            continue
        data = path.read_bytes()
        if b'\0' in data:
            problems.append(name + ': contains NUL bytes')
        try:
            documents[name] = data.decode('utf-8-sig').replace('\r\n', '\n').replace('\r', '\n')
        except UnicodeDecodeError as error:
            problems.append(name + ': invalid UTF-8 at byte ' + str(error.start))
    return documents, problems


def balanced(text, start, opening, closing):
    depth, position = 1, start + 1
    while position < len(text):
        if text[position] == '\\':
            position += 2
            continue
        if text[position] == opening:
            depth += 1
        elif text[position] == closing:
            depth -= 1
            if depth == 0:
                return position
        position += 1
    return None


def destination(raw):
    raw = raw.strip()
    if raw.startswith('<'):
        end = raw.find('>')
        return raw[1:end] if end >= 0 else raw
    # Optional Markdown link titles are not part of the path.
    return re.split(r'\s+[\'\"]', raw, maxsplit=1)[0].strip()


def links(text):
    """Yield ordinary/image/reference links, including balanced target brackets."""
    definitions = {label.casefold(): destination(target)
                   for label, target in DEFINITION.findall(text)}
    position = 0
    while position < len(text):
        start = text.find('[', position)
        if start < 0:
            break
        end = balanced(text, start, '[', ']')
        if end is None:
            break
        label, target, finish = text[start + 1:end], None, end + 1
        if finish < len(text) and text[finish] == '(':
            last = balanced(text, finish, '(', ')')
            if last is not None:
                target, finish = destination(text[finish + 1:last]), last + 1
        elif finish < len(text) and text[finish] == '[':
            last = balanced(text, finish, '[', ']')
            if last is not None:
                ref = text[finish + 1:last] or label
                target, finish = definitions.get(ref.casefold()), last + 1
        elif finish >= len(text) or text[finish] != ':':
            target = definitions.get(label.casefold())
        if target is not None:
            yield start, finish, label, target
        position = max(finish, end + 1)


def plain_inline(text):
    # Protect inline code so paths, underscores and operators survive unchanged.
    code = []
    def protect(match):
        code.append(match.group(2))
        return '\x01' + str(len(code) - 1) + '\x02'
    text = INLINE_CODE.sub(protect, text)
    found = list(links(text))
    for start, end, label, target in reversed(found):
        if start and text[start - 1] == '!':
            start -= 1
        text = text[:start] + label + ' (' + target + ')' + text[end:]
    text = re.sub(r'(\*\*|__)(?=\S)(.+?)(?<=\S)\1', r'\2', text)
    text = re.sub(r'(?<![\w*])\*(?=\S)(.+?)(?<=\S)\*(?!\*)', r'\1', text)
    text = re.sub(r'(?<![\w_])_(?=\S)(.+?)(?<=\S)_(?!\w)', r'\1', text)
    text = re.sub(r'~~(?=\S)(.+?)(?<=\S)~~', r'\1', text)
    text = re.sub(r'\\([\\`*{}\[\]()#+.!_>\-])', r'\1', text)
    text = re.sub(r'\x01(\d+)\x02', lambda match: code[int(match.group(1))], text)
    return html.unescape(text)


def plain_text(markdown):
    """Readable edition: preserve wording, link paths and verbatim code content."""
    lines, fence = [], None
    source = markdown.splitlines()
    index = 0
    divider = re.compile(r'\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*')
    def cells(row):
        return [plain_inline(cell.strip()) for cell in re.split(r'(?<!\\)\|', row.strip().strip('|'))]
    while index < len(source):
        line = source[index]
        index += 1
        match = FENCE.match(line)
        if fence:
            if match and match.group(1)[0] == fence[0] and len(match.group(1)) >= len(fence) and not match.group(2).strip():
                fence = None
            else:
                lines.append(line)
            continue
        if match:
            fence = match.group(1)
            language = match.group(2).strip()
            if language:
                lines.append('Code (' + language + '):')
            continue
        if line.startswith('    ') or line.startswith('\t'):
            lines.append(line)
        elif '|' in line and index < len(source) and divider.fullmatch(source[index]):
            headers = cells(line)
            lines.extend([' — '.join(headers), ''])
            index += 1
            while index < len(source) and '|' in source[index] and source[index].strip():
                row = cells(source[index])
                index += 1
                record = row[0] + ': ' + row[1] if len(row) == 2 else row[0] + ': ' + '; '.join(
                    (headers[column] + ': ' if column < len(headers) else '') + value
                    for column, value in enumerate(row[1:], 1))
                lines.extend(textwrap.wrap(record, width=88, subsequent_indent='  ',
                                           break_long_words=False, break_on_hyphens=False))
                lines.append('')
        else:
            line = re.sub(r'^ {0,3}#{1,6}\s+(.+?)\s*#*\s*$', r'\1', line)
            lines.append(plain_inline(line))
    return '\n'.join(lines).rstrip() + '\n'


def group_for(name):
    path = Path(name)
    if name == 'LICENSE.md' or name.startswith('LICENSES/') or re.search(r'(?:LICENSE|UPSTREAM|SOURCES)', path.name, re.I):
        return GROUPS[6]
    if name.startswith('HHG_Foundation/'):
        return GROUPS[1]
    if name.startswith('docs/') or '/' not in name or name.startswith('.github/') or name in {'GuideOS/README.md', 'GuideOS/docs/README.md', 'prototypes/README.md'}:
        return GROUPS[0]
    if name.startswith('GuideOS/design/'):
        return GROUPS[4]
    if HISTORY.search(path.stem):
        return GROUPS[5]
    if len(path.parts) == 2 and path.parts[0] == 'GuideOS':
        return GROUPS[2]
    if 'CONTRACT' in path.stem or 'DESIGN' in path.stem or 'PROPOSAL' in path.stem:
        return GROUPS[2]
    return GROUPS[3]


def document_title(name, text):
    titles = {
        'HHG_Foundation/02_GUIDE_AND_PROTOTYPE_DEFINITION.txt': 'Project definition and prototype goals',
        'HHG_Foundation/03_DESIGN_PHILOSOPHY.txt': 'Design philosophy',
        '.github/PULL_REQUEST_TEMPLATE.md': 'Pull request template',
    }
    if name in titles:
        return titles[name]
    if name.lower().endswith('.md'):
        for line in text.splitlines():
            match = re.match(r'^#{1,6}\s+(.+?)\s*#*\s*$', line)
            if match:
                # Link targets belong in the catalogue path, not its title.
                title = match.group(1)
                for start, end, label, _ in reversed(list(links(title))):
                    title = title[:start] + label + title[end:]
                return plain_inline(title)
    return Path(name).name


def catalogue(documents):
    retained = sorted(name for name in documents if name not in GENERATED)
    groups = defaultdict(list)
    for name in retained:
        groups[group_for(name)].append(name)
    result = [
        '# Documentation catalogue', '',
        'Generated from the public source selection. Edit the source documents, then run',
        '`python3 -B tools/repository/documentation.py --write` to refresh this catalogue.', '',
        'Start with the [documentation index](README.md) and [project handbook](HANDBOOK.md).',
        'The [plain-text handbook edition](HANDBOOK.txt) contains the same handbook content.', '',
        f'This catalogue links {len(retained)} retained Markdown and plain-text documents.',
        'Document titles and groups help navigation; dated evidence and draft status remain',
        'authoritative within each document. Requirements and CMake input files are omitted.', '',
    ]
    for group in GROUPS:
        result.extend(['## ' + group, ''])
        if group == GROUPS[5]:
            result.extend(['Use the [history guide](HISTORY.md) for context before interpreting older status claims.', ''])
        for name in groups[group]:
            title = document_title(name, documents[name]).replace('\\', '\\\\').replace('[', '\\[').replace(']', '\\]')
            target = '../' + name if not name.startswith('docs/') else name[len('docs/'):]
            target = quote(target, safe='/._-')
            result.append(f'- [{title}]({target}) — `{name}`')
        if not groups[group]:
            result.append('No retained documents in this group.')
        result.append('')
    return '\n'.join(result).rstrip() + '\n'


def outside_code(text, mask_inline=True):
    lines, fence = [], None
    for line in text.splitlines(keepends=True):
        match = FENCE.match(line.rstrip('\r\n'))
        if fence:
            if match and match.group(1)[0] == fence[0] and len(match.group(1)) >= len(fence) and not match.group(2).strip():
                fence = None
            lines.append('\n' if line.endswith('\n') else '')
        elif match:
            fence = match.group(1)
            lines.append('\n' if line.endswith('\n') else '')
        elif line.startswith('    ') or line.startswith('\t'):
            lines.append('\n' if line.endswith('\n') else '')
        else:
            lines.append(INLINE_CODE.sub(lambda item: ' ' * len(item.group(0)), line) if mask_inline else line)
    return ''.join(lines)


def heading_anchors(text):
    # GitHub-style heading ids: punctuation removed, spaces replaced, duplicates suffixed.
    visible = outside_code(text, mask_inline=False)
    anchors = set(re.findall(r'<a\s+[^>]*(?:id|name)=[\'\"]([^\'\"]+)[\'\"]', visible, re.I))
    used = Counter()
    lines = visible.splitlines()
    for index, line in enumerate(lines):
        match = re.match(r'^ {0,3}#{1,6}\s+(.+?)\s*#*\s*$', line)
        heading = match.group(1) if match else None
        if heading is None and index + 1 < len(lines) and line.strip() and re.fullmatch(r' {0,3}(?:=+|-+)\s*', lines[index + 1]):
            heading = line.strip()
        if heading is None:
            continue
        for start, end, label, _ in reversed(list(links(heading))):
            heading = heading[:start] + label + heading[end:]
        heading = re.sub(r'<[^>]+>', '', plain_inline(heading)).lower()
        slug = ''.join(char for char in heading if char.isalnum() or char in '_- ').replace(' ', '-')
        anchor = slug + ('-' + str(used[slug]) if used[slug] else '')
        used[slug] += 1
        anchors.add(anchor)
    return anchors


def check_links(selected, documents):
    problems, checked = [], 0
    entries = ENTRY_POINTS | {name for name in documents if name.startswith('docs/') and name.endswith('.md')}
    selected_set = set(selected)
    anchors = {}
    for name in sorted(entries):
        if name not in documents:
            problems.append(name + ': required documentation entry point is absent from public selection')
            continue
        text = outside_code(documents[name])
        for start, _, _, raw in links(text):
            target = urlsplit(raw)
            if target.scheme or target.netloc:
                continue
            checked += 1
            line = text.count('\n', 0, start) + 1
            prefix = f'{name}:{line}: '
            path = (ROOT / name).parent / unquote(target.path) if target.path else ROOT / name
            resolved = path.resolve()
            try:
                relative = resolved.relative_to(ROOT.resolve()).as_posix()
            except ValueError:
                problems.append(prefix + 'relative link leaves the public checkout: ' + raw)
                continue
            if not path.exists() or path.is_symlink():
                problems.append(prefix + 'missing or linked target: ' + raw)
                continue
            if path.is_file() and relative not in selected_set:
                problems.append(prefix + 'target is outside the public source selection: ' + raw)
                continue
            if path.is_dir() and not any(item.startswith(relative.rstrip('/') + '/') for item in selected_set):
                problems.append(prefix + 'directory has no selected public files: ' + raw)
                continue
            if target.fragment:
                if relative not in documents:
                    problems.append(prefix + 'cannot check non-prose heading anchor: ' + raw)
                    continue
                if relative not in anchors:
                    anchors[relative] = heading_anchors(documents[relative])
                if unquote(target.fragment) not in anchors[relative]:
                    problems.append(prefix + 'missing heading anchor: ' + raw)
    return len(entries), checked, problems


def write_generated(name, text):
    path = ROOT / name
    if path.is_symlink() or path.parent.is_symlink() or ROOT.resolve() not in path.resolve().parents:
        raise ValueError('Unsafe generated destination: ' + name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8', newline='\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--write', action='store_true', help='refresh catalogue/plain handbook, then check')
    mode.add_argument('--check', action='store_true', help='check public prose, generated freshness and entry-point links')
    args = parser.parse_args()
    selected, _ = publication.source_files()
    documents, problems = read_prose(selected)
    if HANDBOOK not in documents:
        problems.append(HANDBOOK + ': canonical handbook is absent or unreadable')
    if problems:
        for problem in problems:
            print(problem, file=sys.stderr)
        return 1
    generated = {CATALOGUE: catalogue(documents), PLAIN_EDITION: plain_text(documents[HANDBOOK])}
    if args.write:
        for name, text in generated.items():
            write_generated(name, text)
        selected, _ = publication.source_files()
        documents, problems = read_prose(selected)
    for name, expected in generated.items():
        path = ROOT / name
        if name not in documents or path.read_bytes() != expected.encode('utf-8'):
            problems.append(name + ': generated content is stale; run documentation.py --write')
    entries, checked, link_problems = check_links(selected, documents)
    problems.extend(link_problems)
    if problems:
        for problem in problems:
            print(problem, file=sys.stderr)
        print(f'FAIL: {len(problems)} documentation problem(s).', file=sys.stderr)
        return 1
    print(f'PASS: {len(documents)} UTF-8 prose files, {entries} entry points, {checked} relative links; generated editions current.')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, RuntimeError, ValueError) as error:
        print('FAIL: ' + str(error), file=sys.stderr)
        sys.exit(1)
