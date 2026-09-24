"""Smash combiner lookup split against its pinned three-field behavior."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from platform_base import resolve
BASE = resolve(ROOT)
sys.path.insert(0, str(BASE / 'python'))
sys.path.insert(0, str(BASE / 'tests'))
from xbox360_platform import combiner_lookup
from combiner_lookup_contract import exercise
import combiner_lookup_projection
import profile_projections


class SmashCombinerLookupTests(unittest.TestCase):
    def test_real_three_field_lookup_and_adapter(self):
        self.assertIs(combiner_lookup_projection.transform, combiner_lookup.transform)
        self.assertIs(combiner_lookup_projection.header, combiner_lookup.header)
        header = (ROOT / 'upstream/BattleShip/libultraship/include/fast/interpreter.h').read_text(encoding='utf-8-sig')
        source = (ROOT / 'upstream/BattleShip/libultraship/src/fast/interpreter.cpp').read_text(encoding='utf-8-sig')
        exercise(self, source, header, combiner_lookup_projection.transform(source),
                 ROOT / 'scratch/fast3d-combiner-lookup-contract',
                 ('{1,2,3}', '{1,2,5}', '{2,2,3}', '{1,4,3}'))

    def test_profiling_scope_stays_on_warm_entry(self):
        source = (ROOT / 'upstream/BattleShip/libultraship/src/fast/interpreter.cpp').read_text(encoding='utf-8-sig')
        projected = combiner_lookup_projection.transform(profile_projections.interpreter(source))
        warm = projected.split('ColorCombiner* Interpreter::LookupOrCreateColorCombiner(', 1)[1]
        warm = warm.split('ColorCombiner* Interpreter::XboxLookupColorCombinerCold(', 1)[0]
        self.assertIn('Smash360PerfScope profileScope(SMASH_PERF_COMBINER);', warm)
        self.assertIn('return XboxLookupColorCombinerCold(key);', warm)


if __name__ == '__main__':
    unittest.main()
