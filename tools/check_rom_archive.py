"""Check the console ROM extractor against Torch on the PC, entry by entry.

    python -B tools/check_rom_archive.py <folder with the US ROM> [torch BattleShip.o2r]

Builds rom_archive.cpp with the host compiler, runs ExtractArchive on the folder, and
requires the same entry names and bytes as Torch's archive (scratch/assets by default).
"""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rom_entries
from platform_base import resolve

ROOT = Path(__file__).resolve().parents[1]
DRIVER = r"""
#include "startup/rom_archive.h"
#include <stdio.h>

int main(int argc, char** argv) {
    if (argc != 3) return 2;
    std::string error;
    if (!Smash360Startup::ExtractArchive(argv[1], argv[2], error)) {
        fprintf(stderr, "%s\n", error.c_str());
        return 1;
    }
    return 0;
}
"""


def build(folder):
    shipyard = resolve(ROOT)
    rom_entries.generate(folder / "rom_entries.cpp")
    (folder / "driver.cpp").write_text(DRIVER)
    sources = [
        folder / "driver.cpp",
        folder / "rom_entries.cpp",
        ROOT / "platform/xbox360/cpp-compat/startup/rom_archive.cpp",
        shipyard / "sources/rom/rom.cpp",
        shipyard / "sources/archive/stored_zip_writer.cpp",
    ]
    includes = [ROOT / "platform/xbox360/cpp-compat", shipyard / "sources"]
    vswhere = Path(os.environ["ProgramFiles(x86)"]) / "Microsoft Visual Studio/Installer/vswhere.exe"
    installation = subprocess.check_output(
        [str(vswhere), "-latest", "-products", "*", "-requires", "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
         "-property", "installationPath"],
        text=True,
    ).strip()
    command = "cl /nologo /O2 /EHsc /MT /W3 " + " ".join('/I"%s"' % p for p in includes)
    command += " " + " ".join('"%s"' % p for p in sources) + " /Fe:extract.exe"
    batch = folder / "build.cmd"
    batch.write_text('@echo off\ncall "%s/VC/Auxiliary/Build/vcvars64.bat" >nul\n%s\nexit /b %%errorlevel%%\n' % (installation, command))
    result = subprocess.run([os.environ["ComSpec"], "/d", "/c", str(batch)], cwd=folder, capture_output=True, text=True)
    if result.returncode:
        raise SystemExit(result.stdout + result.stderr)
    return folder / "extract.exe"


def main():
    rom_folder = Path(sys.argv[1]).resolve()
    torch = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "scratch/assets/BattleShip.o2r"
    with tempfile.TemporaryDirectory(prefix="smash-rom-archive-") as name:
        folder = Path(name)
        output = folder / "BattleShip.o2r"
        ran = subprocess.run([str(build(folder)), str(rom_folder), str(output)], capture_output=True, text=True, timeout=300)
        if ran.returncode:
            raise SystemExit("extraction failed: " + ran.stdout + ran.stderr)
        with zipfile.ZipFile(torch) as expected, zipfile.ZipFile(output) as actual:
            want, got = set(expected.namelist()), set(actual.namelist())
            if want != got:
                raise SystemExit("entry names differ: missing %s extra %s" % (sorted(want - got)[:5], sorted(got - want)[:5]))
            differ = [n for n in sorted(want) if expected.read(n) != actual.read(n)]
            if differ:
                raise SystemExit("%d entries differ, first %s" % (len(differ), differ[:5]))
            if any(i.compress_type != zipfile.ZIP_STORED for i in actual.infolist()):
                raise SystemExit("extractor wrote compressed entries")
        print("%d entries match Torch byte for byte" % len(want))


if __name__ == "__main__":
    main()
