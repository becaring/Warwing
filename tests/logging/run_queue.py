from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
import runpy as _shipyard_runpy

SHIPYARD_BASE = _shipyard_runpy.run_path(str(ROOT / "tools/platform_base.py"))["resolve"](ROOT)
OUT = ROOT / "scratch/logging-xdk/tests"
GENERATED = ROOT / "scratch/logging-xdk/include"


def run(cmd, name):
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
    (OUT / (name + ".log")).write_text(p.stdout + p.stderr)
    if p.returncode:
        raise RuntimeError(p.stdout + p.stderr)
    return p.stdout


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    subprocess.run(["C:/Python313/python.exe", str(ROOT / "tools/prepare_logging_xdk.py")], check=True)
    vs = subprocess.check_output(
        [
            "C:/Program Files (x86)/Microsoft Visual Studio/Installer/vswhere.exe",
            "-latest",
            "-products",
            "*",
            "-requires",
            "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
            "-property",
            "installationPath",
        ],
        text=True,
    ).strip()
    results = []
    source = ROOT / "tests/logging/queue_cases.cpp"
    native = SHIPYARD_BASE / 'sources/async/native.cpp'
    for label, include in [("original", ROOT / "upstream/dependencies/spdlog/include"), ("xdk", GENERATED)]:
        target = OUT / label
        target.mkdir(exist_ok=True)
        exe = target / "queue.exe"
        batch = target / "build.cmd"
        batch.write_text(
            f"""@echo off\n\
call "{vs}/VC/Auxiliary/Build/vcvars64.bat" \
>nul\n\
cl \
/nologo \
/EHsc \
/std:c++20 \
/utf-8 \
/MT \
/I"{ROOT}" \
/I"{SHIPYARD_BASE}" \
/I"{SHIPYARD_BASE}/sources" \
/I"{include}" \
"{source}" \
"{native}" \
/Fo"{target}/" \
/Fe"{exe}"\n\
exit \
/b \
%errorlevel%\n\
"""
        )
        run(["cmd", "/d", "/c", str(batch)], label + "-compile")
        results.append(run([str(exe)], label + "-run"))
    if results[0] != results[1]:
        raise RuntimeError("Output mismatch")
    print(results[0])
    xdk = Path("C:/Program Files (x86)/Microsoft Xbox 360 SDK")
    print(
        run(
            [
                str(xdk / "bin/win32/cl.exe"),
                "/nologo",
                "/TP",
                "/EHsc",
                "/D_XBOX",
                "/c",
                "/I" + str(ROOT),
                "/I" + str(SHIPYARD_BASE),
                "/I" + str(SHIPYARD_BASE / 'sources'),
                "/I" + str(GENERATED),
                "/I" + str(xdk / "include/xbox"),
                "/Fo" + str(OUT / "queue-xdk.obj"),
                str(source),
            ],
            "xdk-compile",
        )
    )
    print("PASS original/generated host differential and XDK compile, no Xbox runtime.")


if __name__ == "__main__":
    main()
