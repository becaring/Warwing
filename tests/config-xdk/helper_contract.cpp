#include "config/compiler.h"
#include <iostream>
#include <string>
#include <stdexcept>
static void Check(bool b){if(!b)throw std::runtime_error("compiler helper contract");}
static std::string events;
static int alive;
class Range {int values[3];public:Range(){values[0]=1;values[1]=2;values[2]=3;++alive;}Range(const Range&r){for(int i=0;i<3;++i)values[i]=r.values[i];++alive;}~Range(){--alive;}int*begin(){events+='B';return values;}int*end(){events+='E';return values+3;}};
static Range Temporary(){events+='R';return Range();}
void Contract(){
    int total=0;events.clear();for(const auto& value:Temporary()){Check(alive==1);total+=value;}
    Check(total==6&&alive==0&&events=="RBE");
    Range range;events.clear();for(auto& value:range){value*=2;if(value==4)continue;total+=value;}Check(total==14&&events=="BE");
    int a[2]={5,7};for(const auto& value:a)total+=value;Check(total==26);
    std::string text("a\0bc",4);xbox_compat::string_view view(text);
    Check(view.data()==text.data()&&view.size()==4&&view.find(xbox_compat::string_view("\0b",2))==1);
    Check(view.substr(1,2)==xbox_compat::string_view("\0b",2));
    Check(view.find("",4)==4&&view.find("",5)==xbox_compat::string_view::npos);
    Check(xbox_compat::hash_string_view(view)==std::hash<std::string>()(text));
    bool threw=false;try{view.substr(5);}catch(const std::out_of_range&){threw=true;}Check(threw);
}
#ifndef _XBOX
int main(){Contract();std::cout<<"range lifetime/cvref/order and string_view/hash=ok\n";}
#endif
