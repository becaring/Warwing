#include "filesystem.h"
#include <filesystem>
#include <fstream>
#include <set>
#include <cstdio>
#include <stdexcept>

namespace fs = xbox_compat::filesystem;
namespace reference = std::filesystem;
static void check(bool condition, const char* text) { if (!condition) throw std::runtime_error(text); }
#define CHECK(x) check(!!(x), #x)

static void lexical_contract() {
    const char* common[] = { "", "a", "a/b.txt", "a/b/", "C:/", "C:/one/../two/./x", ".dot", "a.", "..", "a/../../b", "a/..", "a/.", "C:relative", "a\\b.ext" };
    for (unsigned i = 0; i < sizeof(common)/sizeof(common[0]); ++i) {
        fs::path actual(common[i]); reference::path expected(common[i]);
        CHECK(actual.filename().generic_string() == expected.filename().generic_string());
        CHECK(actual.extension().generic_string() == expected.extension().generic_string());
        CHECK(actual.stem().generic_string() == expected.stem().generic_string());
        CHECK(actual.parent_path().generic_string() == expected.parent_path().generic_string());
        CHECK(actual.lexically_normal().generic_string() == expected.lexically_normal().generic_string());
        CHECK(actual.make_preferred().string() == expected.make_preferred().string());
    }
    CHECK((fs::path("game:/mods") / "pack/file.o2r").generic_string() == "game:/mods/pack/file.o2r");
    CHECK((fs::path("warwingsave:\\") / "logs/BattleShip.log").make_preferred().string() == "warwingsave:\\logs\\BattleShip.log");
    CHECK((fs::path("game:/mods") / "cache:/textures").generic_string() == "cache:/textures");
    CHECK((fs::path("game:/mods") / "/base").generic_string() == "game:/base");
    CHECK(fs::path("XContent:/container/../save.bin").lexically_normal().generic_string() == "XContent:/save.bin");
    CHECK(fs::path("cache:/../../textures").lexically_normal().generic_string() == "cache:/textures");
    CHECK(fs::path("game:/").parent_path().generic_string() == "game:/");
    CHECK(fs::path("game:/").root_name().string() == "game:");
    CHECK(fs::path("game:/data").is_absolute() && !fs::path("game:data").is_absolute());
    fs::path extension("game:/a.shader"); extension.replace_extension("lus.json");
    CHECK(extension.generic_string() == "game:/a.lus.json");
    std::error_code ec;
    CHECK(fs::absolute("game:/data", ec).generic_string() == "game:/data" && !ec);
}

static std::set<std::string> names(const fs::path& root) {
    std::set<std::string> out;
    for (fs::directory_iterator it(root), end; it != end; ++it) out.insert(it->path().filename().string());
    return out;
}

