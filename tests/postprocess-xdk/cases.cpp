#include "fast/postprocess/PostProcessPreset.h"
#include "fast/postprocess/PostProcessGlslNormalizer.h"
#include "fast/postprocess/PostProcessSlangSource.h"
#include "fast/postprocess/PostProcessSlangTranspiler.h"
#include "fast/postprocess/PostProcessTranspiler.h"
#include "fast/postprocess/PostProcessChain.h"
#include "fast/postprocess/PostProcessSourceLoader.h"
#include "fast/debug/GfxDebugger.h"
#include <cstdio>
#include <cstring>
#include <fstream>
#include <sstream>
#include <stdexcept>
static void require(bool value){if(!value)throw std::runtime_error("postprocess actual-source contract failed");}
static void printFloat(float value){unsigned bits;std::memcpy(&bits,&value,4);std::printf("%08x ",bits);}
int main(int argc,char** argv){
    const char* presets[]={"", "shaders=0\n", "shaders=2\nshader0=a.glsl\n",
        "shaders=2\nshader0=a.glsl\nshader1=b.glsl\nfilter_linear0=true\nscale_type1=viewport\nscale_x1=0.5\nscale_y1=1.25\nwrap_mode0=mirrored_repeat\nalias0=First\nfloat_framebuffer0=true\ntextures=\"Lut;Mask\"\nLut=lut.png\nMask=mask.png\nLut_linear=false\nframe_count_mod0=7\nGain=1.5\n",
        "shaders=1\nshader0=x.slang\nscale_type0=invalid\nscale0=2\nValue=invalid\nGain=0.125\n",
        "shaders=3\nshader0=a\nshader2=c\n", "shaders=1\nshader0=\"a name.glsl\" # comment\n"};
    for(int dialect=0;dialect<2;++dialect)for(unsigned i=0;i<sizeof(presets)/sizeof(*presets);++i){
        Fast::PostProcessPreset parsed;std::string error;
        bool ok=dialect?Fast::ParseSlangPreset(presets[i],"base",parsed,error):Fast::ParsePostProcessPreset(presets[i],"base",parsed,error);
        std::printf("preset %d %u %d %s\n",dialect,i,ok,error.c_str());if(!ok)continue;
        std::printf("flavor %d passes %u textures %u\n",static_cast<int>(parsed.flavor),static_cast<unsigned>(parsed.passes.size()),static_cast<unsigned>(parsed.textures.size()));
        for(size_t j=0;j<parsed.passes.size();++j){const Fast::PostProcessPresetPass& p=parsed.passes[j];
            std::printf("%s %d %d %d %d %d %d %d %d %s ",p.shaderPath.c_str(),p.filterLinear,static_cast<int>(p.wrapMode),static_cast<int>(p.scaleTypeX),static_cast<int>(p.scaleTypeY),p.srgbFramebuffer,p.floatFramebuffer,p.mipmapInput,p.frameCountMod,p.alias.c_str());printFloat(p.scaleX);printFloat(p.scaleY);std::puts("");}
        for(size_t j=0;j<parsed.textures.size();++j){const Fast::PostProcessPresetTexture& t=parsed.textures[j];std::printf("texture %s %s %d %d %d\n",t.name.c_str(),t.path.c_str(),t.filterLinear,static_cast<int>(t.wrapMode),t.mipmap);}
        for(std::map<std::string,float>::const_iterator j=parsed.parameterOverrides.begin();j!=parsed.parameterOverrides.end();++j){std::printf("parameter %s ",j->first.c_str());printFloat(j->second);std::puts("");}
    }
    const char* slang[]={"", "#pragma stage vertex\nvoid main() {}\n",
        "#version 450\n#pragma name Demo\n#pragma parameter GAIN \"Gain\" 1.0 0.0 2.0 0.125\n#pragma stage vertex\nvoid main(){gl_Position=vec4(0.0);}\n#pragma stage fragment\nvoid main(){}\n",
        "#pragma parameter GAIN \"Gain\" bad 0 1\n#pragma stage vertex\nx\n#pragma stage fragment\ny\n",
        "#pragma stage unknown\nx\n", "#pragma stage fragment\nf\n#pragma stage vertex\nv\n"};
    for(unsigned i=0;i<sizeof(slang)/sizeof(*slang);++i){Fast::PostProcessSlangSource parsed;std::string error;bool ok=Fast::ParseSlangSource(slang[i],parsed,error);std::printf("slang %u %d %s\n",i,ok,error.c_str());if(!ok)continue;std::printf("name %s format %s\nvertex\n%sfragment\n%s",parsed.name.c_str(),parsed.format.c_str(),parsed.vertex.c_str(),parsed.fragment.c_str());
        for(size_t j=0;j<parsed.parameters.size();++j){const Fast::PostProcessSlangParameter& p=parsed.parameters[j];std::printf("p %s ",p.name.c_str());printFloat(p.defaultValue);printFloat(p.minValue);printFloat(p.maxValue);printFloat(p.step);std::puts("");}
        Fast::PostProcessSlangArtifact artifact;require(!Fast::PostProcessSlangTranspiler::Compile(parsed,artifact,error));std::printf("slang disabled %s\n",error.c_str());
    }
    const char* glsl[]={"", "#version 120\nuniform sampler2D Texture;\nvarying vec2 TEX0;\nvoid main(){gl_FragColor=texture2D(Texture,TEX0);}\n",
        "#if defined(VERTEX)\nvoid main(){}\n#elif defined(FRAGMENT)\nuniform sampler2D Source;\nvoid main(){FragColor=texture(Source,vTexCoord);}\n#endif\n"};
    std::vector<std::string> aliases;aliases.push_back("First");aliases.push_back("Lut");
    for(unsigned i=0;i<sizeof(glsl)/sizeof(*glsl);++i){std::printf("normalized %u\n%s\n",i,Fast::NormalizeUserGlsl(glsl[i],aliases).c_str());}
    for(int i=1;i<argc;++i){std::ifstream input(argv[i],std::ios::binary);require(input.is_open());std::ostringstream text;text<<input.rdbuf();std::printf("file %d\n%s\n",i,Fast::NormalizeUserGlsl(text.str()).c_str());}
    Fast::PostProcessSource source;source.glsl="unchanged";std::string error;
    require(!Fast::PostProcessTranspiler::SynthesizeMissing(source,error)&&source.glsl=="unchanged");std::printf("disabled %s\n",error.c_str());
    Fast::PostProcessChain chain;chain.Init(nullptr);chain.OnResize(nullptr,640,480);require(!chain.IsActive()&&chain.GetLoadedPassCount()==0&&std::strcmp(chain.GetLoadedFlavor(),"none")==0);
    Fast::PostProcessParams params=Fast::PostProcessParams();require(chain.Run(nullptr,17,params)==17);
    require(!Fast::GetPostProcessRuntimeDiagnostics().active);
    Fast::internal::SetPostProcessRuntimeError("expected failure");Fast::internal::SetPostProcessRuntimeResolvedPath("selected/path");
    require(Fast::GetPostProcessRuntimeDiagnostics().resolvedPath=="selected/path");
    Fast::internal::SetPostProcessRuntimeInactive();require(Fast::GetPostProcessRuntimeDiagnostics().lastError=="expected failure"&&Fast::GetPostProcessRuntimeDiagnostics().resolvedPath.empty());
    Fast::internal::SetPostProcessRuntimeActive("actual","glsl",3,"loaded/path");
    Fast::PostProcessRuntimeDiagnostics diag=Fast::GetPostProcessRuntimeDiagnostics();require(diag.active&&diag.name=="actual"&&diag.flavor=="glsl"&&diag.passCount==3&&diag.resolvedPath=="loaded/path"&&diag.lastError.empty());
    Fast::internal::SetPostProcessRuntimeInactive();diag=Fast::GetPostProcessRuntimeDiagnostics();require(!diag.active&&diag.name.empty()&&diag.flavor.empty()&&diag.passCount==0);
    Fast::GfxDebugger debugger;require(!debugger.IsDebugging()&&!debugger.IsDebuggingRequested());debugger.RequestDebugging();require(debugger.IsDebuggingRequested());
    Fast::F3DGfx* first=reinterpret_cast<Fast::F3DGfx*>(static_cast<uintptr_t>(0x1000));Fast::F3DGfx* second=reinterpret_cast<Fast::F3DGfx*>(static_cast<uintptr_t>(0x2000));
    debugger.DebugDisplayList(first);require(debugger.IsDebugging()&&!debugger.IsDebuggingRequested()&&debugger.GetDisplayList()==first);
    std::vector<const Fast::F3DGfx*> path(1,first);require(debugger.HasBreakPoint(path));path.push_back(second);require(!debugger.HasBreakPoint(path));debugger.SetBreakPoint(path);require(debugger.HasBreakPoint(path));debugger.ResumeGame();require(!debugger.IsDebugging()&&debugger.GetDisplayList()==nullptr);
    std::puts("inactive chain passthrough and debugger transitions passed");return 0;
}
