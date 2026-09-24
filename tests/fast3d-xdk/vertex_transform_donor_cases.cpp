// Adapted from current SoH360 bringup_tests.cpp; original test arithmetic,
// random domains and exceptional cases retained. Smash adds CLIP_NEAR=16
// expectations and explicitly checks all clip padding bytes.
#include "fast3d/clip_quantize.h"
#include "fast3d/vertex_transform.h"
#include <stdint.h>
#include <cstring>
#include <cstdio>
#include <cstdlib>
#include <cmath>
typedef short s16;
struct Vtx { struct { s16 ob[3]; unsigned char rest[10]; } v; };
static void Expect(bool ok,const char* message) { if(!ok){fprintf(stderr,"FAIL %s\n",message);exit(1);} }
#define SoH_Log printf
static void TestVertexTransform() {
    __declspec(align(16)) unsigned char vertexBytes[64*sizeof(Vtx)+16];
    Vtx* vertices=(Vtx*)(vertexBytes+8); // Deliberately not vector aligned.
    __declspec(align(16)) float matrixStorage[17],output[64][4],aspectOutput[64][4];
    __declspec(align(16)) unsigned char stridedOutput[64][32];
    float (*matrix)[4]=(float (*)[4])(matrixStorage+1);
    uint32_t random=0x61c88647;
    for(unsigned iteration=0;iteration<512;++iteration) {
        for(unsigned i=0;i<64;++i)for(unsigned c=0;c<3;++c) {
            random=random*1664525u+1013904223u;vertices[i].v.ob[c]=(s16)(random>>16);
        }
        bool normalAspect=true;
        for(unsigned i=0;i<16;++i) {
            random=random*1664525u+1013904223u;
            uint32_t bits=(random&0x807fffff)|((24+(random%212))<<23);
            if((iteration+i)%7==0)bits&=0x80000000; // Include both zero signs.
            if((bits&0x7fffffff)!=0 && (bits&0x7fffffff)<0x12800000)normalAspect=false;
            memcpy(&matrix[i/4][i%4],&bits,4);
        }
        Expect(Shipyard::Fast3D::TransformPositions(vertices,64,matrix,output),"VMX supported matrix range");
        memset(stridedOutput,0x5a,sizeof(stridedOutput));
        Expect(Shipyard::Fast3D::TransformPositions(vertices,64,matrix,stridedOutput,false,32),"VMX direct vertex destination");
        for(unsigned vertex=0;vertex<64;++vertex) {
            Expect(memcmp(stridedOutput[vertex],output[vertex],16)==0,"direct transform preserves all coordinates");
            for(unsigned byte=16;byte<32;++byte)
                Expect(stridedOutput[vertex][byte]==0x5a,"direct transform preserves UV/color/clip fields");
        }
        memset(aspectOutput,0x5a,sizeof(aspectOutput));
        Expect(Shipyard::Fast3D::TransformPositions(vertices,64,matrix,aspectOutput,true)==normalAspect,"normal aspect coefficient guard");
        if(normalAspect)Expect(memcmp(output,aspectOutput,sizeof(output))==0,"normal aspect transform preserves coordinates");
        else for(unsigned byte=0;byte<sizeof(aspectOutput);++byte)
            Expect(((unsigned char*)aspectOutput)[byte]==0x5a,"normal aspect fallback writes nothing");
        for(unsigned i=0;i<64;++i)for(unsigned c=0;c<4;++c) {
            volatile float x=(float)vertices[i].v.ob[0],y=(float)vertices[i].v.ob[1],z=(float)vertices[i].v.ob[2];
            const float expected=x*matrix[0][c]+y*matrix[1][c]+z*matrix[2][c]+matrix[3][c];
            Expect(memcmp(&expected,&output[i][c],4)==0,"VMX vertex result differs from ordered scalar arithmetic");
        }
    }
    const uint32_t fallback[]={1,0x00800000,0x0bffffff,0x76000000,0x7f800000,0xff800000,0x7fc00000};
    for(unsigned i=0;i<sizeof(fallback)/sizeof(fallback[0]);++i)for(unsigned element=0;element<16;++element) {
        memset(matrix,0,64);memcpy(&matrix[element/4][element%4],&fallback[i],4);
        memset(output,0x5a,sizeof(output));
        Expect(!Shipyard::Fast3D::TransformPositions(vertices,64,matrix,output),"VMX exceptional matrix scalar fallback");
        memset(stridedOutput,0x5a,sizeof(stridedOutput));
        Expect(!Shipyard::Fast3D::TransformPositions(vertices,64,matrix,stridedOutput,true,32),"VMX direct destination exceptional fallback");
        for(unsigned byte=0;byte<sizeof(stridedOutput);++byte)
            Expect(((unsigned char*)stridedOutput)[byte]==0x5a,"direct transform fallback writes nothing");
        for(unsigned byte=0;byte<sizeof(output);++byte)
            Expect(((unsigned char*)output)[byte]==0x5a,"VMX transform fallback writes nothing");
    }
    SoH_Log("PASS VMX vertex transform: 131072 coordinates bit-identical, unaligned input and exceptional scalar fallback");
}

