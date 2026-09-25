"""Original-versus-selected postprocess state and settled-frame allocation test."""
import os
from pathlib import Path
import re
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT/'upstream/BattleShip/libultraship/src/fast/interpreter.cpp'
NEW=ROOT/'scratch/fast3d-xdk/overlay/libultraship/src/fast/interpreter.cpp'

def method(path,owner):
    text=path.read_text()
    start=text.index('void Interpreter::UpdatePostProcessFromCVars() {')
    end=text.index('\nvoid Interpreter::',start+1)
    result=text[start:end].replace('Interpreter::UpdatePostProcessFromCVars',owner+'::UpdatePostProcessFromCVars')
    return re.sub(r'(?m)^#line[^\n]*\n','',result)

def main():
    before=method(OLD,'OriginalInterpreter')
    after=method(NEW,'ProjectedInterpreter')
    assert 'const std::string name = nameCStr' in before
    assert 'const std::string name(stableName);' in after
    assert after.index('if (!nameChanged && !enabledChanged')<after.index('const std::string name(stableName);')
    code=r'''#include <string>
#include <vector>
#include <cstdlib>
#include <new>
#include <cstdio>
static int allocations=0;
void* operator new(size_t size){++allocations;void* p=std::malloc(size?size:1);if(!p)throw std::bad_alloc();return p;}
void operator delete(void* p) noexcept {std::free(p);}
void* operator new[](size_t size){++allocations;void* p=std::malloc(size?size:1);if(!p)throw std::bad_alloc();return p;}
void operator delete[](void* p) noexcept {std::free(p);}
#define CVAR_POSTPROCESS_ENABLED "enabled"
#define CVAR_POSTPROCESS_SHADER "shader"
#define SPDLOG_ERROR(...) do{}while(0)
namespace fmt {template<class A> std::string format(const char*,const A&){return "error";}}
struct Vars {
    int enabled=0; std::string name;
    int GetInteger(const char*,int){return enabled;}
    const char* GetString(const char*,const char*){return name.c_str();}
};
namespace Ship {struct Context {
    Vars vars;static Context* GetInstance(){static Context instance;return &instance;}
    Vars* GetConsoleVariables(){return &vars;}
};}
namespace Fast {
namespace internal {void SetPostProcessRuntimeError(const std::string&) {}}
struct PostProcessSlangShaderBundle {std::vector<int> artifacts,configs,diagnosticNames;};
struct PostProcessShaderBundle {std::vector<int> sources,configs,externalTextures;};
struct Chain {
    bool active=false;bool IsActive()const{return active;}
    void UnloadShader(void*){active=false;}
    bool LoadSlangPasses(void*,const std::vector<int>&,const std::vector<int>&,const std::vector<int>&){active=true;return true;}
    bool LoadPasses(void*,const std::vector<int>&,const std::vector<int>&,const std::vector<int>&){active=true;return true;}
};
static bool canLoad=true;
struct Base {
    void* mRapi=nullptr; Chain mPostProcessChain;
    bool mPostProcessEnabled=false,mPostProcessLoadFailed=false;
    std::string mPostProcessName;int loads=0;
    bool LoadPostProcessSlangShader(const std::string&,PostProcessSlangShaderBundle&){return false;}
    bool LoadPostProcessShader(const std::string&,PostProcessShaderBundle&){++loads;return canLoad;}
};
struct OriginalInterpreter:Base {void UpdatePostProcessFromCVars();};
struct ProjectedInterpreter:Base {void UpdatePostProcessFromCVars();};
''' + before + '\n' + after + r'''
template<class A,class B> bool equal(const A& a,const B& b){
    return a.mPostProcessEnabled==b.mPostProcessEnabled && a.mPostProcessLoadFailed==b.mPostProcessLoadFailed &&
           a.mPostProcessName==b.mPostProcessName && a.mPostProcessChain.active==b.mPostProcessChain.active && a.loads==b.loads;
}
}
int main(){
    using namespace Fast;
    OriginalInterpreter a;ProjectedInterpreter b;Vars& vars=Ship::Context::GetInstance()->vars;
    a.UpdatePostProcessFromCVars();b.UpdatePostProcessFromCVars();if(!equal(a,b))return 1;
    vars.name=std::string(256,'x');vars.enabled=1;
    a.UpdatePostProcessFromCVars();b.UpdatePostProcessFromCVars();if(!equal(a,b)||a.loads!=1)return 2;
    allocations=0;for(int i=0;i<20;++i)a.UpdatePostProcessFromCVars();int originalAllocations=allocations;
    allocations=0;for(int i=0;i<20;++i)b.UpdatePostProcessFromCVars();int projectedAllocations=allocations;
    if(!equal(a,b)||originalAllocations!=20||projectedAllocations!=0)return 3;
    canLoad=false;vars.name="missing";
    a.UpdatePostProcessFromCVars();b.UpdatePostProcessFromCVars();if(!equal(a,b)||!a.mPostProcessLoadFailed)return 4;
    int attempts=a.loads;
    for(int i=0;i<20;++i){a.UpdatePostProcessFromCVars();b.UpdatePostProcessFromCVars();}
    if(!equal(a,b)||a.loads!=attempts)return 5;
    vars.enabled=0;a.UpdatePostProcessFromCVars();b.UpdatePostProcessFromCVars();if(!equal(a,b))return 6;
    canLoad=true;vars.enabled=1;a.UpdatePostProcessFromCVars();b.UpdatePostProcessFromCVars();
    if(!equal(a,b)||!a.mPostProcessChain.active)return 7;
    std::printf("postprocess original/selected states PASS, settled allocations %d -> %d for 20 frames\n",originalAllocations,projectedAllocations);
    return 0;
}
'''
    vswhere=Path(os.environ['ProgramFiles(x86)'])/'Microsoft Visual Studio/Installer/vswhere.exe'
    install=subprocess.check_output([str(vswhere),'-latest','-products','*','-requires',
        'Microsoft.VisualStudio.Component.VC.Tools.x86.x64','-property','installationPath'],text=True).strip()
    with tempfile.TemporaryDirectory(prefix='smash-postprocess-') as folder:
        out=Path(folder);source=out/'contract.cpp';source.write_text(code)
        batch=out/'compile.cmd';batch.write_text(
            '@echo off\ncall "'+install+'/VC/Auxiliary/Build/vcvars64.bat" >nul\n'
            'if errorlevel 1 exit /b 1\ncl /nologo /EHsc /MT "'+str(source)+
            '" /Fe"'+str(out/'contract.exe')+'"\nexit /b %errorlevel%\n')
        built=subprocess.run([os.environ['ComSpec'],'/d','/c',str(batch)],cwd=out,capture_output=True,text=True)
        assert built.returncode==0,built.stdout+built.stderr
        result=subprocess.run([str(out/'contract.exe')],cwd=out,capture_output=True,text=True)
        assert result.returncode==0,result.stdout+result.stderr
        print(result.stdout.strip())

if __name__=='__main__':main()
