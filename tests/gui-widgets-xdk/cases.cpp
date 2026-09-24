#include "ship/window/gui/GuiElement.h"
#include "ship/debug/Console.h"
#include <cstdio>
#include <stdexcept>
static void require(bool value){if(!value)throw std::runtime_error("widget differential contract failed");}
class ElementProbe : public Ship::GuiElement {
public:
    int inits,updates,draws;
    ElementProbe():GuiElement(),inits(0),updates(0),draws(0){}
    explicit ElementProbe(bool visible):GuiElement(visible),inits(0),updates(0),draws(0){}
    void Draw(){++draws;}
    void DrawElement(){++draws;}
protected:
    void InitElement(){++inits;}
    void UpdateElement(){++updates;}
};
static int32_t Handler(std::shared_ptr<Ship::Console>,std::vector<std::string> args,std::string* output){
    if(output)*output=args[0];return 73;
}
int main(){
    ElementProbe hidden,visible(true);
    require(!hidden.IsVisible()&&!hidden.IsInitialized()&&visible.IsVisible());
    hidden.Init();hidden.Init();hidden.Update();hidden.Update();hidden.Draw();
    require(hidden.IsInitialized()&&hidden.inits==1&&hidden.updates==2&&hidden.draws==1);
    hidden.Show();require(hidden.IsVisible());hidden.ToggleVisibility();require(!hidden.IsVisible());
    hidden.Hide();require(!hidden.IsVisible());
    Ship::CommandArgument required;
    require(required.Info.empty()&&required.Type==Ship::ArgumentType::NUMBER&&!required.Optional);
    required.Info="amount";
    Ship::CommandArgument optional;
    optional.Info="name";optional.Type=Ship::ArgumentType::TEXT;optional.Optional=true;
    Ship::CommandEntry entry;entry.Handler=Handler;entry.Description="actual console contract";
    entry.Arguments.push_back(required);entry.Arguments.push_back(optional);
    Ship::Console console;console.Init();console.AddCommand("sample",entry);
    require(console.HasCommand("sample")&&!console.HasCommand("absent"));
    require(console.BuildUsage("sample")=="<amount> [name] ");
    entry.Description="replacement";console.AddCommand("sample",entry);
    require(console.GetCommand("sample").Description=="actual console contract");
    std::vector<std::string> args(1,"value");std::string output;
    require(console.GetCommand("sample").Handler(std::shared_ptr<Ship::Console>(),args,&output)==73&&output=="value");
    require(console.GetCommands().size()==1);
    require(console.GetCommand("created").Arguments.empty()&&console.GetCommands().size()==2);
    std::printf("lifecycle %d %d %d; console usage %s; callback %s; duplicate retained\n",hidden.inits,hidden.updates,hidden.draws,console.BuildUsage("sample").c_str(),output.c_str());
    return 0;
}
