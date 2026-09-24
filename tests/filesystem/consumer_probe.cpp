// Compile the actual generated Directory class and exact public call shapes
// used by Config, ArchiveManager, DiskFile/Path, mods and hires. This is not a
// replacement application class or a claim those full TUs already compile.
#include "Directory.h"
#include "filesystem.h"
#include <fstream>

namespace fs = xbox_compat::filesystem;
void filesystem_consumer_probe(const std::string& input) {
    fs::path p(input);
    std::error_code ec;
    bool config = fs::exists(input) && fs::is_regular_file(input);
    std::ifstream reader(fs::absolute(p).string().c_str(), std::ios::binary);
    std::ofstream writer(fs::absolute(p).string().c_str(), std::ios::binary);
    if (config) writer << reader.rdbuf();
    fs::path parent = p.parent_path();
    parent /= p.filename();
    std::string name = parent.stem().string();
    for (fs::directory_iterator it(p, ec), finish; !ec && it != finish; it.increment(ec)) {
        const fs::directory_entry& entry = *it;
        bool file = entry.is_regular_file(ec);
        bool directory = entry.is_directory(ec);
        if (file || directory) name = fs::absolute(entry).string() + entry.path().extension().string();
    }
    Directory::CreateDirectory(parent.string());
    std::vector<std::string> files = Directory::ListFiles(input);
    name += Directory::GetCurrentDirectory();
    fs::InitWorkingDirectory(p, ec);
    fs::current_path(p, ec);
    fs::rename(p, parent, ec);
    fs::remove(p, ec);
}
