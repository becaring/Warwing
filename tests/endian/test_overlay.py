"""Run with python -m unittest discover -s tests/endian -v."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'tools/prepare_endian_xdk.py'

class OverlayTests(unittest.TestCase):
    def test_pinned_source_overlay_is_reproducible_and_mapped(self):
        self.assertTrue(SCRIPT.is_file(), 'endian overlay generator is not implemented')
        with tempfile.TemporaryDirectory(dir=ROOT/'tests/endian') as temporary:
            output = Path(temporary)/'overlay'
            run = subprocess.run([sys.executable,str(SCRIPT),'--output',str(output)],capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stdout+run.stderr)
            manifest = json.loads((output/'endian-manifest.json').read_text())
            self.assertEqual(len(manifest['files']),9)
            before = {p.relative_to(output):p.read_bytes() for p in output.rglob('*') if p.is_file()}
            run = subprocess.run([sys.executable,str(SCRIPT),'--output',str(output)],capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stdout+run.stderr)
            self.assertEqual(before,{p.relative_to(output):p.read_bytes() for p in output.rglob('*') if p.is_file()})
            for row in manifest['files']:
                self.assertEqual(hashlib.sha256((ROOT/'upstream/BattleShip'/row['path']).read_bytes()).hexdigest(), row['source_sha256'])
                self.assertEqual(hashlib.sha256((output/row['path']).read_bytes()).hexdigest(), row['output_sha256'])
                self.assertIn(b'#line 1 ',(output/row['path']).read_bytes())

    def test_source_drift_rejects_before_writing_any_overlay(self):
        self.assertTrue(SCRIPT.is_file(), 'endian overlay generator is not implemented')
        lock=json.loads((ROOT/'platform/xbox360/endian/source-lock.json').read_text())
        with tempfile.TemporaryDirectory(dir=ROOT/'tests/endian') as temporary:
            temporary=Path(temporary); source=temporary/'source'; output=temporary/'overlay'
            for relative in lock:
                target=source/relative; target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes((ROOT/'upstream/BattleShip'/relative).read_bytes())
            (source/'decomp/include/config.h').write_text('/* changed source */\n')
            run=subprocess.run([sys.executable,str(SCRIPT),'--source-root',str(source),'--output',str(output)],capture_output=True,text=True)
            self.assertNotEqual(run.returncode,0)
            self.assertIn('source hash mismatch',run.stderr)
            self.assertFalse(output.exists(), 'must validate every input before writing output')

    def test_refuses_source_tree_output(self):
        self.assertTrue(SCRIPT.is_file(), 'endian overlay generator is not implemented')
        run=subprocess.run([sys.executable,str(SCRIPT),'--output',str(ROOT/'upstream/BattleShip/unsafe-overlay')],capture_output=True,text=True)
        self.assertNotEqual(run.returncode,0)
        self.assertIn('output must not overlap',run.stderr)

if __name__=='__main__': unittest.main()
