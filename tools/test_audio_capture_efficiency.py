"""Verify default WAV I/O removal and opted-in RIFX byte parity."""
import os
from pathlib import Path
import re
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'scratch/port-xdk/composed-overlay/port/audio/audio_playback.cpp'

def main():
    text=SOURCE.read_text()
    start=text.index('static FILE *sWavFile = nullptr;')
    end=text.index('static int16_t clampS16FromDouble(',start)
    selected=re.sub(r'(?m)^#line[^\n]*\n','',text[start:end])
    guard='    const char* capture = XboxEnv_Get("SSB64_AUDIO_WAV_DUMP");\n    if (capture == nullptr || capture[0] != \'1\') return;\n'
    assert selected.count(guard)==1
    assert selected.count('cache:\\\\ssb64_dump.rifx')==2
    selected=selected.replace('cache:\\\\ssb64_dump.rifx','capture.rifx')
    previous=selected.replace(guard,'')
    prefix=r'''#include <cstdio>
#include <cstdint>
#include <vector>
#include <cstring>
static bool captureEnabled=false;
const char* XboxEnv_Get(const char*){return captureEnabled?"1":nullptr;}
void port_log(const char*,...){ }
'''
    suffix=r'''
int main(int argc,char**){
    captureEnabled=argc>1;
    wavMaybeOpen();
    std::vector<unsigned char> pcm(kWavMaxBytes);
    for(size_t i=0;i<pcm.size();++i)pcm[i]=(unsigned char)(i*17u+3u);
    wavAppend(pcm.data(),pcm.size());
    FILE* file=std::fopen("capture.rifx","rb");
    if(!captureEnabled){if(file)return 1;return 0;}
    if(!file)return 2;
    std::fseek(file,0,SEEK_END);long length=std::ftell(file);
    if(length!=44+(long)kWavMaxBytes)return 3;
    std::fseek(file,0,SEEK_SET);char header[4];std::fread(header,1,4,file);
    if(std::memcmp(header,"RIFX",4)!=0)return 4;
    std::fseek(file,44,SEEK_SET);unsigned char first[4];std::fread(first,1,4,file);
    if(std::memcmp(first,pcm.data(),4)!=0)return 5;
    std::fclose(file);return 0;
}
'''
    vswhere=Path(os.environ['ProgramFiles(x86)'])/'Microsoft Visual Studio/Installer/vswhere.exe'
    install=subprocess.check_output([str(vswhere),'-latest','-products','*','-requires',
        'Microsoft.VisualStudio.Component.VC.Tools.x86.x64','-property','installationPath'],text=True).strip()
    with tempfile.TemporaryDirectory(prefix='smash-audio-capture-') as folder:
        out=Path(folder)
        for name,region in (('previous',previous),('selected',selected)):
            sub=out/name;sub.mkdir()
            src=sub/'contract.cpp';src.write_text(prefix+region+suffix)
            batch=sub/'compile.cmd';batch.write_text(
                '@echo off\ncall "'+install+'/VC/Auxiliary/Build/vcvars64.bat" >nul\n'
                'if errorlevel 1 exit /b 1\ncl /nologo /EHsc /MT /D_XBOX "'+str(src)+
                '" /Fe"'+str(sub/'contract.exe')+'"\nexit /b %errorlevel%\n')
            built=subprocess.run([os.environ['ComSpec'],'/d','/c',str(batch)],cwd=sub,capture_output=True,text=True)
            assert built.returncode==0,built.stdout+built.stderr
            if name=='selected':
                disabled=subprocess.run([str(sub/'contract.exe')],cwd=sub,capture_output=True,text=True)
                assert disabled.returncode==0,disabled.stdout+disabled.stderr
                assert not (sub/'capture.rifx').exists()
            enabled=subprocess.run([str(sub/'contract.exe'),'1'],cwd=sub,capture_output=True,text=True)
            assert enabled.returncode==0,enabled.stdout+enabled.stderr
        assert (out/'previous/capture.rifx').read_bytes()==(out/'selected/capture.rifx').read_bytes()
        print('WAV default open/write 0; opted-in RIFX bytes match previous selected output')

if __name__=='__main__':main()
