from pathlib import Path
import runpy, subprocess

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "scratch/controllers-xdk"


def main():
    shipyard = runpy.run_path(str(ROOT / "tools/platform_base.py"))["resolve"](ROOT)
    lower = runpy.run_path(str(ROOT / "platform/xbox360/cpp-compat/controllers/lowering.py"))
    original = ROOT / "tests/controllers-xdk/lowering_contract.cpp"
    # The round-only initializer-list loop is modern host reference vocabulary;
    # transform only audited pair binding and contains syntax for this fixture.
    generated = OUT / "lowering_contract.cpp"
    generated.write_bytes(lower["contains"](lower["pair_bindings"](original.read_bytes())))
    compiler, env = runpy.run_path(str(ROOT / "tests/json/run.py"))["host"]()
    outputs = []
    for label, source in [("original", original), ("generated", generated)]:
        folder = OUT / ("lowering-" + label)
        folder.mkdir(parents=True, exist_ok=True)
        cmd = [
            compiler,
            "/nologo",
            "/std:c++20",
            "/EHsc",
            "/MD",
            "/DNOMINMAX",
            "/I" + str(ROOT / "platform/xbox360/cpp-compat"),
            "/I" + str(shipyard),
            "/I" + str(shipyard / "sources"),
            "/I" + str(shipyard / "sources/value_types"),
            source,
            "/Fo" + str(folder / "test.obj"),
            "/Fe" + str(folder / "test.exe"),
        ]
        build = subprocess.run(list(map(str, cmd)), env=env, cwd=ROOT, capture_output=True, text=True)
        (folder / "compile.log").write_text(build.stdout + build.stderr)
        if build.returncode:
            raise RuntimeError(build.stdout + build.stderr)
        result = subprocess.run([str(folder / "test.exe")], capture_output=True)
        if result.returncode:
            raise RuntimeError("Lowering behavior assertion failed")
        outputs.append(result.stdout)
        (folder / "output.txt").write_bytes(result.stdout)
    assert outputs[0] == outputs[1]
    print(outputs[0].decode().strip())


if __name__ == "__main__":
    main()
