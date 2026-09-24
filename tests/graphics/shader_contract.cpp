#include "shader_provider.h"
#include <cstdio>
#include <cstdlib>
#include <set>
#include <fstream>

static void Require(bool value,const char* why) {
    if(!value){std::fprintf(stderr,"FAIL %s\n",why);std::exit(1);}
}
int main(int argc,char** argv) {
    Fast::ShaderProgramKey key;
    std::set<Fast::ShaderProgramKey> keys;
    keys.insert(key);key.shaderId1=uint64_t(1)<<40;keys.insert(key);
    key.filteringMode=Fast::FILTER_LINEAR;keys.insert(key);
    key.srgbMode=true;keys.insert(key);
    Require(keys.size()==4,"secondary high bits, filtering and sRGB identities must remain distinct");
    Fast::PostProcessParams parameters;
    Require(parameters.srcFilterLinear && !parameters.srcUseMipmap && parameters.extraBindings==NULL,
            "generated API must preserve member initialization");
    const std::string generated=
        "cbuffer PerFrameCB : register(b0) { uint noise_frame; float noise_scale; }\n"
        "cbuffer PerDrawCB : register(b1) { struct { uint width; uint height; bool linear_filtering; } textures[2]; }\n"
        "Texture2D g_texture0 : register(t0);\nSamplerState g_sampler0 : register(s0);\n"
        "Texture2D g_texture1 : register(t1);\nSamplerState g_sampler1 : register(s1);\n"
        "Texture2D g_textureMask0 : register(t2);\nTexture2D g_textureMask1 : register(t3);\n"
        "Texture2D g_textureBlend0 : register(t4);\nTexture2D g_textureBlend1 : register(t5);\n"
        "float4 PSMain(float4 screenSpace : SV_Position) : SV_TARGET {\n"
        "float2 maskSize0; g_textureMask0.GetDimensions(maskSize0.x, maskSize0.y);\n"
        "float4 base = g_texture0.Sample(g_sampler0, float2(0.5, 0.5));\n"
        "float4 replacement = g_textureBlend0.Sample(g_sampler0, float2(0.5, 0.5));\n"
        "float mask = g_textureMask0.Sample(g_sampler0, float2(0.5, 0.5)).a;\n"
        "float4 texel = lerp(base, replacement, mask);\n"
        "if (texel.a > 0.19) texel.a = 1.0; else discard;\n"
        "return clamp(texel, 0.0, 1.0); }\n";
    std::string lowered,error;
    Require(Shipyard_LowerShader(generated,lowered,error),error.c_str());
    Require(lowered.find("sampler2D g_textureBlend1 : register(s5)")!=std::string::npos,"sixth binding retained");
    Require(lowered.find("float2 maskSize0 = bindingInfo[2].xy;")!=std::string::npos,"mask uses its actual dimensions");
    Require(lowered.find("float4 texel = lerp(base, replacement, mask);")!=std::string::npos,"combiner equation unchanged");
    Require(lowered.find("if (texel.a > 0.19) texel.a = 1.0; else clip(-1.0);")!=std::string::npos,"alpha threshold preserved");
    Require(lowered.find("tex2D(g_textureMask0,")!=std::string::npos,"mask sample binds its own Xenos slot");
    if(argc==2) {
        std::ofstream file(argv[1],std::ios::binary);file<<lowered;
        Require(file.good(),"write actual lowered fixture for native shader compiler");
    }
    Require(!Shipyard_LowerShader(generated+"Texture2D unexpected : register(t9);",lowered,error),"unknown shader resource must fail explicitly");
    Require(!Shipyard_LowerShader("@prism()",lowered,error),"unexpanded Prism must not be compiled as a fake shader");
    Require(!Shipyard_LowerShader("float4 PSMain():COLOR0{return 0;}",lowered,error),"missing generated contract must be rejected");
    std::puts("PASS full shader identity, generated defaults, six bindings, mask dimensions, equation/alpha preservation, unsupported-source rejection");
    return 0;
}
