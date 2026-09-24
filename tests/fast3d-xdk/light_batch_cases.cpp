#include "fast3d/light_batch.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <float.h>
static void Require(bool value,const char* message) {if(!value){fprintf(stderr,"FAIL %s\n",message);exit(1);}}
static float FromBits(uint32_t bits){float f;memcpy(&f,&bits,4);return f;}
extern "C" __declspec(noinline) float Original127(float value){volatile float divisor=127.0f;return value/divisor;}
extern "C" __declspec(noinline) float Adapted127(float value){return Smash360Fast::DivideNormal127(value,Shipyard::Fast3D::NearestRounding());}
extern "C" __declspec(noinline) float Bounded127(float value){return Smash360Fast::DivideNormalByte127(value,true);}
static bool Same(float a,float b){return memcmp(&a,&b,4)==0;}
int main(){
    const unsigned rounding[]={_RC_NEAR,_RC_DOWN,_RC_UP,_RC_CHOP};
    unsigned comparisons=0;uint32_t random=0x71453a19;
    const unsigned originalMode=_controlfp(0,0)&_MCW_RC;
    for(unsigned mode=0;mode<4;++mode){
        _controlfp(rounding[mode],_MCW_RC);
        for(unsigned exponent=0;exponent<255;++exponent)for(unsigned sign=0;sign<2;++sign)
        for(unsigned sample=0;sample<1024;++sample){
            random=random*1664525u+1013904223u;
            uint32_t mantissa=random&0x7fffff;
            if(sample<4)mantissa=(sample&1)?0x7fffff-(sample>>1):(sample>>1);
            const float input=FromBits((sign<<31)|(exponent<<23)|mantissa);
            Require(Same(Original127(input),Adapted127(input)),"/127 finite quotient or rounding mode");++comparisons;
        }
        const uint32_t exceptional[]={0x7f800000,0xff800000,0x7fc01234,0xffc01234,0x7f800001,0xff800001};
        for(unsigned i=0;i<6;++i)Require(Same(Original127(FromBits(exceptional[i])),Adapted127(FromBits(exceptional[i]))),"exceptional quotient/payload");
        for(int value=-128;value<128;++value){
            const float input=(float)value;
            Require(Same(Original127(input),Smash360Fast::DivideNormalByte127(input,Shipyard::Fast3D::NearestRounding())),"normal byte quotient");
        }
    }
    _controlfp(originalMode,_MCW_RC);
    struct Light{struct{uint8_t col[3];}l;}lights[33]={};
    Smash360Fast::LightColorFloats cache={};
    for(unsigned iteration=0;iteration<8192;++iteration){
        const unsigned count=1+iteration%33;
        for(unsigned i=0;i<count;++i)for(unsigned c=0;c<3;++c){
            random=random*1664525u+1013904223u;
            if((random&7)==0)lights[i].l.col[c]=(uint8_t)(random>>24);
        }
        const float (*values)[3]=cache.Prepare(lights,count);
        for(unsigned i=0;i<count;++i)for(unsigned c=0;c<3;++c)
            Require(Same(values[i][c],(float)lights[i].l.col[c]),"light RGB value mutation/count/cache mismatch");
        // Reset/replaced RSP, including all-zero new colors, cannot reuse stale floats.
        if(iteration%64==0)memset(lights,0,sizeof(lights));
    }
    printf("PASS %u /127 finite quotients across four rounding modes, NaN/Inf fallback, byte normals; 8192 mutable RGB cache states\n",comparisons);
}
