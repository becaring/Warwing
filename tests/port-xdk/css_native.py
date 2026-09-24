"""Actual synthetic sprite writers checked against verbatim production layouts."""
from pathlib import Path
import hashlib,json,re,subprocess
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'scratch/port-xdk/css-tests'

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    original=ROOT/'upstream/BattleShip/decomp/include/PR/sp.h'
    header=original.read_text();layout=header[header.index('struct bitmap {'):header.index('/*\n * DANGER!')]
    layout=layout.replace('_Static_assert','static_assert')
    prefix='#define PORT\n#include <stdint.h>\n#include <cstddef>\n#include <cstring>\n#include <cassert>\ntypedef int16_t s16; typedef uint16_t u16; typedef uint32_t u32; typedef uint8_t u8; typedef float f32;\n'
    suffix='''
static_assert(offsetof(Sprite,scalex)==8,"actual scale offset");
static_assert(offsetof(Sprite,bitmap)==0x34,"actual bitmap token offset");
static_assert(offsetof(Bitmap,buf)==8,"actual pixel token offset");
extern "C" __declspec(noinline) void StoreNative(uint8_t* p,int16_t a,uint32_t token) { put_s16(p,0,a);put_u32(p,4,token); }
int main() {
    Sprite sprite = {}; Bitmap bitmap = {};
    put_s16((uint8_t*)&sprite,4,-1234); put_s16((uint8_t*)&sprite,6,4321);
    put_u16((uint8_t*)&sprite,0x14,0xa123); put_f32((uint8_t*)&sprite,8,1.25f);
    put_u32((uint8_t*)&sprite,0x34,0x89abcdefu);
    put_u32((uint8_t*)&bitmap,8,0xfedcba98u);
    assert(sprite.width==-1234 && sprite.height==4321 && sprite.attr==0xa123);
    assert(sprite.scalex==1.25f && sprite.bitmap==0x89abcdefu && bitmap.buf==0xfedcba98u);
    return 0;
}
'''
    paths=[]
    for name in ('port_css_arrow','port_css_stage_assets'):
        path=ROOT/'scratch/port-xdk/composed-overlay/port/css_icons'/(name+'.cpp'); paths.append(path)
        text=re.sub(r'^#line[^\n]*\n','',path.read_text(),flags=re.M)
        functions=[]
        for fn in ('put_s16','put_u16','put_u32','put_f32'):
            matches=re.findall(r'static inline void '+fn+r'\([^\n]*\) \{[^}]*\}',text)
            assert len(matches)==1;functions.append(matches[0])
        source=OUT/(name+'.cpp');source.write_text(prefix+layout+'\n'+'\n'.join(functions)+suffix)
        batch=OUT/(name+'.cmd');batch.write_text('@echo off\ncall "C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Auxiliary/Build/vcvars32.bat" >nul\ncl /nologo /TP /MT /EHsc /Fe:'+name+'.exe "'+str(source)+'"\n')
        result=subprocess.run(['cmd.exe','/d','/c',str(batch)],cwd=OUT,capture_output=True)
        (OUT/(name+'-host.log')).write_bytes(result.stdout+result.stderr)
        assert result.returncode==0,(result.stdout+result.stderr).decode(errors='replace')
        assert subprocess.run([str(OUT/(name+'.exe'))],cwd=OUT).returncode==0
        sdk=Path('C:/Program Files (x86)/Microsoft Xbox 360 SDK')
        command=[str(sdk/'bin/win32/cl.exe'),'/nologo','/TP','/MT','/EHsc','/c','/O2','/I'+str(sdk/'include/xbox'),'/FAsc','/Fa'+str(OUT/(name+'.asm')),'/Fo'+str(OUT/(name+'.obj')),str(source)]
        result=subprocess.run(command,cwd=OUT,capture_output=True)
        (OUT/(name+'-native.log')).write_bytes(result.stdout+result.stderr)
        assert result.returncode==0,(result.stdout+result.stderr).decode(errors='replace')
        asm=(OUT/(name+'.asm')).read_text(); body=re.search(r'StoreNative\s+PROC(.*?)StoreNative ENDP',asm,re.S)[1]
        assert re.search(r'\bsth\s',body) and re.search(r'\bstw\s',body),body
        assert 'sthbrx' not in body and 'stwbrx' not in body,body
    report={'production_layout_sha256':hashlib.sha256(original.read_bytes()).hexdigest(),'writer_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},'host_layout_reads':True,'powerpc_native_sth_stw':True,'target_runtime':False}
    (OUT/'results.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

if __name__=='__main__':main()
