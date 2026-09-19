"""Check an extracted delivery archive without dependencies, git or network access."""
import hashlib
import json
from pathlib import Path


def verify(root):
    root = Path(root).resolve()
    manifest = json.loads((root / 'SUBMISSION_MANIFEST.json').read_text(encoding='utf-8'))
    if manifest.get('format') != 'fuel-contour-submission-v1' or not manifest.get('files'):
        raise ValueError('Unknown or empty submission manifest')
    for name, expected in manifest['files'].items():
        path = (root / name).resolve()
        if Path(name).is_absolute() or not path.is_relative_to(root) or '..' in Path(name).parts:
            raise ValueError(f'Unsafe manifest path: {name}')
        if not path.is_file():
            raise ValueError(f'Missing file: {name}')
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f'SHA256 mismatch: {name}')
    return len(manifest['files'])


if __name__ == '__main__':
    try:
        count = verify(Path(__file__).resolve().parents[1])
    except (ValueError, OSError) as exc:
        raise SystemExit(f'FAIL submission: {exc}')
    print(f'PASS submission: {count} files match SHA256; this is not a GitVerse upload confirmation')
