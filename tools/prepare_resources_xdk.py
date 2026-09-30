"""Lower pinned current LUS resource/archive classes; never substitute application classes."""

from pathlib import Path
import hashlib, json, re, runpy

ROOT = Path(__file__).resolve().parents[1]
LUS = ROOT / "upstream/BattleShip/libultraship"
OWN = ROOT / "platform/xbox360/cpp-compat/resources"
OUT = ROOT / "scratch/resources-xdk"
PLATFORM_BASE = runpy.run_path(str(ROOT / "tools/platform_base.py"))["resolve"](ROOT)
from xbox360_platform.libzip import public_config
from xbox360_platform.resource_lookup import synchronous_cache_hit

CONFIG = runpy.run_path(str(ROOT / "tools/prepare_config_xdk.py"))
LOWER = CONFIG["LOWER"]["lower_ranges"]
MAPPED = CONFIG["PRISM"]["mapped"]


class StableOutput:
    """Keep identical mapped files untouched while sibling compilers read them."""

    def __init__(self, path):
        self.path = path

    def __getattr__(self, name):
        return getattr(self.path, name)

    def write_text(self, text, encoding="utf-8", newline="\n"):
        raw = text.encode(encoding)
        if self.path.exists() and self.path.read_bytes() == raw:
            return len(text)
        temporary = self.path.with_name(self.path.name + ".pending")
        temporary.write_text(text, encoding=encoding, newline=newline)
        temporary.replace(self.path)
        return len(text)


def once(text, before, after, count=1):
    if text.count(before) != count:
        raise ValueError("Resource anchor changed: " + before[:100])
    return text.replace(before, after)


