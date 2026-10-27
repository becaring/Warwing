"""Fail-closed source anchors and range lifetime rules."""
from pathlib import Path
import runpy,unittest
ROOT=Path(__file__).resolve().parents[2]
GEN=runpy.run_path(str(ROOT/'tools/prepare_config_xdk.py'))
class Lowering(unittest.TestCase):
    def test_unknown_structured_binding_rejected(self):
        with self.assertRaisesRegex(ValueError,'Structured-binding'):
            GEN['LOWER']['lower_ranges'](b'void f(){for(auto [a,b]:values){use(a,b);}}')
    def test_unknown_initializer_list_rejected(self):
        with self.assertRaisesRegex(ValueError,'initializer-list'):
            GEN['LOWER']['lower_ranges'](b'void f(){for(int x:{1,2}){use(x);}}')
    def test_missing_exact_anchor_rejected(self):
        with self.assertRaisesRegex(ValueError,'anchor changed|patch context mismatch'):
            GEN['transform']('src/ship/config/Config.cpp','#include <any>\n')
    def test_cached_end_and_lifetime(self):
        result=GEN['LOWER']['lower_ranges'](b'void f(){for(const auto& item:temporary()){use(item);}}').decode()
        self.assertEqual(result.count('temporary()'),1)
        self.assertEqual(result.count('Smash360Config::End('),1)
        self.assertIn('auto&& _configRange',result)
        self.assertIn('const auto& item = *',result)
    def test_snapshot_generation_counts_every_mutator(self):
        text=(ROOT/'scratch/config-xdk/generated/src/ship/config/ConsoleVariable.cpp').read_text()
        self.assertEqual(text.count('++sXboxCVarMutations;'),len(GEN['CVAR_MUTATORS']))
        self.assertIn('sXboxCapturedGeneration == generation',text)
        with self.assertRaisesRegex(ValueError,'Re-audit CVar mutators'):
            GEN['snapshot_generation']('void ConsoleVariable::SetBool(int x) {\n}\n')
    def test_mapping_and_determinism(self):
        first=GEN['prepare']();second=GEN['prepare']()
        self.assertEqual(first['output_hashes'],second['output_hashes'])
        self.assertEqual(first['cvars_header_sha256'],second['cvars_header_sha256'])
        self.assertIn('#define CVAR_VSYNC_ENABLED "gVsyncEnabled"',
                      (ROOT/'scratch/config-xdk/cvars.h').read_text())
        for relative in first['output_hashes']:
            text=(ROOT/'scratch/config-xdk/generated'/relative).read_text()
            self.assertIn('#line',text)
            self.assertIn('upstream/BattleShip/libultraship/'+relative,text)
if __name__=='__main__':unittest.main()
