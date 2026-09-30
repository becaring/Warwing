param([switch]$HostOnly)
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$output = Join-Path $root 'tests\async-compat\out'
New-Item -ItemType Directory -Force -Path $output | Out-Null
$include = Join-Path $root 'platform\xbox360\cpp-compat\async'
$shipyardRoot = if ($env:XBOX360_PLATFORM_BASE) { $env:XBOX360_PLATFORM_BASE } else {
    Join-Path $root ((Get-Content -LiteralPath (Join-Path $root 'platform-base.lock.json') -Raw | ConvertFrom-Json).base)
}
$shipyard = Join-Path $shipyardRoot 'sources'
$test = Join-Path $root 'tests\async-compat\async_tests.cpp'
$native = Join-Path $shipyard 'async\native.cpp'
$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
$vs = & $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if (!$vs) { throw 'A host MSVC C++ installation is required' }
$vcvars = Join-Path $vs 'VC\Auxiliary\Build\vcvars64.bat'
$exe = Join-Path $output 'async_tests.exe'
$batch = Join-Path $output 'build-host.cmd'
@"
@echo off
call "$vcvars" >nul
if errorlevel 1 exit /b 1
cl /nologo /EHsc /W4 /WX /MT /I"$include" /I"$shipyardRoot" /I"$shipyard" "$test" "$native" /Fo"$output\\" /Fe"$exe"
exit /b %errorlevel%
"@ | Set-Content -LiteralPath $batch -Encoding Ascii
& $env:ComSpec /d /c $batch 2>&1 | Tee-Object -FilePath (Join-Path $output 'host-compile.log')
if ($LASTEXITCODE -ne 0) { throw 'Host async compatibility compilation failed' }
$process = Start-Process -FilePath $exe -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $output 'host-test.log') -RedirectStandardError (Join-Path $output 'host-test-errors.log')
if (!$process.WaitForExit(30000)) { $process.Kill(); throw 'Async tests deadlocked or exceeded the 30-second deadline' }
$process.WaitForExit()
Get-Content (Join-Path $output 'host-test.log')
Get-Content (Join-Path $output 'host-test-errors.log')
if ($process.ExitCode -ne 0) { throw "Async compatibility tests failed: $($process.ExitCode)" }
if (!$HostOnly) {
    $xdk = if ($env:XEDK) { $env:XEDK } else { 'C:\Program Files (x86)\Microsoft Xbox 360 SDK' }
    $compiler = Join-Path $xdk 'bin\win32\cl.exe'
    $flags = @('/nologo','/TP','/D_XBOX','/D_WIN32','/EHsc','/MT','/W4',('/I'+(Join-Path $xdk 'include\xbox')),('/I'+$include),('/I'+$shipyardRoot),('/I'+$shipyard))
    foreach ($source in @($native, $test)) {
        $obj = Join-Path $output (([IO.Path]::GetFileNameWithoutExtension($source))+'-xdk.obj')
        & $compiler @flags /c ('/Fo'+$obj) $source 2>&1 | Tee-Object -FilePath ($obj+'.log')
        if ($LASTEXITCODE -ne 0) { throw "XDK object compilation failed: $source" }
    }
    Write-Output 'XDK objects compiled only. No Xbox link, runtime, application build, or boot claim.'
}
