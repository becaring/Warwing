"""Execute real BattleShip vertex/light routines before/after byte-table reuse.

Catches wrong signed-byte indices, changed light/color rounding, and projection
edits leaking into positional lighting, texture generation, fog or clip output.
"""

from pathlib import Path
import importlib
import re
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
import runpy as _shipyard_runpy

SHIPYARD_BASE = _shipyard_runpy.run_path(str(ROOT / "tools/platform_base.py"))["resolve"](ROOT)
sys.path.insert(0, str(ROOT / "tools"))


def extract(source, signature):
    start = source.index(signature)
    brace = source.index("{", start)
    depth = 1
    end = brace + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


def accumulation_probe(source, name):
    """Compile the actual RGB update statements, independently of vertex setup."""
    vertex = extract(source, "void Interpreter::GfxSpVertex(")
    start = vertex.index("            int r =")
    loop = vertex.index("            for (int i =", start)
    positive = extract(vertex[loop:], "if (intensity > 0.0f)")
    publication = vertex.index("            d->color.r =", loop)
    # Include any accumulator materialization between the light loop and stores.
    light_loop = extract(vertex[loop:], "for (int i =")
    tail = vertex[loop + len(light_loop) + len("            ") : publication]
    body = (
        vertex[start:loop]
        + "\nfor (int i = 0; i < count - 1; ++i) {\n"
        + "float intensity = intensities[i];\n"
        + positive
        + "\n}\n"
        + tail
    )
    body = body.replace("mRsp->current_num_lights", "count")
    body = re.sub(r"mRsp->current_lights\[(.*?)\]\.l\.col", r"colors[\1]", body)
    return (
        'extern "C" __declspec(noinline) void '
        + name
        + "(const uint8_t (*colors)[3], const float* intensities, uint8_t count, int* out) {\n"
        + body
        + "\nout[0] = r; out[1] = g; out[2] = b;\n}\n"
    )


