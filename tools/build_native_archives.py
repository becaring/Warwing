"""Build production libzip/zlib for XDK from their pinned owned sources."""

from pathlib import Path
import hashlib, json, os, subprocess
from prepare_libzip_xdk import prepare
from platform_base import resolve as resolve_platform_base

ROOT = Path(__file__).resolve().parents[1]
PLATFORM_BASE = resolve_platform_base(ROOT)
SDK = Path(os.environ.get("XEDK", "C:/Program Files (x86)/Microsoft Xbox 360 SDK"))
OUT = ROOT / "scratch/libzip-xdk"
BUILD = OUT / "xdk"
# zlib's compression/decompression core; no gzip filesystem API is consumed.
ZLIB_UNITS = "adler32 compress crc32 deflate infback inffast inflate inftrees trees uncompr zutil".split()


def main():
    manifest = prepare()
    BUILD.mkdir(parents=True, exist_ok=True)
    locks = json.loads((ROOT / "dependencies.lock.json").read_text())
    for name in ("zlib", "libzip"):
        lock = next(item for item in locks if item["path"] == "upstream/dependencies/" + name)
        path = ROOT / lock["path"]
        git = ["git", "-c", "safe.directory=" + path.as_posix(), "-C", str(path)]
        head = subprocess.run(git + ["rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(
            git + ["status", "--porcelain", "--untracked-files=no"], capture_output=True, text=True, check=True
        ).stdout
        if head != lock["revision"] or dirty:
            raise ValueError("Compression dependency revision/working tree changed: " + name)
    records = []
    flags = [
        "/nologo",
        "/c",
        "/MT",
        "/W3",
        "/DNOMINMAX",
        "/D_CRT_SECURE_NO_WARNINGS",
        "/D_XBOX",
        "/I" + str(SDK / "include/xbox"),
        "/I" + str(OUT / "generated"),
        "/I" + str(PLATFORM_BASE / "sources"),
        "/I" + str(ROOT / "platform/xbox360/cpp-compat"),
        "/I" + str(ROOT / "upstream/dependencies/zlib"),
    ]
    groups = {
        "zip": [OUT / "generated" / name for name in manifest["units"]]
        + [PLATFORM_BASE / "sources/libzip/native_boundary.cpp"],
        "zlib": [ROOT / "upstream/dependencies/zlib" / (name + ".c") for name in ZLIB_UNITS],
    }
    for group, sources in groups.items():
        objects = []
        for source in sources:
            obj = BUILD / ((("zlib-" if group == "zlib" else "") + source.stem) + ".obj")
            objects.append(obj)
            command = (
                [str(SDK / "bin/win32/cl.exe")]
                + flags
                + (["/TP", "/EHsc"] if source.suffix == ".cpp" else ["/TC"])
                + [str(source), "/Fo" + str(obj)]
            )
            result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            (BUILD / (obj.stem + ".log")).write_text(result.stdout + result.stderr)
            source_name = (
                "shipyard/" + source.relative_to(PLATFORM_BASE).as_posix()
                if source.is_relative_to(PLATFORM_BASE)
                else source.relative_to(ROOT).as_posix()
            )
            records.append(
                {
                    "source": source_name,
                    "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                    "command": command,
                    "exit": result.returncode,
                }
            )
            if result.returncode:
                raise RuntimeError("Native archive source failed: " + str(source))
        response = BUILD / (group + "-production.rsp")
        response.write_text(
            '/nologo\n/OUT:"'
            + str(BUILD / (group + ".lib"))
            + '"\n'
            + "\n".join('"' + str(p) + '"' for p in objects)
            + "\n"
        )
        result = subprocess.run(
            [str(SDK / "bin/win32/lib.exe"), "@" + str(response)], cwd=ROOT, capture_output=True, text=True
        )
        (BUILD / (group + "-production.log")).write_text(result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError("Native archive failed: " + group)
    (OUT / "production-build.json").write_text(
        json.dumps(
            {
                "objects": records,
                "libraries": {
                    name: hashlib.sha256((BUILD / (name + ".lib")).read_bytes()).hexdigest() for name in groups
                },
            },
            indent=2,
        )
        + "\n"
    )
    print("Built production Xbox libzip and zlib")


if __name__ == "__main__":
    main()
