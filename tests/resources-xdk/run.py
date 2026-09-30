"""Original/generated actual resource+archive integration on Windows."""

from pathlib import Path
import hashlib, json, re, runpy, subprocess, shutil, zipfile, struct

ROOT = Path(__file__).resolve().parents[2]
import runpy as _shipyard_runpy

SHIPYARD_BASE = _shipyard_runpy.run_path(str(ROOT / "tools/platform_base.py"))["resolve"](ROOT)
OUT = ROOT / "scratch/resources-xdk"
LUS = ROOT / "upstream/BattleShip/libultraship"


def execute(args, folder, env=None, timeout=120):
    folder.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(list(map(str, args)), cwd=folder, env=env, text=True, capture_output=True, timeout=timeout)
    (folder / "command.json").write_text(json.dumps(list(map(str, args)), indent=2) + "\n")
    (folder / "result.log").write_text(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    return result


def fixture(root):
    (root / "folder/assets").mkdir(parents=True, exist_ok=True)
    manifest = {
        "name": "Folder fixture",
        "binaries": {"xbox": "plugin.bin"},
        "dependencies": ["first", "second"],
        "code-version": 3,
    }
    entries = {"assets/folder.json": '{"value":7}', "bad/data.json": "{broken", "probe/data": "probe"}
    entries["manifest.json"] = json.dumps(manifest)

    def binary(data, type_id=0x4A534F4E):
        return struct.pack("<BBHIIQ", 0, 0, 0, type_id, 0, 0) + bytes(44) + data.encode() + b"\0"

    for name, data in entries.items():
        target = root / "folder" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(
            data.encode() + b"\0"
            if name == "manifest.json"
            else binary(data, 0x50524F42 if name.startswith("probe/") else 0x4A534F4E)
        )
        # Earlier failed fixture revisions used sidecars; remove these exact
        # known files only, inside this explicit generated fixture root.
        sidecar = target.with_name(target.name + ".meta")
        if sidecar.exists():
            sidecar.unlink()
    with zipfile.ZipFile(root / "archive.o2r", "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps({"name": "Zip fixture"}))
        archive.writestr("assets/zip.json", binary('{"value":9}'))
    for name in ("corrupt.o2r", "failure.o2r"):
        with zipfile.ZipFile(root / name, "w", zipfile.ZIP_STORED) as archive:
            archive.writestr("data", "uncorrupted payload")
    corrupt = bytearray((root / "corrupt.o2r").read_bytes())
    central = corrupt.index(b"PK\x01\x02")
    checksum = struct.unpack_from("<I", corrupt, central + 16)[0]
    struct.pack_into("<I", corrupt, central + 16, checksum ^ 0xFFFFFFFF)
    (root / "corrupt.o2r").write_bytes(corrupt)


def build(adapted, libzip_library=None):
    mode = "generated" if adapted else "original"
    folder = OUT / ("integration-" + mode)
    folder.mkdir(parents=True, exist_ok=True)
    fixture(folder / "data")
    compiler, env = runpy.run_path(str(ROOT / "tests/json/run.py"))["host"]()
    sdk = Path("C:/Program Files (x86)/Windows Kits/10/Include/10.0.26100.0")
    env["INCLUDE"] += ";" + str(sdk / "winrt") + ";" + str(sdk / "cppwinrt")
    deps = OUT / "host-dependencies"
    if not (deps / "libzip-ninja/lib/zip.lib").exists():
        raise RuntimeError("Run dependencies.py first")
    sdl = folder / "include/SDL2"
    sdl.mkdir(parents=True, exist_ok=True)
    for p in (ROOT / "upstream/dependencies/SDL/include").glob("*.h"):
        shutil.copyfile(p, sdl / p.name)
    cvars = (LUS / "cmake/cvars.cmake").read_text()
    (folder / "cvars.h").write_text(
        "\n".join(
            "#define " + key + ' "' + value + '"'
            for key, value in re.findall(r'set\((CVAR_\w+) "([^"\n]+)" CACHE STRING ""\)', cvars)
        )
        + "\n"
    )
    if adapted:
        paths = runpy.run_path(str(ROOT / "tests/resources-xdk/compile.py"))["paths"]()
    else:
        paths = [
            ROOT / "upstream/dependencies/json/include",
            LUS / "include",
            LUS / "src",
            ROOT / "upstream/dependencies/thread-pool/include",
            OUT / "libzip-public",
            ROOT / "upstream/dependencies/libzip/lib",
        ]
    paths += [
        folder / "include",
        ROOT / "upstream/dependencies/spdlog/include",
        ROOT / "upstream/dependencies/tinyxml2",
        ROOT / "upstream/dependencies/imgui",
        ROOT / "upstream/BattleShip/torch/lib/n64graphics",
    ]
    source_root = OUT / "generated" if adapted else LUS
    sources = sorted((source_root / "src/ship/resource").rglob("*.cpp"))
    sources = [p for p in sources if p.name != "OtrArchive.cpp"]
    sources += [
        ROOT / "tests/resources-xdk/resource_contract.cpp",
        ROOT / "tests/resources-xdk/context_fixture.cpp",
        ROOT / "upstream/dependencies/tinyxml2/tinyxml2.cpp",
    ]
    sources += [source_root / ("src/ship/utils/" + unit) for unit in ("Utils.cpp", "StrHash64.cpp", "glob.c")]
    binary = ROOT / "scratch/binary-reader-xdk/generated" if adapted else LUS
    sources += [
        binary / ("src/ship/utils/binarytools/" + name + ".cpp") for name in ("Stream", "MemoryStream", "BinaryReader")
    ]
    sources += [(ROOT / "scratch/config-xdk/generated" if adapted else LUS) / "src/ship/utils/StringHelper.cpp"]
    if adapted:
        sources += [
            SHIPYARD_BASE / 'sources/json/json.cpp',
            SHIPYARD_BASE / 'sources/async/native.cpp',
            SHIPYARD_BASE / 'sources/filesystem/filesystem.cpp',
        ]
    headers = sorted(
        {p for base in paths for p in base.rglob("*") if p.is_file() and p.suffix in (".h", ".hpp", ".inl")}
    )
    header_hash = hashlib.sha256()
    for header in headers:
        header_hash.update(str(header).encode())
        header_hash.update(header.read_bytes())
    objects = []
    for index, source in enumerate(sources):
        obj = folder / ("unit-" + str(index) + ".obj")
        objects.append(obj)
        command = (
            [
                compiler,
                "/nologo",
                "/c",
                "/TC" if source.suffix == ".c" else "/TP",
                "/std:c++20",
                "/utf-8",
                "/EHsc",
                "/MT",
                "/Gy",
                "/O1",
                "/W3",
                "/DNOMINMAX",
                "/DDISABLE_SCRIPTING",
                "/DSDL_MAIN_HANDLED",
                "/D_CRT_SECURE_NO_WARNINGS",
                "/FI" + str(folder / "cvars.h"),
            ]
            + ["/I" + str(p) for p in paths]
            + [source, "/Fo" + str(obj)]
        )
        if adapted:
            command.insert(1, "/DRESOURCE_ADAPTED")
        stamp = folder / ("unit-" + str(index) + ".sha256")
        digest = hashlib.sha256(
            header_hash.digest() + source.read_bytes() + json.dumps(list(map(str, command))).encode()
        ).hexdigest()
        if not obj.exists() or not stamp.exists() or stamp.read_text() != digest:
            execute(command, folder / ("compile-" + source.stem), env)
            stamp.write_text(digest)
    exe = folder / "test.exe"
    execute(
        [compiler.parent / "link.exe", "/nologo", "/OPT:REF", "/OUT:" + str(exe)]
        + objects
        + [libzip_library or deps / "libzip-ninja/lib/zip.lib", deps / "zlib/zlib.lib", "advapi32.lib"],
        folder / "link",
        env,
    )
    result = execute([exe, folder / "data", folder / "result.json"], folder / "run", timeout=30)
    print(mode, result.stdout.strip())
    return (folder / "result.json").read_bytes()


def main():
    runpy.run_path(str(ROOT / "tools/prepare_resources_xdk.py"))["prepare"]()
    original = build(False)
    generated = build(True)
    if original != generated:
        raise RuntimeError("Actual resource outputs diverged")
    digest = hashlib.sha256(generated).hexdigest()
    print("PASS identical original/generated resource output", digest)
    base = OUT / "integration-original"
    try:
        execute([base / "test.exe", base / "data", base / "single.json", "single"], base / "single-worker", timeout=5)
        raise RuntimeError("Original single-worker deadlock unexpectedly absent")
    except subprocess.TimeoutExpired as error:
        output = error.stdout or b""
        if isinstance(output, bytes):
            output = output.decode(errors="replace")
        if "ENTER single-worker nested load" not in output:
            raise RuntimeError("Timeout before expected blocked load")
        (base / "single-worker/result.log").write_text(
            output + "\nEXPECTED TIMEOUT: nested load cannot run behind its blocked sole worker\n"
        )
        print("PASS reproduced original single-worker nested load timeout")
    base = OUT / "integration-generated"
    for mode in ("single", "teardown"):
        result = execute([base / "test.exe", base / "data", base / (mode + ".json"), mode], base / mode, timeout=15)
        print(result.stdout.strip())
    (OUT / "host-integration.json").write_text(
        json.dumps(
            {
                "passed": True,
                "result_sha256": digest,
                "scope": "Actual ResourceManager/Loader/Folder/O2r/Archive/ArchiveManager; test-only Context service injection; existing full host logging",
                "regressions": [
                    "original single-worker timeout",
                    "corrected single-worker queued load",
                    "blocked-worker destructor drain",
                    "reentrant resource destructor after cache erase unlock",
                    "parallel missing loads",
                    "corrupt ZIP read rejected",
                    "failed ZIP replacement safely discarded",
                ],
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
