#include "interop.h"
#define STB_IMAGE_WRITE_IMPLEMENTATION
#define STB_IMAGE_WRITE_STATIC
#include "fast/backends/stb_image_write.h"

// Keeps BattleShip's optional capture contract: a PNG of the current backbuffer,
// 1 on success, 0 on failure, and no C++ exception escapes.
extern "C" int portFastCaptureBackbufferPNG(const char* path) {
    if (!path) return 0;
    try {
        std::vector<uint8_t> rgba;
        uint32_t width=0,height=0;
        if (!Fast::ReadPresentedFrameRGBA(rgba,width,height)) return 0;
        return stbi_write_png(path,(int)width,(int)height,4,&rgba[0],(int)width*4) ? 1 : 0;
    } catch (...) {
        return 0;
    }
}
