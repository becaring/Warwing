"""Compile actual staged consumer sources; unresolved dependencies remain errors."""

from pathlib import Path
import json, re, subprocess, hashlib

ROOT = Path(__file__).resolve().parents[2]
import runpy as _shipyard_runpy

SHIPYARD_BASE = _shipyard_runpy.run_path(str(ROOT / "tools/platform_base.py"))["resolve"](ROOT)
OUT = ROOT / "scratch/config-xdk"
SDK = Path("C:/Program Files (x86)/Microsoft Xbox 360 SDK")


def main():
    cvars = (ROOT / "upstream/BattleShip/libultraship/cmake/cvars.cmake").read_text()
    header = OUT / "cvars.h"
    header.write_text(
        "\n".join(
            "#define " + k + ' "' + v + '"'
            for k, v in re.findall(r'set\((CVAR_\w+) "([^"\n]+)" CACHE STRING ""\)', cvars)
        )
        + "\n"
    )
    includes = [
        OUT / "generated/include",
        ROOT / "scratch/logging-xdk/core-include",
        ROOT / "scratch/logging-xdk/include",
        ROOT / "scratch/audio-xdk/generated/include",
        SHIPYARD_BASE,
        SHIPYARD_BASE / 'sources',
        SHIPYARD_BASE / 'sources/json/include',
        ROOT / "scratch/json-xdk/backend-generated",
        ROOT / "platform/xbox360/cpp-compat",
        ROOT / "platform/xbox360",
        ROOT / "platform/xbox360/audio",
        ROOT / "upstream/BattleShip/libultraship/include",
        ROOT / "upstream/dependencies/spdlog/include",
        ROOT / "upstream/dependencies/fmt-xdk",
        SDK / "include/xbox",
    ]
    common = [
        SDK / "bin/win32/cl.exe",
        "/nologo",
        "/EHsc",
        "/D_XBOX",
        "/D_XBOX_VER=200",
        "/DDISABLE_SCRIPTING",
        "/DNOMINMAX",
        "/D_CRT_SECURE_NO_WARNINGS",
        "/FI" + str(header),
    ] + ["/I" + str(p) for p in includes]
    status = {}
    for relative in (
        "src/ship/config/Config.cpp",
        "src/ship/config/ConsoleVariable.cpp",
        "src/ship/utils/StringHelper.cpp",
        "src/ship/audio/Audio.cpp",
    ):
        source = OUT / "generated" / relative
        folder = OUT / "native" / source.stem
        folder.mkdir(parents=True, exist_ok=True)
        obj = folder / (source.stem + ".obj")
        command = common + ["/c", "/Fo" + str(obj), source]
        result = subprocess.run(list(map(str, command)), cwd=ROOT, text=True, capture_output=True)
        (folder / "command.json").write_text(json.dumps(list(map(str, command)), indent=2) + "\n")
        (folder / "result.log").write_text(result.stdout + result.stderr)
        item = {"exit": result.returncode}
        if result.returncode == 0:
            raw = obj.read_bytes()
            assert int.from_bytes(raw[:2], "little") == 0x1F2
            item["object_sha256"] = hashlib.sha256(raw).hexdigest()
        else:
            print((result.stdout + result.stderr)[-2500:])
        status[relative] = item
        print(source.name + ": " + ("PowerPC object PASS" if result.returncode == 0 else "compile failed (see log)"))
    (OUT / "native-verification.json").write_text(json.dumps(status, indent=2) + "\n")
    if any(v["exit"] for v in status.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
