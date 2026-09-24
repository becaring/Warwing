"""Execute real projected clear/start code against an independent SDK model."""
import importlib.util
import os
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]


def function(source, signature):
    start = source.index(signature)
    brace = source.index('{', start)
    depth, end = 1, brace + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end] + '\n'


class FramebufferClearTests(unittest.TestCase):
    def test_selective_clear_preserves_other_attachment_without_discarded_restores(self):
        spec = importlib.util.spec_from_file_location('graphics_prepare', ROOT/'tools/prepare_graphics_xdk.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        source = (module.PLATFORM_BASE/'sources/xenos/core.cpp').read_text()
        out = ROOT/'scratch/graphics-xdk/clear-contract'
        out.mkdir(exist_ok=True)
        (out/'actual_framebuffer_clear.inc').write_text(
            function(source, 'void BeginFramebuffer() {') + function(source, 'void Clear(bool color,bool depth) {'))
        vswhere = Path(os.environ['ProgramFiles(x86)'])/'Microsoft Visual Studio/Installer/vswhere.exe'
        vs = subprocess.check_output([str(vswhere), '-latest', '-products', '*', '-requires',
                                      'Microsoft.VisualStudio.Component.VC.Tools.x86.x64', '-property', 'installationPath'], text=True).strip()
        batch = out/'compile.cmd'
        batch.write_text('@echo off\ncall "'+vs+'/VC/Auxiliary/Build/vcvars64.bat" >nul\n'
                         'if errorlevel 1 exit /b 1\ncl /nologo /EHsc /W4 /WX /MT /I"'+str(out)+'" "'+
                         str(ROOT/'tests/graphics/framebuffer_clear_contract.cpp')+'" /Fo"'+str(out/'contract.obj')+
                         '" /Fe"'+str(out/'contract.exe')+'"\nexit /b %errorlevel%\n')
        compiled = subprocess.run([os.environ['ComSpec'], '/d', '/c', str(batch)], capture_output=True, text=True)
        self.assertEqual(compiled.returncode, 0, compiled.stdout+compiled.stderr)
        result = subprocess.run([str(out/'contract.exe')], capture_output=True, text=True)
        (out/'result.log').write_text(result.stdout+result.stderr)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)


if __name__ == '__main__':
    unittest.main()
