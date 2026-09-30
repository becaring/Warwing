"""Build real pinned dependency sources for host tests; no donor/extraction binaries."""

from pathlib import Path
import hashlib, json, runpy, subprocess

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "scratch/resources-xdk/host-dependencies"
ZLIB_UNITS = "adler32 compress crc32 deflate infback inffast inflate inftrees trees uncompr zutil".split()


def execute(command, folder, env=None):
    folder.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(list(map(str, command)), cwd=folder, env=env, capture_output=True, text=True)
    (folder / "command.json").write_text(json.dumps(list(map(str, command)), indent=2) + "\n")
    (folder / "result.log").write_text(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)


def main():
    locks = json.loads((ROOT / "platform/xbox360/cpp-compat/resources/dependencies.lock.json").read_text())
    for relative, digest in locks["files"].items():
        if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != digest:
            raise RuntimeError("Dependency source drift: " + relative)
    compiler, env = runpy.run_path(str(ROOT / "tests/json/run.py"))["host"]()
    zroot = ROOT / "upstream/dependencies/zlib"
    zout = OUT / "zlib"
    zout.mkdir(parents=True, exist_ok=True)
    objects = []
    for unit in ZLIB_UNITS:
        obj = zout / (unit + ".obj")
        objects.append(obj)
        execute(
            [
                compiler,
                "/nologo",
                "/c",
                "/TC",
                "/MT",
                "/O2",
                "/D_CRT_SECURE_NO_WARNINGS",
                "/I" + str(zroot),
                zroot / (unit + ".c"),
                "/Fo" + str(obj),
            ],
            zout / unit,
            env,
        )
    library = zout / "zlib.lib"
    execute([compiler.parent / "lib.exe", "/nologo", "/OUT:" + str(library)] + objects, zout / "archive", env)
    build = OUT / "libzip-ninja"
    ninja = Path(
        "C:/Program Files/Microsoft Visual Studio/2022/Community/Common7/IDE/CommonExtensions/Microsoft/CMake/Ninja/ninja.exe"
    )
    env["PATH"] += ";C:/Program Files (x86)/Windows Kits/10/bin/10.0.26100.0/x64"
    flags = [
        "-DBUILD_SHARED_LIBS=OFF",
        "-DBUILD_TOOLS=OFF",
        "-DBUILD_REGRESS=OFF",
        "-DBUILD_EXAMPLES=OFF",
        "-DBUILD_DOC=OFF",
        "-DBUILD_OSSFUZZ=OFF",
        "-DENABLE_COMMONCRYPTO=OFF",
        "-DENABLE_GNUTLS=OFF",
        "-DENABLE_MBEDTLS=OFF",
        "-DENABLE_OPENSSL=OFF",
        "-DENABLE_WINDOWS_CRYPTO=OFF",
        "-DENABLE_BZIP2=OFF",
        "-DENABLE_LZMA=OFF",
        "-DENABLE_ZSTD=OFF",
        "-DCMAKE_POLICY_DEFAULT_CMP0091=NEW",
        "-DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreaded",
        "-DZLIB_INCLUDE_DIR=" + str(zroot),
        "-DZLIB_LIBRARY=" + str(library),
    ]
    execute(
        [
            "cmake",
            "-S",
            ROOT / "upstream/dependencies/libzip",
            "-B",
            build,
            "-G",
            "Ninja",
            "-DCMAKE_MAKE_PROGRAM=" + str(ninja),
            "-DCMAKE_C_COMPILER=" + str(compiler),
            "-DCMAKE_BUILD_TYPE=Release",
        ]
        + flags,
        OUT / "configure",
        env,
    )
    execute(
        ["cmake", "--build", build, "--config", "Release", "--target", "zip", "--parallel", "4"], OUT / "build", env
    )
    print("PASS host static zlib 1.3.1 + actual libzip 1.11.4 source build")


if __name__ == "__main__":
    main()