def transform(relative, text):
    name = Path(relative).name
    if name in ("glob.c", "StrHash64.h"):
        return text
    if name == "glob.h":
        return once(
            text,
            "#include <stdbool.h>",
            "#ifndef __cplusplus\n#ifdef _XBOX\ntypedef unsigned char bool;\n#define true"
            " 1\n#define false 0\n#else\n#include <stdbool.h>\n#endif\n#endif",
        )
    text = '#include "resources/compiler.h"\n' + text
    text = text.replace("#include <mutex>", '#include "async/native.h"')
    text = text.replace("#include <thread>", '#include "thread-pool/native_support.h"')
    text = text.replace("#include <variant>", "#include <xbox_compat/variant.h>")
    text = text.replace("#include <filesystem>", '#include "filesystem/filesystem.h"')
    for word in (
        "variant",
        "get",
        "holds_alternative",
        "bad_variant_access",
        "shared_future",
        "promise",
        "lock_guard",
        "mutex",
    ):
        text = text.replace("std::" + word, "xbox_compat::" + word)
    text = text.replace("std::filesystem::", "xbox_compat::filesystem::")
    text = text.replace(
        "std::thread::hardware_concurrency()", "xbox_compat::hardware_concurrency()"
    )
    text = text.replace(" final :", " :")  # final has no runtime representation.
    if name == "File.h":
        text = once(
            text, "struct File {", "struct File {\n    File() : BufferOffset(0), IsLoaded(false) {}"
        )
        text = once(text, "size_t BufferOffset = 0;", "size_t BufferOffset;")
        text = once(text, "bool IsLoaded = false;", "bool IsLoaded;")
    elif name == "Resource.h":
        text = once(
            text,
            'inline static const std::string gAltAssetPrefix = "alt/";',
            "static const std::string gAltAssetPrefix;",
        )
        text = once(text, "bool mIsDirty = false;", "bool mIsDirty;")
        text = once(
            text,
            "using IResource::IResource;",
            "explicit Resource(std::shared_ptr<ResourceInitData> initData) :"
            " IResource(initData) {}",
        )
    elif name == "Resource.cpp":
        text = once(
            text,
            "namespace Ship {",
            'namespace Ship {\nconst std::string IResource::gAltAssetPrefix = "alt/";',
        )
        text = once(text, ": mInitData(initData)", ": mInitData(initData), mIsDirty(false)")
        text = once(
            text,
            "#include <spdlog/spdlog.h>",
            "// Unused spdlog include; destructor intentionally silent upstream.",
        )
    elif name == "ResourceType.h":
        match = re.search(r"enum class ResourceType \{(.*?)\};", text, re.S)
        if not match:
            raise ValueError("ResourceType shape drift")
        text = (
            text[: match.start()]
            + CONFIG["enum_type"]("ResourceType", match.group(1))
            + text[match.end() :]
        )
    elif name == "ResourceManager.h":
        text = once(
            text,
            "typedef enum class ResourceLoadError { None, NotCached, NotFound } ResourceLoadError;",
            CONFIG["enum_type"]("ResourceLoadError", "None, NotCached, NotFound"),
        )
        for before, after in [
            ("const uintptr_t Owner = 0;", "const uintptr_t Owner;"),
            (
                "const std::shared_ptr<Archive> Parent = nullptr;",
                "const std::shared_ptr<Archive> Parent;",
            ),
        ]:
            text = once(text, before, after, 2)
        text = once(text, 'const std::string Path = "";', "const std::string Path;")
        text = once(text, "bool mAltAssetsEnabled = false;", "bool mAltAssetsEnabled;")
        text = once(text, "uintptr_t mDefaultCacheOwner = 0;", "uintptr_t mDefaultCacheOwner;")
        text = once(
            text,
            "std::shared_ptr<Archive> mDefaultCacheArchive = nullptr;",
            "std::shared_ptr<Archive> mDefaultCacheArchive;",
        )
    elif name == "ResourceManager.cpp":
        text = once(
            text,
            "ResourceManager::ResourceManager() {",
            "ResourceManager::ResourceManager() : mAltAssetsEnabled(false), mDefaultCacheOwner(0),"
            " mDefaultCacheArchive(nullptr) {",
        )
        text = text.replace("std::hash<std::string>{}", "std::hash<std::string>()").replace(
            "std::hash<std::uintptr_t>{}", "std::hash<uintptr_t>()"
        )
        for obj in ("identifier.Path",):
            text = text.replace(
                obj + ".starts_with(IResource::gAltAssetPrefix)",
                obj
                + ".compare(0, IResource::gAltAssetPrefix.size(), IResource::gAltAssetPrefix) == 0",
            )
        # Keep precedence of the negated starts_with expression.
        text = text.replace(
            "!identifier.Path.compare(0, IResource::gAltAssetPrefix.size(),"
            " IResource::gAltAssetPrefix) == 0",
            "(identifier.Path.compare(0, IResource::gAltAssetPrefix.size(),"
            " IResource::gAltAssetPrefix) != 0)",
        )
        for expression in (
            "newFilePath, identifier.Owner, identifier.Parent",
            "std::move(altPath), identifier.Owner, identifier.Parent",
            "altPath, identifier.Owner, identifier.Parent",
            "filePath, mDefaultCacheOwner, mDefaultCacheArchive",
            "fileName, filter.Owner, filter.Parent",
            "key, filter.Owner, filter.Parent",
            "key, mDefaultCacheOwner, mDefaultCacheArchive",
        ):
            text = text.replace("{ " + expression + " }", "ResourceIdentifier(" + expression + ")")
        text = text.replace(
            "{ { searchMask }, {}, mDefaultCacheOwner, mDefaultCacheArchive }",
            "ResourceFilter(Smash360Resources::OneMask(searchMask), std::list<std::string>(),"
            " mDefaultCacheOwner, mDefaultCacheArchive)",
        )
        text = text.replace(
            "mResourceCache.contains(identifier)",
            "(mResourceCache.find(identifier) != mResourceCache.end())",
        )
        for header in (
            "ship/utils/StringHelper.h",
            "ship/config/ConsoleVariable.h",
            "ship/Context.h",
        ):
            text = text.replace(
                '#include "' + header + '"',
                "// Unused include in pinned ResourceManager: " + header,
            )
    elif name == "ResourceLoader.cpp":
        text = once(
            text,
            "ResourceFactoryKey key{ .resourceFormat = format, .resourceType = type,"
            " .resourceVersion = version };",
            "ResourceFactoryKey key = { format, type, version };",
            2,
        )
        for container, arg in (
            ("mResourceTypes", "typeName"),
            ("mResourceTypes", "type"),
            ("mFactories", "key"),
        ):
            text = text.replace(
                container + ".contains(" + arg + ")",
                "(" + container + ".find(" + arg + ") != " + container + ".end())",
            )
    elif name == "Archive.h":
        text = once(
            text,
            "struct ArchiveManifest {",
            "struct ArchiveManifest {\n    ArchiveManifest() : CodeVersion(0), GameVersion(0) {}",
        )
        text = text.replace("uint32_t CodeVersion = 0;", "uint32_t CodeVersion;").replace(
            "uint32_t GameVersion = 0;", "uint32_t GameVersion;"
        )
    elif name == "Archive.cpp":
        text = once(
            text,
            '#include "ship/window/Window.h"',
            '#include "ship/resource/ResourceManager.h" // Explicit actual type; Window was only a'
            " transitive include.",
        )
        text = once(
            text,
            'for (auto& [key, value] : j["binaries"].items()) {',
            'for (const auto& entry : j["binaries"].items()) {\n                const std::string&'
            " key = entry.key();\n                auto& value = entry.value();",
        )
    elif name == "O2rArchive.cpp":
        text = once(
            text,
            '#include "ship/window/Window.h"',
            '#include "ship/resource/ResourceManager.h" // Explicit actual type; Window was only a'
            " transitive include.",
        )
    elif name == "ArchiveManager.cpp":
        text = text.replace("= dynamic_pointer_cast<", "= std::dynamic_pointer_cast<")
        text = text.replace(
            "Init(archivePaths, {});", "Init(archivePaths, std::unordered_set<uint32_t>());"
        )
        text = text.replace(
            "std::list<std::string> includes = {};", "std::list<std::string> includes;"
        )
        text = text.replace(
            "return ListFiles(includes, {});",
            "return ListFiles(includes, std::list<std::string>());",
        )
        text = text.replace(
            "std::vector<std::string> fileList = {};", "std::vector<std::string> fileList;"
        )
        text = once(
            text,
            "for (const auto& [hash, path] : mHashes) {",
            "for (const auto& entry : mHashes) {\n        const std::string& path = entry.second;",
        )
        text = once(
            text,
            "for (auto& [hash, filename] : *fileList.get()) {",
            "for (auto& entry : *fileList.get()) {\n        const uint64_t hash = entry.first;\n   "
            "     std::string& filename = entry.second;",
        )
        for expression in ("archive->GetGameVersion()", "gameVersion"):
            text = text.replace(
                "mValidGameVersions.contains(" + expression + ")",
                "(mValidGameVersions.find(" + expression + ") != mValidGameVersions.end())",
            )
    elif name == "FileHelper.h":
        text = once(
            text, '#include "Directory.h"', '#include "ship/utils/filesystemtools/Directory.h"'
        )
        text = text.replace(
            "file(filePath,", "file(xbox_compat::filesystem::absolute(filePath).string().c_str(),"
        )
    elif name == "PathHelper.h":
        text = once(text, '#include "../StringHelper.h"', '#include "ship/utils/StringHelper.h"')
        a = text.index("#if __has_include(<filesystem>)")
        b = text.index("#endif", a) + len("#endif")
        text = (
            text[:a]
            + '#include "filesystem/filesystem.h"\nnamespace fs = xbox_compat::filesystem;'
            + text[b:]
        )
    elif name in ("Json.h", "Shader.h", "Blob.h"):
        typ = Path(relative).stem
        text = once(
            text,
            "using Resource::Resource;",
            "explicit "
            + typ
            + "(std::shared_ptr<ResourceInitData> initData) : Resource(initData) {}",
        )
    elif name == "BlobFactory.cpp":
        text = once(
            text, "constexpr uint32_t kBlobPadding = 16;", "const uint32_t kBlobPadding = 16;"
        )
    elif name == "Utils.cpp":
        text = once(text, "if constexpr (sizeof(size_t) >= 8)", "if (sizeof(size_t) >= 8)")
        text = once(text, "args.emplace_back(tmp);", "args.push_back(std::string(tmp));", 2)
    text = LOWER(
        text.encode(), begin="Smash360Resources::Begin", end="Smash360Resources::End"
    ).decode()
    return text


