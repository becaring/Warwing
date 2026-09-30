"""Compile the pinned LUS stb image implementation with the donor XDK setup."""

from pathlib import Path
import hashlib, json, subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "scratch/stb-xdk"


def main():
    dependency = ROOT / "upstream/dependencies/stb"
    header = dependency / "stb_image.h"
    recipe = (ROOT / "upstream/BattleShip/libultraship/cmake/dependencies/common.cmake").read_text()
    if "0bc88af4de5fb022db643c2d8e549a0927749354/stb_image.h" not in recipe:
        raise ValueError("LUS stb pin changed")
    OUT.mkdir(parents=True, exist_ok=True)
    source = OUT / "stb_impl.cpp"
    # Same implementation switch as LUS common.cmake and SoH image_codec.cpp.
    source.write_text('#define STB_IMAGE_IMPLEMENTATION\n#include "stb_image.h"\n')
    sdk = Path("C:/Program Files (x86)/Microsoft Xbox 360 SDK")
    command = [
        str(sdk / "bin/win32/cl.exe"),
        "/nologo",
        "/c",
        "/TP",
        "/EHsc",
        "/MT",
        "/W3",
        "/D_XBOX",
        "/DNOMINMAX",
        "/I" + str(dependency),
        "/I" + str(sdk / "include/xbox"),
        "/Fo" + str(OUT / "stb_impl.obj"),
        str(source),
    ]
    run = subprocess.run(command, capture_output=True, text=True)
    (OUT / "compile.log").write_text(run.stdout + run.stderr)
    report = {
        "source_revision": "0bc88af4de5fb022db643c2d8e549a0927749354",
        "header_sha256": hashlib.sha256(header.read_bytes()).hexdigest(),
        "command": command,
        "exit": run.returncode,
        "native_runtime_validated": False,
    }
    (OUT / "compile-report.json").write_text(json.dumps(report, indent=2) + "\n")
    print("Pinned stb XDK compile:", run.returncode)
    if run.returncode:
        print((run.stdout + run.stderr)[-3000:])
    return run.returncode


if __name__ == "__main__":
    raise SystemExit(main())
