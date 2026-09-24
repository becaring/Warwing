"""Contract checks for the real, hash-locked graphics source preparation."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


class PrepareTests(unittest.TestCase):
    def setUp(self):
        script = ROOT / "tools/prepare_graphics_xdk.py"
        self.assertTrue(script.is_file(), "Missing pinned graphics preparation implementation")
        spec = importlib.util.spec_from_file_location("graphics_prepare", script)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    def test_rejects_source_drift(self):
        with self.assertRaisesRegex(ValueError, "expected exactly"):
            self.module.replace_once("changed upstream", "original upstream", "replacement")

    def test_generated_api_keeps_every_virtual_operation(self):
        import re
        self.module.prepare()
        source = (ROOT / "upstream/BattleShip/libultraship/include/fast/backends/gfx_rendering_api.h").read_text()
        generated = (ROOT / "scratch/graphics-xdk/include/fast/backends/gfx_rendering_api.h").read_text()
        names = lambda text: re.findall(r"virtual\s+[^;{}]*?\b(\w+)\s*\(", text)
        self.assertEqual(names(source), names(generated))
        self.assertIn("uint64_t shaderId1", generated)
        self.assertIn("filteringMode", generated)
        self.assertIn("srgbMode", generated)
        self.assertIn("#line", generated)

    def test_source_lock_detects_mutated_bytes(self):
        self.module.prepare()
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            self.module.check_bytes(b"mutated", "0" * 64, "fixture")


if __name__ == "__main__":
    unittest.main()
