"""Behavior checks for reproducible generation and fail-closed input locking."""
import contextlib
import importlib.util
import io
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
SPEC = importlib.util.spec_from_file_location("prepare_bs", ROOT / "tools/prepare_thread_pool_xdk.py")
GENERATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GENERATOR)


class GeneratorTests(unittest.TestCase):
    def setUp(self):
        self.source = GENERATOR.SOURCE
        self.output = GENERATOR.OUTPUT
        self.scratch = self.output / "generator-tests"
        self.scratch.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        GENERATOR.SOURCE = self.source
        GENERATOR.OUTPUT = self.output

    def generate(self, destination):
        GENERATOR.OUTPUT = destination
        with contextlib.redirect_stdout(io.StringIO()):
            GENERATOR.main()

    def test_same_pinned_input_produces_identical_header_and_manifest(self):
        first, second = self.scratch / "first", self.scratch / "second"
        self.generate(first)
        self.generate(second)
        self.assertEqual((first / "BS_thread_pool.hpp").read_bytes(), (second / "BS_thread_pool.hpp").read_bytes())
        self.assertEqual((first / "provenance.json").read_bytes(), (second / "provenance.json").read_bytes())

    def test_changed_source_is_rejected_before_output_mutation(self):
        altered = self.scratch / "altered-input.hpp"
        altered.write_bytes(self.source.read_bytes() + b"\n// changed upstream\n")
        GENERATOR.SOURCE = altered
        destination = self.scratch / "rejected"
        destination.mkdir(exist_ok=True)
        sentinel = destination / "BS_thread_pool.hpp"
        sentinel.write_text("previous output must survive", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Refusing changed BS source"):
            self.generate(destination)
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "previous output must survive")


if __name__ == "__main__":
    unittest.main()
