import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from platform_base import resolve

class DiagnosticsSourceTests(unittest.TestCase):
    def test_direct_queue_and_local_adapter(self):
        base = resolve(ROOT)
        items = json.loads((ROOT/'scratch/application-xdk/native/project-items.json').read_text())['Smash360']
        by_path = {item['path']: item for item in items}
        self.assertEqual(by_path['shipyard/sources/diagnostics/queue.cpp']['shipyard_source'],
                         'sources/diagnostics/queue.cpp')
        self.assertIn('platform/xbox360/runtime/diagnostics_adapter.cpp', by_path)
        self.assertNotIn('scratch/runtime-xdk/diagnostics.cpp', by_path)
        project = (ROOT/'platform/xbox360/Smash360.vcxproj').read_text()
        self.assertIn('$(ShipyardRoot)\\sources\\diagnostics\\queue.cpp', project)
        self.assertIn('platform\\xbox360\\runtime\\diagnostics_adapter.cpp', project)
        self.assertNotIn('scratch\\runtime-xdk\\diagnostics.cpp', project)
        self.assertNotIn('donor/platform.cpp', (ROOT/'tools/prepare_runtime_xdk.py').read_text())
        self.assertFalse((ROOT/'platform/xbox360/runtime/donor/platform.cpp').exists())
        self.assertFalse((ROOT/'scratch/runtime-xdk/diagnostics.cpp').exists())
        result = subprocess.run([sys.executable, '-B', str(base/'tests/test_diagnostic_queue.py')],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

if __name__ == '__main__': unittest.main()
