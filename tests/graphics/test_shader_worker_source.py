import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]

class ShaderWorkerSourceTests(unittest.TestCase):
    def test_physical_worker_and_atomic_file(self):
        items=json.loads((ROOT/'scratch/application-xdk/native/project-items.json').read_text())['Smash360']
        by_path={item['path']:item for item in items}
        self.assertEqual(by_path['shipyard/sources/io/shader_worker.cpp']['shipyard_source'],
                         'sources/io/shader_worker.cpp')
        self.assertEqual(by_path['shipyard/sources/storage/atomic_file.cpp']['shipyard_source'],
                         'sources/storage/atomic_file.cpp')
        self.assertIn('platform/xbox360/runtime/shader_worker_adapter.cpp',by_path)
        self.assertIn('platform/xbox360/runtime/diagnostic_file_adapter.cpp',by_path)
        self.assertNotIn('scratch/runtime-xdk/shader_worker.cpp',by_path)
        self.assertNotIn('scratch/runtime-xdk/diagnostic_files.cpp',by_path)
        project=(ROOT/'platform/xbox360/Smash360.vcxproj').read_text()
        self.assertIn('$(ShipyardRoot)\\sources\\io\\shader_worker.cpp',project)
        self.assertIn('$(ShipyardRoot)\\sources\\storage\\atomic_file.cpp',project)
        self.assertFalse((ROOT/'scratch/runtime-xdk/shader_worker.cpp').exists())
        self.assertFalse((ROOT/'scratch/runtime-xdk/diagnostic_files.cpp').exists())
        generator=(ROOT/'tools/prepare_runtime_xdk.py').read_text()
        self.assertNotIn('save_worker.cpp',generator)
        self.assertNotIn('diagnostic_files.cpp',generator)

if __name__=='__main__':unittest.main()
