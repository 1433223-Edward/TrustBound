"""Generate inert scale datasets; never execute generated Python."""
import argparse
import hashlib
import json
from pathlib import Path

p=argparse.ArgumentParser(__doc__)
p.add_argument('--out',type=Path,required=True)
p.add_argument('--config',type=Path,default=Path('benchmarks/configs/scale.json'))
a=p.parse_args()
cfg=json.loads(a.config.read_text(encoding='utf-8-sig'))
a.out.mkdir(parents=True,exist_ok=False)
for n in cfg['file_counts']:
    files={'main.py':'def solve(value):\n    return value + 1\n'}
    files.update({f'helper_{i}.py':f'VALUE = {i}\n' for i in range(1,n)})
    total=sum(len(v.encode()) for v in files.values())
    data=dict(files=[dict(path=k,content=v) for k,v in files.items()],plan=dict(revision=0,goal='Change solve to return value + 2',entrypoint='main.py:solve',allowed_write_paths=['main.py'],public_cases=[dict(input=0,expected=2)],acceptance_cases=[dict(input=-2,expected=0)],acceptance_basis='Reviewed integer addition contract'),metadata=dict(total_files=n,total_source_bytes=total,estimated_source_tokens=(total+3)//4,directory_depth=1,dependency_edges=0,expected_files_modified=1,source_hash=hashlib.sha256(json.dumps(files,sort_keys=True).encode()).hexdigest(),eligibility='UNSUPPORTED_FILE_COUNT' if n>20 else 'ELIGIBLE',task='Change solve to return value + 2',cases=[dict(input=0,expected=2),dict(input=-2,expected=0)]))
    (a.out/f'scale-{n}.json').write_text(json.dumps(data,indent=2),encoding='utf-8')
