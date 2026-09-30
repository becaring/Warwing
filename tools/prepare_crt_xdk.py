"""Build the owned snprintf adapter object; no executable or XEX link."""

from pathlib import Path
import hashlib
import json
import os
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
from platform_base import resolve as resolve_platform_base

PLATFORM_BASE = resolve_platform_base(ROOT)


def main():
    source = PLATFORM_BASE / "sources/crt"
    out = ROOT / "scratch/crt-xdk"
    out.mkdir(parents=True, exist_ok=True)
    xdk = Path(os.environ.get("XEDK", "C:/Program Files (x86)/Microsoft Xbox 360 SDK"))
    command = [
        str(xdk / "bin/win32/cl.exe"),
        "/nologo",
        "/TP",
        "/MT",
        "/O2",
        "/W3",
        "/D_XBOX",
        "/D_CRT_SECURE_NO_WARNINGS",
        "/I" + str(xdk / "include/xbox"),
        "/c",
        "/FAs",
        "/Fa" + str(out / "snprintf.asm"),
        "/Fo" + str(out / "snprintf.obj"),
        str(source / "format.cpp"),
    ]
    result = subprocess.run(command, cwd=ROOT, capture_output=True)
    (out / "compile.log").write_bytes(result.stdout + result.stderr)
    inputs = [
        source / "format.h",
        source / "format.cpp",
        xdk / "include/xbox/vadefs.h",
        xdk / "include/xbox/stdio.h",
        Path(__file__),
    ]
    report = {
        "command": command,
        "exit": result.returncode,
        "input_sha256": {
            str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs
        },
        "canonical_header": str(source / "format.h"),
        "object": str(out / "snprintf.obj") if result.returncode == 0 else None,
        "scope": (
            "Native PowerPC object compiled from Shipyard; host contract tests separate, Xbox"
            " execution not proven"
        ),
    }
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    formats = []
    upstream = ROOT / "upstream/BattleShip"
    for directory in ("decomp", "port", "debug_tools", "libultraship/src", "libultraship/include"):
        for path in sorted((upstream / directory).rglob("*")):
            if path.suffix not in (".c", ".cpp", ".h", ".hpp"):
                continue
            for number, line in enumerate(
                path.read_text(encoding="utf-8", errors="replace").splitlines(), 1
            ):
                if re.search(r"%[-+ #0-9.*]*z[diouxX]", line):
                    formats.append(
                        {
                            "path": path.relative_to(upstream).as_posix(),
                            "line": number,
                            "text": line.strip(),
                            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        }
                    )
    (out / "format-audit.json").write_text(
        json.dumps(
            {
                "scope": (
                    "Upstream source occurrences, not all selected or enabled; snprintf and"
                    " Smash360_Vsnprintf only are adapted"
                ),
                "z_formats": formats,
            },
            indent=2,
        )
        + "\n"
    )
    print(json.dumps(report, indent=2))
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
