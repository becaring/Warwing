from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
import runpy as _shipyard_runpy

SHIPYARD_BASE = _shipyard_runpy.run_path(str(ROOT / "tools/platform_base.py"))["resolve"](ROOT)
OUT = ROOT / "scratch/logging-xdk/chrono-tests"


def run(cmd, name):
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
    (OUT / (name + ".log")).write_text(p.stdout + p.stderr)
    if p.returncode:
        raise RuntimeError(p.stdout + p.stderr)
    return p.stdout


def main():
    OUT.mkdir(parents=True, exist_ok=True)
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
    source = ROOT / "tests/logging/chrono_cases.cpp"
    native = SHIPYARD_BASE / 'sources/clock/chrono.cpp'
    results = []
    for standard in (1, 0):
        target = OUT / str(standard)
        target.mkdir(exist_ok=True)
        exe = target / "chrono.exe"
        batch = target / "build.cmd"
        batch.write_text(
            f"""@echo off\n\
call "{vs}/VC/Auxiliary/Build/vcvars64.bat" \
>nul\n\
cl \
/nologo \
/EHsc \
/std:c++20 \
/MT \
/DUSE_STD_CHRONO={standard} \
/I"{ROOT}" \
/I"{SHIPYARD_BASE}" \
/I"{SHIPYARD_BASE}/sources" \
"{source}" \
"{native}" \
/Fo"{target}/" \
/Fe"{exe}"\n\
exit \
/b \
%errorlevel%\n\
"""
        )
        run(["cmd", "/d", "/c", str(batch)], str(standard) + "-compile")
        results.append(run([str(exe)], str(standard) + "-run"))
    if results[0] != results[1]:
        raise RuntimeError("std/compat difference")
    target = OUT / "frequency"
    target.mkdir(exist_ok=True)
    exe = target / "frequency.exe"
    batch = target / "build.cmd"
    frequency_source = ROOT / "tests/logging/chrono_frequency_cases.cpp"
    batch.write_text(
        f"""@echo off\n\
call "{vs}/VC/Auxiliary/Build/vcvars64.bat" \
>nul\n\
cl \
/nologo \
/EHsc \
/std:c++20 \
/MT \
/I"{ROOT}" \
/I"{SHIPYARD_BASE}" \
/I"{SHIPYARD_BASE}/sources" \
"{frequency_source}" \
/Fo"{target}/" \
/Fe"{exe}"\n\
exit \
/b \
%errorlevel%\n\
"""
    )
    run(["cmd", "/d", "/c", str(batch)], "frequency-compile")
    print(run([str(exe)], "frequency-run"))
    xdk = Path("C:/Program Files (x86)/Microsoft Xbox 360 SDK")
    for p in (source, native):
        print(
            run(
                [
                    str(xdk / "bin/win32/cl.exe"),
                    "/nologo",
                    "/TP",
                    "/EHsc",
                    "/D_XBOX",
                    "/DUSE_STD_CHRONO=0",
                    "/c",
                    "/I" + str(ROOT),
                    "/I" + str(SHIPYARD_BASE),
                    "/I" + str(SHIPYARD_BASE / 'sources'),
                    "/I" + str(xdk / "include/xbox"),
                    "/Fo" + str(OUT / (p.stem + ".obj")),
                    str(p),
                ],
                p.stem + "-xdk",
            )
        )
    print(results[0].splitlines()[-1])
    print("PASS std/compat host differential and XDK object compilation.")


if __name__ == "__main__":
    main()
