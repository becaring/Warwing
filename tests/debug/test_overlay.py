"""Run with python -m unittest discover -s tests/debug -v."""
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'tools/prepare_debug_xdk.py'


class OverlayTests(unittest.TestCase):
    def test_restores_battle_debug_scenes_reproducibly(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'tests/debug') as temporary:
            output = Path(temporary) / 'overlay'
            for _ in range(2):
                run = subprocess.run([sys.executable, str(SCRIPT), '--output', str(output)], capture_output=True, text=True)
                self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
                files = {p.relative_to(output): p.read_bytes() for p in output.rglob('*') if p.is_file()}
                if _ == 0:
                    first = files
            self.assertEqual(first, files)
            manifest = json.loads((output / 'debug-manifest.json').read_text())
            self.assertEqual(len(manifest['files']), 8)
            menu = (output / 'decomp/src/db/dbmenu.c').read_text()
            self.assertIn('vsnprintf(sDBMenuStringBuffer', menu)
            self.assertNotIn('func_ovl8_80386BE0(sDBMenuStringBuffer, &str)', menu)
            stubs = (output / 'port/stubs/debug_stubs.c').read_text()
            self.assertNotIn('void dbBattleStartScene(void)', stubs)
            self.assertIn('void dbCubeStartScene(void)', stubs)
            self.assertEqual((output / 'decomp/src/sc/scmanager.c').read_text().count('portDebugBattleIsBootScene()'), 2)


if __name__ == '__main__':
    unittest.main()
