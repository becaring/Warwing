#include "controllers/compiler.h"
#include <cassert>
#include <limits>
#include <cstring>
#include <iostream>
#include <map>
#include <vector>
#include <stdint.h>
struct Counted {
    static int copies;
    int value;
    Counted(int v=0):value(v){}
    Counted(const Counted& other):value(other.value){++copies;}
};
int Counted::copies=0;
std::map<int,Counted> Make() { std::map<int,Counted> value;value.emplace(1,Counted(10));value.emplace(2,Counted(20));return value; }
int main() {
    auto values=Make();Counted::copies=0;
    int sum=0;
    for(auto [key,value]:values){value.value+=key;sum+=value.value;}
    assert(sum==33 && values[1].value==10 && Counted::copies==2);
    for(auto& [key,value]:values){value.value+=key;}
    assert(values[1].value==11 && values[2].value==22);
    for(const auto& [key,value]:Make()){sum+=key+value.value;}
    std::map<int,std::map<int,int>> nested;nested[1][2]=3;nested[2][4]=5;
    for(auto [a,inner]:nested){for(auto [b,v]:inner){sum+=a+b+v;}}
    auto [a,b]=std::make_pair(4,7);assert(a+b==11);
    assert(values.contains(1) && !values.contains(99));
    uint64_t state=0x3275b3a7215beefULL;
    for(int i=0;i<20000;++i){
        state=state*6364136223846793005ULL+1;double value;std::memcpy(&value,&state,8);
        const double actual=Smash360Controllers::Round(value),expected=std::round(value);
        if(std::isnan(expected)){assert(std::isnan(actual));continue;}
        assert(actual==expected && std::signbit(actual)==std::signbit(expected));
    }
    for(double value:{-0.0,0.0,-0.5,0.5,std::nextafter(0.5,0.0),std::nextafter(-0.5,0.0),2.5,-2.5}){
        double actual=Smash360Controllers::Round(value),expected=std::round(value);assert(actual==expected&&std::signbit(actual)==std::signbit(expected));
    }
    std::cout<<sum<<' '<<a+b<<" binding, contains and 20000 round cases PASS\n";
}
