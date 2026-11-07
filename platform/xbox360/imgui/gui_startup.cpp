// Same GUI initialization contract as the DX11 backend Init().
#include "ship/Context.h"
#include "ship/window/Window.h"
#include "ship/window/gui/Gui.h"
void Smash360_InitializeGuiForXenos() {
    Ship::GuiWindowInitData data = {};
    Ship::Context::GetInstance()->GetWindow()->GetGui()->Init(data);
}
