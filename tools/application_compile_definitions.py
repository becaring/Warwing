"""Read the pinned BattleShip compile definitions for the US application."""

from pathlib import Path
import hashlib, re, subprocess
from game_source_manifest import CMAKE_SHA256

ROOT = Path(__file__).resolve().parents[1]
UP = ROOT / "upstream/BattleShip"


def application_definitions():
    source = UP / "CMakeLists.txt"
    if hashlib.sha256(source.read_bytes()).hexdigest() != CMAKE_SHA256:
        raise ValueError("Application CMake changed; review compile definitions")
    text = source.read_text(encoding="utf-8")
    version = subprocess.run(
        ["git", "-c", "safe.directory=" + UP.as_posix(), "-C", str(UP), "describe", "--tags", "--abbrev=0"],
        capture_output=True,
        text=True,
    )
    version = version.stdout.strip() if version.returncode == 0 else "dev"
    torch = subprocess.run(
        ["git", "-c", "safe.directory=" + (UP / "torch").as_posix(), "-C", str(UP / "torch"), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    sha1 = lambda p: hashlib.sha1(p.read_bytes()).hexdigest()
    recipe = ":".join([torch, sha1(UP / "config.yml")] + [sha1(p) for p in sorted((UP / "yamls/us").glob("*.yml"))])
    variables = {
        "SSB64_VERSION_UC": "US",
        "SSB64_APP_NAME": "BattleShip",
        "BATTLESHIP_VERSION": version,
        "SSB64_ASSET_RECIPE_HASH": hashlib.sha1(recipe.encode()).hexdigest(),
    }
    block = text.split("set(SSB64_COMPILE_DEFS\n", 1)[1].split("\n)", 1)[0]
    result = []
    for line in block.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        line = re.sub(r"\$\{(\w+)\}", lambda m: variables[m[1]], line).replace('\\"', '"')
        if not re.fullmatch(r'[A-Z_][A-Z_0-9]*(?:=(?:[A-Z_0-9]+|"[^"\n]+"))?', line):
            raise ValueError("Unexpected definition syntax: " + line)
        result.append(line)
    if "list(APPEND SSB64_COMPILE_DEFS PORT_HIRES_ENABLED=1)" not in text:
        raise ValueError("US high-resolution capability selection changed")
    result.append("PORT_HIRES_ENABLED=1")
    return result
