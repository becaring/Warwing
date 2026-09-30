"""Actual writer original/projected byte parity and native object compilation."""

from pathlib import Path
import json, runpy, struct

HELP = runpy.run_path(str(Path(__file__).with_name("run.py")))
ROOT = HELP["ROOT"]
OUT = HELP["OUT"] / "writer"
OUT.mkdir(exist_ok=True)
cl, env = HELP["host_environment"]()
outputs = []
names = ("BinaryWriter", "MemoryStream", "Stream")
fixture = Path(__file__).with_name("writer_contract.cpp").resolve()
generated = HELP["OUT"] / "generated"
for tag, source in [("original", HELP["LUS"]), ("projected", generated)]:
    folder = OUT / tag
    folder.mkdir(exist_ok=True)
    args = [
        cl,
        "/nologo",
        "/std:c++20",
        "/EHsc",
        "/MD",
        "/W4",
        "/I" + str(source / "include"),
        "/I" + str(ROOT / "platform/xbox360/cpp-compat"),
        "/I" + str(HELP["PLATFORM_BASE"] / "sources"),
        "/Fo" + str(folder) + "/",
        "/Fe" + str(folder / "writer.exe"),
        fixture,
    ]
    args += [source / "src/ship/utils/binarytools" / (name + ".cpp") for name in names]
    (folder / "compile.log").write_text(HELP["run"](args, env=env, cwd=folder))
    result = HELP["run"]([folder / "writer.exe"], cwd=folder)
    (folder / "bytes.txt").write_text(result)
    outputs.append(result)
assert outputs[0] == outputs[1]
expected = []
for order in ("<", "<", ">"):
    blob = struct.pack(
        order + "bBhHiIqQfdfd",
        -42,
        240,
        -12345,
        0xFEDC,
        -123456789,
        0xFEDCBA98,
        -0x0102030405060708,
        0xFEDCBA9876543210,
        1.5,
        -1234.125,
        -0.0,
        float("inf"),
    )
    blob += struct.pack(order + "i", 3) + b"a\0b" + struct.pack(order + "ii", 123, -456) + bytes((0, 1, 127, 255))
    expected.extend([blob.hex()] * 3)
assert outputs[1].splitlines() == expected
sdk = Path("C:/Program Files (x86)/Microsoft Xbox 360 SDK")
native = OUT / "xdk"
native.mkdir(exist_ok=True)
args = [
    sdk / "bin/win32/cl.exe",
    "/nologo",
    "/c",
    "/EHsc",
    "/MT",
    "/D_XBOX",
    "/I" + str(sdk / "include/xbox"),
    "/I" + str(generated / "include"),
    "/I" + str(ROOT / "platform/xbox360/cpp-compat"),
    "/I" + str(HELP["PLATFORM_BASE"] / "sources"),
    "/Fo" + str(native) + "/",
    generated / "src/ship/utils/binarytools/BinaryWriter.cpp",
    fixture,
]
(native / "compile.log").write_text(HELP["run"](args, cwd=native))
(OUT / "verification.json").write_text(
    json.dumps(
        {
            "host_original_projected_exact": True,
            "independent_python_bytes_match": True,
            "native_compile": True,
            "native_execution": False,
        },
        indent=2,
    )
    + "\n"
)
print("Actual writer bytes: original/projected/Python agree; XDK production writer and contract compile PASS")
