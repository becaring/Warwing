#include "fast3d/platform.h"
#include <unordered_map>
#include <stdexcept>
#include <cstdio>
#if !defined(_XBOX)
#include <cfenv>
#endif
static void require(bool value) { if(!value)throw std::runtime_error("Fast3D platform arithmetic contract failed"); }
int main() {
    require(!Smash360Fast3D::LowAddressInLoadedModule(nullptr));
    require(!Smash360Fast3D::LowAddressInLoadedModule(reinterpret_cast<const void*>(0x0E000000u)));
    bool rejected=false;
    try { Smash360Fast3D::LowAddressInLoadedModule(reinterpret_cast<const void*>(static_cast<uintptr_t>(0x82000000u))); }
    catch(const std::logic_error&) { rejected=true; }
    require(rejected);
    std::unordered_map<int,int> map;
    map.max_load_factor(0.7f);
    Smash360Fast3D::ReserveEntries(map,2048);
    const size_t buckets=map.bucket_count();
    for(int i=0;i<2048;++i)map.insert(std::make_pair(i,i));
    require(map.bucket_count()==buckets && map.size()==2048);
    std::unordered_map<int,int> depths;
    depths.insert(std::make_pair(1,99));depths.insert(std::make_pair(4096,42));
    map.insert(depths.begin(),depths.end());
    require(map.find(1)->second==1 && map.find(4096)->second==42);
#if !defined(_XBOX)
    const int modes[]={FE_TONEAREST,FE_DOWNWARD,FE_UPWARD,FE_TOWARDZERO};
    unsigned comparisons=0;
    for(int mode:modes) {
        require(std::fesetround(mode)==0);
        for(int i=-16000;i<=16000;++i) {
            const float value=static_cast<float>(i)*0.125f;
            require(Smash360Fast3D::RoundMatrixWord(value)==std::lrintf(value));
            const double precise=static_cast<double>(value)+0.49999999999999994;
            require(Smash360Fast3D::RoundSignedWord(precise)==std::lrint(precise));
            ++comparisons;
        }
    }
    std::fesetround(FE_TONEAREST);
    for(int i=-16000;i<=16000;++i) {
        const double value=static_cast<float>(i)*0.125f;
        require(Smash360Fast3D::RoundViewport(value)==std::round(value));
    }
    const float edges[]={0.0f,-0.0f,0.49999997f,-0.49999997f,0.5f,-0.5f,16777216.0f,2147483520.0f};
    for(float edge:edges) {
        require(Smash360Fast3D::RoundViewport(edge)==std::round(static_cast<double>(edge)));
        require(Smash360Fast3D::RoundMatrixWord(edge)==std::lrintf(edge));
    }
    std::printf("%u current-mode matrix rounding comparisons; viewport rounding/cache reserve/depth insertion passed\n",comparisons);
#endif
    return 0;
}
