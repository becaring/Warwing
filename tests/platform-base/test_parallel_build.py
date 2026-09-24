"""Production Smash projects must shard their real source/object inventory."""

from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import build_parallel_xdk


class ParallelBuildTests(unittest.TestCase):
    def test_both_projects_use_exact_generated_items_and_objects(self):
        for name, expected in (('Libultraship360', 140), ('Smash360', 112)):
            with self.subTest(name=name):
                planned = build_parallel_xdk.project_plan(name, jobs=8)
                self.assertEqual(len(planned.sources), expected)
                self.assertEqual(len(planned.shards), 8)
                self.assertEqual(
                    {str(row.object) for row in planned.sources},
                    {str(ROOT/'scratch/application-xdk/native/obj'/name /
                         ('%04d_%s.obj' % (index, Path(item['path']).stem)))
                     for index, item in enumerate(build_parallel_xdk.items(name))},
                )
                physical = [row for row in planned.sources
                            if row.source.is_relative_to(build_parallel_xdk.PLATFORM_BASE)]
                if name == 'Smash360':
                    self.assertTrue(physical)
                    self.assertIn('shipyard/sources/diagnostics/queue.cpp',
                                  {item['path'] for item in build_parallel_xdk.items(name)})
                self.assertEqual(sum(len(shard.sources) for shard in planned.shards), expected)

    def test_shard_projects_remain_until_link_receipt_is_verified(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output/'build').mkdir()
            (output/'build/Libultraship360.lib').write_bytes(b'library')
            planned = SimpleNamespace(output=output/'parallel', sources=(), shards=())
            planned.output.mkdir()
            view = SimpleNamespace(project=output/'link.vcxproj')
            events = []
            receipt = {'builds': (), 'build_exit': 0}
            with (patch.object(build_parallel_xdk, 'OUT', output),
                  patch.object(build_parallel_xdk, 'project_plan', return_value=planned),
                  patch.object(build_parallel_xdk.parallel_build, 'run', return_value=receipt),
                  patch.object(build_parallel_xdk.parallel_build, 'plan_link_view',
                               side_effect=lambda *_: events.append('plan-link') or view),
                  patch.object(build_parallel_xdk.parallel_build, 'write_link_view'),
                  patch.object(build_parallel_xdk.parallel_build, 'remove_link_view'),
                  patch.object(build_parallel_xdk.parallel_build, 'verify_receipt',
                               side_effect=lambda *_: events.append('verify')),
                  patch.object(build_parallel_xdk.parallel_build, 'remove_shards',
                               side_effect=lambda *_: events.append('remove-shards')),
                  patch.object(build_parallel_xdk.subprocess, 'run',
                               return_value=SimpleNamespace(returncode=0))):
                self.assertEqual(build_parallel_xdk.build_project('Libultraship360'), 0)
            self.assertEqual(events, ['plan-link', 'verify', 'remove-shards'])


if __name__ == '__main__':
    unittest.main()
