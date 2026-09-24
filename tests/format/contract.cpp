#ifdef SMASH360_FMT_REFERENCE
#define FMT_HEADER_ONLY 1
#include "spdlog/fmt/bundled/format.h"
#else
#include "format/format.h"
#endif
#include <fstream>
#include <limits>
#include <stdint.h>
int main(int argc, char** argv) {
    std::ofstream exact(argv[1], std::ios::binary);
    exact << fmt::format("Player {}|  ({} -> {}, Col {})|##{}{}", 4, std::string("Menu"), "Input", 2, "Flag", 9) << '\n';
    exact << fmt::format("{}|{}|{}|{}|{}|{}", false, true, (int8_t)-128, (uint8_t)255,
                       std::numeric_limits<int64_t>::min(), std::numeric_limits<uint64_t>::max()) << '\n';
    exact << fmt::format("0x{:08X}|0x{:016X}|{:x}|{}|{}", (uint32_t)0xdeadbeef, (uint64_t)0x123456789abcdef0ULL,
                       (uint32_t)0xcafe, fmt::ptr(reinterpret_cast<void*>(0x1230)), "UTF-8 \xC3\xA9") << '\n';
    exact << fmt::format("{:>9}|{:<9}|{:^9}|{:+d}|{:#x}|{{escaped}}", "a", "b", "c", 7, 32) << '\n';
    exact << fmt::format("{} {} {} {} {} {} {} {} {} {} {} {} {}", 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13) << '\n';
    exact.close();
    std::ofstream floats(argv[2], std::ios::binary);
    floats << fmt::format("{}|{}|{:.3f}|{:.3e}", 1.2345678901234567, -0.0, 1.2345, 12345.0) << '\n';
    return exact.fail() || floats.fail();
}
