#pragma once
#include <xtl.h>

namespace Fast {
// The same donor Xenos device is reused by GfxRenderingAPIXenos::Init. System
// UI needs it before storage/configuration and therefore before Fast3D setup.
void InitializeNativeDisplay();
HRESULT PresentNativeStartupUI();
void ShutdownNativeDisplay();
}
