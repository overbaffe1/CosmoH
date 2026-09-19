import hashlib
import json
from pathlib import Path
root = Path(__file__).resolve().parents[1]
expected = json.loads((root/'vendor-manifest.json').read_text())
actual = {p.relative_to(root/'vendor/test_oil').as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'vendor/test_oil').rglob('*') if p.is_file() and '__pycache__' not in p.parts}
assert actual == expected, 'Organizer snapshot differs from pinned SHA256 manifest'
print(f'PASS immutable organizer snapshot: {len(actual)} files')
