"""Fail-closed and reproducibility checks for the narrowly scoped generator."""
import hashlib
import importlib.util
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('binary_generator', ROOT / 'tools/prepare_binary_reader_xdk.py')
generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)
SOURCE = ROOT / 'upstream/BattleShip/libultraship'
SCRATCH = ROOT / 'scratch/binary-reader-xdk/generator-contract'


def snapshot(folder):
    return {str(p.relative_to(folder)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in folder.rglob('*') if p.is_file()} if folder.exists() else {}


class GeneratorContract(unittest.TestCase):
    def test_physical_shipyard_compat_header(self):
        self.assertFalse((ROOT / 'platform/xbox360/cpp-compat/binary/compat.h').exists())
        self.assertFalse((ROOT / 'scratch/application-xdk/native/source/platform/xbox360/cpp-compat/binary/compat.h').exists())
        self.assertTrue((generator.PLATFORM_BASE / 'sources/binary/compat.h').is_file())
        self.assertIn('Shipyard::Binary::ScopedEnum', generator.strong_enum('Boundary', 'One'))
        result = generator.generate(SOURCE, SCRATCH / 'physical-helper')
        self.assertEqual(result['compat_header_source'], 'platform_base:sources/binary/compat.h')

    def test_exact_generation_is_reproducible(self):
        output = SCRATCH / 'reproducible'
        generator.generate(SOURCE, output)
        first = snapshot(output)
        generator.generate(SOURCE, output)
        self.assertEqual(first, snapshot(output))
        self.assertEqual(len(first), len(generator.INPUTS)+1)

    def test_source_change_fails_before_any_output_write(self):
        source = SCRATCH / 'changed-source'
        output = SCRATCH / 'rejected-output'
        for relative in generator.INPUTS:
            target = source / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((SOURCE / relative).read_bytes())
        target = source / 'src/ship/utils/binarytools/Stream.cpp'
        target.write_bytes(target.read_bytes() + b'\n// deliberate contract-test mutation\n')
        output.mkdir(parents=True, exist_ok=True)
        sentinel = output / 'sentinel.txt'
        sentinel.write_text('existing output must remain unchanged\n')
        before = snapshot(output)
        with self.assertRaisesRegex(ValueError, 'source SHA-256 mismatch'):
            generator.generate(source, output)
        self.assertEqual(before, snapshot(output))

    def test_changed_constructor_anchor_is_rejected(self):
        relative = 'src/ship/utils/binarytools/MemoryStream.cpp'
        raw = (SOURCE / relative).read_bytes().replace(b'mBufferSize = 0;', b'mBufferSize = 1;', 1)
        with self.assertRaisesRegex(ValueError, 'default MemoryStream constructor changed'):
            generator.transform(relative, raw, SOURCE / relative)

    def test_outputs_cannot_escape_owned_scratch(self):
        with self.assertRaisesRegex(ValueError, 'output must remain'):
            generator.generate(SOURCE, ROOT / 'upstream/generated-binary-test')

    def test_generated_headers_have_guards_before_source_mapping(self):
        for relative in generator.INPUTS:
            if not relative.endswith('.h'):
                continue
            content, _ = generator.transform(relative, (SOURCE / relative).read_bytes(), SOURCE / relative)
            self.assertLess(content.index(b'#ifndef SMASH360_GENERATED_'), content.index(b'#line 1'))
            self.assertIn((SOURCE / relative).as_posix().encode(), content)


if __name__ == '__main__':
    unittest.main()