class LightingTests(unittest.TestCase):
    def test_xdk_accumulation_uses_fpr_truncation(self):
        sdk = Path("C:/Program Files (x86)/Microsoft Xbox 360 SDK")
        out = ROOT / "scratch/fast3d-xdk/lighting-tests"
        out.mkdir(parents=True, exist_ok=True)
        module = importlib.import_module("vertex_lighting_projection")
        source = (ROOT / "upstream/BattleShip/libultraship/src/fast/interpreter.cpp").read_text(encoding="utf-8-sig")
        projected = module.transform(source)
        probe = (
            '#include "fast3d/vertex_lighting.h"\n'
            + accumulation_probe(source, "AccumulationOriginal")
            + accumulation_probe(projected, "AccumulationProjected")
        )
        (out / "accumulation.cpp").write_text(probe)
        obj = out / "accumulation.obj"
        result = subprocess.run(
            [
                str(sdk / "bin/win32/cl.exe"),
                "/nologo",
                "/c",
                "/O2",
                "/Ob2",
                "/MT",
                "/EHsc",
                "/fp:precise",
                "/D_XBOX",
                "/DNOMINMAX",
                "/I" + str(ROOT / "platform/xbox360/cpp-compat"),
                "/I" + str(SHIPYARD_BASE / 'sources'),
                "/I" + str(sdk / "include/xbox"),
                "/Fo" + str(obj),
                str(out / "accumulation.cpp"),
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        result = subprocess.run(
            [str(sdk / "bin/win32/dumpbin.exe"), "/disasm", str(obj)], capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        (out / "accumulation.asm").write_text(result.stdout)
        for name in ("AccumulationOriginal", "AccumulationProjected"):
            block = re.search(
                r"(?m)^" + name + r":\s*\n(.*?)(?=^(?:\?|[A-Za-z_])[^\n]*:\s*\n|\Z)", result.stdout, re.S | re.M
            )
            self.assertIsNotNone(block, name)
            ops = re.findall(r"(?m)^\s*[0-9A-Fa-f]+:\s+[0-9A-Fa-f]{8}\s+(\S+)", block[1])
            self.assertIn("fctiwz", ops, "original 32-bit conversion/fallback must remain: " + name)
            if name.endswith("Projected"):
                self.assertGreaterEqual(
                    ops.count("fctidz"), 3, "bounded RGB still uses integer store/reload conversion"
                )
                self.assertGreaterEqual(ops.count("fcfid"), 3)
                # The bounded block is bracketed by the guard's branch and its
                # branch to the loop latch. Prove that actual production RGB
                # arithmetic uses separate multiply/add/truncation without the
                # integer spill/reload sequence retained in the fallback.
                first = ops.index("fctidz")
                guard = max(i for i in range(first) if ops[i].startswith("b"))
                latch = next(i for i in range(first, len(ops)) if ops[i] == "b")
                fast = ops[guard + 1 : latch]
                for opcode in ("fmuls", "fadds", "fctidz", "fcfid"):
                    self.assertEqual(fast.count(opcode), 3, "bounded RGB arithmetic changed: " + opcode)
                for forbidden in ("std", "stfd", "lfd", "lwz", "fctiwz", "fmadd", "fmadds", "bl"):
                    self.assertNotIn(forbidden, fast, "bounded RGB spilled or changed rounding: " + forbidden)
            else:
                self.assertNotIn("fctidz", ops)

    def test_xdk_replaces_store_reload_conversion(self):
        sdk = Path("C:/Program Files (x86)/Microsoft Xbox 360 SDK")
        out = ROOT / "scratch/fast3d-xdk/lighting-tests"
        out.mkdir(parents=True, exist_ok=True)
        obj = out / "probe.obj"
        command = [
            str(sdk / "bin/win32/cl.exe"),
            "/nologo",
            "/c",
            "/O2",
            "/Ob2",
            "/MT",
            "/EHsc",
            "/fp:precise",
            "/D_XBOX",
            "/DNOMINMAX",
            "/I" + str(ROOT / "platform/xbox360/cpp-compat"),
            "/I" + str(SHIPYARD_BASE / 'sources'),
            "/I" + str(sdk / "include/xbox"),
            "/Fo" + str(obj),
            str(Path(__file__).with_name("vertex_lighting_probe.cpp")),
        ]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        result = subprocess.run(
            [str(sdk / "bin/win32/dumpbin.exe"), "/disasm", str(obj)], capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        (out / "probe.asm").write_text(result.stdout)
        for name in (
            "NormalOriginal",
            "NormalProjected",
            "LightOriginal",
            "LightProjected",
            "TruncateOriginal",
            "TruncateProjected",
        ):
            block = re.search(r"(?m)^" + name + r":\s*\n(.*?)(?=^\S|\Z)", result.stdout, re.S | re.M)
            self.assertIsNotNone(block, name + " missing from actual XDK object")
            ops = re.findall(r"(?m)^\s*[0-9A-Fa-f]+:\s+[0-9A-Fa-f]{8}\s+(\S+)", block[1])
            if name.endswith("Original"):
                self.assertIn("std", ops, name)
                self.assertIn("lfd", ops, name)
                self.assertIn("fcfid", ops, name)
            elif name == "TruncateProjected":
                self.assertEqual(ops, ["fctidz", "fcfid", "frsp", "blr"], name)
            else:
                self.assertIn("lfsx", ops, name)
                for forbidden in ("std", "stfd", "lfd", "fcfid", "bl", "b"):
                    self.assertNotIn(forbidden, ops, name)

    def test_real_vertex_lighting(self):
        self.assertTrue(
            (ROOT / "tools/vertex_lighting_projection.py").exists(), "exact Xbox byte-table lighting adapter is missing"
        )
        module = importlib.import_module("vertex_lighting_projection")
        source = (ROOT / "upstream/BattleShip/libultraship/src/fast/interpreter.cpp").read_text(encoding="utf-8-sig")
        projected = module.transform(source)
        reuse = importlib.import_module("vertex_reuse_projection")
        projected = reuse.transform(projected)
        projected = projected.replace(reuse.COPY_MARKER, reuse.COPY_MARKER + "\n            ++observedShadeReuse;")
        signatures = [
            "void Interpreter::NormalizeVector(",
            "void Interpreter::TransposedMatrixMul(",
            "void Interpreter::CalculateNormalDir(",
            "float Interpreter::GetWidescreenClipXScale(",
            "float Interpreter::AdjXForAspectRatio(",
            "void Interpreter::GfxSpVertex(",
        ]
        functions = []
        for name, text in [("Original", source), ("Projected", projected)]:
            for signature in signatures:
                functions.append(extract(text, signature).replace("Interpreter::", name + "::"))
        accumulations = accumulation_probe(source, "AccumulationOriginal") + accumulation_probe(
            projected, "AccumulationProjected"
        )
        driver = Path(__file__).with_name("vertex_lighting_contract.cpp").read_text()
        utils = (ROOT / "upstream/BattleShip/libultraship/src/ship/utils/Utils.cpp").read_text()
        driver = driver.replace("// EXTRACTED_SHIP_CLAMP", extract(utils, "float clamp("))
        out = ROOT / "scratch/fast3d-xdk/lighting-tests"
        out.mkdir(parents=True, exist_ok=True)
        driver = driver.replace("// EXTRACTED_ACCUMULATION", accumulations)
        (out / "contract.cpp").write_text(driver.replace("// EXTRACTED_FUNCTIONS", "\n\n".join(functions)))
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
            + " contract.cpp /Fe:lighting.exe\nexit /b %errorlevel%\n"
        )
        result = subprocess.run(["cmd", "/d", "/c", str(batch)], cwd=out, capture_output=True, text=True)
        (out / "compile.log").write_text(result.stdout + result.stderr)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        result = subprocess.run([str(out / "lighting.exe")], cwd=out, capture_output=True, text=True)
        (out / "run.log").write_text(result.stdout + result.stderr)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout.strip())


if __name__ == "__main__":
    unittest.main()
