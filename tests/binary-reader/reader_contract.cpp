#include "ship/utils/binarytools/BinaryReader.h"
#include "ship/utils/binarytools/MemoryStream.h"
#include <cmath>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iostream>
#include <iterator>
#include <limits>
#include <new>
#include <stdexcept>

static size_t allocations = 0;
void* operator new(size_t size) {
    ++allocations;
    void* p = std::malloc(size ? size : 1);
    if (!p) throw std::bad_alloc();
    return p;
}
void operator delete(void* p) noexcept { std::free(p); }
void* operator new[](size_t size) { return ::operator new(size); }
void operator delete[](void* p) noexcept { ::operator delete(p); }
void operator delete(void* p, size_t) noexcept { ::operator delete(p); }
void operator delete[](void* p, size_t) noexcept { ::operator delete(p); }

static void Check(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}
static std::vector<char> Load(const char* path) {
    std::ifstream input(path, std::ios::binary);
    Check(input.good(), "fixture open");
    return std::vector<char>(std::istreambuf_iterator<char>(input), std::istreambuf_iterator<char>());
}
static void Numeric(const char* path) {
    std::vector<char> bytes = Load(path);
    Ship::BinaryReader reader(bytes.data(), bytes.size());
    Check(reader.GetEndianness() == Ship::Endianness::Native, "raw reader native default");
    reader.SetEndianness(static_cast<Ship::Endianness>(reader.ReadUByte()));
    Check(reader.ReadInt8() == -42, "int8");
    Check(reader.ReadUByte() == 240, "uint8");
    Check(reader.ReadInt16() == -12345, "int16");
    Check(reader.ReadUInt16() == 0xfedc, "uint16");
    Check(reader.ReadInt32() == -123456789, "int32");
    Check(reader.ReadUInt32() == 0xfedcba98U, "uint32");
    Check(reader.ReadInt64() == -0x0102030405060708LL, "int64");
    Check(reader.ReadUInt64() == 0xfedcba9876543210ULL, "uint64");
    Check(reader.ReadFloat() == 1.5f, "float");
    Check(reader.ReadDouble() == -1234.125, "double");
    Check(std::isinf(reader.ReadFloat()), "infinite float retained");
    Check(std::isinf(reader.ReadDouble()), "infinite double retained");
    Check(std::signbit(reader.ReadFloat()), "float negative zero retained");
    Check(std::signbit(reader.ReadDouble()), "double negative zero retained");
    bool nanFloat = false, nanDouble = false;
    try { reader.ReadFloat(); } catch (const std::runtime_error& e) {
        nanFloat = std::string(e.what()) == "BinaryReader::ReadFloat(): Error reading stream";
    }
    try { reader.ReadDouble(); } catch (const std::runtime_error& e) {
        nanDouble = std::string(e.what()) == "BinaryReader::ReadDouble(): Error reading stream";
    }
    Check(nanFloat && nanDouble, "NaN exceptions");
    Check(reader.GetBaseAddress() == bytes.size(), "numeric cursor");
    std::cout << "numeric=ok\n";
}

