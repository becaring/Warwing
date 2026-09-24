#requires -Version 7.0
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$out = Join-Path $root 'scratch/filesystem-xdk'
New-Item -ItemType Directory -Force -Path $out | Out-Null
$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
$vs = & $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
$vcvars = Join-Path $vs 'VC/Auxiliary/Build/vcvars64.bat'
$inc = Join-Path $root 'platform/xbox360/cpp-compat/filesystem'
$shipyardRoot = Join-Path (Split-Path $root -Parent) 'LibUltraShip+Fast3D360'
$shipyard = Join-Path $shipyardRoot 'sources'
$source = Join-Path $shipyard 'filesystem/filesystem.cpp'
$native = Join-Path $shipyard 'async/native.cpp'
$test = Join-Path $PSScriptRoot 'filesystem_tests.cpp'
foreach ($variant in @('windows','logical')) {
$define = if ($variant -eq 'logical') { '/DSHIPYARD_TEST_LOGICAL_CWD' } else { '' }
$exe = Join-Path $out ($variant+'-filesystem_tests.exe')
$batch = Join-Path $out ('build-'+$variant+'.cmd')
@"
@echo off
call "$vcvars" >nul
if errorlevel 1 exit /b 1
cl /nologo /std:c++17 /EHsc /W4 /WX /MT $define /I"$inc" /I"$shipyardRoot" /I"$shipyard" "$test" "$source" "$native" /Fo"$out\\" /Fe"$exe"
exit /b %errorlevel%
"@ | Set-Content -LiteralPath $batch -Encoding Ascii
& $env:ComSpec /d /c $batch 2>&1 | Tee-Object -FilePath (Join-Path $out ($variant+'-compile.log'))
if ($LASTEXITCODE -ne 0) { throw 'Filesystem host compile failed' }
$fixture = [IO.Path]::GetFullPath((Join-Path $out ('fixture-'+[guid]::NewGuid().ToString())))
if (!$fixture.StartsWith([IO.Path]::GetFullPath($out)+[IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw 'Fixture escaped filesystem test workspace' }
$process = Start-Process -FilePath $exe -ArgumentList ('"'+$fixture+'"') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $out ($variant+'-test.log')) -RedirectStandardError (Join-Path $out ($variant+'-errors.log'))
if (!$process.WaitForExit(30000)) { $process.Kill(); throw 'Filesystem tests exceeded deadline' }
$process.WaitForExit()
Get-Content (Join-Path $out ($variant+'-test.log'))
Get-Content (Join-Path $out ($variant+'-errors.log'))
if ($process.ExitCode -ne 0) { throw 'Filesystem host tests failed' }
}
& python (Join-Path $root 'tools/prepare_filesystem_xdk.py')
if ($LASTEXITCODE -ne 0) { throw 'Filesystem XDK preparation failed' }
$xdk = if ($env:XEDK) { $env:XEDK } else { 'C:/Program Files (x86)/Microsoft Xbox 360 SDK' }
$compiler = Join-Path $xdk 'bin/win32/cl.exe'
foreach ($unit in @($source,$native,(Join-Path $PSScriptRoot 'consumer_probe.cpp'))) {
    $obj = Join-Path $out (([IO.Path]::GetFileNameWithoutExtension($unit))+'-xdk.obj')
    & $compiler /nologo /c /TP /EHsc /MT /W4 /WX /D_XBOX /DNOMINMAX ('/I'+(Join-Path $xdk 'include/xbox')) ('/I'+$inc) ('/I'+$shipyardRoot) ('/I'+$shipyard) ('/I'+$out) ('/Fo'+$obj) $unit 2>&1 | Tee-Object -FilePath ($obj+'.log')
    if ($LASTEXITCODE -ne 0) { throw "XDK filesystem object compile failed: $unit" }
}
$negative = Join-Path $PSScriptRoot 'unsupported.cpp'
& $compiler /nologo /c /TP /EHsc /MT /D_XBOX /DNOMINMAX ('/I'+(Join-Path $xdk 'include/xbox')) ('/I'+$inc) ('/I'+$shipyardRoot) ('/I'+$shipyard) ('/Fo'+(Join-Path $out 'unsupported.obj')) $negative 2>&1 | Set-Content (Join-Path $out 'unsupported.log')
if ($LASTEXITCODE -eq 0) { throw 'Unsupported remove_all was silently accepted' }
if (!(Select-String -Quiet -LiteralPath (Join-Path $out 'unsupported.log') -Pattern 'remove_all')) { throw 'Negative probe failed for unrelated reason' }
Write-Output 'PASS XDK objects and rejected unsupported API. No XEX or native storage execution.'
# The negative compile is expected to fail; don't leak its code to callers.
$global:LASTEXITCODE = 0
