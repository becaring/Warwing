#include "ship/window/gui/StatsWindow.h"
#include "ship/window/gui/ConsoleWindow.h"
#include "ship/window/gui/GameOverlay.h"
#include "libultraship/window/gui/GfxDebuggerWindow.h"
#include "ship/window/gui/resource/GuiTexture.h"
#include "ship/window/gui/resource/Font.h"
void ProbeActualWidgetConstructors() {
    Ship::StatsWindow stats("stats", "Stats");
    Ship::ConsoleWindow console("console", "Console", ImVec2(520,600), ImGuiWindowFlags_None);
    LUS::GfxDebuggerWindow debugger("debugger", "Debugger", ImVec2(520,600));
    std::shared_ptr<Ship::ResourceInitData> initData;
    Ship::Font font(initData);
    Ship::GuiTexture texture(initData);
}
