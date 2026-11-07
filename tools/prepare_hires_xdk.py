"""Pinned HiRes cache/worker/hook source projection plus explicit LE dump IO."""

from pathlib import Path
import argparse, hashlib, json, re, runpy, subprocess, sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
UP = ROOT / "upstream/BattleShip"
OUT = ROOT / "scratch/hires-xdk"
BASE = ROOT / "platform/xbox360/cpp-compat/hires"
from platform_base import resolve as resolve_platform_base

PLATFORM_BASE = resolve_platform_base(ROOT)
PRISM = runpy.run_path(str(ROOT / "tools/prepare_prism_xdk.py"))
LOWER = runpy.run_path(str(ROOT / "platform/xbox360/cpp-compat/controllers/lowering.py"))
STAGE = runpy.run_path(str(ROOT / "platform/xbox360/game-compat/source_tree.py"))["stage_sources"]


def once(t, a, b):
    if t.count(a) != 1:
        raise ValueError("HiRes anchor drift " + a[:100])
    return t.replace(a, b)


def transform(relative, t):
    if relative.endswith("HiResHook.h"):
        return t  # Keep the genuine C-ABI header C-compatible.
    t = t.replace("namespace ssb64::hires {", "namespace ssb64 { namespace hires {").replace(
        "} // namespace ssb64::hires", "} } // namespace ssb64::hires"
    )
    t = (
        t.replace("inline constexpr ", "static const ")
        .replace("constexpr ", "const ")
        .replace("noexcept", "throw()")
    )
    if relative.endswith("HiResPack.h"):
        t = once(t, "uint16_t w = 0;", "uint16_t w;").replace(
            "uint16_t h = 0;", "uint16_t h;\n    DecodedTexture() : w(0),h(0) {}"
        )
        t = once(
            t,
            "uint8_t pad0 = 0, pad1 = 0;",
            "uint8_t pad0,pad1;\n    HashKey() : rgba8Crc(0),fmt(0),siz(0),pad0(0),pad1(0) {}",
        )
        t = once(
            t,
            "bool operator==(const HashKey&) const throw() = default;",
            "bool operator==(const HashKey& other) const throw() { return rgba8Crc==other.rgba8Crc"
            " && fmt==other.fmt && siz==other.siz && pad0==other.pad0 && pad1==other.pad1; }",
        )
        t = once(t, "HiResPack() = default;", "HiResPack() : mStats(),mLookupStats() {}")
        t = (
            t.replace(" = delete;", ";")
            .replace("PackStats mStats{};", "PackStats mStats;")
            .replace("LookupStats mLookupStats{};", "LookupStats mLookupStats;")
            .replace("mLookupStats = {};", "mLookupStats = LookupStats();")
        )
    if relative.endswith(".cpp"):
        t = t.replace(
            "#include <libultraship/libultraship.h>",
            '#include "ship/Context.h"\n#include "libultraship/bridge/consolevariablebridge.h"',
        )
        for inc in ("atomic", "filesystem", "mutex", "optional", "string_view", "thread"):
            t = t.replace("#include <" + inc + ">", "")
        t = t.replace("std::atomic<", "Shipyard::Atomic::atomic<").replace(
            "std::memory_order_", "Shipyard::Atomic::memory_order_"
        )
        t = t.replace("std::mutex", "xbox_compat::mutex").replace(
            "std::lock_guard", "xbox_compat::lock_guard"
        )
        t = (
            t.replace("std::filesystem::", "xbox_compat::filesystem::")
            .replace("std::string_view", "xbox_compat::string_view")
            .replace("std::optional<", "xbox_compat::optional<")
            .replace("std::nullopt", "xbox_compat::nullopt")
        )
        t = t.replace(
            "std::vector<std::thread>", "std::vector<xbox_compat::joining_thread>"
        ).replace("std::thread::hardware_concurrency()", "xbox_compat::hardware_concurrency()")
        t = re.sub(r"(Shipyard::Atomic::atomic<[^>]+>\s+\w+)\{([^}]+)\};", r"\1(\2);", t)
        t = t.replace("std::array<uint32_t, 256> t{};", "std::array<uint32_t, 256> t = {0};")
    if relative.endswith("HiResPack.cpp"):
        t = once(t, "const Crc32Table() : v{} {", "Crc32Table() {")
        t = once(t, "size_t mBytes = 0;", "size_t mBytes;")
        t = once(t, ": mBudget(budgetBytes)", ": mBytes(0),mBudget(budgetBytes)")
        t = once(
            t,
            "LruCache gLru{ (size_t)kDefaultLruBudgetMB * 1024u * 1024u };",
            "LruCache gLru((size_t)kDefaultLruBudgetMB * 1024u * 1024u);",
        )
        t = (
            t.replace("HashKey key{};", "HashKey key;")
            .replace("DumpHeader hdr{};", "DumpHeader hdr = {0};")
            .replace("mStats = {};", "mStats = PackStats();")
        )
        t = once(
            t,
            "struct PackEntry {",
            "struct PackEntry {\n    PackEntry(std::string c=std::string(),std::string"
            " m=std::string()) : container(std::move(c)),member(std::move(m)) {}",
        )
        t = t.replace(
            "PackEntry{zipPath, std::string(name)}", "PackEntry(zipPath,std::string(name))"
        ).replace("PackEntry{path, std::string()}", "PackEntry(path,std::string())")
        t = once(
            t, "mList.emplace_back(k, std::move(tex));", "mList.push_back(Node(k,std::move(tex)));"
        )
        t = once(
            t,
            "gIndex.emplace(key, std::move(entry));",
            "gIndex.insert(std::make_pair(key,std::move(entry)));",
        )
        t = once(
            t,
            "gPreloadThreads.emplace_back(PreloadWorker);",
            "gPreloadThreads.push_back(xbox_compat::make_thread(PreloadWorker));",
        )
        t = once(
            t,
            "[](const auto& a, const auto& b)",
            "[](const std::pair<HashKey,PackEntry>& a,const std::pair<HashKey,PackEntry>& b) ->"
            " bool",
        )
        t = once(
            t,
            "void HiResPack::StartPreload() {",
            "static void StopPreloadAtExit() { HiResPack::Get().StopPreload(); }\n\nvoid"
            " HiResPack::StartPreload() {",
        )
        t = once(
            t,
            "std::atexit([] { HiResPack::Get().StopPreload(); });",
            "std::atexit(&StopPreloadAtExit);",
        )
        t = once(
            t,
            "const auto& [key, entry] = gPreloadWork[i];",
            "const auto& work = gPreloadWork[i];\n        const auto& key = work.first; const auto&"
            " entry = work.second;",
        )
        for variable, obj in [("it", "mIndex"), ("it", "gOpenZips"), ("it", "localZips")]:
            # Preserve the initializer's lexical scope, including the one-line
            # return cases, without expanding scope into later declarations.
            old = "if (auto it = " + obj + ".find("
            start = t.index(old)
            close = t.index("); it != " + obj + ".end())", start)
            expr = t[start + len("if (auto it = ") : close + 1]
            body_start = close + len("); it != " + obj + ".end())")
            if t[body_start:].lstrip().startswith("{"):
                end = t.index("\n        }", body_start) + len("\n        }")
            else:
                end = t.index(";", body_start) + 1
            body = t[body_start:end]
            t = (
                t[:start]
                + "{ auto it = "
                + expr
                + "; if(it != "
                + obj
                + ".end())"
                + body
                + " }"
                + t[end:]
            )
        t = once(
            t, "std::fwrite(&hdr, sizeof(hdr), 1, f);", "Smash360HiRes::WriteDumpHeader(f,hdr);"
        )
    if relative.endswith("HiResHook.cpp"):
        start = t.index("    static const auto tbl = [] {")
        end = t.index("    }();", start) + len("    }();")
        body = t[start + len("    static const auto tbl = [] {") : end - len("    }();")]
        t = (
            t[:start]
            + "    static const std::array<uint32_t,256> tbl = MakeMissDumpCrcTable();"
            + t[end:]
        )
        t = once(
            t,
            "uint32_t MissDumpCrc32(",
            "std::array<uint32_t,256> MakeMissDumpCrcTable() {"
            + body
            + "}\n\nuint32_t MissDumpCrc32(",
        )
    t = re.sub(r"\busing\s+(\w+)\s*=\s*([^;]+);", r"typedef \2 \1;", t)
    t = LOWER["syntax"](t, set())
    return '#include "hires/compiler.h"\n#ifdef _XBOX\n#include "crt/snprintf.h"\n#endif\n' + t