def corrections(relative, text):
    """Separately authorized correctness fixes; not disguised as syntax lowering."""
    name = Path(relative).name
    if name == "ResourceManager.cpp":
        text = synchronous_cache_hit(text)
        text = once(
            text,
            '    SPDLOG_INFO("destruct ResourceManager");',
            '    SPDLOG_INFO("destruct ResourceManager");\n    if (mThreadPool) {'
            " mThreadPool->wait(); mThreadPool.reset(); }",
        )
        text = once(
            text,
            "        mResourceCache[identifier] = ResourceLoadError::NotFound;\n        return"
            " nullptr;",
            "        { const xbox_compat::lock_guard<xbox_compat::mutex> lock(mMutex);\n         "
            " mResourceCache[identifier] = ResourceLoadError::NotFound; }\n        return nullptr;",
        )
        text = once(
            text,
            "        auto resource = LoadResource(ResourceIdentifier(fileName, filter.Owner,"
            " filter.Parent));",
            "        const ResourceIdentifier identifier(fileName, filter.Owner, filter.Parent);\n "
            "       auto resource = mThreadPool->get_thread_count() == 1\n            ?"
            " LoadResourceProcess(identifier, false) : LoadResource(identifier);",
        )
        start = text.index(
            "    // We can only erase the resource if we have any resources for that owner."
        )
        end = text.index("    return ret;", start)
        text = (
            text[:start]
            + """    {
        const xbox_compat::lock_guard<xbox_compat::mutex> lock(mMutex);
        auto cached = mResourceCache.find(identifier);
        if (cached != mResourceCache.end()) {
            value = std::move(cached->second);
            mResourceCache.erase(cached);
            ret = 1;
        }
    }

"""
            + text[end:]
        )
    elif name == "O2rArchive.cpp":
        text = once(
            text,
            "O2rArchive::O2rArchive(const std::string& archivePath) : Archive(archivePath) {",
            "O2rArchive::O2rArchive(const std::string& archivePath) : Archive(archivePath),"
            " mZipArchive(nullptr) {",
        )
        text = once(
            text,
            "    Close();",
            "    if (!Close() && mZipArchive != nullptr) { zip_discard(mZipArchive); mZipArchive ="
            " nullptr; }",
        )
        text = once(
            text,
            "    auto fileToLoad = std::make_shared<File>();",
            "    std::unique_ptr<zip_file, int (*)(zip_file*)> entryOwner(zipEntryFile,"
            " &zip_fclose);\n    if (zipEntryStat.size >"
            " static_cast<zip_uint64_t>(static_cast<size_t>(-1))) return nullptr;\n    auto"
            " fileToLoad = std::make_shared<File>();",
        )
        text = once(
            text,
            "    if (zip_fread(zipEntryFile, fileToLoad->Buffer->data(), zipEntryStat.size) < 0) {",
            "    const zip_int64_t bytesRead = zip_fread(zipEntryFile, fileToLoad->Buffer->data(),"
            " zipEntryStat.size);\n    if (bytesRead < 0 || static_cast<zip_uint64_t>(bytesRead) !="
            " zipEntryStat.size) {",
        )
        text = once(
            text,
            '        SPDLOG_TRACE("Error reading file {} in zip archive  {}.", filePath,'
            " GetPath());",
            '        SPDLOG_TRACE("Error reading file {} in zip archive  {}.", filePath,'
            " GetPath());\n        return nullptr;",
        )
        text = once(
            text,
            "    if (zip_fclose(zipEntryFile) != 0) {",
            "    if (zip_fclose(entryOwner.release()) != 0) {",
        )
        text = once(
            text,
            "    if (zip_fclose(entryOwner.release()) != 0) {",
            "    char unexpectedByte;\n    if (zip_fread(zipEntryFile, &unexpectedByte, 1) != 0)"
            " return nullptr; // Reach EOF and force deferred CRC/size validation.\n    if"
            " (zip_fclose(entryOwner.release()) != 0) {",
        )
        text = once(
            text,
            '        SPDLOG_TRACE("Error closing file {} in zip archive  {}.", filePath,'
            " GetPath());",
            '        SPDLOG_TRACE("Error closing file {} in zip archive  {}.", filePath,'
            " GetPath());\n        return nullptr;",
        )
        text = once(
            text,
            "        zip_discard(mZipArchive); // Close zip and discard changes",
            "        zip_discard(mZipArchive); // Close zip and discard changes\n       "
            " mZipArchive = nullptr;",
        )
    elif name == "FolderArchive.cpp":
        text = once(
            text,
            '    mArchiveBasePath = archivePath + "/";',
            "    mArchiveBasePath = xbox_compat::filesystem::path(archivePath).generic_string() +"
            ' "/";',
        )
    elif name == "ArchiveManager.cpp":
        text = once(
            text,
            "    auto archive = mFileToArchive[hash];",
            "    const auto entry = mFileToArchive.find(hash);\n    auto archive = entry =="
            " mFileToArchive.end() ? std::shared_ptr<Archive>() : entry->second;",
        )
        text = once(
            text,
            "    return mFileToArchive[CRC64(filePath.c_str())];",
            "    const auto entry = mFileToArchive.find(CRC64(filePath.c_str()));\n    return entry"
            " == mFileToArchive.end() ? std::shared_ptr<Archive>() : entry->second;",
        )
    return text


