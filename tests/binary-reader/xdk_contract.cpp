#include "ship/utils/binarytools/BinaryReader.h"
#include "ship/utils/binarytools/MemoryStream.h"
// Multiple paths must remain valid even with original-filename #line mappings.
#include "ship/utils/binarytools/Stream.h"
#include "ship/utils/binarytools/endianness.h"

#if !defined(_XBOX) || !defined(_M_PPC)
#error Contract object must be compiled by the native Xbox PowerPC toolchain
#endif
#ifndef IS_BIGENDIAN
#error Native Xbox endian macros must select big endian
#endif
typedef char NativeIsBig[(Ship::Endianness::Native == Ship::Endianness::Big) ? 1 : -1];
typedef char EndianWidth[(sizeof(Ship::Endianness) == sizeof(int)) ? 1 : -1];
typedef char SeekWidth[(sizeof(Ship::SeekOffsetType) == sizeof(int)) ? 1 : -1];
typedef char PointerWidth[(sizeof(void*) == 4) ? 1 : -1];

// Compile native ownership/NaN helper instantiations. This object is not linked
// into a separate test XEX, and is not a claim of target runtime validation.
int CompileReaderContract(char* bytes, size_t length) {
    Ship::BinaryReader reader(bytes, length);
    reader.SetEndianness(Ship::Endianness::Little);
    reader.Seek(0, Ship::SeekOffsetType::Start);
    std::unique_ptr<char[]> zeroed = Shipyard::Binary::MakeZeroedChars(8);
    return reader.ReadInt32() + zeroed[0] + Shipyard::Binary::IsNaN(Shipyard::Binary::QuietNaN());
}
