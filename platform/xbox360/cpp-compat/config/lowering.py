"""Reusable range lowering adapted from donor cpp_range_lower + current Prism fix."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "scratch/host-python"))
import tree_sitter as ts
import tree_sitter_cpp

PARSER = ts.Parser(ts.Language(tree_sitter_cpp.language()))


def walk(node):
    yield node
    for child in node.named_children:
        yield from walk(child)


def lower_ranges(source, begin="Smash360Config::Begin", end="Smash360Config::End"):
    for iteration in range(64):
        edits = []
        for node in walk(PARSER.parse(source).root_node):
            if node.type != "for_range_loop":
                continue
            if any(n.type == "for_range_loop" for n in list(walk(node))[1:]):
                continue
            right = node.child_by_field_name("right")
            body = node.child_by_field_name("body")
            decl = node.child_by_field_name("declarator")
            if right.type == "initializer_list":
                raise ValueError("Unaudited initializer-list range")
            opening = next(n for n in node.children if n.type == "(")
            declaration = source[opening.end_byte : decl.end_byte].decode().strip()
            if "[" in declaration:
                raise ValueError("Structured-binding range must be lowered explicitly first")
            suffix = str(node.start_byte)
            rng = "_configRange" + suffix
            it = "_configIt" + suffix
            stop = "_configEnd" + suffix
            inner = body.text.decode()[1:-1] if body.type == "compound_statement" else body.text.decode()
            replacement = (
                "{ auto&& "
                + rng
                + " = "
                + right.text.decode()
                + "; auto "
                + it
                + " = "
                + begin
                + "("
                + rng
                + "); auto "
                + stop
                + " = "
                + end
                + "("
                + rng
                + "); for (; "
                + it
                + " != "
                + stop
                + "; ++"
                + it
                + ") { "
                + declaration
                + " = *"
                + it
                + "; "
                + inner
                + " } }"
            )
            edits.append((node.start_byte, node.end_byte, replacement.encode()))
        if not edits:
            return source
        for start, stop, value in sorted(edits, reverse=True):
            source = source[:start] + value + source[stop:]
    raise ValueError("Unexpected range nesting")