def prepare():
    locks = json.loads((OWN / "sources.lock.json").read_text())
    hashes = {}
    for relative, expected in locks["lus"].items():
        raw = (LUS / relative).read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError("Resource source SHA drift: " + relative)
        text = corrections(
            relative, transform(relative, raw.decode("utf-8-sig").replace("\r\n", "\n"))
        )
        target = OUT / "generated" / relative
        MAPPED("upstream/BattleShip/libultraship/" + relative, text, StableOutput(target))
        hashes[relative] = hashlib.sha256(target.read_bytes()).hexdigest()
    ziproot = ROOT / "upstream/dependencies/libzip"
    for relative, expected in locks["libzip"].items():
        if hashlib.sha256((ziproot / relative).read_bytes()).hexdigest() != expected:
            raise ValueError("libzip source drift: " + relative)
    config = public_config((ziproot / "zipconf.h.in").read_text())
    destination = OUT / "libzip-public"
    destination.mkdir(parents=True, exist_ok=True)
    StableOutput(destination / "zipconf.h").write_text(config, newline="\n")
    manifest = {
        "source_locks": locks,
        "output_hashes": hashes,
        "libzip_public_configuration": (
            "Actual 1.11.4 zipconf template; XDK fixed-width types, static linkage. Library runtime"
            " not yet compiled."
        ),
        "authorized_corrections": [
            (
                "ResourceManager missing-cache write lock and atomic lookup/erase with resource"
                " destruction after unlock"
            ),
            "Drain and reset pool before mutex/cache member destruction",
            (
                "Single-worker queued batch calls same LoadResourceProcess on worker to avoid"
                " nested-task deadlock"
            ),
            (
                "O2r handle initialization, bounded allocation, exact read/close validation and"
                " RAII entry closure"
            ),
            "O2r discard clears handle; destructor discards after failed close",
            "Folder archive prefix uses same generic separator representation as enumeration",
            "ArchiveManager missing-file lookups do not mutate archive map",
        ],
        "source_mapping": (
            "Central exact-source mapped #line lowering; actual class declarations and algorithms"
            " retained."
        ),
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    prepare()
    print("Staged actual LUS resource/archive classes and pinned libzip public configuration")
