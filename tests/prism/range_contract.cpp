#include <stdexcept>
#include <string>

namespace {
std::string events;
int alive=0;
class Range {
    int entries[3];
public:
    Range(){entries[0]=1;entries[1]=2;entries[2]=3;++alive;}
    Range(const Range& other){for(int i=0;i<3;++i)entries[i]=other.entries[i];++alive;}
    ~Range(){--alive;}
    int* begin(){events+='B';return entries;}
    int* end(){events+='E';return entries+3;}
};
Range makeRange(){events+='R';return Range();}
void check(bool okay){if(!okay)throw std::runtime_error("range lifetime/order contract failed");}
}

void TestPrismRangeContract(){
    events.clear();int total=0;
    for(const auto& value:makeRange()){
        check(alive==1);total+=value;
    }
    check(total==6&&alive==0&&events=="RBE");
    Range values;events.clear();
    for(auto& value:values){value*=2;if(value==4)continue;total+=value;}
    check(total==14&&events=="BE");
    events.clear();for(const auto& value:values){total+=value;break;}
    check(total==16&&events=="BE");
    int array[2]={5,7};
    for(const auto& value:array){total+=value;}
    check(total==28);
}
