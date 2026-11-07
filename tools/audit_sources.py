"""Read-only source audit; writes reports under Smash360/scratch/audit only.

This reconstructs sources for review. It does not build for Xbox or check runtime behavior.
"""

from pathlib import Path
import hashlib
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BATTLESHIP = ROOT / "upstream/BattleShip"
OUT = ROOT / "scratch/audit"
OUT.mkdir(parents=True, exist_ok=True)

REVISIONS = {
    ".": "07d04c5a8d3b1b712e2a749cbdd3812588bdb756",
    "decomp": "2898d4d94e998ddb4e971addf7f6d85a39792f3d",
    "libultraship": "89d9de83a8d09bd7d3b7bc7f8d08554ee2ce8459",
    "torch": "3aa9c9739af95659f19adc73afeb12df93957fc3",
}


def git(path, *args):
    # Fetch may run as the desktop user and audit as the sandbox user. Trust
    # only this explicit checkout for this invocation; never change global Git.
    return subprocess.check_output(
        ["git", "-c", "safe.directory=" + path.resolve().as_posix(), "-C", str(path), *args], text=True
    ).strip()


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def main():
    sources = []
    for relative, expected in REVISIONS.items():
        path = BATTLESHIP / relative
        actual = git(path, "rev-parse", "HEAD")
        status = git(path, "status", "--porcelain")
        sources.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "url": git(path, "remote", "get-url", "origin"),
                "expected": expected,
                "actual": actual,
                "matches": actual == expected,
                "status": status,
            }
        )
    write("source-revisions.json", sources)
    if any(not item["matches"] or item["status"] for item in sources):
        raise SystemExit("Source revisions differ or checkouts are dirty; inspect source-revisions.json")

    # These patterns find audit candidates only; they prove nothing about the code.
    patterns = {
        """\
desktop_platform""": """\
SDL_\\w+|<windows\\.h>|<dbghelp\\.h>|<psapi\\.h>|<unistd\\.h>|\
<dlfcn\\.h>|\\b(?:dlopen|dlsym|popen|fork|execv|CreateProcess|\
ShellExecute|GetProcAddress|LoadLibrary)\\w*\\b""",
        """\
standard_runtime""": """\
std::(?:filesystem|thread|mutex|recursive_mutex|condition_variable|\
future|shared_future|promise|async|chrono|atomic|variant|optional|\
visit)\\b|\\bthread_local\\b""",
        "compiler_syntax": r"\b(?:constexpr|consteval|constinit|nullptr|noexcept|override|final)\b|\benum\s+class\b|if\s+constexpr|auto\s*\[",
        """\
endian_layout""": """\
(?:[Bb]yte[Ss]wap|byteswap|bswap|BSWAP|SWAP16|SWAP32|SWAP64|\
IS_BIG_ENDIAN|IS_BIGENDIAN|__BYTE_ORDER|__BIG_ENDIAN|reinterpret_cast|\
#pragma\\s+pack)""",
    }
    compiled = {key: re.compile(value) for key, value in patterns.items()}
    candidates = []
    for subtree in ("port", "libultraship/src", "libultraship/include", "decomp/include", "decomp/src/sys"):
        for path in sorted((BATTLESHIP / subtree).rglob("*")):
            if path.suffix not in (".c", ".cpp", ".h", ".hpp"):
                continue
            for number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                groups = [key for key, regex in compiled.items() if regex.search(line)]
                if groups:
                    candidates.append(
                        {
                            "path": path.relative_to(BATTLESHIP).as_posix(),
                            "line": number,
                            "categories": groups,
                            "text": line.strip(),
                        }
                    )
    write(
        "source-candidates.json",
        {
            "scope": "Lexical audit candidates; comments and inactive platform branches included. Not a reachability or completeness proof.",
            "patterns": patterns,
            "matches": candidates,
        },
    )

    donor = Path("D:/Projects/SoH360")
    donor_paths = list((donor / "platform/xbox360").rglob("*"))
    donor_paths += [
        donor / "tools/c89_lower.py",
        donor / "tools/prepare_xbox_c.py",
        donor / "upstream/libultraship/libultraship/CompilerCompat.h",
    ]
    write(
        "soh360-donor-hashes.json",
        {
            "root": str(donor),
            "purpose": "Read-only observed donor snapshot; no files imported yet",
            "files": [
                {"path": path.relative_to(donor).as_posix(), "sha256": sha256(path)}
                for path in sorted(donor_paths)
                if path.is_file()
            ],
        },
    )
    print(f"Pinned sources verified: {len(sources)} clean checkouts")
    print(f"Source audit candidates: {len(candidates)} in {len({item['path'] for item in candidates})} files")
    print(f"Reports: {OUT}")


if __name__ == "__main__":
    main()
