#include "ship/utils/binarytools/BinaryWriter.h"
#include "ship/utils/binarytools/MemoryStream.h"
#include <cstdio>
#include <limits>

static void exercise(Ship::BinaryWriter& writer, Ship::Endianness order) {
    writer.SetEndianness(order);
    writer.Write(int8_t(-42)); writer.Write(uint8_t(240));
    writer.Write(int16_t(-12345)); writer.Write(uint16_t(0xfedc));
    writer.Write(int32_t(-123456789)); writer.Write(uint32_t(0xfedcba98));
    writer.Write(int64_t(-0x0102030405060708LL));
    writer.Write(uint64_t(0xfedcba9876543210ULL));
    writer.Write(1.5f); writer.Write(-1234.125);
    writer.Write(-0.0f); writer.Write(std::numeric_limits<double>::infinity());
    writer.Write(std::string("a\0b",3));
    writer.Write(int32_t(123),int32_t(-456));
    char raw[] = {0,1,127,char(255)}; writer.Write(raw,sizeof(raw));
    std::vector<char> bytes=writer.ToVector();
    for (size_t i=0;i<bytes.size();++i) std::printf("%02x",static_cast<unsigned char>(bytes[i]));
    std::printf("\n");
}
int main() {
    for (int i=0;i<3;++i) {
        Ship::Endianness order=i==0?Ship::Endianness::Native:(i==1?Ship::Endianness::Little:Ship::Endianness::Big);
        Ship::BinaryWriter owned; exercise(owned,order);
        Ship::BinaryWriter raw(new Ship::MemoryStream()); exercise(raw,order);
        std::shared_ptr<Ship::Stream> stream(new Ship::MemoryStream());
        Ship::BinaryWriter shared(stream); exercise(shared,order);
    }
}
