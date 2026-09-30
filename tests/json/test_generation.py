"""Generator invariants: upstream identity, deterministic outputs, fail closed."""
from pathlib import Path
import hashlib
import runpy
import unittest
import uuid
ROOT=Path(__file__).resolve().parents[2]
import runpy as _shipyard_runpy

SHIPYARD_BASE = _shipyard_runpy.run_path(str(ROOT / "tools/platform_base.py"))["resolve"](ROOT)
MODULE=runpy.run_path(str(SHIPYARD_BASE / 'python/xbox360_platform/json/generate_algorithms.py'))
class Generation(unittest.TestCase):
    def setUp(self):
        self.folder=ROOT/'scratch/json-xdk/generator-tests'/uuid.uuid4().hex
        self.source=self.folder/'source'; self.output=self.folder/'output'
        for relative in ('detail/input/lexer.hpp','detail/conversions/to_chars.hpp'):
            target=self.source/'include/nlohmann'/relative
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes((SHIPYARD_BASE / 'third_party/nlohmann-3.12.0/include/nlohmann'/relative).read_bytes())
    def test_deterministic_and_mapped(self):
        first=MODULE['generate'](self.source,self.output)
        snapshots={p.name:p.read_bytes() for p in self.output.iterdir()}
        self.assertEqual(first,MODULE['generate'](self.source,self.output))
        self.assertEqual(snapshots,{p.name:p.read_bytes() for p in self.output.iterdir()})
        for data in snapshots.values():
            self.assertIn(b'#line 1 ',data)
            self.assertIn(b'SPDX-License-Identifier: MIT',data)
    def test_any_input_change_rejects_before_write(self):
        target=self.source/'include/nlohmann/detail/conversions/to_chars.hpp'
        target.write_bytes(target.read_bytes()+b'\n')
        with self.assertRaisesRegex(ValueError,'source mismatch'):
            MODULE['generate'](self.source,self.output)
        self.assertFalse(self.output.exists())
    def test_exact_anchor_count(self):
        with self.assertRaisesRegex(ValueError,'anchor changed'):
            MODULE['exact']('repeated repeated','repeated','replacement')
        self.assertEqual('after',MODULE['exact']('before','before','after'))
if __name__=='__main__':unittest.main()
