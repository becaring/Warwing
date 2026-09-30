from pathlib import Path
import json, subprocess, hashlib

ROOT = Path(__file__).resolve().parents[2]
import runpy as _shipyard_runpy

SHIPYARD_BASE = _shipyard_runpy.run_path(str(ROOT / "tools/platform_base.py"))["resolve"](ROOT)
OUT = ROOT / "scratch/libultra-xdk"
SDK = Path("C:/Program Files (x86)/Microsoft Xbox 360 SDK")


def main():
    includes = [
        OUT / "generated/include",
        ROOT / "scratch/controllers-xdk/generated/include",
        ROOT / "scratch/gui-xdk/overlay/libultraship/include",
        ROOT / "scratch/config-xdk/generated/include",
        ROOT / "scratch/input-xdk/source/libultraship/include",
        ROOT / "platform/xbox360/input",
        ROOT / "scratch/audio-xdk/generated/include",
        ROOT / "scratch/logging-xdk/core-include",
        ROOT / "scratch/logging-xdk/include",
        ROOT / "scratch/imgui-xdk/source",
        ROOT / "platform/xbox360/imgui",
        ROOT / "scratch/graphics-xdk/include",
        SHIPYARD_BASE / 'sources/json/include',
        ROOT / "platform/xbox360/cpp-compat",
        ROOT / "upstream/dependencies/fmt-xdk",
        ROOT / "upstream/BattleShip/libultraship/include",
        SDK / "include/xbox",
    ]
    results = {}
    includes[1:1] = [
        ROOT / "scratch/resources-xdk/generated/include",
        ROOT / "scratch/binary-reader-xdk/generated/include",
        ROOT / "scratch/fast3d-xdk/overlay/libultraship/include",
        SHIPYARD_BASE / 'sources/value_types',
        ROOT / "scratch/thread-pool-xdk",
        ROOT / "platform/xbox360/cpp-compat/thread-pool",
        ROOT / "platform/xbox360/cpp-compat/async",
        SHIPYARD_BASE,
        SHIPYARD_BASE / 'sources',
    ]
    includes[1:1] = [
        ROOT / "scratch/gui-widgets-xdk/generated/include",
        ROOT / "scratch/json-xdk/backend-generated",
        ROOT / "upstream/dependencies/stb",
    ]
    for source in sorted((OUT / "generated/src").rglob("*.cpp")):
        relative = source.relative_to(OUT / "generated").as_posix()
        folder = OUT / "native" / Path(relative).parent / source.stem
        folder.mkdir(parents=True, exist_ok=True)
        obj = folder / "source.obj"
        command = (
            [
                SDK / "bin/win32/cl.exe",
                "/nologo",
                "/c",
                "/TP",
                "/EHsc",
                "/MT",
                "/W3",
                "/D_XBOX",
                "/DNOMINMAX",
                "/DDISABLE_SCRIPTING",
                "/D_USE_MATH_DEFINES",
                "/FI" + str(ROOT / "scratch/config-xdk/cvars.h"),
            ]
            + ["/I" + str(p) for p in includes]
            + ["/Fo" + str(obj), source]
        )
        result = subprocess.run(list(map(str, command)), cwd=ROOT, capture_output=True, text=True)
        log = result.stdout + result.stderr
        (folder / "result.log").write_text(log)
        item = {
            "exit": result.returncode,
            "command": list(map(str, command)),
            "errors": [line for line in log.splitlines() if "error " in line],
        }
        if not result.returncode:
            raw = obj.read_bytes()
            assert int.from_bytes(raw[:2], "little") == 0x1F2
            item["object_sha256"] = hashlib.sha256(raw).hexdigest()
        results[relative] = item
        print(("PASS " if result.returncode == 0 else "FAIL ") + relative, flush=True)
    (OUT / "native-verification.json").write_text(json.dumps(results, indent=2) + "\n")
    return all(item["exit"] == 0 for item in results.values())


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
