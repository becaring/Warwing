#pragma once
// Actual directly used public contracts; the upstream umbrella additionally
// imports desktop WASAPI/SDL player implementations into every GUI header.
#include <libultraship/libultra.h>
#include <libultraship/bridge.h>
#include <libultraship/color.h>
#include <libultraship/luslog.h>
#include <ship/Context.h>
#include <ship/window/Window.h>
#include <ship/window/gui/Gui.h>
#include <ship/window/gui/GuiWindow.h>
#include <ship/window/gui/GuiMenuBar.h>
#include <ship/config/ConsoleVariable.h>
#include <ship/config/Config.h>
#include <ship/audio/Audio.h>
#include <ship/audio/AudioPlayer.h>
#include <ship/debug/Console.h>
namespace Smash360Port {
inline Color_RGBA8 RGBA(uint8_t r=0,uint8_t g=0,uint8_t b=0,uint8_t a=0) { Color_RGBA8 value={r,g,b,a}; return value; }
inline Color_RGB8 RGB(uint8_t r=0,uint8_t g=0,uint8_t b=0) { Color_RGB8 value={r,g,b}; return value; }
}
