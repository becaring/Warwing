#pragma once
#include <xtl.h>
#include <stdint.h>
#include <vector>
namespace Fast {
extern IDirect3DDevice9* xenos_device;
// Same interop points the donor uses around native ImGui draws.
// Preserve/resume framebuffer contents and invalidate cached Xenos state.
void BeginNativeGuiDraw();
void InvalidateNativeGuiState();
bool ReadPresentedFrameRGBA(std::vector<uint8_t>& pixels, uint32_t& width, uint32_t& height);
}
