from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
import runpy as _shipyard_runpy

SHIPYARD_BASE = _shipyard_runpy.run_path(str(ROOT / "tools/platform_base.py"))["resolve"](ROOT)
OUT = ROOT / "scratch/value-types/negative"
INCLUDE = SHIPYARD_BASE / 'sources/value_types'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    vswhere = Path("C:/Program Files (x86)/Microsoft Visual Studio/Installer/vswhere.exe")
    vs = subprocess.check_output(
        [
            str(vswhere),
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
    cases = {
        "double-to-float": "V::variant<int,float> bad=3.5;",
        "pointer-to-bool": 'V::variant<bool> bad="shader";',
        "wrong-get-type": "V::variant<int,float> value; double bad=V::get<double>(value);",
    }
    for name, body in cases.items():
        for standard in (1, 0):
            cpp = OUT / f"{name}-{standard}.cpp"
            cpp.write_text(
                (
                    "#include <variant>\n#define V std\n"
                    if standard
                    else "#include <xbox_compat/variant.h>\n#define V xbox_compat\n"
                )
                + "void rejected() { "
                + body
                + " }\n"
            )
            batch = OUT / f"{name}-{standard}.cmd"
            batch.write_text(
                f"""@echo off\n\
call "{vs}/VC/Auxiliary/Build/vcvars64.bat" >nul\n\
if errorlevel 1 exit /b 1\n\
cl /nologo /Zs /EHsc /std:c++17 /I"{INCLUDE}" "{cpp}"\n\
exit /b %errorlevel%\n\
"""
            )
            run = subprocess.run(["cmd", "/d", "/c", str(batch)], capture_output=True, text=True)
            (OUT / f"{name}-{standard}.log").write_text(run.stdout + run.stderr)
            if run.returncode == 0:
                raise AssertionError(f"{name}: {standard} unexpectedly accepted unsupported/narrowing request")
    xdk = Path("C:/Program Files (x86)/Microsoft Xbox 360 SDK")
    alignment = OUT / "unsupported-align16.cpp"
    alignment.write_text(
        "#include <xbox_compat/variant.h>\n__declspec(align(16)) struct Align16 { char bytes[16]; };\nxbox_compat::variant<int,Align16> blocked;\n"
    )
    command = [
        str(xdk / "bin/win32/cl.exe"),
        "/nologo",
        "/Zs",
        "/TP",
        "/EHsc",
        "/D_XBOX",
        "/I" + str(INCLUDE),
        "/I" + str(xdk / "include/xbox"),
        str(alignment),
    ]
    run = subprocess.run(command, capture_output=True, text=True)
    (OUT / "unsupported-align16.log").write_text(run.stdout + run.stderr)
    if run.returncode == 0 or "negative subscript" not in run.stdout + run.stderr:
        raise AssertionError("XDK over-alignment must fail closed at storage assertion")
    print(
        "PASS std/xbox_compat narrowing and absent-get rejection; XDK unsupported alignment rejected at compile time."
    )


if __name__ == "__main__":
    main()
