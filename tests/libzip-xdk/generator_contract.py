"""Source-lock rejection, deterministic output, and stable source mapping."""
from pathlib import Path
from unittest.mock import patch
import runpy
ROOT=Path(__file__).resolve().parents[2]
module=runpy.run_path(str(ROOT/'tools/prepare_libzip_xdk.py'))
first=module['prepare']()
files=[module['OUT']/name for name in first['outputs']]
times={p:p.stat().st_mtime_ns for p in files}
assert first==module['prepare']()
assert times=={p:p.stat().st_mtime_ns for p in files},'Unchanged generated files rewritten'
target=ROOT/next(iter(first['locks']['files']))
read=Path.read_bytes
def drift(self):
    data=read(self)
    return data+b'\n/* drift */\n' if self==target else data
with patch.object(Path,'read_bytes',drift):
    try:module['prepare']()
    except ValueError as error:assert 'source drift' in str(error)
    else:raise AssertionError('Changed source accepted')
assert '#line' in (module['OUT']/'zip_dirent.c').read_text()
print('PASS libzip/zlib source locks, deterministic mapping and unchanged output stability')
