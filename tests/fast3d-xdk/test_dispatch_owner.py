from pathlib import Path
import subprocess
import re
import unittest
ROOT=Path(__file__).resolve().parents[2]
PLATFORM_BASE=ROOT.parent/'LibUltraShip+Fast3D360'
class DispatchOwnerTests(unittest.TestCase):
    def test_selected_interpreter_projection(self):
        original=(ROOT/'upstream/BattleShip/libultraship/src/fast/interpreter.cpp').read_text(encoding='utf-8-sig')
        selected=(ROOT/'scratch/application-xdk/native/composed-overlay/libultraship/src/fast/interpreter.cpp').read_text()
        self.assertEqual(original.count('Interpreter* gfx = mInstance.lock().get();'),90)
        self.assertEqual(selected.count('gfx = XboxDispatchInterpreter();'),90)
        self.assertEqual(selected.count('mInstance.lock()'),6)
        self.assertIn('typedef Shipyard::Fast3D::DispatchOwner<Interpreter> XboxDispatchOwner;',selected)
        self.assertRegex(selected,r'mInstance = gfx;\s*(?:#line[^\n]*\n\s*)?XboxDispatchOwner::Invalidate\(sXboxDispatchOwner\);')
        run=selected[selected.index('void Interpreter::Run('):]
        self.assertIn('XboxDispatchOwner dispatchOwner(sXboxDispatchOwner, mInstance);',run)
        self.assertLess(run.index('XboxDispatchOwner dispatchOwner'),run.index('g_exec_stack.start('))
        self.assertLess(run.index('} // Release the dispatch pin'),run.index('    Flush();'))

    def test_xdk_cached_owner_has_no_call_or_stack(self):
        out=ROOT/'scratch/fast3d-xdk/dispatch-owner-tests';out.mkdir(parents=True,exist_ok=True)
        sdk=Path('C:/Program Files (x86)/Microsoft Xbox 360 SDK')
        (out/'probe.cpp').write_text('#include "fast3d/dispatch_owner.h"\nstruct Object {int value;};\n'
            'extern "C" __declspec(noinline) Object* Borrow(Shipyard::Fast3D::DispatchOwner<Object>* scope,const std::weak_ptr<Object>& selected) {return scope->Get(selected);}\n')
        run=subprocess.run([str(sdk/'bin/win32/cl.exe'),'/nologo','/c','/O2','/Ob2','/MT','/EHsc','/D_XBOX','/DNDEBUG',
            '/showIncludes','/I'+str(sdk/'include/xbox'),'/I'+str(PLATFORM_BASE/'sources'),'/Fo'+str(out/'probe.obj'),str(out/'probe.cpp')],capture_output=True,text=True)
        self.assertEqual(run.returncode,0,run.stdout+run.stderr)
        self.assertIn(str(PLATFORM_BASE/'sources/fast3d/dispatch_owner.h').replace('\\','/').casefold(),
                      (run.stdout+run.stderr).replace('\\','/').casefold())
        run=subprocess.run([str(sdk/'bin/win32/dumpbin.exe'),'/disasm',str(out/'probe.obj')],capture_output=True,text=True)
        self.assertEqual(run.returncode,0,run.stdout+run.stderr)
        (out/'probe.asm').write_text(run.stdout)
        block=re.search(r'(?m)^Borrow:\s*\n(.*?)(?=^[^\s$]|\Z)',run.stdout,re.S|re.M)
        self.assertIsNotNone(block)
        ops=re.findall(r'(?m)^\s*[0-9A-Fa-f]+:\s+[0-9A-Fa-f]{8}\s+(\S+)',block[1])
        self.assertIn('blr',ops)
        hot=ops[:ops.index('blr')+1]
        self.assertIn('lbz',hot);self.assertIn('lwz',hot)
        for forbidden in ('bl','b','mflr','mtlr','stwu','stw','std','lwarx','ldarx'):
            self.assertNotIn(forbidden,hot,'cached owner should only check validity and return existing pointer')

    def test_scoped_owner(self):
        helper=PLATFORM_BASE/'sources/fast3d/dispatch_owner.h'
        self.assertTrue(helper.exists())
        self.assertFalse((ROOT/'platform/xbox360/cpp-compat/fast3d/dispatch_owner.h').exists())
        self.assertFalse((ROOT/'scratch/application-xdk/native/source/platform/xbox360/cpp-compat/fast3d/dispatch_owner.h').exists())
        out=ROOT/'scratch/fast3d-xdk/dispatch-owner-tests';out.mkdir(parents=True,exist_ok=True)
        source=PLATFORM_BASE/'tests/dispatch_owner_contract.cpp';batch=out/'build.cmd'
        batch.write_text('@echo off\ncall "C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Auxiliary/Build/vcvars32.bat" >nul\ncl /nologo /std:c++17 /O2 /EHsc /MT /I"'+str(PLATFORM_BASE/'sources')+'" "'+str(source)+'" /Fe:owner.exe\nexit /b %errorlevel%\n')
        result=subprocess.run(['cmd','/d','/c',str(batch)],cwd=out,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        result=subprocess.run([str(out/'owner.exe')],cwd=out,capture_output=True,text=True)
        (out/'run.log').write_text(result.stdout+result.stderr)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        print(result.stdout.strip())
if __name__=='__main__':unittest.main()
