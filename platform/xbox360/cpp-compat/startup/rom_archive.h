#ifndef SMASH360_STARTUP_ROM_ARCHIVE_H
#define SMASH360_STARTUP_ROM_ARCHIVE_H
// Builds BattleShip.o2r on the console from the player's US v1.0 ROM, so assets need no PC step.
// Entries match pinned Torch byte for byte: SSB64 reloc files (table entry, optional VPK0 decode,
// extern file IDs) and raw audio blobs, plus Torch's version record. tools/rom_entries.py
// generates the entry list from the pinned Torch YAMLs.
#include <stddef.h>
#include <stdint.h>
#include <string>
#include <vector>

namespace Smash360Startup {
struct RomEntry {
    const char* name;
    int fileId; // reloc file ID, or -1 for a raw blob at offset/size
    uint32_t offset;
    uint32_t size;
};
extern const RomEntry kRomEntries[];
extern const size_t kRomEntryCount;

// rom is a US v1.0 image in .z64 order; the archive is written to path.
bool BuildArchive(const std::vector<unsigned char>& rom, const char* path, std::string& error);
// Builds archivePath from the first matching ROM in directory, through a temporary file.
bool ExtractArchive(const std::string& directory, const std::string& archivePath, std::string& error);
} // namespace Smash360Startup
#endif
