#include "startup/rom_archive.h"
#include "archive/stored_zip_writer.h"
#include "rom/rom.h"
#include <stdio.h>
#include <string.h>

// Torch's VPK0 decoder mixes declarations and statements, which the XDK C89 compiler rejects; it is valid C++.
#include "../../../../upstream/BattleShip/torch/lib/libvpk0/vpk0.c"

namespace Smash360Startup {
namespace {
// US v1.0 reloc table (Torch SSB64::GetRelocLayout, NALE); one sentinel entry follows the last file.
const uint32_t kTable = 0x001AC870u;
const uint32_t kFiles = 2132u;
const uint32_t kEntrySize = 12u;
const uint32_t kData = kTable + (kFiles + 1u) * kEntrySize;
const uint32_t kRomSize = 0x1000000u;
const unsigned char kUsSha1[20] = { 0xe2, 0x92, 0x9e, 0x10, 0xfc, 0xcc, 0x0a, 0xa8, 0x4e, 0x57,
                                    0x76, 0x22, 0x7e, 0x79, 0x8a, 0xbc, 0x07, 0xce, 0xda, 0xbf };
const uint32_t kRelocType = 0x52454C4Fu; // "RELO"
const uint32_t kBlobType = 0x4F424C42u;  // "OBLB"

uint16_t Big16(const unsigned char* data) {
    return static_cast<uint16_t>((data[0] << 8) | data[1]);
}

// Torch writes resource fields little-endian on every host, so bytes are placed explicitly.
void Put16(std::vector<unsigned char>& out, uint32_t value) {
    out.push_back(static_cast<unsigned char>(value));
    out.push_back(static_cast<unsigned char>(value >> 8));
}

void Put32(std::vector<unsigned char>& out, uint32_t value) {
    Put16(out, value & 0xFFFFu);
    Put16(out, value >> 16);
}

// Torch's 0x40-byte LUS header: little-endian marker, type, version 0 and its placeholder ID.
void Header(std::vector<unsigned char>& out, uint32_t type) {
    out.assign(4, 0);
    Put32(out, type);
    Put32(out, 0);
    Put32(out, 0xDEADBEEFu);
    Put32(out, 0xDEADBEEFu);
    out.resize(0x40, 0);
}

bool Fail(std::string& error, const char* what, uint32_t value) {
    char text[96];
    _snprintf(text, sizeof(text), "%s %lu", what, static_cast<unsigned long>(value));
    text[sizeof(text) - 1] = 0;
    error = text;
    return false;
}

bool Reloc(const std::vector<unsigned char>& rom, uint32_t fileId, std::vector<unsigned char>& out, std::string& error) {
    if (fileId >= kFiles) return Fail(error, "reloc file ID out of range:", fileId);
    const unsigned char* entry = &rom[kTable + fileId * kEntrySize];
    const uint32_t first = Shipyard::Rom::ReadBig32(entry);
    const bool compressed = (first >> 31) != 0;
    const size_t start = kData + (first & 0x7FFFFFFFu);
    const uint32_t compressedBytes = Big16(entry + 6) * 4u;
    const uint32_t bytes = Big16(entry + 10) * 4u;
    const size_t next = kData + (Shipyard::Rom::ReadBig32(entry + kEntrySize) & 0x7FFFFFFFu);
    if (start + compressedBytes > rom.size() || (!compressed && start + bytes > rom.size()))
        return Fail(error, "reloc file outside the ROM:", fileId);
    Header(out, kRelocType);
    Put32(out, fileId);
    Put16(out, Big16(entry + 4));
    Put16(out, Big16(entry + 8));
    // Extern file IDs sit between this file's data and the next file's.
    const size_t externStart = start + compressedBytes;
    const uint32_t externCount =
        next > externStart && next <= rom.size() ? static_cast<uint32_t>((next - externStart) / 2) : 0;
    Put32(out, externCount);
    for (uint32_t i = 0; i < externCount; ++i) Put16(out, Big16(&rom[externStart + i * 2]));
    Put32(out, bytes);
    const size_t at = out.size();
    out.resize(at + bytes);
    if (bytes == 0) return true;
    if (!compressed) {
        memcpy(&out[at], &rom[start], bytes);
        return true;
    }
    if (vpk0_decode(&rom[start], compressedBytes, &out[at], bytes) == 0)
        return Fail(error, "VPK0 decode failed for reloc file", fileId);
    return true;
}

bool Blob(const std::vector<unsigned char>& rom, const RomEntry& entry, std::vector<unsigned char>& out, std::string& error) {
    if (static_cast<size_t>(entry.offset) + entry.size > rom.size()) return Fail(error, "blob outside the ROM at", entry.offset);
    Header(out, kBlobType);
    Put32(out, entry.size);
    out.insert(out.end(), rom.begin() + entry.offset, rom.begin() + entry.offset + entry.size);
    return true;
}
} // namespace

bool BuildArchive(const std::vector<unsigned char>& rom, const char* path, std::string& error) {
    if (rom.size() != kRomSize) return Fail(error, "unexpected ROM size", static_cast<uint32_t>(rom.size()));
    Shipyard::Archive::StoredZipWriter writer;
    if (!writer.Open(path)) {
        error = std::string("cannot create ") + path;
        return false;
    }
    std::vector<unsigned char> bytes;
    for (size_t i = 0; i < kRomEntryCount; ++i) {
        const RomEntry& entry = kRomEntries[i];
        const bool built = entry.fileId < 0 ? Blob(rom, entry, bytes, error)
                                            : Reloc(rom, static_cast<uint32_t>(entry.fileId), bytes, error);
        if (!built) return false;
        if (!writer.Add(entry.name, &bytes[0], bytes.size())) {
            error = std::string("cannot write ") + entry.name;
            return false;
        }
    }
    // Torch's version record: big-endian marker, then the header CRC with its bytes reversed as Torch writes it.
    unsigned char version[5] = { 1, rom[0x13], rom[0x12], rom[0x11], rom[0x10] };
    if (!writer.Add("version", version, sizeof(version)) || !writer.Finish()) {
        error = std::string("cannot finish ") + path;
        return false;
    }
    return true;
}

bool ExtractArchive(const std::string& directory, const std::string& archivePath, std::string& error) {
    const std::vector<std::string> roms = Shipyard::Rom::Find(directory);
    const size_t sizes[] = { kRomSize };
    std::vector<unsigned char> rom;
    for (size_t i = 0; i < roms.size(); ++i) {
        if (Shipyard::Rom::Load(roms[i], sizes, 1, rom) != Shipyard::Rom::LoadOk) continue;
        unsigned char digest[20];
        Shipyard::Rom::Sha1(&rom[0], rom.size(), digest);
        if (memcmp(digest, kUsSha1, sizeof(digest)) != 0) continue;
        const std::string partial = archivePath + ".part";
        if (!BuildArchive(rom, partial.c_str(), error)) {
            remove(partial.c_str());
            return false;
        }
        if (rename(partial.c_str(), archivePath.c_str()) != 0) {
            remove(partial.c_str());
            error = "cannot rename " + partial;
            return false;
        }
        return true;
    }
    error = "no Super Smash Bros. US v1.0 ROM (.z64, .n64 or .v64) in " + directory;
    return false;
}
} // namespace Smash360Startup
