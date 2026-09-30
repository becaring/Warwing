from pathlib import Path
import importlib
import re
import subprocess
import sys
import unittest
import test_vertex_transform as vertex

ROOT = Path(__file__).resolve().parents[2]
import runpy as _shipyard_runpy

SHIPYARD_BASE = _shipyard_runpy.run_path(str(ROOT / "tools/platform_base.py"))["resolve"](ROOT)
sys.path.insert(0, str(ROOT / "tools"))
OUT = ROOT / "scratch/fast3d-xdk/light-batch-tests"


class LightBatchTests(unittest.TestCase):
    extra_includes = '#include "fast3d/light_batch.h"\n'

    @staticmethod
    def extra_projection(text):
        return importlib.import_module("light_batch_projection").transform(text)

    def test_actual_vertex_composition(self):
        vertex.OUT.mkdir(parents=True, exist_ok=True)
        vertex.TransformTests.test_actual_vertex_composition(self)

    def test_values_rounding_and_xdk(self):
        OUT.mkdir(parents=True, exist_ok=True)
        source = Path(__file__).with_name("light_batch_cases.cpp")
        batch = OUT / "build.cmd"
        batch.write_text(
            '@echo off\ncall "C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Auxiliary/Build/vcvars32.bat" >nul\n'
            'cl /nologo /std:c++20 /O2 /fp:precise /arch:SSE2 /EHsc /MT /I"'
            + str(SHIPYARD_BASE / 'sources')
            + '" /I"'
            + str(ROOT / "platform/xbox360/cpp-compat")
            + '" "'
            + str(source)
            + '" /Fe:cases.exe\nexit /b %errorlevel%\n'
        )

        def run(command, label):
            p = subprocess.run(command, cwd=OUT, capture_output=True, text=True)
            (OUT / (label + ".log")).write_text(p.stdout + p.stderr)
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
            return p.stdout

        run(["cmd", "/d", "/c", str(batch)], "host-compile")
        print(run([str(OUT / "cases.exe")], "host-run"))
        sdk = Path("C:/Program Files (x86)/Microsoft Xbox 360 SDK")
        obj = OUT / "cases.obj"
        run(
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
                "/I" + str(SHIPYARD_BASE / 'sources'),
                "/I" + str(ROOT / "platform/xbox360/cpp-compat"),
                "/I" + str(sdk / "include/xbox"),
                "/Fo" + str(obj),
                str(source),
            ],
            "xdk-compile",
        )
        asm = run([str(sdk / "bin/win32/dumpbin.exe"), "/disasm", str(obj)], "xdk-disasm")
        block = re.search(r"(?m)^Bounded127:\s*\n(.*?)(?=^[^\s$]|\Z)", asm, re.S)
        self.assertIsNotNone(block)
        ops = re.findall(r"(?m)^\s*[0-9A-Fa-f]+:\s+[0-9A-Fa-f]{8}\s+(\S+)", block[1])
        self.assertIn("fmul", ops)
        self.assertIn("frsp", ops)
        self.assertFalse(any(op.startswith(("fdiv", "fres", "fmadd")) for op in ops), str(ops))
        block = re.search(r"(?m)^\?NearestRounding[^\n]*:\s*\n(.*?)(?=^[^\s$]|\Z)", asm, re.S)
        self.assertIsNotNone(block)
        ops = re.findall(r"(?m)^\s*[0-9A-Fa-f]+:\s+[0-9A-Fa-f]{8}\s+(\S+)", block[1])
        self.assertEqual(
            ops,
            ["mffs", "stfd", "lwz", "clrlwi", "cntlzw", "srwi", "blr"],
            "rounding read must not write FPSCR, call CRT/kernel, or allocate a frame",
        )


if __name__ == "__main__":
    unittest.main()
