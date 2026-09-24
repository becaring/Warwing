"""Audit pinned filesystem consumers and generate a narrowly lowered real Directory header."""
import difflib
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
OWN = ROOT / "platform/xbox360/cpp-compat/filesystem"
OUT = ROOT / "scratch/filesystem-xdk"
DIRECTORY = "upstream/BattleShip/libultraship/include/ship/utils/filesystemtools/Directory.h"

def main():
    locks = json.loads((OWN / "sources.lock.json").read_text())
    sources = {}
    for relative, expected in locks["sources"].items():
        raw = (ROOT / relative).read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise SystemExit("Filesystem consumer hash mismatch: " + relative)
        sources[relative] = raw.decode("utf-8").replace("\r\n", "\n")
    audit = []
    for relative, text in sources.items():
        matches = []
        for number, line in enumerate(text.splitlines(), 1):
            if re.search(r"(?:std::filesystem|\bfs::|(?:ifstream|ofstream|fopen|rename|remove)\s*\()", line):
                matches.append({"line": number, "source": line.strip()})
        audit.append({"path": relative, "sha256": locks["sources"][relative], "uses": matches})
    original = sources[DIRECTORY]
    text, count = re.subn(r"#if __has_include\(<filesystem>\).*?#endif", '#include "filesystem.h"\nnamespace fs = xbox_compat::filesystem;', original, count=1, flags=re.S)
    if count != 1: raise SystemExit("Directory filesystem include shape changed")
    old = "for (auto& p : fs::recursive_directory_iterator(dir)) {"
    new = "for (fs::recursive_directory_iterator it(dir), finish; it != finish; ++it) {\n                const fs::directory_entry& p = *it;"
    if text.count(old) != 1: raise SystemExit("Directory loop shape changed")
    text = text.replace(old, new)
    mapped = []
    old_lines, new_lines = original.splitlines(True), text.splitlines(True)
    for kind, old_start, old_end, new_start, new_end in difflib.SequenceMatcher(None, old_lines, new_lines, autojunk=False).get_opcodes():
        if new_start != new_end:
            mapped.append(f'#line {old_start+1} "{DIRECTORY}"\n')
            mapped.extend(new_lines[new_start:new_end])
    generated = "#ifndef SMASH360_GENERATED_DIRECTORY_H\n#define SMASH360_GENERATED_DIRECTORY_H\n" + "".join(mapped) + "\n#endif\n"
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "Directory.h").write_text(generated, encoding="utf-8", newline="\n")
    (OUT / "provenance.json").write_text(json.dumps({"historical_donor_sha256": locks["donor_sha256"], "consumers": audit,
        "generated_directory_sha256": hashlib.sha256(generated.encode()).hexdigest(),
        "changes": ["filesystem include and namespace", "range-for lowered to prefix input iterator"],
        "limits": "Actual Directory header only; Config/ArchiveManager translation units are audited, not replaced or compiled by this probe."}, indent=2)+"\n")
    print("Generated mapped current Directory.h; audited " + str(len(audit)) + " pinned filesystem consumers")

if __name__ == "__main__": main()