def prepare():
    locks = json.loads((BASE / "source-lock.json").read_text())
    records = []
    for rel, sha in locks.items():
        source = UP / rel
        if hashlib.sha256(source.read_bytes()).hexdigest() != sha:
            raise ValueError("HiRes source drift " + rel)
        target = OUT / "overlay" / rel
        PRISM["mapped"](
            source.as_posix(), transform(rel, source.read_text(encoding="utf-8-sig")), target
        )
        records.append(
            {
                "source": rel,
                "sha256": sha,
                "generated_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            }
        )
    headers = {}
    layers = [ROOT / "scratch/context-xdk/compile-tree", OUT / "overlay"]
    for directory in layers:
        for path in directory.rglob("*.h"):
            headers[path.relative_to(directory).as_posix()] = path
    for rel, path in headers.items():
        target = OUT / "composed" / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())
    for rel in locks:
        if rel.endswith(".cpp"):
            target = OUT / "composed" / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((OUT / "overlay" / rel).read_bytes())
    staged = STAGE(
        UP, OUT / "compile-tree", [r for r in locks if r.endswith(".cpp")], [OUT / "composed"]
    )
    (OUT / "manifest.json").write_text(
        json.dumps(
            {
                "transforms": records,
                "staged": staged,
                "support": {
                    str(
                        p.relative_to(ROOT)
                        if p.is_relative_to(ROOT)
                        else p.relative_to(PLATFORM_BASE)
                    ): (hashlib.sha256(p.read_bytes()).hexdigest())
                    for p in [
                        BASE / "compiler.h",
                        ROOT / "platform/xbox360/cpp-compat/config/string_view.h",
                        PLATFORM_BASE / "sources/atomic/atomic.h",
                    ]
                },
            },
            indent=2,
        )
        + "\n"
    )


