"""Deterministic standalone submission ZIP; no upload, credentials or git metadata."""
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[1]


def package(output=None):
    output=Path(output or ROOT/'results/fuel-contour-submission.zip')
    output.parent.mkdir(parents=True,exist_ok=True)
    repo=Path(subprocess.check_output(['git','rev-parse','--show-toplevel'],cwd=ROOT,text=True).strip())
    names=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z',str(ROOT.relative_to(repo))],cwd=repo).decode().split('\0')
    files={}
    for name in filter(None,names):
        path=repo/name
        if path.is_file():
            files[path.relative_to(ROOT).as_posix()]=path.read_bytes()
    for name in ['summary.json','comparison.csv','decision_brief.json']:
        path=ROOT/'results'/name
        if not path.exists():
            raise SystemExit('Run python -m fuel.cli suite before packaging')
        files['results/'+name]=path.read_bytes()
    for strategy in ['earth','lunar']:
        for path in sorted((ROOT/'results'/strategy).rglob('*')):
            if path.is_file():files[path.relative_to(ROOT).as_posix()]=path.read_bytes()
    workflow=(repo/'.github/workflows/fuel-contour.yml').read_text()
    workflow=workflow.replace("paths: ['solutions/fuel-contour/**', '.github/workflows/fuel-contour.yml']", "paths: ['**']")
    workflow=workflow.replace('working-directory: solutions/fuel-contour','working-directory: .').replace('path: solutions/fuel-contour/results','path: results')
    files['.github/workflows/fuel-contour.yml']=workflow.encode()
    revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
    manifest={'format':'fuel-contour-submission-v1','source_git_revision':revision,
              'note':'Content SHA256 is authoritative; GitVerse upload must be performed by project owner. Known upstream reference error is documented, not suppressed.',
              'files':{name:hashlib.sha256(data).hexdigest() for name,data in sorted(files.items())}}
    files['SUBMISSION_MANIFEST.json']=(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode()
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for name,data in sorted(files.items()):
            info=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.create_system=3
            info.external_attr=(0o100755 if name.endswith('.sh') else 0o100644)<<16
            archive.writestr(info,data)
    print(f'Packaged {len(files)} files: {output} ({output.stat().st_size} bytes)')
    return output

if __name__=='__main__':package()
