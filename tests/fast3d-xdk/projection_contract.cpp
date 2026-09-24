#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <math.h>
#include <float.h>
#include "fast3d/cull_projection.h"
struct Vertex { float x,y,z,w; };
struct Rsp { unsigned geometry_mode,extra_geometry_mode; };
struct Dimensions { unsigned width,height; };
namespace UcodeHandlers { enum { ucode_f3dex2=1 }; }
enum { G_EX_INVERT_CULLING=1 };
static Smash360Fast::CullProjection sXboxCullProjection[68];
static unsigned char gIndices[3];
// EXTRACTED_FUNCTIONS
static uint32_t state=0x8643ace1;
static uint32_t Next() {state=state*1664525U+1013904223U;return state;}
static float Bits(uint32_t bits) {float v;memcpy(&v,&bits,4);return v;}
static uint32_t Bits(float v) {uint32_t b;memcpy(&b,&v,4);return b;}
int main() {
    // Identical source bits can divide differently after an FPSCR RN change.
    // The cache must not publish a value computed under the old mode.
    {
        Smash360Fast::CullProjection projection={};
        float numerator=Bits(0x3f800000U), denominator=Bits(0x40400000U);
        const unsigned saved=_controlfp(0,0)&_MCW_RC;
        const unsigned rounding[]={_RC_NEAR,_RC_DOWN,_RC_UP,_RC_CHOP,_RC_NEAR};
        for(unsigned i=0;i<5;i++) {
            _controlfp(rounding[i],_MCW_RC);
            volatile float lhs=numerator, rhs=denominator;
            volatile float expected=lhs/rhs;
            projection.Load(numerator,numerator,denominator);
            if(Bits(projection.x)!=Bits(expected) || Bits(projection.y)!=Bits(expected)) {
                printf("rounding-key mismatch mode %u expected %08x actual %08x\n",
                       i,Bits(expected),Bits(projection.x));
                _controlfp(saved,_MCW_RC);
                return 4;
            }
        }
        _controlfp(saved,_MCW_RC);
    }
    const unsigned savedMode=_controlfp(0,0)&_MCW_RC;
    const unsigned modes[]={_RC_NEAR,_RC_DOWN,_RC_UP,_RC_CHOP};
    Vertex v[68]={};
    const unsigned char indexCases[][3]={{0,1,2},{0,0,1},{64,65,67},{2,1,0},{67,67,67}};
    const uint32_t edges[]={0,0x80000000U,0x3f800000U,0xbf800000U,0x38d1b716U,
        0x38d1b717U,0x38d1b718U,0xb8d1b717U,0x7f800000U,0xff800000U,
        0x7fc01234U,0x7f801234U,1,0x80000001U,0x7f7fffffU};
    float totalA=0,totalB=0;
    for(unsigned n=0;n<100000;n++) {
        // Every consecutive triangle can reuse an identical vertex key under
        // a different thread rounding mode, including the area reread.
        _controlfp(modes[n%4],_MCW_RC);
        memcpy(gIndices,indexCases[(n/3375)%5],3);
        // Repeated triangles, partial slot reloads, rectangle coordinates and
        // adversarial values all pass through the same persistent cache slots.
        for(unsigned i=0;i<3;i++) if(n%4!=1) {
            Vertex& vertex=v[gIndices[i]];
            if(n<3375) {unsigned k=(n/(i==0?1:i==1?15:225))%15;
                vertex.x=Bits(edges[k]);vertex.y=Bits(edges[(k+5)%15]);vertex.w=Bits(edges[(k+9)%15]);
            } else if(n%11==0) {vertex.x=i==0?-1.0f:1.0f;vertex.y=i==2?1.0f:-1.0f;vertex.w=1;}
            else if(n%3 || i==1) {vertex.x=(int)(Next()%20001)-10000.0f;
                vertex.y=(int)(Next()%20001)-10000.0f;vertex.w=((int)(Next()%20001)-10000.0f)*0.03125f;}
        }
        for(unsigned mode=0;mode<4;mode++) for(unsigned invert=0;invert<2;invert++) for(int ucode=0;ucode<2;ucode++) {
            Rsp rsp={mode,invert};
            if(original_cull(v,rsp,ucode)!=cached_cull(v,rsp,ucode)) {printf("cull mismatch %u\n",n);return 1;}
        }
        // A resource/backend callback can occur between cull and area reads.
        if(n%7==0) v[gIndices[0]].x=-v[gIndices[0]].x;
        float a=0,b=0;original_area(v,a);cached_area(v,b);
        if(Bits(a)!=Bits(b)) {printf("area mismatch %u %08x %08x\n",n,Bits(a),Bits(b));return 2;}
        if(n>=3375) {original_area(v,totalA);cached_area(v,totalB);
            if(Bits(totalA)!=Bits(totalB)) {printf("accumulation mismatch %u\n",n);return 3;}}
    }
    _controlfp(savedMode,_MCW_RC);
    puts("five identical-key rounding transitions, 1600000 cull and 196625 area/accumulation comparisons across four rounding modes passed");return 0;
}
