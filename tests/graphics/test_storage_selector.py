"""The active storage adapter compiles the pinned Shipyard selector directly."""
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from platform_base import resolve


class StorageSelectorTests(unittest.TestCase):
    def test_direct_source_and_host_contract(self):
        base = resolve(ROOT)
        items = json.loads((ROOT / 'scratch/application-xdk/native/project-items.json').read_text())['Smash360']
        canonical = [item for item in items if item['path'] == 'shipyard/sources/storage/device.cpp']
        self.assertEqual(len(canonical), 1)
        self.assertEqual(canonical[0]['input'], 'platform_base:sources/storage/device.cpp')
        self.assertIn('platform/xbox360/runtime/storage_adapter.cpp', [item['path'] for item in items])
        self.assertNotIn('scratch/runtime-xdk/storage.cpp', [item['path'] for item in items])
        project = (ROOT / 'platform/xbox360/Smash360.vcxproj').read_text()
        self.assertIn('$(ShipyardRoot)\\sources\\storage\\device.cpp', project)
        self.assertIn('$(SmashSourceRoot)platform\\xbox360\\runtime\\storage_adapter.cpp', project)
        self.assertNotIn('scratch\\runtime-xdk\\storage.cpp', project)
        self.assertFalse((ROOT / 'scratch/runtime-xdk/storage.cpp').exists())
        adapter = (ROOT / 'platform/xbox360/runtime/storage_adapter.cpp').read_text()
        self.assertIn('Shipyard::Storage::SelectAndMount(policy, display)', adapter)
        self.assertNotIn('XShowDeviceSelectorUI', adapter)
        runtime_projection = (ROOT / 'tools/prepare_runtime_xdk.py').read_text()
        self.assertNotIn('storage_selector_events.h', runtime_projection)
        self.assertNotIn('"storage.cpp", storage', runtime_projection)
        result = subprocess.run([sys.executable, '-B', str(base / 'tests/test_storage_device.py')],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__=='__main__':unittest.main()
