$ErrorActionPreference='Stop'
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$out=Join-Path $root 'scratch/prism-xdk'
$base=Join-Path $root 'platform/xbox360/cpp-compat/prism'
$graphics=Join-Path $root 'platform/xbox360/graphics'
$platformBase=if($env:XBOX360_PLATFORM_BASE){$env:XBOX360_PLATFORM_BASE}else{Join-Path $root ((Get-Content (Join-Path $root 'platform-base.lock.json') -Raw | ConvertFrom-Json).base)}
$shaderLower=Join-Path $platformBase 'sources/graphics/shader_lower.cpp'
$shaderProvider=Join-Path $platformBase 'sources/graphics/shader_provider.cpp'
$upstream=Join-Path $root 'upstream/dependencies/prism/src'
& python (Join-Path $root 'tools/prepare_prism_xdk.py') --compile
if($LASTEXITCODE -ne 0){throw 'Prism XDK compilation failed'}
$vswhere=Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
$vs=& $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
$vcvars=Join-Path $vs 'VC/Auxiliary/Build/vcvars64.bat'
foreach($mode in @('reference','adapted')) {
    $hostDir=Join-Path $out "host-$mode"
    New-Item -ItemType Directory -Force -Path $hostDir | Out-Null
    $src=$upstream
    $builder=Join-Path $out 'reference/shader_builder.cpp'
    $define=''
    $range=Join-Path $PSScriptRoot 'range_contract.cpp'
    if($mode -eq 'adapted'){$src=$out;$builder=Join-Path $out 'shader_builder.cpp';$define='/DPRISM_ADAPTED';$range=Join-Path $out 'range_contract.cpp'}
    $batch=Join-Path $hostDir 'build.cmd'
    @"
@echo off
call "$vcvars" >nul
if errorlevel 1 exit /b 1
cl /nologo /TC /c /MT "$src/prism/utils/invoke.c" /Fo"$hostDir/invoke.obj"
if errorlevel 1 exit /b 1
cl /nologo /std:c++17 /EHsc /MT /O2 /DNDEBUG /I"$root/scratch/graphics-xdk/include" /I"$graphics" /c "$shaderProvider" /Fo"$hostDir/shipyard_shader_provider.obj"
if errorlevel 1 exit /b 1
cl /nologo /std:c++17 /utf-8 /EHsc /MT /O2 /DNDEBUG /DSPDLOG_ACTIVE_LEVEL=2 /D_CRT_SECURE_NO_WARNINGS $define /I"$src" /I"$base" /I"$out" /I"$platformBase/sources" /I"$platformBase/sources/value_types" /I"$root/scratch/value-types/include" /I"$root/scratch/graphics-xdk/include" /I"$graphics" /I"$root/upstream/dependencies/spdlog/include" "$src/prism/lexer.cpp" "$src/prism/ast.cpp" "$src/prism/processor.cpp" "$src/prism/utils/gv.cpp" "$builder" "$graphics/shader_provider.cpp" "$shaderLower" "$out/test_shader_features.cpp" "$PSScriptRoot/differential.cpp" "$range" "$hostDir/invoke.obj" "$hostDir/shipyard_shader_provider.obj" /Fo"$hostDir\\" /Fe"$hostDir/differential.exe"
exit /b %errorlevel%
"@ | Set-Content -LiteralPath $batch -Encoding Ascii
    & $env:ComSpec /d /c $batch 2>&1 | Tee-Object -FilePath (Join-Path $hostDir 'compile.log')
    if($LASTEXITCODE -ne 0){throw "$mode host compilation failed"}
    & (Join-Path $hostDir 'differential.exe') (Join-Path $root 'upstream/BattleShip/libultraship/src/fast/shaders/directx/default.shader.hlsl') $hostDir 2>&1 | Tee-Object -FilePath (Join-Path $hostDir 'run.log')
    if($LASTEXITCODE -ne 0){throw "$mode host execution failed"}
}
& python (Join-Path $PSScriptRoot 'verify_outputs.py')
if($LASTEXITCODE -ne 0){throw 'Differential or actual HLSL compile failed'}
& python -m unittest discover -s $PSScriptRoot -p 'test_*.py'
if($LASTEXITCODE -ne 0){throw 'Preparation tests failed'}

