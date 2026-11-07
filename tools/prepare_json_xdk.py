"""Pin and list JSON 3.12.0, and generate XDK algorithms for the API the port reaches.

The full generic basic_json template is not downleveled. The separate
compiler-library backend keeps the pinned lexical and numeric algorithms and
exposes the reviewed runtime interfaces under the unchanged LUS consumers.
"""

import hashlib
import json
from pathlib import Path
import re
import subprocess
import runpy
from platform_base import resolve as resolve_platform_base

ROOT = Path(__file__).resolve().parents[1]
PLATFORM_BASE = resolve_platform_base(ROOT)
SOURCE = ROOT / "upstream/dependencies/json"
OUT = ROOT / "scratch/json-xdk/generated"
COMMIT = "55f93686c01528224f448c19128836e7df245f72"
HASHES = {
    "include/nlohmann/detail/abi_macros.hpp": (
        "878aea894ebfd3af5095b79506c399017443f02988c2581b177b497202c3ac50"
    ),
    "include/nlohmann/detail/string_escape.hpp": (
        "088b06aa33cae1366a0e5ccfbd9c0c86909dbcad8ad52a63ec5acb55e674357e"
    ),
    "include/nlohmann/detail/meta/type_traits.hpp": (
        "c50fadc087dbc1ef1d8d82289f5b8f9b09c8c76aff2f62f0e6a1be060d37c4e8"
    ),
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def closure(source):
    pending = ["nlohmann/json.hpp"]
    visited = {}
    while pending:
        relative = pending.pop()
        if relative in visited:
            continue
        path = source / "include" / relative
        raw = path.read_bytes()
        text = raw.decode("utf-8")
        dependencies = sorted(set(re.findall(r'#\s*include\s*[<"](nlohmann/[^>"\n]+)[>"]', text)))
        features = {}
        for label, pattern in {
            "packs": r"(?:typename|class)\s*\.\.\.|\.\.\.\s*[A-Za-z_]|[A-Za-z_]\w*\s*\.\.\.",
            "alias_declarations": r"\busing\s+\w+\s*=",
            "scoped_enums": r"\benum\s+class\b",
            "constexpr": r"\bconstexpr\b",
            "noexcept": r"\bnoexcept\b",
            "allocator_traits": r"\bstd::allocator_traits\b",
        }.items():
            lines = [
                number
                for number, line in enumerate(text.splitlines(), 1)
                if re.search(pattern, line)
            ]
            if lines:
                features[label] = lines
        visited[relative] = {
            "sha256": sha(raw),
            "includes": dependencies,
            "lexical_feature_lines": features,
        }
        pending.extend(dependencies)
    return visited


def transform_escape(raw, path):
    expected = HASHES["include/nlohmann/detail/string_escape.hpp"]
    if sha(raw) != expected:
        raise ValueError("string_escape.hpp source SHA-256 mismatch")
    text = raw.decode("utf-8").replace("\r\n", "\n")
    changes = (
        (
            '    replace_substring(s, StringType{"~"}, StringType{"~0"});',
            '    replace_substring(s, StringType("~"), StringType("~0"));',
        ),
        (
            '    replace_substring(s, StringType{"/"}, StringType{"~1"});',
            '    replace_substring(s, StringType("/"), StringType("~1"));',
        ),
        (
            '    replace_substring(s, StringType{"~1"}, StringType{"/"});',
            '    replace_substring(s, StringType("~1"), StringType("/"));',
        ),
        (
            '    replace_substring(s, StringType{"~0"}, StringType{"~"});',
            '    replace_substring(s, StringType("~0"), StringType("~"));',
        ),
    )
    for before, after in changes:
        if text.count(before) != 1:
            raise ValueError("unexpected escaping implementation")
        text = text.replace(before, after)
    prefix = (
        "// Generated actual JSON 3.12.0 leaf; not a full XDK JSON implementation.\n"
        "#ifndef SMASH360_GENERATED_JSON_STRING_ESCAPE_HPP\n"
        "#define SMASH360_GENERATED_JSON_STRING_ESCAPE_HPP\n"
        '#include "json/config.h"\n'
        f'#line 1 "{path.as_posix()}"\n'
    )
    return (prefix + text + "\n#endif\n").encode("utf-8")


def transform_conversion_registry(raw, path):
    if sha(raw) != HASHES["include/nlohmann/detail/meta/type_traits.hpp"]:
        raise ValueError("type_traits.hpp source SHA-256 mismatch")
    text = raw.decode("utf-8").replace("\r\n", "\n")
    changes = (
        (
            (
                "    static constexpr bool value = is_detected<get_template_function, const"
                " BasicJsonType&, T>::value;"
            ),
            (
                "    static const bool value = Smash360Json::RuntimeConversion<BasicJsonType,"
                " T>::getable;"
            ),
        ),
        (
            (
                "    static constexpr bool value =\n        is_detected_exact<void,"
                " from_json_function, serializer,\n        const BasicJsonType&, T&>::value;"
            ),
            (
                "    static const bool value =\n       "
                " Smash360Json::RuntimeConversion<BasicJsonType, T>::from_json;\n        //"
                " Explicit compiler-boundary conversion fact."
            ),
        ),
        (
            (
                "    static constexpr bool value =\n        is_detected_exact<T,"
                " from_json_function, serializer,\n        const BasicJsonType&>::value;"
            ),
            (
                "    static const bool value =\n       "
                " Smash360Json::RuntimeConversion<BasicJsonType, T>::non_default_from_json;\n      "
                "  // Explicit compiler-boundary conversion fact."
            ),
        ),
        (
            (
                "    static constexpr bool value =\n        is_detected_exact<void,"
                " to_json_function, serializer, BasicJsonType&,\n        T>::value;"
            ),
            (
                "    static const bool value =\n       "
                " Smash360Json::RuntimeConversion<BasicJsonType, T>::to_json;\n        // Explicit"
                " compiler-boundary conversion fact."
            ),
        ),
    )
    for before, after in changes:
        if text.count(before) != 1:
            raise ValueError("unexpected conversion trait implementation")
        assert before.count("\n") == after.count("\n")
        text = text.replace(before, after)
    prefix = (
        "// Candidate actual-library conversion binding; closure must compile before use.\n"
        "#ifndef SMASH360_GENERATED_JSON_TYPE_TRAITS_HPP\n#define"
        " SMASH360_GENERATED_JSON_TYPE_TRAITS_HPP\n"
        '#include "json/config.h"\n#include "json/runtime_conversions.h"\n'
        f'#line 1 "{path.as_posix()}"\n'
    )
    return (prefix + text + "\n#endif\n").encode("utf-8")


def generate():
    commit = subprocess.check_output(
        [
            "git",
            "-c",
            "safe.directory=" + SOURCE.as_posix(),
            "-C",
            str(SOURCE),
            "rev-parse",
            "HEAD",
        ],
        text=True,
    ).strip()
    if commit != COMMIT:
        raise ValueError("JSON source commit mismatch")
    status = subprocess.check_output(
        [
            "git",
            "-c",
            "safe.directory=" + SOURCE.as_posix(),
            "-C",
            str(SOURCE),
            "status",
            "--porcelain",
            "--untracked-files=all",
        ],
        text=True,
    )
    if status:
        raise ValueError("official JSON checkout is modified")
    for relative, expected in HASHES.items():
        if sha((SOURCE / relative).read_bytes()) != expected:
            raise ValueError(f"{relative}: source SHA-256 mismatch")
    relative = "include/nlohmann/detail/string_escape.hpp"
    output = transform_escape((SOURCE / relative).read_bytes(), SOURCE / relative)
    registry_relative = "include/nlohmann/detail/meta/type_traits.hpp"
    registry = transform_conversion_registry(
        (SOURCE / registry_relative).read_bytes(), SOURCE / registry_relative
    )
    algorithms = runpy.run_path(str(PLATFORM_BASE / "python/xbox360_platform/json/backend.py"))[
        "generate"
    ](ROOT / "scratch/json-xdk/backend-generated/json/generated")["algorithms"]
    manifest = {
        "generated_algorithms": algorithms,
        "backend_kind": "explicit reached API; not original generic basic_json",
        "repository": "https://github.com/nlohmann/json",
        "tag": "v3.12.0",
        "commit": COMMIT,
        "selection": (
            "Matches pinned LUS cmake/dependencies/android.cmake; Windows selection was unpinned."
        ),
        "full_xdk_json_implemented": False,
        "generated_inputs": HASHES,
        "generator_sha256": sha(Path(__file__).read_bytes()),
        "algorithm_generator_sha256": sha(
            (PLATFORM_BASE / "python/xbox360_platform/json/generate_algorithms.py").read_bytes()
        ),
        "backend_source_sha256": sha((PLATFORM_BASE / "sources/json/json.cpp").read_bytes()),
        "backend_header_sha256": sha(
            (PLATFORM_BASE / "sources/json/include/nlohmann/json.hpp").read_bytes()
        ),
        "config_sha256": sha((ROOT / "platform/xbox360/cpp-compat/json/config.h").read_bytes()),
        "runtime_conversion_registry_sha256": sha(
            (ROOT / "platform/xbox360/cpp-compat/json/runtime_conversions.h").read_bytes()
        ),
        "outputs": {relative: sha(output)},
        "candidate_outputs": {registry_relative: sha(registry)},
        "conservative_header_closure": closure(SOURCE),
    }
    target = OUT / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(output)
    target = ROOT / "scratch/json-xdk/registry-candidate" / registry_relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(registry)
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    manifest = generate()
    print(
        "Generated pinned lexer/Grisu2 and escape algorithms; inventoried"
        f' {len(manifest["conservative_header_closure"])} headers; generic upstream basic_json is'
        " not lowered"
    )
