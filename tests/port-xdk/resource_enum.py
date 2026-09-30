"""Verify the actual unsigned ResourceType projection on Win32 and PowerPC."""

from pathlib import Path
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "scratch/port-xdk/enum-tests"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    headers = {
        "original": ROOT / "upstream/BattleShip/port/resource/ResourceType.h",
        "projected": ROOT / "scratch/port-xdk/compile-tree/port/resource/ResourceType.h",
    }
    # The only actual qualified consumer passes the exact RELO value to the
    # real ResourceLoader registration. No ResourceType object crosses an ABI.
    uses = []
    for path in (ROOT / "upstream/BattleShip/port").rglob("*.cpp"):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "SSB64::ResourceType" in line:
                uses.append((str(path.relative_to(ROOT)), number, line.strip()))
    assert len(uses) == 1 and "static_cast<uint32_t>(SSB64::ResourceType::SSB64Reloc)" in uses[0][2], uses
    for name, header in headers.items():
        source = OUT / (name + ".cpp")
        source.write_text(
            '#include "'
            + header.as_posix()
            + '"\n#include <stdint.h>\n'
            + """
typedef char ResourceWidth[(sizeof(SSB64::ResourceType)==sizeof(uint32_t))?1:-1];
typedef char ResourceUnsigned[(static_cast<SSB64::ResourceType>(-1)>static_cast<SSB64::ResourceType>(0))?1:-1];
typedef char ResourceValue[(static_cast<uint32_t>(SSB64::ResourceType::SSB64Reloc)==0x52454c4fu)?1:-1];
extern "C" __declspec(noinline) uint64_t WidenResource(SSB64::ResourceType value) { return static_cast<uint64_t>(value); }
int main() { return WidenResource(static_cast<SSB64::ResourceType>(0x80000000u))==0x80000000ULL ? 0 : 1; }
"""
        )
        batch = OUT / (name + ".cmd")
        batch.write_text(
            """\
@echo off
call \"C:/Program Files/Microsoft Visual \
Studio/2022/Community/VC/Auxiliary/Build/vcvars32.bat\" >nul
cl /nologo /MT /EHsc /std:c++20 /Fe:"""
            + name
            + '.exe "'
            + str(source)
            + '"\n'
        )
        result = subprocess.run(["cmd.exe", "/d", "/c", str(batch)], cwd=OUT, capture_output=True)
        (OUT / (name + "-host.log")).write_bytes(result.stdout + result.stderr)
        assert result.returncode == 0, (result.stdout + result.stderr).decode(errors="replace")
        assert subprocess.run([str(OUT / (name + ".exe"))], cwd=OUT).returncode == 0
    sdk = Path("C:/Program Files (x86)/Microsoft Xbox 360 SDK")
    command = [
        str(sdk / "bin/win32/cl.exe"),
        "/nologo",
        "/TP",
        "/MT",
        "/EHsc",
        "/c",
        "/O2",
        "/I" + str(sdk / "include/xbox"),
        "/FAsc",
        "/Fa" + str(OUT / "projected.asm"),
        "/Fo" + str(OUT / "projected.obj"),
        str(OUT / "projected.cpp"),
    ]
    result = subprocess.run(command, cwd=OUT, capture_output=True)
    (OUT / "native.log").write_bytes(result.stdout + result.stderr)
    assert result.returncode == 0, (result.stdout + result.stderr).decode(errors="replace")
    assert (OUT / "projected.obj").read_bytes()[:2] == b"\xf2\x01"
    report = {
        "actual_qualified_uses": uses,
        "host_original_projected_high_bit_widening": True,
        "native_unsigned_width_value_assertions": True,
        "native_runtime": False,
        "input_sha256": {k: hashlib.sha256(p.read_bytes()).hexdigest() for k, p in headers.items()},
        "native_command": command,
    }
    (OUT / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
