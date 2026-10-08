"""Small local media catalog and explicit output selection for the first audio provider."""
import hashlib
from itertools import islice
import json
from pathlib import Path

EXTENSIONS = {'.wav', '.flac', '.ogg', '.mp3'}


def catalog(directory):
    root = Path(directory).resolve()
    rows = []
    if not root.is_dir():
        return rows
    for path in sorted(islice(root.iterdir(), 512), key=lambda p: p.name.lower()):
        if len(rows) >= 128:
            break
        if path.is_symlink() or not path.is_file() or path.suffix.lower() not in EXTENSIONS:
            continue
        if path.stat().st_size > 2 * 1024**3:
            continue
        rows.append(dict(id=hashlib.sha256(path.name.encode()).hexdigest()[:24],
                         title=''.join(c for c in path.stem if c.isprintable())[:100],
                         path=str(path)))
    return rows


def outputs_from_dump(values):
    rows = []
    for item in values:
        props = item.get('info', {}).get('props', {})
        name = props.get('node.name')
        if item.get('type') != 'PipeWire:Interface:Node' or props.get('media.class') != 'Audio/Sink':
            continue
        if not isinstance(name, str) or len(name) > 256:
            continue
        rows.append(dict(id=name, title=str(props.get('node.description', name))[:100],
                         bluetooth=name.startswith('bluez_output.'), node_id=item.get('id')))
    return rows[:64]


def selected_path(rows, identity, directory):
    row = next((r for r in rows if r['id'] == identity), None)
    if row is None:
        raise ValueError('File no longer available')
    path = Path(row['path'])
    if path.is_symlink() or path.resolve().parent != Path(directory).resolve() or not path.is_file():
        raise ValueError('File no longer available')
    return path


def atomic_json(path, value):
    path = Path(path)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=True))
    temporary.replace(path)
