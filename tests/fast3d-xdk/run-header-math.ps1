$ErrorActionPreference='Stop'
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$out=Join-Path $root 'scratch/fast3d-xdk'
$cpp=Join-Path $root 'platform/xbox360/cpp-compat'
$shipyardRoot=[IO.Path]::GetFullPath((Join-Path $root '../LibUltraShip+Fast3D360'))
$shipyard=Join-Path $shipyardRoot 'sources'
$xdk='C:/Program Files (x86)/Microsoft Xbox 360 SDK'
& python (Join-Path $root 'tools/prepare_fast3d_xdk.py')
if($LASTEXITCODE -ne 0){throw 'Fast3D source staging failed'}
$xdkIncludes=@("/I$cpp","/I$shipyardRoot","/I$shipyard","/I$cpp/async","/I$root/scratch/fast3d-xdk/compile-tree/libultraship/include","/I$root/scratch/value-types/include","/I$root/scratch/graphics-xdk/include","/I$xdk/include/xbox")
foreach($source in @("$PSScriptRoot/header_math.cpp","$out/test_math.cpp","$out/test_opcode_tables.cpp")) {
    $name=[IO.Path]::GetFileNameWithoutExtension($source)
    & "$xdk/bin/win32/cl.exe" /nologo /TP /EHsc /MT /D_XBOX /DNOMINMAX /DSMASH360_TEST_RDP_VALUE_INIT @xdkIncludes /c "/Fo$out/$name-xdk.obj" $source 2>&1 | Tee-Object -FilePath "$out/$name-xdk.log"
    if($LASTEXITCODE -ne 0){throw 'Actual Fast3D header/math XDK compile failed'}
}
$vswhere=Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
$vs=& $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
$vcvars=Join-Path $vs 'VC/Auxiliary/Build/vcvars64.bat'
foreach($mode in @('original','adapted')) {
    $directory=Join-Path $out "math-$mode"
    New-Item -ItemType Directory -Force -Path $directory | Out-Null
    $header=Join-Path $root 'upstream/BattleShip/libultraship/include'
    $implementation=Join-Path $out 'test_math_original.cpp'
    $rdpDefine=''
    if($mode -eq 'adapted'){$header=Join-Path $out 'compile-tree/libultraship/include';$implementation=Join-Path $out 'test_math.cpp';$rdpDefine='/DSMASH360_TEST_RDP_VALUE_INIT'}
    $batch=Join-Path $directory 'build.cmd'
    @"
@echo off
call "$vcvars" >nul
if errorlevel 1 exit /b 1
    cl /nologo /std:c++20 /EHsc /MT /fp:precise /DNOMINMAX $rdpDefine /I"$header" /I"$cpp" /I"$shipyardRoot" /I"$shipyard" /I"$root/scratch/value-types/include" /I"$root/scratch/graphics-xdk/include" "$PSScriptRoot/header_math.cpp" "$implementation" /Fo"$directory\\" /Fe"$directory/test.exe"
exit /b %errorlevel%
"@ | Set-Content -LiteralPath $batch -Encoding Ascii
    & $env:ComSpec /d /c $batch 2>&1 | Tee-Object -FilePath "$directory/compile.log"
    if($LASTEXITCODE -ne 0){throw "$mode actual-header compile failed"}
    $test=Start-Process -FilePath "$directory/test.exe" -WindowStyle Hidden -Wait -PassThru -RedirectStandardOutput "$directory/results.txt" -RedirectStandardError "$directory/diagnostics.txt"
    if($test.ExitCode -ne 0){throw "$mode actual-header execution failed"}
}
if((Get-Content "$out/math-original/results.txt" -Raw) -cne (Get-Content "$out/math-adapted/results.txt" -Raw)){throw 'Actual header/math differential mismatch'}
if((Get-Content "$out/math-original/diagnostics.txt" -Raw) -cne (Get-Content "$out/math-adapted/diagnostics.txt" -Raw)){throw 'Actual combiner diagnostics differential mismatch'}
Get-Content "$out/math-adapted/results.txt"
