"""Run pinned BattleShip host generators with outputs isolated in scratch.

No game/resource logic is reimplemented here. Original scripts remain unchanged.
"""

from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT / "upstream/BattleShip"
GENERATED = ROOT / "scratch/generated"
ASSETS = ROOT / "scratch/assets"
HOST_PYTHON = ROOT / "scratch/host-python"


def load(name):
    path = UPSTREAM / "tools" / (name + ".py")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extract", action="store_true")
    args = parser.parse_args()
    # Keep host dependencies inside the owned tree. Subprocesses run unchanged
    # upstream scripts with this explicit dependency path.
    if HOST_PYTHON.is_dir():
        os.environ["PYTHONPATH"] = str(HOST_PYTHON) + os.pathsep + os.environ.get("PYTHONPATH", "")
    for path in (
        GENERATED / "include",
        GENERATED / "port/resource",
        GENERATED / "decomp/src/credits",
        ASSETS,
    ):
        path.mkdir(parents=True, exist_ok=True)

    symbols = load("generate_reloc_stubs")
    symbols.select_version("us")
    symbols.HEADER_OUT = GENERATED / "include/reloc_data.us.h"
    values = symbols.parse_symbol_values()
    extra = symbols.collect_src_symbols() - set(values)
    symbols.write_header(values, extra)
    # Match upstream generation, report its inherited unresolved symbols.
    print(f"Reloc symbols: {len(values)} resolved; {len(extra)} upstream unresolved symbols")

    table = load("generate_reloc_table")
    table.select_version("us")
    table.YAML_DIR = UPSTREAM / table.YAML_DIR
    entries = table.parse_yaml_entries(table.YAML_DIR)
    missing = set(range(table.FILE_COUNT)) - set(entries)
    if missing:
        raise RuntimeError(f"Missing reloc resource IDs: {sorted(missing)}")
    table.generate(entries, GENERATED / "port/resource/RelocFileTable.us.cpp")
    table.generate_header(GENERATED / "port/resource/RelocFileTable.us.h")

    credit_dir = GENERATED / "decomp/src/credits"
    for name, flags in (
        ("staff", []),
        ("titles", []),
        ("info", ["-paragraphFont", "-multiline"]),
        ("companies", ["-paragraphFont"]),
    ):
        filename = name + ".credits.us.txt"
        shutil.copyfile(UPSTREAM / "decomp/src/credits" / filename, credit_dir / filename)
        subprocess.run(
            [
                sys.executable,
                "-B",
                str(UPSTREAM / "tools/creditsTextConverter.py"),
                *flags,
                filename,
            ],
            cwd=credit_dir,
            check=True,
        )

    # Exact upstream CMake baked UI asset recipes; redirect every output so the
    # original tree (including its PNG paths) remains untouched. RGBA16 is
    # emitted as explicit high/low bytes by the authoritative generator.
    css = GENERATED / "css_icons"
    css.mkdir(parents=True, exist_ok=True)
    for name, symbol, flags in (("arrow", "arrow", []), ("arrow_left", "arrowLeft", ["--mirror"])):
        png = css / (name + ".png")
        subprocess.run(
            [
                sys.executable,
                "-B",
                str(UPSTREAM / "tools/generate_arrow_svg.py"),
                str(png),
                "6",
                "44",
                *flags,
            ],
            check=True,
        )
        subprocess.run(
            [
                sys.executable,
                "-B",
                str(UPSTREAM / "tools/png_to_c_array.py"),
                str(png),
                str(css / (name + "_data.h")),
                symbol,
            ],
            check=True,
        )
    for stem, title, symbol in (
        ("final_destination", "FINAL DESTINATION", "nameFinalDestination"),
        ("metal_cavern", "METAL CAVERN", "nameMetalCavern"),
        ("battlefield", "BATTLEFIELD", "nameBattlefield"),
    ):
        png = css / (stem + "_name.png")
        subprocess.run(
            [sys.executable, "-B", str(UPSTREAM / "tools/render_nameplates.py"), title, str(png)],
            check=True,
        )
        subprocess.run(
            [
                sys.executable,
                "-B",
                str(UPSTREAM / "tools/png_to_c_array.py"),
                str(png),
                str(css / (stem + "_name_data.h")),
                symbol,
            ],
            check=True,
        )

    shaders = UPSTREAM / "libultraship/src/fast/shaders"
    with zipfile.ZipFile(ASSETS / "f3d.o2r", "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(shaders.rglob("*")):
            if path.is_file():
                # Stable metadata, identical original resource paths/payloads.
                info = zipfile.ZipInfo(
                    "shaders/" + path.relative_to(shaders).as_posix(), (1980, 1, 1, 0, 0, 0)
                )
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, path.read_bytes())

    if args.extract:
        rom = ROOT / "baserom.us.z64"
        if hashlib.sha1(rom.read_bytes()).hexdigest() != "e2929e10fccc0aa84e5776227e798abc07cedabf":
            raise RuntimeError("Wrong US ROM hash; refusing extraction")
        torch = ROOT / "scratch/torch-host/Release/torch.exe"
        subprocess.run(
            [str(torch), "o2r", str(rom), "-s", str(UPSTREAM), "-d", str(ASSETS)],
            cwd=ASSETS,
            check=True,
        )
        with zipfile.ZipFile(ASSETS / "BattleShip.o2r") as archive:
            bad = archive.testzip()
            if bad:
                raise RuntimeError("Bad archive entry: " + bad)
            archive_names = set(archive.namelist())
            absent = set(entries.values()) - archive_names
            if absent:
                raise RuntimeError(
                    f"Archive missing {len(absent)} reloc entries: {sorted(absent)[:8]}"
                )
            print(f"Verified archive CRCs and all {len(entries)} reloc paths")

    report = {
        "generators": {
            name: digest(UPSTREAM / "tools" / (name + ".py"))
            for name in (
                "generate_reloc_stubs",
                "generate_reloc_table",
                "creditsTextConverter",
                "generate_arrow_svg",
                "png_to_c_array",
                "render_nameplates",
            )
        },
        "reloc_paths": len(entries),
        "inherited_unresolved_symbols": sorted(extra),
        "outputs": {
            str(path.relative_to(ROOT)): digest(path)
            for path in sorted(GENERATED.rglob("*"))
            if path.is_file()
        },
        "archives": {
            str(path.relative_to(ROOT)): digest(path) for path in sorted(ASSETS.glob("*.o2r"))
        },
    }
    (ROOT / "scratch/audit/asset-generation.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
