#include "shader_provider.h"
#include "prism_shader_builder.h"
#include "prism/processor.h"
#include "shader_constants.h"
#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>
#ifdef PRISM_ADAPTED
namespace values = xbox_compat;
#else
namespace values = std;
#endif

static std::string templateSource;
static bool missingResource=false;
static std::vector<std::string> loaded;
void TestPrismRangeContract();

// Test-only resource provider reads the actual pinned template from argv.
// Production supplies its real LUS resource-loader implementation.
bool Smash360_LoadShaderResource(const std::string& path,std::string& output) {
    loaded.push_back(path);
    if(missingResource)return false;
    if(path=="shaders/directx/default.shader.hlsl"){output=templateSource;return true;}
    return false;
}
namespace Fast { const char* gfx_get_shader(int16_t id) {
    return id==7?"test/custom":nullptr;
} }

static void require(bool value,const char* message) {if(!value)throw std::runtime_error(message);}
static void write(const std::string& path,const std::string& value) {
    std::ofstream file(path.c_str(),std::ios::binary);file<<value;
    require(file.good(),"cannot write differential output");
}
static values::optional<std::string> includes(const std::string& path) {
    if(path=="test/include")return std::string("@prism(type='test')\n\nINCLUDED @{answer}\n");
    return values::nullopt;
}
static std::string process(const std::string& source,bool include) {
    prism::Processor proc;prism::ContextItems context;
    context["answer"]=42;proc.populate(context);
    if(include)proc.bind_include_loader(includes);
    proc.load(source);return proc.process();
}
static void parserTests(std::ostream& log) {
    const char* cases[]={
        "", "plain text\n", "@prism(name='missing type')\nbody\n",
        "@prism(type='test')\n\n@{missing}\n",
        "@prism(type='test')\n\n@if(answer > 0)\nYES\n@end\n",
        "@prism(type='test')\n\n@if(answer == 42)\nYES\n@else\nNO\n@end\n",
        "@prism(type='test')\n\n@for(i in 0..3)\n@{i}\n@end\n",
        "@prism(type='test')\n\n@include(\"test/include\")\nDONE\n",
        "@prism(type='test')\n\n@include(\"missing/include\")\nDONE\n",
        "@prism(type='test')\n\n@{(answer}\n"
    };
    for(size_t i=0;i<sizeof(cases)/sizeof(*cases);++i){
        log<<"case "<<i<<"\n";
        try {log<<process(cases[i],true);}
        catch(const std::exception& error){log<<"exception "<<error.what()<<"\n";}
    }
    prism::Processor proc;prism::ContextItems reserved;reserved["@if"]=1;
    try {proc.populate(reserved);require(false,"reserved keyword accepted");}
    catch(const prism::SyntaxError& error){log<<"reserved "<<error.what()<<"\n";}
    prism::RuntimeContext initial;
    require(initial.scope==prism::ScopeType::None && !initial.skipUntilEnd,"lost member defaults");
    // The generated builder explicitly casts these bounded anonymous-enum
    // constants because the XDK value helper has no general enum trait.
#ifdef PRISM_ADAPTED
    prism::ContextTypes integer(static_cast<int>(SHADER_INPUT_7));
#else
    prism::ContextTypes integer(SHADER_INPUT_7);
#endif
    require(values::holds_alternative<int>(integer)&&values::get<int>(integer)==7,"enum selection mismatch");
    prism::ContextTypes boolean(true);
    require(values::holds_alternative<int>(boolean)&&values::get<int>(boolean)==1,"bool selection mismatch");
    std::shared_ptr<prism::Node> parent;
    prism::NodeType root = prism::RootNode();
    prism::Node node(root,parent);
    require(node.depth==0,"lost Node depth default");
}

int main(int argc,char** argv) {
    try {
        require(argc==3,"template and output directory required");
        std::ifstream source(argv[1],std::ios::binary);std::ostringstream contents;contents<<source.rdbuf();
        require(source.good()&&!contents.str().empty(),"cannot read actual template");templateSource=contents.str();
        std::ostringstream log;parserTests(log);TestPrismRangeContract();
        // Real decoded combiner modes: vertex input, texture, multiply, mix,
        // general equation, separate alpha, two-cycle combined and noise.
        const uint64_t combiners[]={0x10001000ULL,0x80008000ULL,0x01080108ULL,
            0xA1A8A1A8ULL,0xA218A218ULL,0x90008000ULL,
            0xE1EAE1EAULL,0xD1DAD1DA80008000ULL,0xA278A278ULL};
        const uint64_t options[]={0,1,3,5,9,17,33,65,129,0xF01,0xF001,0xFF1F,0xFFFF};
        unsigned count=0;
        for(size_t c=0;c<sizeof(combiners)/sizeof(*combiners);++c)
            for(size_t o=0;o<sizeof(options)/sizeof(*options);++o)
                for(int filter=0;filter<3;++filter)
                    for(int srgb=0;srgb<2;++srgb){
                        Fast::ShaderProgramKey key;key.shaderId0=combiners[c];
                        key.shaderId1=0xFFFF0000ULL|options[o];
                        key.filteringMode=static_cast<Fast::FilteringMode>(filter);key.srgbMode=srgb!=0;
                        CCFeatures features;size_t floats=999;std::string hlsl,error,lowered;
                        require(Shipyard_BuildFast3DShader(key,features,floats,hlsl,error),error.c_str());
                        require(hlsl.find('@')==std::string::npos,"unexpanded Prism token");
                        require(Shipyard_LowerShader(hlsl,lowered,error),error.c_str());
                        if(features.clamp[0][0]&&features.usedTextures[0]) {
                            require(lowered.find(", float texClampS0 : TEXCOORD11")!=std::string::npos,"vertex clamp input changed");
                            require(lowered.find("result.texClampPacked.x = texClampS0;")!=std::string::npos,"clamp not packed by VS");
                            require(lowered.find("input.texClampPacked.x")!=std::string::npos,"clamp not unpacked by PS");
                        }
                        std::ostringstream filename;filename<<argv[2]<<"/shader-"<<count;
                        write(filename.str()+".hlsl",hlsl);write(filename.str()+"-xenos.hlsl",lowered);
                        log<<"shader "<<count<<" "<<std::hex<<key.shaderId0<<" "<<key.shaderId1<<std::dec
                           <<" "<<filter<<" "<<srgb<<" "<<floats<<"\n";
                        ++count;
                    }
        Fast::ShaderProgramKey key;key.shaderId1=7ULL<<16;
        CCFeatures features;size_t floats;std::string hlsl,error;
        loaded.clear();require(Shipyard_BuildFast3DShader(key,features,floats,hlsl,error),error.c_str());
        require(loaded.size()==1&&loaded[0]=="shaders/directx/default.shader.hlsl","pinned resource behavior changed");
        log<<"custom-key-default-resource "<<loaded[0]<<"\n";
        missingResource=true;floats=123;hlsl="previous";
        require(!Shipyard_BuildFast3DShader(key,features,floats,hlsl,error)&&floats==0&&hlsl.empty()&&!error.empty(),"missing resource did not fail");
        log<<"missing-resource "<<error<<"\n";
        write(std::string(argv[2])+"/results.txt",log.str());
        std::cout<<"Prism generated "<<count<<" real shader permutations; parser/default/error checks passed\n";
        return 0;
    } catch(const std::exception& error){std::cerr<<error.what()<<"\n";return 1;}
}
