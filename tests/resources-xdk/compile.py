"""Compile real resource sources, retain per-TU blockers without fake headers."""

from pathlib import Path
import json, runpy, subprocess, sys

ROOT = Path(__file__).resolve().parents[2]
import runpy as _shipyard_runpy

SHIPYARD_BASE = _shipyard_runpy.run_path(str(ROOT / "tools/platform_base.py"))["resolve"](ROOT)
OUT = ROOT / "scratch/resources-xdk"


def paths():
    return [
        SHIPYARD_BASE,
        SHIPYARD_BASE / 'sources',
        SHIPYARD_BASE / 'sources/json/include',
        SHIPYARD_BASE / 'sources/value_types',
    ] + [
        ROOT / p
        for p in (
            "scratch/resources-xdk/generated/include",
            "scratch/config-xdk/generated/include",
            "scratch/audio-xdk/generated/include",
            "scratch/binary-reader-xdk/generated/include",
            "platform/xbox360/cpp-compat",
            "platform/xbox360/cpp-compat/async",
            "platform/xbox360/cpp-compat/thread-pool",
            "scratch/thread-pool-xdk",
            "scratch/resources-xdk/libzip-public",
            "upstream/dependencies/libzip/lib",
            "scratch/json-xdk/backend-generated",
            "upstream/dependencies/tinyxml2",
            "upstream/BattleShip/libultraship/include",
            "upstream/BattleShip/libultraship/src",
        )
    ]


def main():
    if "--no-generate" not in sys.argv:
        runpy.run_path(str(ROOT / "tools/prepare_resources_xdk.py"))["prepare"]()
    compiler, env = runpy.run_path(str(ROOT / "tests/json/run.py"))["host"]()
    xdk = Path("C:/Program Files (x86)/Microsoft Xbox 360 SDK")
    sources = sorted((OUT / "generated/src/ship/resource").rglob("*.cpp"))
    sources += sorted((OUT / "generated/src/ship/utils").glob("*.cpp")) + sorted(
        (OUT / "generated/src/ship/utils").glob("*.c")
    )
    sources.insert(0, ROOT / "tests/resources-xdk/header_probe.cpp")
    results = {}
    for mode in ("host", "xdk"):
        build = OUT / ("compile-" + mode)
        build.mkdir(parents=True, exist_ok=True)
        executable = compiler if mode == "host" else xdk / "bin/win32/cl.exe"
        includes = paths()
        flags = ["/std:c++20", "/utf-8"] if mode == "host" else ["/D_XBOX", "/I" + str(xdk / "include/xbox")]
        # Generated actual current logging source, never a fake logger.
        if mode == "xdk":
            includes = [
                ROOT / p
                for p in (
                    "scratch/logging-xdk/core-include",
                    "scratch/logging-xdk/include",
                    "upstream/dependencies/fmt-xdk",
                )
            ] + includes
        else:
            includes.append(ROOT / "upstream/dependencies/spdlog/include")
        records = []
        for source in sources:
            log = build / (source.stem + ".log")
            obj = build / (source.stem + ".obj")
            command = (
                [
                    str(executable),
                    "/nologo",
                    "/c",
                    "/TC" if source.suffix == ".c" else "/TP",
                    "/EHsc",
                    "/MT",
                    "/W3",
                    "/Gy",
                    "/DNOMINMAX",
                    "/DDISABLE_SCRIPTING",
                    "/D_CRT_SECURE_NO_WARNINGS",
                ]
                + flags
                + ["/I" + str(p) for p in includes]
                + [str(source), "/Fo" + str(obj)]
            )
            result = subprocess.run(
                command, cwd=ROOT, env=env if mode == "host" else None, text=True, capture_output=True
            )
            log.write_text(result.stdout + result.stderr)
            (build / (source.stem + "-command.json")).write_text(json.dumps(command, indent=2) + "\n")
            records.append(
                {
                    "source": source.relative_to(ROOT).as_posix(),
                    "exit": result.returncode,
                    "log": log.relative_to(ROOT).as_posix(),
                }
            )
            print(mode, source.stem, "PASS" if result.returncode == 0 else "BLOCKED")
        results[mode] = records
    (OUT / "compile-results.json").write_text(json.dumps(results, indent=2) + "\n")
    if any(r["exit"] for mode in results.values() for r in mode):
        raise SystemExit("Source compile errors remain; inspect logs")


if __name__ == "__main__":
    main()
