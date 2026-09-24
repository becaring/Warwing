#pragma once
#include "shipyard_imgui_xenos.h"
#include "services.h"
#include "interop.h"
void Smash360_ImGuiPlatformInit();
void Smash360_ImGuiPlatformShutdown();
void Smash360_ImGuiPlatformNewFrame(unsigned width, unsigned height, bool menuVisible);
