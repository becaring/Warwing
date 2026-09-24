#include "binary/compat.h"
#include "ship/utils/binarytools/endianness.h"
#include "ship/utils/binarytools/Stream.h"
#include <type_traits>

static_assert(!std::is_convertible<Ship::Endianness, int>::value, "scoped enum must not implicitly convert to integer");
static_assert(!std::is_convertible<int, Ship::Endianness>::value, "integer construction must stay explicit");
static_assert(!std::is_convertible<Ship::Endianness, Ship::SeekOffsetType>::value, "enum domains stay distinct");
static_assert(sizeof(Ship::Endianness) == sizeof(int), "enum storage width");

int main() {
    std::unique_ptr<char[]> bytes = Shipyard::Binary::MakeZeroedChars(257);
    for (size_t i = 0; i < 257; ++i) if (bytes[i] != 0) return 1;
    if (!Shipyard::Binary::IsNaN(Shipyard::Binary::QuietNaN())) return 2;
    if (Shipyard::Binary::IsNaN(1.0) || Shipyard::Binary::IsNaN(std::numeric_limits<double>::infinity())) return 3;
    return 0;
}