static void io_contract(const fs::path& root) {
    std::error_code ec, refEc;
    CHECK(fs::create_directories(root / "mods" / "nested", ec) && !ec);
    CHECK(!fs::create_directories(root / "mods" / "nested", ec) && !ec);
    CHECK(fs::is_directory(root / "mods") && reference::is_directory((root / "mods").string()));
    const fs::path config = root / "config.json";
    const char content[] = "{\"rate\":32000}";
    CHECK(fs::write_file(config, content, sizeof(content)-1, ec) && !ec);
    CHECK(fs::exists(config) && fs::is_regular_file(config));
    CHECK(fs::file_size(config) == reference::file_size(config.string()));
    std::vector<unsigned char> read;
    CHECK(fs::read_file(config, read, ec) && !ec);
    CHECK(std::string(read.begin(), read.end()) == content);
    std::ifstream stream(config, std::ios::binary);
    std::string viaStream; std::getline(stream, viaStream);
    CHECK(viaStream == content); stream.close();
    CHECK(fs::write_file(root / "mods" / "pack.o2r", content, sizeof(content)-1, ec));
    CHECK(fs::write_file(root / "mods" / "nested" / "texture.png", content, sizeof(content)-1, ec));
    std::set<std::string> actual = names(root / "mods"), expected;
    for (const auto& entry : reference::directory_iterator((root / "mods").string())) expected.insert(entry.path().filename().string());
    CHECK(actual == expected && actual.size() == 2);
    actual.clear(); expected.clear();
    for (fs::recursive_directory_iterator it(root / "mods"), end; it != end; ++it) actual.insert(it->path().filename().string());
    for (const auto& entry : reference::recursive_directory_iterator((root / "mods").string())) expected.insert(entry.path().filename().string());
    CHECK(actual == expected && actual.size() == 3);
    fs::directory_iterator it(root / "mods"), shared = it;
    CHECK(shared == it);
    ++it;
    CHECK(shared->path() == it->path()); // Single-pass iterator copies share enumeration.
    fs::path oldCwd = fs::current_path();
    fs::InitWorkingDirectory(root);
    CHECK(fs::exists("config.json"));
#ifdef SHIPYARD_TEST_LOGICAL_CWD
    CHECK(fs::absolute("config.json").generic_string() == (root / "config.json").generic_string());
    CHECK(reference::current_path().generic_string() == oldCwd.generic_string());
#else
    CHECK(fs::absolute("config.json").generic_string() == reference::absolute("config.json").generic_string());
#endif
    fs::current_path(root / "missing", ec);
    CHECK(ec && fs::current_path() == root);
    fs::current_path("mods");
    CHECK(fs::exists("pack.o2r"));
    fs::current_path(oldCwd);
    CHECK(!fs::exists(root / "missing", ec) && !ec);
    bool ours = fs::is_directory(root / "missing", ec);
    bool theirs = reference::is_directory((root / "missing").string(), refEc);
    CHECK(ours == theirs && !!ec == !!refEc);
    CHECK(!fs::is_directory(root / "missing")); // Throwing status does not throw for not-found.
    fs::directory_iterator missing(root / "missing", ec);
    CHECK(ec && missing == fs::directory_iterator());
    bool threw = false;
    try { fs::directory_iterator absent(root / "missing"); }
    catch (const fs::filesystem_error& error) { threw = error.code().value() != 0; }
    CHECK(threw);
    CHECK(!fs::create_directories(config / "child", ec) && ec);
    CHECK(!fs::exists(fs::path(std::string("bad\0name", 8)), ec) && ec);
    CHECK(!fs::exists(root / "wild*card", ec) && ec);
    CHECK(SetFileAttributesA(config.c_str(), FILE_ATTRIBUTE_READONLY));
    CHECK(!fs::write_file(config, content, sizeof(content)-1, ec) && ec.value() == ERROR_ACCESS_DENIED);
    CHECK(fs::exists(config, ec) && !ec);
    CHECK(SetFileAttributesA(config.c_str(), FILE_ATTRIBUTE_NORMAL));
    HANDLE exclusive = CreateFileA(config.c_str(), GENERIC_READ, 0, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    CHECK(exclusive != INVALID_HANDLE_VALUE);
    CHECK(!fs::read_file(config, read, ec) && ec.value() == ERROR_SHARING_VIOLATION && read.empty());
    CHECK(!fs::write_file(config, content, sizeof(content)-1, ec) && ec.value() == ERROR_SHARING_VIOLATION);
    CHECK(CloseHandle(exclusive));
    fs::rename(config, root / "renamed.json", ec);
    CHECK(!ec && !fs::exists(config) && fs::exists(root / "renamed.json"));
    CHECK(fs::write_file(config, "old", 3, ec));
    fs::rename(root / "renamed.json", config, ec);
    CHECK(!ec && fs::file_size(config) == sizeof(content)-1);
    CHECK(!fs::remove(root / "mods", ec) && ec);
    CHECK(!fs::remove(root / "absent", ec) && !ec);
    CHECK(fs::remove(root / "mods" / "nested" / "texture.png"));
    CHECK(fs::remove(root / "mods" / "nested"));
    CHECK(fs::remove(root / "mods" / "pack.o2r"));
    it = fs::directory_iterator(); shared = fs::directory_iterator();
    CHECK(fs::remove(root / "mods"));
    CHECK(fs::remove(config));
    CHECK(fs::remove(root));
}

int main(int argc, char** argv) {
    try { CHECK(argc == 2); lexical_contract();
#ifdef SHIPYARD_TEST_LOGICAL_CWD
        std::error_code ec;
        CHECK(fs::current_path(ec).empty() && ec.value() == ERROR_NOT_READY);
        CHECK(!fs::exists("relative-before-init", ec) && ec.value() == ERROR_NOT_READY);
        CHECK(!fs::InitWorkingDirectory("relative", ec) && ec.value() == ERROR_INVALID_PARAMETER);
        CHECK(fs::InitWorkingDirectory(reference::current_path().string(), ec) && !ec);
#endif
        io_contract(fs::path(argv[1]));
        std::puts("PASS filesystem: lexical/device roots, Windows differential IO/enumeration, working directory, native errors, rename/remove"); return 0;
    } catch (const std::exception& error) { std::fprintf(stderr, "FAIL: %s\n", error.what()); return 1; }
}