static void TestMatrixQuantization() {
    __declspec(align(16)) float input[4][4],output[4][4];
    const uint32_t edges[]={0,0x80000000,1,0x80000001,0x007fffff,0x807fffff,
        0x37800000,0xb7800000,0x377fffff,0xb77fffff,0x37800001,0xb7800001,
        0x46ffffff,0xc6ffffff,0xc7000000};
    uint32_t random=0x148ecc37;unsigned compared=0;
    for(unsigned batch=0;batch<8192;++batch) {
        for(unsigned i=0;i<16;++i) {
            random=random*1664525u+1013904223u;
            uint32_t bits=random;
            if((bits&0x7fffffff)>=0x47000000)bits=(bits&0x807fffff)|0x46000000;
            if(batch<15)bits=edges[(batch+i)%15];
            memcpy(&input[i/4][i%4],&bits,4);
        }
        Expect(Shipyard::Fast3D::QuantizeMatrix(input,output),"VMX matrix fixed point valid input");
        for(unsigned i=0;i<16;++i) {
            volatile float scaled=input[i/4][i%4]*65536.0f;
            volatile int32_t fixed=(int32_t)scaled;
            float expected=fixed*(1.0f/65536.0f);
            Expect(memcmp(&expected,&output[i/4][i%4],4)==0,"VMX matrix quantization bit identity");
            ++compared;
        }
    }
    const uint32_t exceptional[]={0x47000000,0xc7000001,0x7f800000,0xff800000,0x7fc00000};
    for(unsigned e=0;e<5;++e)for(unsigned i=0;i<16;++i) {
        memset(input,0,sizeof(input));memset(output,0x5a,sizeof(output));
        memcpy(&input[i/4][i%4],&exceptional[e],4);
        Expect(!Shipyard::Fast3D::QuantizeMatrix(input,output),"VMX matrix exceptional scalar fallback");
        for(unsigned c=0;c<64;++c)Expect(((unsigned char*)output)[c]==0x5a,"VMX matrix fallback writes nothing");
    }
    SoH_Log("PASS VMX matrix quantization: %u bit-exact elements plus complete exceptional fallback",compared);
}

