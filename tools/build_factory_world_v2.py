# /// script
# requires-python = ">=3.12"
# dependencies = ["pydantic>=2.10,<3"]
# ///
# Run: backend/.venv/bin/python tools/build_factory_world_v2.py --output <new-path.json>
"""Generate, physically admit, then publish one explicit synthetic world artifact.

No legacy global output paths or implicit overwrite. Standard-library CLI matches
repository tooling and avoids installing another CLI runtime for local generation.
"""
import argparse
import json
import os
import sys
import tempfile
from hashlib import sha256
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'backend')]
from app.operations.world_spatial_geometry import validate_factory_layout
from app.operations.world_layout_requirements import LayoutRequirements
from app.operations.world_types import WorldContractError,require
from tools.factory_world.assembly import assemble


def guarded_output(path: Path, replace_owned: bool) -> Path:
    candidate=path.absolute()
    for ancestor in (candidate,*candidate.parents):
        require(not ancestor.is_symlink(),'output_symlink',str(ancestor))
    candidate=candidate.resolve()
    protected=(ROOT/'shared/factory-layout.json',ROOT/'shared/factory-campus.json',
               ROOT/'shared/coverage-registry.json',ROOT/'shared/asset-requirements.json')
    require(candidate.resolve() not in protected,'protected_output',str(candidate))
    if candidate.exists():
        require(replace_owned and candidate.is_relative_to(ROOT/'.omo/evidence'),'output_exists',str(candidate))
        marker=candidate.with_suffix(candidate.suffix+'.owner.json')
        require(marker.is_file() and not marker.is_symlink(),'output_owner',str(candidate))
        try:
            data=json.loads(marker.read_text())
        except (json.JSONDecodeError,UnicodeDecodeError) as error:
            raise WorldContractError('output_owner',str(marker)) from error
        require(data=={'generator':'factory-world-v2','path':str(candidate),
                      'sha256':sha256(candidate.read_bytes()).hexdigest()},'output_owner',str(candidate))
    return candidate


def publish(path: Path, raw: bytes, replace_owned: bool) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent,prefix='.factory-world-',delete=False) as handle:
        temporary=Path(handle.name)
        handle.write(raw);handle.flush();os.fsync(handle.fileno())
    try:
        if replace_owned and path.exists(): os.replace(temporary,path)
        else: os.link(temporary,path)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--replace-owned',action='store_true',help='Replace only matching marker+bytes under .omo/evidence')
    args=parser.parse_args()
    output=guarded_output(args.output,args.replace_owned)
    marker=output.with_suffix(output.suffix+'.owner.json')
    proof_path=output.with_suffix(output.suffix+'.proof.json')
    for companion in (marker,proof_path):
        require(not companion.is_symlink(),'output_symlink',str(companion))
        require(not companion.exists() or (args.replace_owned and output.exists()),'output_exists',str(companion))
    requirements=LayoutRequirements.read(ROOT)
    raw=assemble(ROOT).model_dump_json(indent=2).encode('utf8')+b'\n'
    proof=validate_factory_layout(raw,requirements)
    report={'raw_sha256':proof.raw_sha256,'requirements_sha256':proof.requirements_sha256,
        'requirement_sources':dict(requirements.source_hashes),'coverage':dict(proof.coverage),
        'swept_checks':proof.swept_checks,'registered_crossings':proof.registered_crossings,
        'boundary':'synthetic design admission; not engineering certification, GLB fit or dynamic reservation execution'}
    publish(output,raw,args.replace_owned)
    publish(proof_path,(json.dumps(report,indent=2)+'\n').encode(),args.replace_owned)
    publish(marker,(json.dumps({'generator':'factory-world-v2','path':str(output),'sha256':proof.raw_sha256},indent=2)+'\n').encode(),args.replace_owned)
    print(json.dumps({'output':str(output),'proof':str(proof_path),**report}))
    return 0


if __name__=='__main__':
    try:
        raise SystemExit(main())
    except WorldContractError as error:
        print(str(error),file=sys.stderr)
        raise SystemExit(2) from error
