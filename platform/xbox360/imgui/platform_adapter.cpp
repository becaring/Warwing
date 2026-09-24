#include "imgui_xenos.h"
#include "platform_frame.h"
#include "input/physical.h"

#ifdef _XBOX
IDirect3DDevice9* Shipyard_ImGuiDevice(){return Fast::xenos_device;}
void Shipyard_ImGuiBeginNativeDraw(){Fast::BeginNativeGuiDraw();}
void Shipyard_ImGuiInvalidateNativeState(){Fast::InvalidateNativeGuiState();}
void Shipyard_ImGuiLogShader(const char* message){Smash360_Log("ImGui shader: %s",message);}
__declspec(noreturn) void Shipyard_ImGuiFatal(const char* operation,HRESULT result){Smash360_Fatal(operation,result);}
#endif

void Smash360_ImGuiPlatformInit(){
    const Shipyard::ImGuiPlatform::Services services={Smash360_Time,ShipyardInput_BeginGamepadPresentation,"Smash360_Xbox360"};
    Shipyard::ImGuiPlatform::Init(services);
}
void Smash360_ImGuiPlatformShutdown(){Shipyard::ImGuiPlatform::Shutdown();}
void Smash360_ImGuiPlatformNewFrame(unsigned width,unsigned height,bool menuVisible){
    Shipyard::ImGuiPlatform::NewFrame(width,height,menuVisible);
}
