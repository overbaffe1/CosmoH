"""Read-only structural audit. Does not load pickle, run inference or edit submissions."""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import re


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(root, template=None):
    root = Path(root)
    file = root / 'submission_probe_35.csv'
    with file.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != ['chip_id', 'class_id', 'rle']:
            raise ValueError('Unexpected CSV header')
        rows = list(reader)
    keys, chips, intervals = set(), {}, {}
    row_counts, pixels = {'AF': 0, 'BS': 0}, {'AF': 0, 'BS': 0}
    for row in rows:
        cid = row['chip_id']
        if not re.fullmatch(r'(AF|BS)_te_\d{6}', cid):
            raise ValueError('Unexpected chip identifier')
        kind, cls = cid[:2], int(row['class_id'])
        allowed = {1} if kind == 'AF' else {1, 2, 3}
        if cls not in allowed or (cid, cls) in keys:
            raise ValueError('Invalid or duplicate class key')
        keys.add((cid, cls))
        chips.setdefault(cid, set()).add(cls)
        n = 256 ** 2 if kind == 'AF' else 512 ** 2
        if row['rle'] is None or None in row:
            raise ValueError('Missing/extra CSV values')
        vals = [int(x) for x in row['rle'].split()]
        if len(vals) % 2:
            raise ValueError('Odd number of RLE tokens')
        previous_end = 0
        for start, length in zip(vals[::2], vals[1::2]):
            end = start + length - 1
            if start < 1 or length <= 0 or end > n or (previous_end and start <= previous_end + 1):
                raise ValueError('RLE boundary, ordering or adjacency error')
            intervals.setdefault(cid, []).append((start, end))
            previous_end = end
            pixels[kind] += length
        row_counts[kind] += 1
    if row_counts != {'AF': 180, 'BS': 267} or len(chips) != 269:
        raise ValueError('Unexpected row/chip counts')
    for cid, classes in chips.items():
        if classes != ({1} if cid.startswith('AF') else {1, 2, 3}):
            raise ValueError('Missing class rows')
        runs = sorted(intervals.get(cid, []))
        if any(a[1] >= b[0] for a, b in zip(runs, runs[1:])):
            raise ValueError('Class masks overlap')
    template_status = 'NOT RUN: organizer template not present'
    if template is not None:
        with Path(template).open(encoding='utf-8-sig', newline='') as stream:
            reference = list(csv.DictReader(stream))
        expected = {(r['chip_id'], int(r['class_id'])) for r in reference}
        if expected != keys or len(expected) != len(reference):
            raise ValueError('Template keys differ or template has duplicates')
        template_status = 'PASS'
    return {
        'rows': len(rows), 'chips': len(chips), 'row_counts': row_counts,
        'pixel_counts': pixels, 'shape_AF': [256, 256], 'shape_BS': [512, 512],
        'structural_RLE_check': 'PASS', 'template_identity_check': template_status,
        'sha256': sha(file),
        'identical_to_TOPsubmission': sha(file) == sha(root / 'TOPsubmission.csv'),
        'identical_to_default_submission': sha(file) == sha(root / 'submission.csv'),
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive_root', type=Path)
    parser.add_argument('--template', type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(audit(args.archive_root, args.template), ensure_ascii=False, indent=2))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise SystemExit(f'FAIL: {exc}')
