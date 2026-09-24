$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$out = Join-Path $root 'scratch/fmt-xdk'
New-Item -ItemType Directory -Force $out | Out-Null
$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
$vs = & $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
$vcvars = Join-Path $vs 'VC/Auxiliary/Build/vcvars64.bat'
$fixture = Join-Path $PSScriptRoot 'contract.cpp'
foreach ($mode in @('reference','adapted')) {
    $flag = if ($mode -eq 'reference') { '/DSMASH360_FMT_REFERENCE' } else { '' }
    $batch = Join-Path $out ($mode+'.cmd')
    $exe = Join-Path $out ($mode+'.exe')
    @"
@echo off
call "$vcvars" >nul
if errorlevel 1 exit /b 1
cl /nologo /std:c++20 /utf-8 /EHsc /MT /W3 /D_CRT_SECURE_NO_WARNINGS $flag /I"$root/upstream/dependencies/spdlog/include" /I"$root/upstream/dependencies/fmt-xdk" /I"$root/platform/xbox360/cpp-compat" "$fixture" /Fo"$out/$mode.obj" /Fe"$exe"
exit /b %errorlevel%
"@ | Set-Content -LiteralPath $batch -Encoding ascii
    & $env:ComSpec /d /c $batch *> (Join-Path $out ($mode+'.log'))
    if ($LASTEXITCODE) { Get-Content (Join-Path $out ($mode+'.log')) -Tail 12; throw 'Formatter host compilation failed' }
    & $exe (Join-Path $out ($mode+'.exact.txt')) (Join-Path $out ($mode+'.floats.txt'))
    if ($LASTEXITCODE) { throw 'Formatter host fixture failed' }
}
$reference = (Get-FileHash (Join-Path $out 'reference.exact.txt')).Hash
$adapted = (Get-FileHash (Join-Path $out 'adapted.exact.txt')).Hash
if ($reference -ne $adapted) { throw 'Reached nonfloating formatting contract differs' }
$xdk = if ($env:XEDK) { $env:XEDK } else { 'C:/Program Files (x86)/Microsoft Xbox 360 SDK' }
& (Join-Path $xdk 'bin/win32/cl.exe') /nologo /c /TP /EHsc /MT /W3 /D_XBOX /DNOMINMAX ('/I'+$xdk+'/include/xbox') ('/I'+$root+'/upstream/dependencies/fmt-xdk') ('/I'+$root+'/platform/xbox360/cpp-compat') ('/Fo'+$out+'/native.obj') $fixture *> (Join-Path $out 'native.log')
if ($LASTEXITCODE) { Get-Content (Join-Path $out 'native.log') -Tail 15; throw 'Formatter XDK fixture failed' }
[ordered]@{ nonfloating_sha256=$reference; native_compile=$true; float_reference=[IO.File]::ReadAllText((Join-Path $out 'reference.floats.txt')); float_adapted=[IO.File]::ReadAllText((Join-Path $out 'adapted.floats.txt')); limitation='Floating diagnostic spelling explicitly differs; no game/resource/config use allowed' } | ConvertTo-Json | Set-Content (Join-Path $out 'verification.json')
Write-Output 'PASS reached integer/string/pointer formats + 13 argument diagnostic; XDK compile. Floating spelling difference recorded explicitly.'
