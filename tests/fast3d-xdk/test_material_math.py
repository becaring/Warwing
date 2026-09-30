"""Differentially execute BattleShip's material calculations and Xbox caches."""

from pathlib import Path
import importlib
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
import runpy as _shipyard_runpy

SHIPYARD_BASE = _shipyard_runpy.run_path(str(ROOT / "tools/platform_base.py"))["resolve"](ROOT)
sys.path.insert(0, str(ROOT / "tools"))


class MaterialMathTests(unittest.TestCase):
    def test_real_material_calculations_and_dependency_changes(self):
        module = importlib.import_module("material_math_projection")
        source = (ROOT / "upstream/BattleShip/libultraship/src/fast/interpreter.cpp").read_text(encoding="utf-8-sig")
        projected = module.transform(source)
        self.assertIn('#include "fast3d/material_value_cache.h"', projected)
        self.assertNotIn("struct XboxDrawOptionsCache", projected)
        self.assertNotIn("struct XboxTextureGeometryCache", projected)
        functions = []
        for name, text in [("Original", source), ("Projected", projected)]:
            tri = text.split("void Interpreter::GfxSpTri1(", 1)[1]
            options = tri[tri.index("    uint64_t cc_id =") : tri.index("    if (!mShaderStack.empty())")]
            geometry = tri[
                tri.index("            uint8_t cms =") : tri.index(
                    "            if (mRenderingState.mTextures[i] == nullptr)"
                )
            ]
            if name == "Original":
                geometry += """\

xboxTextureWidth[i]=(float)tex_width[i];\
xboxTextureHeight[i]=(float)tex_height[i];\
xboxTextureBoundWidth[i]=(float)tex_width2[i];\
xboxTextureBoundHeight[i]=(float)tex_height2[i];
"""
            functions.append(
                "void Harness::"
                + name
                + "() {\n"
                + options
                + "\noptions_out=cc_options; alpha=use_alpha; fog=use_fog; blend=use_blend_color; gray=use_grayscale;\n"
                + geometry
                + "\ncms_out=cms; cmt_out=cmt;\n}"
            )
        helpers = projected.split("// XBOX MATERIAL MATH BEGIN\n", 1)[1].split("// XBOX MATERIAL MATH END", 1)[0]
        # Count actual cold rebuilds in this differential test only.
        helpers = helpers.replace("// TEST REBUILD GEOMETRY", "++geometryBuilds;").replace(
            "// TEST REBUILD OPTIONS", "++optionBuilds;"
        )
        driver = Path(__file__).with_name("material_math_contract.cpp").read_text()
        driver = driver.replace("// GENERATED_HELPERS", helpers).replace("// EXTRACTED_FUNCTIONS", "\n".join(functions))
        with tempfile.TemporaryDirectory(prefix="smash-material-cache-") as folder:
            out = Path(folder)
            (out / "contract.cpp").write_text(driver)
            includes = [
                ROOT / "upstream/BattleShip/libultraship/include",
                ROOT / "platform/xbox360/cpp-compat",
                SHIPYARD_BASE / 'sources',
                SHIPYARD_BASE / 'sources/value_types',
                ROOT / "scratch/graphics-xdk/include",
            ]
            batch = out / "build.cmd"
            batch.write_text(
                '@echo off\ncall "C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Auxiliary/Build/vcvars32.bat" >nul\n'
                "cl /nologo /std:c++20 /O2 /fp:precise /arch:SSE2 /EHsc /MT /DNOMINMAX "
                + " ".join('/I"' + str(p) + '"' for p in includes)
                + " contract.cpp /Fe:material.exe\nexit /b %errorlevel%\n"
            )
            result = subprocess.run(["cmd", "/d", "/c", str(batch)], cwd=out, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = subprocess.run([str(out / "material.exe")], cwd=out, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            print(result.stdout.strip())


if __name__ == "__main__":
    unittest.main()
