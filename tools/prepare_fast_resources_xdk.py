"""Project the pinned Fast3D resource readers without altering their formats."""

from pathlib import Path
import hashlib, json, re
from prepare_prism_xdk import mapped, once, PARSER, walk, field, tx, lower_ranges

ROOT = Path(__file__).resolve().parents[1]
UP = ROOT / "upstream/BattleShip/libultraship"
OUT = ROOT / "scratch/fast-resources-xdk/generated"
BASE = ROOT / "platform/xbox360/cpp-compat/fast-resources"


def transform(text, name):
    text = text.replace("std::get<", "xbox_compat::get<")
    if name == "DisplayListFactory.cpp":
        text = once(text, "std::size(values)", "(sizeof(values) / sizeof(values[0]))")
        match = re.search(
            r"std::unordered_map<std::string, uint32_t> renderModes = \{(.*?)\n\};", text, re.S
        )
        if not match:
            raise ValueError("Render mode table changed")
        entries = re.findall(r'\{\s*"([^"]+)"\s*,\s*(\w+)\s*\}', match[1])
        if not entries:
            raise ValueError("Missing mode entries")
        table = "\n".join(
            '    std::make_pair(std::string("' + key + '"), uint32_t(' + value + ")),"
            for key, value in entries
        )
        replacement = (
            "static const std::pair<std::string, uint32_t> renderModeEntries[] = {\n"
            + table
            + "\n};\nstd::unordered_map<std::string, uint32_t> renderModes(renderModeEntries,"
            " renderModeEntries + sizeof(renderModeEntries)/sizeof(renderModeEntries[0]));"
        )
        text = text[: match.start()] + replacement + text[match.end() :]
        # gs* command macros expand to aggregate initializers. A local Gfx
        # declaration supports these in XDK without changing command bits or
        # evaluating any argument twice. Retain each original initializer.
        data = text.encode()
        edits = []
        for node in walk(PARSER.parse(data).root_node):
            if node.type != "assignment_expression" or tx(field(node, "left")) != "g":
                continue
            right = field(node, "right")
            if right.type not in ("call_expression", "initializer_list"):
                continue
            if node.parent.type != "expression_statement":
                raise ValueError("Changed Gfx assignment context")
            rhs = tx(right)
            if "//" in rhs:
                raise ValueError(
                    "Comment in multiline Gfx initializer requires explicit preservation"
                )
            # Keep each macro invocation on one physical line: source mapping
            # directives must never be inserted between its argument lines.
            rhs = " ".join(rhs.splitlines())
            edits.append(
                (
                    node.parent.start_byte,
                    node.parent.end_byte,
                    ("{ Gfx command = " + rhs + "; g = command; }").encode(),
                )
            )
        for start, end, value in sorted(edits, reverse=True):
            data = data[:start] + value + data[end:]
        text = data.decode()
    return '#include "prism/compat.h"\n' + lower_ranges(text.encode()).decode()


def main():
    records = []
    for rel, expected in json.loads((BASE / "source-lock.json").read_text()).items():
        source = UP / rel
        if hashlib.sha256(source.read_bytes()).hexdigest() != expected:
            raise ValueError("Resource source drift: " + rel)
        target = OUT / rel
        mapped(
            "upstream/BattleShip/libultraship/" + rel,
            transform(source.read_text(encoding="utf-8-sig"), source.name),
            target,
        )
        records.append(
            {
                "source": rel,
                "sha256": expected,
                "generated_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            }
        )
    (OUT.parent / "manifest.json").write_text(json.dumps(records, indent=2) + "\n")


if __name__ == "__main__":
    main()
