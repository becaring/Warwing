// Test-only object graph for executing exact extracted editor cache algorithms.
#include <cassert>
#include <cstdio>
#include <map>
#include <memory>
#include <string>
#include <vector>
#include <unordered_map>
#include <set>
#include <algorithm>
#include <stdint.h>
#include "libultraship/libultra/controller.h"
#include "controllers/compiler.h"
enum Direction { LEFT,RIGHT,UP,DOWN };
struct ControllerRumbleMapping {};
struct ControllerButton {
    std::map<std::string,int> mappings;
    std::map<std::string,int> GetAllButtonMappings(){return mappings;}
};
struct ControllerStick {
    std::map<Direction,std::map<std::string,int> > mappings;
    std::map<std::string,int> GetAllAxisDirectionMappingByDirection(Direction d){return mappings[d];}
};
struct Controller {
    std::map<CONTROLLERBUTTONS_T,std::shared_ptr<ControllerButton> > buttons;
    std::shared_ptr<ControllerStick> left,right;
    Controller():left(new ControllerStick),right(new ControllerStick){}
    std::map<CONTROLLERBUTTONS_T,std::shared_ptr<ControllerButton> > GetAllButtons(){return buttons;}
    std::shared_ptr<ControllerStick> GetLeftStick(){return left;}
    std::shared_ptr<ControllerStick> GetRightStick(){return right;}
};
struct ControlDeck {
    Controller controllers[4];
    Controller* GetControllerByPort(uint8_t port){return &controllers[port];}
};
struct Context {
    ControlDeck deck;
    static Context* GetInstance(){static Context context;return &context;}
    ControlDeck* GetControlDeck(){return &deck;}
};
class InputEditorWindow {
public:
    int32_t mGameInputBlockTimer,mMappingInputBlockTimer,mRumbleTimer;
    std::shared_ptr<ControllerRumbleMapping> mRumbleMappingToTest;
    bool mInputEditorPopupOpen;
    std::set<CONTROLLERBUTTONS_T> mButtonsBitmasks,mDpadBitmasks;
    std::unordered_map<uint8_t,std::unordered_map<CONTROLLERBUTTONS_T,std::vector<std::string> > > mBitmaskToMappingIds;
    std::unordered_map<uint8_t,std::unordered_map<uint8_t,std::unordered_map<Direction,std::vector<std::string> > > > mStickDirectionToMappingIds;
    void InitElement();void UpdateBitmaskToMappingIds(uint8_t);void UpdateStickDirectionToMappingIds(uint8_t);
};
#include "actual_methods.inc"
int main(){
    InputEditorWindow editor;editor.InitElement();
    assert(editor.mButtonsBitmasks.size()==10&&editor.mDpadBitmasks.size()==4);
    assert(editor.mGameInputBlockTimer==INT32_MAX&&!editor.mInputEditorPopupOpen);
    for(uint8_t port=0;port<4;++port){
        Controller* controller=Context::GetInstance()->deck.GetControllerByPort(port);
        controller->buttons[BTN_A].reset(new ControllerButton);
        controller->buttons[BTN_A]->mappings["z-last-existing"]=1;
        editor.UpdateBitmaskToMappingIds(port);
        controller->buttons[BTN_A]->mappings["a-new"]=2;
        editor.UpdateBitmaskToMappingIds(port);editor.UpdateBitmaskToMappingIds(port);
        const std::vector<std::string>& ids=editor.mBitmaskToMappingIds[port][BTN_A];
        assert(ids.size()==2&&ids[0]=="z-last-existing"&&ids[1]=="a-new");
        controller->left->mappings[UP]["left-up"]=1;controller->right->mappings[DOWN]["right-down"]=1;
        editor.UpdateStickDirectionToMappingIds(port);editor.UpdateStickDirectionToMappingIds(port);
        assert(editor.mStickDirectionToMappingIds[port][LEFT][UP].size()==1);
        assert(editor.mStickDirectionToMappingIds[port][LEFT][UP][0]=="left-up");
        assert(editor.mStickDirectionToMappingIds[port][RIGHT][DOWN][0]=="right-down");
        assert(editor.mStickDirectionToMappingIds[port][RIGHT][UP].empty());
    }
    puts("PASS actual editor initialization and four-port mapping ID insertion order, deduplication, and stick/direction routing");
}
