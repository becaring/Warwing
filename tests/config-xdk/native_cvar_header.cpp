#include "ship/config/ConsoleVariable.h"
typedef char CVarTypeWidth[sizeof(Ship::ConsoleVariableType)==sizeof(int)?1:-1];
typedef char CVarNativeLayout[sizeof(Ship::CVar)==8?1:-1];
void VerifyActualCVarHeader() {
    Ship::CVar value;
    value.Type=Ship::ConsoleVariableType::String;
    value.String=0;
    std::shared_ptr<Ship::CVar> shared=std::make_shared<Ship::CVar>();
    shared->Type=Ship::ConsoleVariableType::Integer;
    shared->Integer=42;
}