static void Ownership() {
    char raw[] = {'a', 'b', 'c', 'd', 'e', 'f'};
    size_t before = allocations;
    Ship::MemoryStream empty;
    size_t emptyAllocations = allocations - before;
    Check(empty.GetLength() == 0 && empty.GetBaseAddress() == 0, "default stream");
    before = allocations;
    Ship::MemoryStream copied(raw, sizeof(raw));
    size_t copiedAllocations = allocations - before;
    raw[0] = 'z';
    Check(copied.ReadByte() == 'a', "raw constructor copies input");
    std::shared_ptr<std::vector<char>> storage = std::make_shared<std::vector<char>>(raw, raw + sizeof(raw));
    before = allocations;
    Ship::MemoryStream shared(storage);
    size_t sharedAllocations = allocations - before;
    before = allocations;
    std::shared_ptr<Ship::MemoryStream> offset = std::make_shared<Ship::MemoryStream>(storage, 2);
    size_t offsetAllocations = allocations - before;
    Check(storage.use_count() == 3, "shared storage ownership");
    (*storage)[2] = 'X';
    Ship::BinaryReader reader(offset);
    Check(reader.GetEndianness() == Ship::Endianness::Native, "shared reader native default");
    std::weak_ptr<Ship::MemoryStream> lifetime = offset;
    offset.reset();
    storage.reset();
    Check(!lifetime.expired() && reader.ReadChar() == 'X', "reader preserves shared stream and offset");
    reader.Seek(-1, Ship::SeekOffsetType::Current);
    Check(reader.ReadChar() == 'X', "relative seek");
    reader.Seek(1, Ship::SeekOffsetType::End);
    Check(reader.ReadChar() == 'e', "preserve end-minus-one-minus-offset seek");
    reader.Seek(0, Ship::SeekOffsetType::Start);
    Check(reader.ReadChar() == 'z', "start seek");
    Check(reader.ToVector().size() == sizeof(raw), "ToVector copies full backing store");
    reader.Close();
    Check(!lifetime.expired() && reader.ReadChar() == 'b', "Close remains no-op");
    Ship::BinaryReader owning(new Ship::MemoryStream(raw, sizeof(raw)));
    Check(owning.GetEndianness() == Ship::Endianness::Native, "raw stream reader native default");
    uint32_t nativeValue = 0x12345678;
    Ship::BinaryReader native(reinterpret_cast<char*>(&nativeValue), sizeof(nativeValue));
    Check(native.ReadUInt32() == nativeValue, "native default decodes native bytes");
    shared.Seek(0, Ship::SeekOffsetType::Start);
    std::unique_ptr<char[]> ownedBytes = shared.Read(2);
    Check(ownedBytes[0] == 'z' && ownedBytes[1] == 'b', "owned read");
    shared.Seek(0, Ship::SeekOffsetType::Start);
    char replacement[] = {'q', 'r'};
    shared.Write(replacement, 2);
    shared.Seek(0, Ship::SeekOffsetType::Start);
    Check(shared.ReadByte() == 'q', "write through shared storage");
    std::cout << "ownership=ok allocations=" << emptyAllocations << ',' << copiedAllocations << ','
              << sharedAllocations << ',' << offsetAllocations << '\n';
}

static void Reloc(const char* path) {
    std::shared_ptr<std::vector<char>> bytes = std::make_shared<std::vector<char>>(Load(path));
    Ship::BinaryReader header(std::make_shared<Ship::MemoryStream>(bytes));
    Ship::Endianness order = static_cast<Ship::Endianness>(header.ReadUByte());
    header.SetEndianness(order);
    header.Read(3);
    Check(header.ReadUInt32() == 0x52454c4f, "real RELO resource tag");
    Check(header.ReadUInt32() == 0, "real RELO version");
    Ship::BinaryReader data(std::make_shared<Ship::MemoryStream>(bytes, 0x40));
    data.SetEndianness(order);
    uint32_t id = data.ReadUInt32();
    uint16_t internal = data.ReadUInt16(), external = data.ReadUInt16();
    uint32_t count = data.ReadUInt32();
    std::cout << "reloc=" << id << ',' << internal << ',' << external << ',' << count;
    for (uint32_t i = 0; i < count; ++i) std::cout << ',' << data.ReadUInt16();
    uint32_t size = data.ReadUInt32();
    std::vector<char> payload(size);
    data.Read(payload.data(), static_cast<int32_t>(size));
    uint32_t hash = 2166136261U;
    for (size_t i = 0; i < payload.size(); ++i) hash = (hash ^ static_cast<unsigned char>(payload[i])) * 16777619U;
    Check(data.GetBaseAddress() == bytes->size(), "real RELO payload/cursor");
    std::cout << ',' << size << ',' << hash << '\n';
}

int main(int argc, char** argv) {
    try {
        Check(argc == 4, "requires LE, BE, RELO fixtures");
        Numeric(argv[1]); Numeric(argv[2]); Ownership(); Reloc(argv[3]);
        return 0;
    } catch (const std::exception& e) {
        std::cerr << e.what() << '\n'; return 1;
    }
}
