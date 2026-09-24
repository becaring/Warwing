import importlib.util
import hashlib
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]

class Preparation(unittest.TestCase):
    def setUp(self):
        path=ROOT/'tools/prepare_prism_xdk.py'
        self.assertTrue(path.exists(),'Actual pinned Prism preparation is missing')
        spec=importlib.util.spec_from_file_location('prism_prepare',path)
        self.module=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.module)

    def test_range_caches_end_once(self):
        lowered=self.module.lower_ranges(b'for(const auto& value : values) { use(value); }').decode()
        self.assertEqual(lowered.count('PrismEnd('),1)
        self.assertLess(lowered.index('PrismBegin('),lowered.index('PrismEnd('))
        condition=lowered[lowered.index('for ('):]
        self.assertNotIn('!= PrismEnd(',condition)

    def test_hash_rejects_drift(self):
        with self.assertRaisesRegex(ValueError,'SHA-256'):
            self.module.check_bytes(b'drift','0'*64,'test')

    def test_variant_rewrite_respects_identifier_boundaries(self):
        source='std::getline(input,line); std::get<int>(value);'
        result=self.module.lower(source,'fixture.cpp')
        self.assertIn('std::getline(input,line)',result)
        self.assertIn('xbox_compat::get<int>(value)',result)

    def test_aggregate_constructor_does_not_add_implicit_conversion(self):
        result=self.module.aggregates('struct Opaque { uintptr_t ptr; };')
        self.assertIn('explicit Opaque(',result)
        self.assertIn('ptr(ptr_)',result)

    def test_c_header_remains_c_compatible(self):
        result=self.module.lower('#pragma once\n#include <stdint.h>\n','invoke.h')
        self.assertNotIn('compat.h',result)

    def test_smash_adapter_uses_reviewed_shared_projector(self):
        from xbox360_platform.prism import PrismProjector
        self.assertIsInstance(self.module.PROJECTOR, PrismProjector)
        self.assertEqual(self.module.PROJECTOR.revision,
                         '1de054450e7b3c5f777d2e3dfcb228ad120c329d')

    def test_processor_projection_matches_premigration_bytes(self):
        self.module.prepare()
        data=(self.module.OUT/'prism/processor.cpp').read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(),
                         '39e9c37774b1eba7293604fdde75a8024ab515b575999b3f6926436366c11ca0')

if __name__=='__main__':unittest.main()
