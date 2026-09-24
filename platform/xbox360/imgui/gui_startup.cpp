// Same production GUI initialization contract as current DX11 backend Init().
#include "ship/Context.h"
#include "ship/window/Window.h"
#include "ship/window/gui/Gui.h"
void Smash360_InitializeGuiForXenos() {
    Ship::GuiWindowInitData data = {};
    Ship::Context::GetInstance()->GetWindow()->GetGui()->Init(data);
}
