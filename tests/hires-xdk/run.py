from pathlib import Path
import json,struct,subprocess,zlib,zipfile
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'scratch/hires-xdk/tests'
def png(w,h,color):
    def chunk(tag,data):return struct.pack('>I',len(data))+tag+data+struct.pack('>I',zlib.crc32(tag+data))
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>2I5B',w,h,8,6,0,0,0))+chunk(b'IDAT',zlib.compress((b'\0'+bytes(color)*w)*h))+chunk(b'IEND',b'')
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    vs=subprocess.check_output(['C:/Program Files (x86)/Microsoft Visual Studio/Installer/vswhere.exe','-latest','-products','*','-requires','Microsoft.VisualStudio.Component.VC.Tools.x86.x64','-property','installationPath'],text=True).strip()
    outputs=[];dumps=[]
    for projected in (0,1):
        target=OUT/str(projected);target.mkdir(exist_ok=True);data=target/'data';mods=data/'mods';mods.mkdir(parents=True,exist_ok=True)
        for old in (data/'hires_dump').glob('*.bin'):old.unlink()
        crc=zlib.crc32(bytes([1,2,3,255,4,5,6,255,7,8,9,255,10,11,12,255]));bad=zlib.crc32(bytes([91,92,93,255]))
        (mods/f'a#{crc:08x}#0#2.png').write_bytes(png(4,4,[200,0,0,255]));(mods/f'b#{bad:08x}#0#2.png').write_bytes(b'broken')
        with zipfile.ZipFile(mods/'z_pack.zip','w',zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(f'folder/key#{crc:08x}#0#2.png',png(4,4,[0,0,200,255]));archive.writestr('other#abcdef12#0#2.png',png(2,2,[0,200,0,255]))
        source=ROOT/('scratch/hires-xdk/overlay/port/hires' if projected else 'upstream/BattleShip/port/hires')
        text=(source/'HiResPack.cpp').read_text();text=text.replace('#include <libultraship/libultraship.h>','#include "test_path.h"').replace('#include "ship/Context.h"','#include "test_path.h"').replace('#include "libultraship/bridge/consolevariablebridge.h"','')
        text=text.replace('#include "../port_log.h"','extern "C" void port_log(const char*,...);')
        (target/'actual_pack.cpp').write_text(text);(target/'HiResPack.h').write_bytes((source/'HiResPack.h').read_bytes())
        (target/'test_path.h').write_text('#pragma once\n#include <string>\n#include <stdint.h>\nnamespace Ship { class Context {public:static std::string GetPathRelativeToAppDirectory(const std::string&);};}\nextern "C" int32_t CVarGetInteger(const char*,int32_t);\n')
        (target/'stb.cpp').write_text('#define STB_IMAGE_IMPLEMENTATION\n#include <stb_image.h>\n')
        includes=[target,ROOT/'platform/xbox360/cpp-compat',ROOT.parent/'LibUltraShip+Fast3D360/sources/value_types',ROOT/'platform/xbox360/cpp-compat/thread-pool',ROOT/'upstream/dependencies/stb',ROOT/'upstream/dependencies/libzip/lib',ROOT/'scratch/resources-xdk/libzip-public']
        includes += [ROOT/'platform/xbox360/cpp-compat/async',ROOT.parent/'LibUltraShip+Fast3D360',ROOT.parent/'LibUltraShip+Fast3D360/sources',ROOT/('scratch/hires-xdk/compile-tree/libultraship/include' if projected else 'upstream/BattleShip/libultraship/include')]
        files=[ROOT/'tests/hires-xdk/contract.cpp',target/'stb.cpp',ROOT.parent/'LibUltraShip+Fast3D360/sources/async/native.cpp',
               ROOT.parent/'LibUltraShip+Fast3D360/sources/filesystem/filesystem.cpp']
        libs=[ROOT/'scratch/resources-xdk/host-dependencies/libzip-ninja/lib/zip.lib',ROOT/'scratch/resources-xdk/host-dependencies/zlib/zlib.lib']
        batch=target/'build.cmd';exe=target/'hires.exe'
        batch.write_text('@echo off\ncall "'+vs+'/VC/Auxiliary/Build/vcvars64.bat" >nul\ncl /nologo /EHsc /std:c++20 /utf-8 /MT /D_CRT_SECURE_NO_WARNINGS /DNOMINMAX /DPROJECTED='+str(projected)+' '+ ' '.join('/I"'+str(p)+'"' for p in includes)+' '+ ' '.join('"'+str(p)+'"' for p in files+libs)+' advapi32.lib /Fo"'+str(target)+'/" /Fe"'+str(exe)+'"\nexit /b %errorlevel%\n')
        p=subprocess.run(['cmd','/d','/c',str(batch)],capture_output=True,text=True);(target/'compile.log').write_text(p.stdout+p.stderr)
        if p.returncode:raise RuntimeError(p.stdout+p.stderr)
        p=subprocess.run([str(exe),str(data)],capture_output=True,text=True,timeout=30);(target/'run.log').write_text(p.stdout+p.stderr);assert p.returncode==0,p.stderr;outputs.append(p.stdout)
        dump=list((data/'hires_dump').glob('*.bin'));assert len(dump)==1;dumps.append(dump[0].read_bytes())
    expected=struct.pack('<7I2B6x',0x44524853,1,2,2,6,8,4,2,2)+bytes([1,2,3,4,5,6,7,8,0x12,0x34,0xab,0xcd])
    assert dumps[0]==dumps[1]==expected;assert outputs[0]==outputs[1];print(outputs[0]);print('PASS full real original/projected HiResPack differential and exact36-byte desktop LE header/row-stride/palette bytes; converter unavailable')
if __name__=='__main__':main()
