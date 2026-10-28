"""SHADE-only fighter parts must reuse the PRIM*SHADE program, exactly."""

from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))


class CombinerAliasTests(unittest.TestCase):
    def test_pin_matches_ssb64_fighter_modes(self):
        import combiner_alias_projection as projection

        body = """#include <stdint.h>
#include <stdio.h>
#define __forceinline inline
#define G_CCMUX_PRIMITIVE 3
#define G_CCMUX_SHADE 4
#define G_CCMUX_PRIMITIVE_ALPHA 10
#define G_CCMUX_0 31
#define G_ACMUX_PRIMITIVE 3
""" + projection.PIN + """
static int check(uint64_t in, uint64_t out) {
  if (XboxPinShadePrim(in) == out) return 0;
  printf("%llx -> %llx, expected %llx\\n", (unsigned long long)in,
         (unsigned long long)XboxPinShadePrim(in), (unsigned long long)out);
  return 1;
}
int main() {
  const uint64_t primShade = 0xf78e5f0dffe4f3ull, shade = 0xf78e5f0dff9fffull, texel = 0xf78e5f03ffe4f1ull;
  int bad = 0;
  bad += check(shade, primShade | XBOX_PRIM_WHITE);   // same fields as its neighbour
  bad += check(primShade, primShade);
  bad += check(texel, texel);
  const uint64_t primAlpha2 = (shade & ~(7ull << 44)) | (3ull << 44);  // cycle-2 alpha reads PRIM
  bad += check(primAlpha2, primAlpha2);
  if (!bad) puts("fighter SHADE parts pinned to the PRIM*SHADE program; PRIM readers untouched");
  return bad;
}
"""
        out = ROOT / "scratch/combiner-alias-tests"
        out.mkdir(exist_ok=True)
        (out / "alias.cpp").write_text(body, encoding="utf-8")
        (out / "build.cmd").write_text(
            """\
@echo off
call \"C:/Program Files/Microsoft Visual \
Studio/2022/Community/VC/Auxiliary/Build/vcvars32.bat\" >nul
cl /nologo /utf-8 /O2 /EHsc /MT alias.cpp /Fe:alias.exe
exit /b %errorlevel%
"""
        )
        run = subprocess.run(["cmd", "/d", "/c", str(out / "build.cmd")], cwd=out, capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        run = subprocess.run([str(out / "alias.exe")], cwd=out, capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        print(run.stdout.strip())

    def test_generated_interpreter_pins_prim(self):
        text = (ROOT / "scratch/fast3d-xdk/overlay/libultraship/src/fast/interpreter.cpp").read_text(
            encoding="utf-8-sig")
        self.assertEqual(text.count("mRdp->combine_mode = XboxPinShadePrim("), 1)
        self.assertEqual(text.count("? &kXboxPrimWhite : &mRdp->prim_color"), 2)
        # GenerateCC must never read the marker bit.
        self.assertIn("(key.combine_mode >> (i * 28 + 16 + 9)) & 7;", text)


if __name__ == "__main__":
    unittest.main()
