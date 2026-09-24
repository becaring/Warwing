from pathlib import Path
import sys,unittest
ROOT=Path(__file__).resolve().parents[2]
class GeneratorTests(unittest.TestCase):
    def test_fixed_arity_source_matches_canonical_generator(self):
        sys.path.insert(0,str(ROOT/'tools'))
        from platform_base import resolve
        base=resolve(ROOT)
        sys.path.insert(0,str(base/'python'))
        from xbox360_platform.value_types import MAX,variant_header
        self.assertEqual(MAX,19)
        self.assertEqual((base/'sources/value_types/xbox_compat/variant.h').read_text(),variant_header())
if __name__=='__main__':unittest.main()