def compile_xdk():
    base = json.loads((ROOT / "scratch/context-xdk/compile-report.json").read_text())[0]["command"]
    includes = [
        a.replace(str(ROOT / "scratch/context-xdk/compile-tree"), str(OUT / "compile-tree"))
        for a in base
        if a.startswith("/I")
    ]
    includes += [
        "/I" + str(PLATFORM_BASE),
        "/I" + str(PLATFORM_BASE / "sources"),
        "/I" + str(PLATFORM_BASE / "sources/value_types"),
        "/I" + str(PLATFORM_BASE / "sources/json/include"),
        "/I" + str(ROOT / "scratch/json-xdk/backend-generated"),
        "/I" + str(ROOT / "upstream/dependencies/libzip/lib"),
        "/I" + str(ROOT / "scratch/resources-xdk/libzip-public"),
    ]
    sdk = Path("C:/Program Files (x86)/Microsoft Xbox 360 SDK")
    results = []
    for name in ("HiResPack", "HiResHook"):
        cmd = (
            [
                str(sdk / "bin/win32/cl.exe"),
                "/nologo",
                "/c",
                "/TP",
                "/EHsc",
                "/MT",
                "/W3",
                "/D_XBOX",
                "/DNOMINMAX",
                "/DDISABLE_SCRIPTING",
                "/FI" + str(ROOT / "scratch/config-xdk/cvars.h"),
            ]
            + includes
            + [
                "/Fo" + str(OUT / (name + ".obj")),
                str(OUT / "compile-tree/port/hires" / (name + ".cpp")),
            ]
        )
        p = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
        log = p.stdout + p.stderr
        (OUT / (name + ".log")).write_text(log)
        results.append(
            {"source": "port/hires/" + name + ".cpp", "command": cmd, "exit": p.returncode}
        )
        print(name, p.returncode)
        print("\n".join(l for l in log.splitlines() if "error " in l)[:5000])
    (OUT / "compile-report.json").write_text(json.dumps(results, indent=2) + "\n")
    return any(r["exit"] for r in results)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--compile", action="store_true")
    a = p.parse_args()
    prepare()
    if a.compile:
        raise SystemExit(compile_xdk())
