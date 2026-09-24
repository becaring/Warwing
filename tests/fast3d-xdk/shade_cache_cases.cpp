#include "fast3d/shade_cache.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
struct Light {struct {uint8_t col[3];} l;};
struct LightColorAt {
    uint8_t operator()(const Light& light,unsigned channel) const {return light.l.col[channel];}
};
extern "C" __declspec(noinline) bool NativeShadeProbe(const Light* lights,const float (*directions)[3],
    const float (*lookat)[3],unsigned count,unsigned mode,unsigned s,unsigned t,uint32_t normal,
    Shipyard::Fast3D::ShadeValue* output,Shipyard::Fast3D::ShadeCache& cache) {
    cache.Initialize();
    Shipyard::Fast3D::ShadeKey key;key.Set(count,lights,LightColorAt(),directions,mode,lookat,s,t);
    cache.Select(key);
    const Shipyard::Fast3D::ShadeValue* found=cache.Find(normal);
    if(found){*output=*found;return true;}
    cache.Store(normal,*output);return false;
}
int main(){
    Light lights[33];float dirs[32][3],lookat[2][3];
    memset(lights,27,sizeof(lights));memset(dirs,0,sizeof(dirs));memset(lookat,0,sizeof(lookat));
    Shipyard::Fast3D::ShadeCache cache;cache.Initialize();
    Shipyard::Fast3D::ShadeKey base; base.Set(33,lights,LightColorAt(),dirs,2,lookat,32767,65535);
    assert(base.count<=140);
    Shipyard::Fast3D::ShadeValue value={{7,91,253},-32768.0f,32767.0f};
    cache.Select(base);cache.Store(0x12ab34,value);
    assert(cache.Find(0x12ab34));assert(!cache.Find(0x12ab35));
    for(unsigned word=0;word<base.count;++word){
        Shipyard::Fast3D::ShadeKey changed=base;changed.words[word]^=1;
        cache.Select(changed);assert(!cache.Find(0x12ab34));
        cache.Select(base);assert(cache.Find(0x12ab34));
        assert(memcmp(cache.Find(0x12ab34),&value,sizeof(value))==0);
    }
    // Exact-key ownership survives source arrays and the temporary key changing.
    memset(lights,0,sizeof(lights));memset(dirs,0x3f,sizeof(dirs));memset(lookat,0x4f,sizeof(lookat));
    assert(cache.Find(0x12ab34));
    const int8_t signedNormal[3]={-128,-1,127};
    assert(Shipyard::Fast3D::ShadeCache::Normal(signedNormal)==0x80ff7f);
    for(unsigned state=0;state<256;++state){
        Shipyard::Fast3D::ShadeKey key=base;key.words[0]^=state;
        cache.Select(key);
        for(unsigned normal=0;normal<512;++normal){
            Shipyard::Fast3D::ShadeValue local={{(uint8_t)state,(uint8_t)normal,0},(float)normal,(float)-((int)normal)};
            cache.Store(normal,local);
            assert(memcmp(cache.Find(normal),&local,sizeof(local))==0);
        }
    }
    puts("PASS every active shade-key word invalidates, value/key ownership, signed normals, 256 states/131072 collision stores");
}
