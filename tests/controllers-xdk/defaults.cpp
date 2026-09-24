#include "libultraship/controller/controldevice/controller/mapping/ControllerDefaultMappings.h"
#include <iostream>
#include <map>
#include <set>

template<class T> void Print(const T& value);
template<class A,class B> void Print(const std::pair<A,B>& value);
template<class T,class A> void Print(const std::vector<T,A>& values);
template<class T,class H,class E,class A> void Print(const std::unordered_set<T,H,E,A>& values);
template<class K,class V,class H,class E,class A> void Print(const std::unordered_map<K,V,H,E,A>& values);
template<class T> void Print(const T& value) { std::cout << static_cast<int>(value); }
template<class A,class B> void Print(const std::pair<A,B>& value) { std::cout << '('; Print(value.first);std::cout<<':';Print(value.second);std::cout<<')'; }
template<class T,class A> void Print(const std::vector<T,A>& values) { std::cout<<'[';for(const auto& value:values){Print(value);std::cout<<',';}std::cout<<']'; }
template<class T,class H,class E,class A> void Print(const std::unordered_set<T,H,E,A>& values) { std::set<T> ordered(values.begin(),values.end());std::cout<<'{';for(const auto& value:ordered){Print(value);std::cout<<',';}std::cout<<'}'; }
template<class K,class V,class H,class E,class A> void Print(const std::unordered_map<K,V,H,E,A>& values) { std::map<K,V> ordered(values.begin(),values.end());std::cout<<'{';for(const auto& value:ordered){Print(value);std::cout<<',';}std::cout<<'}'; }
void Dump(Ship::ControllerDefaultMappings& mappings) {
    Print(mappings.GetDefaultKeyboardKeyToButtonMappings()); std::cout<<'\n';
    Print(mappings.GetDefaultKeyboardKeyToAxisDirectionMappings()); std::cout<<'\n';
    Print(mappings.GetDefaultSDLButtonToButtonMappings()); std::cout<<'\n';
    Print(mappings.GetDefaultSDLButtonToAxisDirectionMappings()); std::cout<<'\n';
    Print(mappings.GetDefaultSDLAxisDirectionToButtonMappings()); std::cout<<'\n';
    Print(mappings.GetDefaultSDLAxisDirectionToAxisDirectionMappings()); std::cout<<'\n';
}
int main() {
    Ship::ControllerDefaultMappings ship; Dump(ship);
    LUS::ControllerDefaultMappings lus; Dump(lus);
    std::unordered_map<CONTROLLERBUTTONS_T,std::unordered_set<Ship::KbScancode>> keyboard;
    keyboard[0x8000].insert(Ship::LUS_KB_Z); keyboard[0x8000].insert(Ship::LUS_KB_X);
    std::unordered_map<Ship::StickIndex,std::vector<std::pair<Ship::Direction,Ship::KbScancode>>> axis;
    axis[Ship::RIGHT_STICK].push_back(std::make_pair(Ship::UP,Ship::LUS_KB_E));
    LUS::ControllerDefaultMappings custom(keyboard,axis,{}, {}, {}, {}); Dump(custom);
    Ship::ControllerDefaultMappings customShip(keyboard,axis,{}, {}, {}, {}); Dump(customShip);
    LUS::ControllerDefaultMappings explicitEmpty({}, {}, {}, {}, {}, {}); Dump(explicitEmpty);
    return 0;
}
