"""Determinism, unchanged-output stability and fail-closed source locks."""
from pathlib import Path
from unittest.mock import patch
import json,runpy
ROOT=Path(__file__).resolve().parents[2]
module=runpy.run_path(str(ROOT/'tools/prepare_resources_xdk.py'))
first=module['prepare']()
outputs=[module['OUT']/'generated'/p for p in first['output_hashes']]
times={p:p.stat().st_mtime_ns for p in outputs}
second=module['prepare']()
assert first==second
assert times=={p:p.stat().st_mtime_ns for p in outputs},'Unchanged files rewritten under sibling compiler'
relative=next(iter(first['source_locks']['lus']))
target=module['LUS']/relative
original=Path.read_bytes
def changed(self):
    data=original(self)
    return data+b'\n// drift probe\n' if self==target else data
with patch.object(Path,'read_bytes',changed):
    try:module['prepare']()
    except ValueError as error:assert 'Resource source SHA drift' in str(error)
    else:raise AssertionError('Changed source was accepted')
print('PASS resource generation deterministic, stable for concurrent readers, rejects source drift')
