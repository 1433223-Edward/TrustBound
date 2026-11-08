"""Hash manifests detect missing or modified raw evidence; not authenticity signatures."""
import hashlib
import json
from pathlib import Path


def seal(directory):
    directory=Path(directory)
    rows={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in directory.iterdir() if p.is_file() and p.name!='integrity.json'}
    with (directory/'integrity.json').open('x',encoding='utf-8') as stream:
        json.dump(rows,stream,indent=2)


def verify(directory):
    directory=Path(directory)
    rows=json.loads((directory/'integrity.json').read_text(encoding='utf-8'))
    actual={p.name for p in directory.iterdir() if p.is_file() and p.name!='integrity.json'}
    if actual!=set(rows):raise ValueError(f'{directory}: missing or extra evidence files')
    for name,digest in rows.items():
        if Path(name).name!=name or hashlib.sha256((directory/name).read_bytes()).hexdigest()!=digest:
            raise ValueError(f'{directory}: evidence hash mismatch: {name}')
    return rows
