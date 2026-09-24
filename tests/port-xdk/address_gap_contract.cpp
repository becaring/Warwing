#include "memory/address_gap.h"

extern "C" uintptr_t SmashAddressGapAfterExclude(uintptr_t addr, uintptr_t first, size_t length) {
    Shipyard::Memory::AddressGap gap = {0, ~uintptr_t(0)};
    gap.Exclude(addr, first, length);
    return gap.lo ^ gap.hi;
}
