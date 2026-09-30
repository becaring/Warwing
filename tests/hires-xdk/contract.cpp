// Full real pack source; only application path/CVar/log providers are test seams.
#include "actual_pack.cpp"
#include <cassert>
#include <fstream>
#include <string_view>
#include "config/string_view.h"
#include "hires/compiler.h"
static std::string rootPath;
namespace Ship {
std::string Context::GetPathRelativeToAppDirectory(const std::string &path) { return rootPath + "/" + path; }
}
extern "C" int32_t CVarGetInteger(const char *name, int32_t fallback) {
    if (std::string(name) == "gHiResTextures.CacheBudgetMB")
        return 16;
    if (std::string(name) == "gHiResTextures.DumpSource")
        return 1;
    return fallback;
}
extern "C" void port_log(const char *, ...) {}
static void views() {
    const char bytes[] = {'a', '/', 'b', '\0', '#', '/', 'z'};
    for (size_t len = 0; len <= sizeof(bytes); ++len)
        for (size_t pos = 0; pos < 10; ++pos) {
            std::string_view standard(bytes, len);
            xbox_compat::string_view adapted(bytes, len);
            const char choices[] = {'/', '\0', '#'};
            for (unsigned i = 0; i < 3; ++i)
                assert(standard.rfind(choices[i], pos) == adapted.rfind(choices[i], pos));
            assert(standard.find_last_of(std::string_view(choices, 3), pos) ==
                   adapted.find_last_of(xbox_compat::string_view(choices, 3), pos));
            assert(standard.find_last_of(std::string_view(), pos) ==
                   adapted.find_last_of(xbox_compat::string_view(), pos));
            assert(standard.rfind('/') == adapted.rfind('/'));
        }
}
int main(int argc, char **argv) {
    assert(argc == 2);
    rootPath = argv[1];
    views();
    using namespace ssb64::hires;
    const char *valid[] = {"SMASH BROTHERS#A1B2C3D4#0#2_all.png", "anything#cafe1234#3#0.PNG",
                           "pre_fix#cafe1234#3#0_suffix.png"};
    for (unsigned i = 0; i < 3; ++i)
        assert(ParseFilename(valid[i]));
    const char *invalid[] = {"bad.png", "x#123#0#2.png", "x#GAFE1234#0#2.png", "x#cafe1234#12#2.png",
                             "x#cafe1234#0#2.jpg"};
    for (unsigned i = 0; i < 5; ++i)
        assert(!ParseFilename(invalid[i]));
    assert(Crc32Bytes(reinterpret_cast<const uint8_t *>("123456789"), 9) == 0xcbf43926u);
    HashKey a, b, c;
    a.rgba8Crc = 1;
    b.rgba8Crc = 2;
    c.rgba8Crc = 3;
    LruCache cache(16);
    std::shared_ptr<DecodedTexture> ta(new DecodedTexture), tb(new DecodedTexture), tc(new DecodedTexture);
    ta->rgba.resize(8, 1);
    tb->rgba.resize(8, 2);
    tc->rgba.resize(8, 3);
    cache.Insert(a, ta);
    cache.Insert(b, tb);
    auto pin = cache.Get(a);
    cache.Insert(c, tc);
    assert(cache.Contains(a) && !cache.Contains(b) && cache.Contains(c) && cache.Bytes() == 16);
    cache.Clear();
    assert(pin->rgba[0] == 1 && cache.Bytes() == 0);
    HiResPack &pack = HiResPack::Get();
    assert(pack.Init());
    assert(pack.Stats().indexedTextures == 3 && pack.Stats().collisions == 1);
    const uint8_t source[16] = {1, 2, 3, 255, 4, 5, 6, 255, 7, 8, 9, 255, 10, 11, 12, 255};
    const DecodedTexture *hit = pack.Lookup(0, 2, source, 2, 2);
    assert(hit && hit->w == 4 && hit->h == 4 && hit->rgba[2] == 200);
    const uint8_t bad[4] = {91, 92, 93, 255};
    assert(!pack.Lookup(0, 2, bad, 1, 1));
    assert(pack.LookupStatsSnapshot().decodeFails == 1);
    assert(!pack.Lookup(0, 2, bad, 1, 1));
    assert(pack.LookupStatsSnapshot().decodeFails == 1);
    pack.StartPreload();
#if PROJECTED
    for (unsigned i = 0; i < 5000 && gPreloadLive.load() != 0; ++i)
        Sleep(1);
#else
    for (unsigned i = 0; i < 5000 && gPreloadLive.load() != 0; ++i)
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
#endif
    assert(gPreloadLive.load() == 0);
    pack.StopPreload();
    assert(gPreloadThreads.empty());
    hit = pack.Lookup(0, 2, source, 2, 2);
    assert(hit && hit->rgba[2] == 200);
    const uint8_t texels[12] = {1, 2, 3, 4, 99, 99, 5, 6, 7, 8, 99, 99};
    const uint8_t palette[4] = {0x12, 0x34, 0xab, 0xcd};
    pack.MaybeDumpSource(2, 2, texels, 2, 2, 6, palette, 4);
    DumpHeader hdr = {0};
    hdr.magic = 0x44524853;
    hdr.version = 1;
    hdr.width = 0x1234;
    hdr.height = 0xabcd;
    hdr.bpl = 0x12345678;
    hdr.texelBytes = 0x89abcdef;
    hdr.paletteBytes = 0x10203040;
    hdr.fmt = 2;
    hdr.siz = 3;
    unsigned char encoded[36];
    Smash360HiRes::EncodeDumpHeader(encoded, hdr);
    assert(sizeof(hdr) == 36 && std::memcmp(encoded, &hdr, 36) == 0);
    assert(encoded[0] == 'S' && encoded[1] == 'H' && encoded[2] == 'R' && encoded[3] == 'D');
    pack.StopPreload();
    assert(pack.Init());
    assert(pack.Stats().indexedTextures == 3);
    puts("PASS real HiRes parser/CRC/LRU pinning, loose+ZIP collision/decode/failure, preload/join/reinit, explicit LE "
         "dump and string_view boundaries");
}
