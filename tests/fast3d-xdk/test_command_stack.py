from pathlib import Path
import re
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
PLATFORM_BASE=ROOT.parent/'LibUltraShip+Fast3D360'
sys.path.insert(0,str(ROOT/'tools'))
from command_work_projection import header as project_header

class CommandStackTests(unittest.TestCase):
    def test_actual_stack_operations(self):
        header=(ROOT/'upstream/BattleShip/libultraship/include/fast/interpreter.h').read_text(encoding='utf-8-sig')
        start=header.index('struct GfxExecStack {');end=header.index('\n};',start)+3
        original=header[start:end]
        selected=project_header(header)
        projected=selected[selected.index('struct GfxExecStack {'):selected.index('\n};',selected.index('struct GfxExecStack {'))+3]
        self.assertIn('#include "fast3d/command_stack.h"',selected)
        self.assertIn('Shipyard::Fast3D::CommandStack<F3DGfx*> cmd_stack',projected)
        self.assertFalse((ROOT/'platform/xbox360/cpp-compat/fast3d/command_stack.h').exists())
        self.assertFalse((ROOT/'scratch/application-xdk/native/source/platform/xbox360/cpp-compat/fast3d/command_stack.h').exists())
        source=(ROOT/'upstream/BattleShip/libultraship/src/fast/interpreter.cpp').read_text(encoding='utf-8-sig')
        begin=source.index('void GfxExecStack::start(');end=source.index('\nvoid gfx_set_framebuffer(',begin)
        methods=source[begin:end]
        driver=(PLATFORM_BASE/'tests/command_stack_contract.cpp').read_text()
        for key,value in [('ORIGINAL_STACK',original),('PROJECTED_STACK',projected),
                          ('ORIGINAL_METHODS',methods),('PROJECTED_METHODS',methods)]:
            driver=driver.replace('// '+key,value)
        out=ROOT/'scratch/command-stack-tests';out.mkdir(exist_ok=True)
        (out/'contract.cpp').write_text(driver,encoding='utf-8')
        (out/'build.cmd').write_text('@echo off\ncall "C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Auxiliary/Build/vcvars32.bat" >nul\ncl /nologo /utf-8 /std:c++17 /O2 /EHsc /MT /I"'+str(PLATFORM_BASE/'sources')+'" contract.cpp /Fe:contract.exe\nexit /b %errorlevel%\n')
        p=subprocess.run(['cmd','/d','/c',str(out/'build.cmd')],cwd=out,capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)
        p=subprocess.run([str(out/'contract.exe')],cwd=out,capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)
        (out/'run.log').write_text(p.stdout+p.stderr)
        print(p.stdout.strip())

    def test_xdk_fetch_has_no_iterator_calls(self):
        out=ROOT/'scratch/command-stack-tests';out.mkdir(exist_ok=True)
        (out/'probe.cpp').write_text('#include "fast3d/command_stack.h"\nextern "C" __declspec(noinline) void** Fetch(Shipyard::Fast3D::CommandStack<void*>* s) { return &s->top(); }\n')
        sdk=Path('C:/Program Files (x86)/Microsoft Xbox 360 SDK')
        p=subprocess.run([str(sdk/'bin/win32/cl.exe'),'/nologo','/c','/O2','/Ob2','/EHsc','/MT','/D_XBOX','/DNDEBUG','/showIncludes',
            '/I'+str(sdk/'include/xbox'),'/I'+str(PLATFORM_BASE/'sources'),'/Fo'+str(out/'probe.obj'),str(out/'probe.cpp')],capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)
        self.assertIn(str(PLATFORM_BASE/'sources/fast3d/command_stack.h').replace('\\','/').casefold(),
                      (p.stdout+p.stderr).replace('\\','/').casefold())
        p=subprocess.run([str(sdk/'bin/win32/dumpbin.exe'),'/disasm',str(out/'probe.obj')],capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)
        (out/'probe.asm').write_text(p.stdout)
        block=re.search(r'(?m)^Fetch:\s*\n(.*?)(?=^\S|\Z)',p.stdout,re.S|re.M)
        self.assertIsNotNone(block)
        ops=re.findall(r'(?m)^\s*[0-9A-Fa-f]+:\s+[0-9A-Fa-f]{8}\s+(\S+)',block[1])
        self.assertEqual(ops[:ops.index('blr')+1] if 'blr' in ops else ops,['lwz','blr'])

if __name__=='__main__':unittest.main()
