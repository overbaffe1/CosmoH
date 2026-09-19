import hashlib
import json
from pathlib import Path

import pytest
from tools.verify_submission import verify

ROOT = Path(__file__).resolve().parents[1]


def test_team_identity_and_clean_delivery_guidance():
    for name in ['web/calculator.html', 'web/index.html', 'web/showcase.html', 'README.md', 'GITVERSE.md']:
        assert 'ЛЕНИВЫЕ В ОРБИТЕ' in (ROOT/name).read_text()
    guide = (ROOT/'GITVERSE.md').read_text()
    assert 'credential.helper=' in guide
    assert 'kosmo-piter_lenivye_v_orbite_197.git' in guide
    assert 'arena/01a0b7c5-cosmoh' in guide
    assert 'не выполнена' in guide


def test_submission_integrity_and_tampering(tmp_path):
    (tmp_path/'README.md').write_text('team')
    manifest = {'format': 'fuel-contour-submission-v1', 'files': {
        'README.md': hashlib.sha256(b'team').hexdigest()}}
    (tmp_path/'SUBMISSION_MANIFEST.json').write_text(json.dumps(manifest))
    assert verify(tmp_path) == 1
    (tmp_path/'README.md').write_text('changed')
    with pytest.raises(ValueError, match='SHA256 mismatch'):verify(tmp_path)
    manifest['files'] = {'../outside': 'x'}
    (tmp_path/'SUBMISSION_MANIFEST.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='Unsafe'):verify(tmp_path)
