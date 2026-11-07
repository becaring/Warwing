"""Keep the previous XEX and empty only Smash's build outputs.

Pinned Git sources, installed host Python dependencies, the host Torch
dependency build cache, ROMs, Xenia state, and old build records are kept.
The generators named in prepare-native.ps1 and build-assets.ps1 recreate these
outputs; application assembly recreates the generated Visual Studio projects.
"""

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRATCH = ROOT / "scratch"
PROJECTS = ROOT / "platform/xbox360"
NAMES = (
    "application-xdk", "assets", "audio-xdk", "audit", "binary-reader-xdk",
    "config-xdk", "context-xdk", "controllers-xdk", "crt-xdk",
    "endian-xdk", "fast-resources-xdk", "fast3d-xdk", "filesystem-xdk",
    "fmt-xdk", "game-xdk", "generated", "graphics-xdk", "gui-widgets-xdk",
    "gui-xdk", "hires-xdk", "imgui-xdk", "input-editor-xdk", "input-xdk",
    "json-xdk", "libultra-xdk", "libzip-xdk", "logging-xdk", "port-xdk",
    "postprocess-xdk", "prism-xdk", "resources-xdk", "runtime-xdk",
    "startup-xdk", "stb-xdk", "thread-pool-xdk", "tinyxml2-xdk",
    "value-types",
)


def targets():
    return [SCRATCH / name for name in NAMES] + [
        PROJECTS / "Smash360.vcxproj", PROJECTS / "Libultraship360.vcxproj"]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean():
    scratch = SCRATCH.resolve()
    projects = PROJECTS.resolve()
    for path in targets():
        resolved = path.resolve()
        if not ((resolved.parent == scratch and path.parent == SCRATCH) or
                (resolved.parent == projects and path.parent == PROJECTS)):
            raise ValueError("Unexpected generated target: " + str(path))
        if path.is_dir() and any(p.name == ".git" for p in path.rglob(".git")):
            raise ValueError("Generated target contains a Git checkout: " + str(path))
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    preserved = SCRATCH / "final-preclean" / stamp
    preserved.mkdir(parents=True, exist_ok=False)
    records = []
    for relative in ("application-xdk/native/build/Warwing.xex",
                     "application-xdk/native/build/build-options.json",
                     "application-xdk/native/assembly-report.json"):
        source = SCRATCH / relative
        if source.is_file():
            target = preserved / source.name
            shutil.copy2(source, target)
            records.append({"source": relative, "sha256": sha(target),
                            "preserved": target.relative_to(ROOT).as_posix()})
    (preserved / "manifest.json").write_text(json.dumps(records, indent=2) + "\n",
                                                encoding="utf-8")
    for path in targets():
        if path.is_dir():
            shutil.rmtree(path)
        elif path.is_file():
            path.unlink()
    (preserved / "emptied.json").write_text(json.dumps(
        [path.relative_to(ROOT).as_posix() for path in targets()], indent=2) + "\n",
        encoding="utf-8")
    print("Preserved", len(records), "prior artifacts in", preserved)
    print("Emptied", len(targets()), "owned generated targets")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--clean", action="store_true")
    args = parser.parse_args()
    if args.list:
        print("\n".join(path.relative_to(ROOT).as_posix() for path in targets()))
    elif args.clean:
        clean()
    else:
        parser.error("choose --list or --clean")
