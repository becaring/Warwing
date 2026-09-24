#include "../graphics/services.h"
#include "input/physical.h"

void Smash360_PollWindowInput(Smash360WindowInput* state,bool (*)(int),bool (*)(int),void (*)(),bool (*)(int),bool (*)(int)){
    ShipyardInput_PumpGamepads();
    if(!state)return;
    // This backend currently exposes controllers only. Leave the window's running
    // lifetime with its owner, and never manufacture key or pointer events.
    state->x=state->y=state->deltaX=state->deltaY=0;
    state->wheelX=state->wheelY=0;state->buttons=0;state->captured=false;
}
void Smash360_SetPointerPosition(int32_t,int32_t){}
void Smash360_SetPointerVisible(bool){}
void Smash360_SetPointerCaptured(bool){}
const char* Smash360_KeyName(int){return "Unknown";}
