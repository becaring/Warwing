"""Compare reached API backend with pinned official library, then compile with XDK."""

from pathlib import Path
import runpy
import json
import hashlib
import sys

M = runpy.run_path(str(Path(__file__).with_name("run.py")))
ROOT = M["ROOT"]
OUT = M["OUT"]
TESTS = M["TESTS"]
execute = M["execute"]
sys.path.insert(0, str(ROOT / "tools"))
from platform_base import resolve as resolve_platform_base

BACKEND = resolve_platform_base(ROOT) / "sources/json"
INCLUDES = ["/I" + str(BACKEND / "include"), "/I" + str(BACKEND.parent), "/I" + str(OUT / "backend-generated")]


def build(source, label, success=True):
    compiler, env = M["host"]()
    folder = OUT / label
    args = (
        [compiler, "/nologo", "/std:c++20", "/EHsc", "/MD", "/W4"]
        + INCLUDES
        + ["/Fo" + str(folder) + "\\", "/Fe" + str(folder / "test.exe"), source, BACKEND / "json.cpp"]
    )
    r = execute(args, label, env, success)
    if r.returncode:
        return r
    return execute([folder / "test.exe"], label + "-run", success=success)


def main():
    original = M["build_host"]("host-original", TESTS / "reference.cpp")
    adapted = build(TESTS / "reference.cpp", "host-backend")
    if adapted.stdout != original.stdout:
        import difflib

        print("".join(difflib.unified_diff(original.stdout.splitlines(True), adapted.stdout.splitlines(True))))
        raise AssertionError("backend behavior differs")
    original_edges = M["build_host"]("edges-original", TESTS / "edge_contract.cpp")
    adapted_edges = build(TESTS / "edge_contract.cpp", "edges-backend")
    assert original_edges.stdout == adapted_edges.stdout, "edge contract differs"
    sdk = Path("C:/Program Files (x86)/Microsoft Xbox 360 SDK")
    execute(
        [sdk / "bin/win32/cl.exe", "/nologo", "/EHsc", "/D_XBOX", "/D_XBOX_VER=200", "/I" + str(sdk / "include/xbox")]
        + INCLUDES
        + ["/c", "/Fo" + str(OUT / "xdk-backend/json.obj"), BACKEND / "json.cpp"],
        "xdk-backend",
    )
    assert int.from_bytes((OUT / "xdk-backend/json.obj").read_bytes()[:2], "little") == 0x1F2
    native_api = execute(
        [sdk / "bin/win32/cl.exe", "/nologo", "/EHsc", "/D_XBOX", "/D_XBOX_VER=200", "/I" + str(sdk / "include/xbox")]
        + INCLUDES
        + ["/c", "/Fo" + str(OUT / "xdk-api/api.obj"), TESTS / "xdk_api.cpp"],
        "xdk-api",
    )
    unknown = execute(
        [sdk / "bin/win32/cl.exe", "/nologo", "/EHsc", "/D_XBOX", "/D_XBOX_VER=200", "/I" + str(sdk / "include/xbox")]
        + INCLUDES
        + ["/Zs", TESTS / "unsupported_get.cpp"],
        "xdk-unsupported-get",
        success=False,
    )
    assert (
        unknown.returncode != 0 and "error C2027" in unknown.stdout and "T=UnregisteredValue" in unknown.stdout
    ), "unknown conversion did not fail closed"
    (OUT / "backend-verification.json").write_text(
        json.dumps(
            {
                "rich_contract_sha256": hashlib.sha256(original.stdout.encode()).hexdigest(),
                "edge_contract_sha256": hashlib.sha256(original_edges.stdout.encode()).hexdigest(),
                "float_bit_patterns": 4000,
                "backend_object_sha256": hashlib.sha256((OUT / "xdk-backend/json.obj").read_bytes()).hexdigest(),
                "powerpc_machine": hex(0x1F2),
                "unknown_conversion_rejected": True,
                "whole_generic_basic_json_lowered": False,
                "console_execution_tested": False,
            },
            indent=2,
        )
        + "\n"
    )
    print("Reached JSON API host differential PASS; backend PowerPC compile PASS. Consumer integration separate.")


if __name__ == "__main__":
    main()