static void TestVectorClip() {
    struct ClipVertex {float p[4];uint32_t untouched[3];uint8_t flags,padding[3];};
    static_assert(sizeof(ClipVertex)==32,"clip test layout");
    ClipVertex vertices[64];uint8_t expected[64];
    __declspec(align(16)) unsigned char finite_storage[64*sizeof(ClipVertex)+16];
    uint32_t random=0x62c701a1;
    const uint32_t edges[]={0,0x80000000,1,0x80000001,0x007fffff,0x807fffff,
        0x00800000,0x80800000,0x3f7fffff,0xbf7fffff,0x3f800000,0xbf800000,
        0x3f800001,0xbf800001,0x7f7fffff,0xff7fffff,0x7f800000,0xff800000,
        0x7fc00000,0xffc01234,0x7f800001,0xff800001};
    unsigned compared=0,finiteCompared=0;
    for(unsigned batch=0;batch<4096;++batch) {
        // Odd-size batches exercise tail preservation; below tests all four
        // naturally float-aligned offsets within a VMX alignment boundary.
        unsigned count=1+batch%64;
        memset(vertices,0x5a,sizeof(vertices));
        for(unsigned i=0;i<count;++i) {
            for(unsigned c=0;c<4;++c) {
                random=random*1664525u+1013904223u;
                uint32_t bits=batch<88?edges[(batch+i+c*7)%22]:random;
                memcpy(&vertices[i].p[c],&bits,4);
            }
            if(batch%4==0)vertices[i].p[0]=vertices[i].p[3];
            if(batch%4==1)vertices[i].p[1]=-vertices[i].p[3];
            if(batch%4==2)vertices[i].p[2]=vertices[i].p[3];
            if(batch<4) {
                // Finite VMX comparisons flush subnormals. Their signs must
                // still affect clipping when w is either sign of zero.
                uint32_t x=(batch&1)?0x80000001u:1u,w=(batch&2)?0x80000000u:0u;
                memcpy(&vertices[i].p[0],&x,4);memcpy(&vertices[i].p[3],&w,4);
                vertices[i].p[1]=0.0f;vertices[i].p[2]=1.0f;
            }
            volatile float x=vertices[i].p[0],y=vertices[i].p[1],z=vertices[i].p[2],w=vertices[i].p[3];
            uint8_t flags=0;
            if(x<-w)flags|=1;if(x>w)flags|=2;if(y<-w)flags|=4;if(y>w)flags|=8;if(z<-w)flags|=16;if(z>w)flags|=32;
            expected[i]=flags;
        }
        Shipyard::Fast3D::ClipVertices(vertices,count,true);
        for(unsigned i=0;i<count;++i) {
            Expect(vertices[i].flags==expected[i],"VMX clip IEEE strict comparison identity");
            for(unsigned c=0;c<3;++c)Expect(vertices[i].untouched[c]==0x5a5a5a5a,"VMX clip preserves UV and color");
            for(unsigned c=0;c<3;++c)Expect(vertices[i].padding[c]==0x5a,"clip preserves padding");
            ++compared;
        }
        Shipyard::Fast3D::ClipVertices(vertices,count,false);
        for(unsigned i=0;i<count;++i)
            Expect(vertices[i].flags==(uint8_t)(expected[i]&~16u),"9.x near-plane policy changed clip result");
        if(count<64)Expect(vertices[count].flags==0x5a,"VMX clip batch bound");
        bool finiteBatch=true;
        for(unsigned i=0;i<count;++i)for(unsigned c=0;c<4;++c) {
            uint32_t bits;memcpy(&bits,&vertices[i].p[c],4);bits&=0x7fffffff;
            if(bits>=0x7f800000 || (c==3 && bits && bits<0x00800000))finiteBatch=false;
        }
        if(finiteBatch) {
            for(unsigned offset=0;offset<16;offset+=4) {
                ClipVertex* finite_vertices=(ClipVertex*)(finite_storage+offset);
                memcpy(finite_vertices,vertices,sizeof(vertices));
                for(unsigned i=0;i<count;++i)finite_vertices[i].flags=0x5a;
                Shipyard::Fast3D::ClipFiniteVertices(finite_vertices,count,true);
                for(unsigned i=0;i<count;++i) {
                    Expect(finite_vertices[i].flags==expected[i],"finite VMX clip agrees with original comparisons at every alignment");
                    for(unsigned c=0;c<3;++c)Expect(finite_vertices[i].untouched[c]==0x5a5a5a5a,"finite clip preserves UV and color");
                    for(unsigned c=0;c<3;++c)Expect(finite_vertices[i].padding[c]==0x5a,"finite clip preserves padding");
                    ++finiteCompared;
                }
                Shipyard::Fast3D::ClipFiniteVertices(finite_vertices,count,false);
                for(unsigned i=0;i<count;++i)
                    Expect(finite_vertices[i].flags==(uint8_t)(expected[i]&~16u),"9.x finite near-plane policy changed clip result");
                if(count<64)Expect(finite_vertices[count].flags==0x5a,"finite clip batch bound");
            }
        }
    }
    SoH_Log("PASS VMX clip: %u exact results, all finite exponents, signed zero, infinities, NaNs and batch bounds",compared);
    SoH_Log("PASS finite VMX clip: %u exact results including subnormal coordinates at signed-zero w",finiteCompared);
}
int main(){TestVertexTransform();TestMatrixQuantization();TestVectorClip();}
