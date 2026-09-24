$ErrorActionPreference='Stop'
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$out=Join-Path $root 'scratch/graphics-xdk'
$hostObjects=Join-Path $out 'host'
New-Item -ItemType Directory -Force -Path $hostObjects | Out-Null
& python (Join-Path $root 'tools/prepare_graphics_xdk.py') --compile
if($LASTEXITCODE -ne 0){throw 'Graphics XDK compilation failed'}
$vswhere=Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
$vs=& $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
$vcvars=Join-Path $vs 'VC/Auxiliary/Build/vcvars64.bat'
$base=Join-Path $root 'platform/xbox360/graphics'
$platformBase=if($env:XBOX360_PLATFORM_BASE){$env:XBOX360_PLATFORM_BASE}else{Join-Path $root ((Get-Content (Join-Path $root 'platform-base.lock.json') -Raw | ConvertFrom-Json).base)}
$shaderLower=Join-Path $platformBase 'sources/graphics/shader_lower.cpp'
$test=Join-Path $PSScriptRoot 'shader_contract.cpp'
$batch=Join-Path $out 'build-host.cmd'
@"
@echo off
call "$vcvars" >nul
if errorlevel 1 exit /b 1
cl /nologo /EHsc /W4 /WX /D_CRT_SECURE_NO_WARNINGS /MT /I"$out/include" /I"$base" "$test" "$shaderLower" /Fo"$hostObjects\\" /Fe"$out/shader_contract.exe"
exit /b %errorlevel%
"@ | Set-Content -LiteralPath $batch -Encoding Ascii
& $env:ComSpec /d /c $batch 2>&1 | Tee-Object -FilePath (Join-Path $out 'host-compile.log')
if($LASTEXITCODE -ne 0){throw 'Shader contract host compilation failed'}
& (Join-Path $out 'shader_contract.exe') (Join-Path $out 'lowered-fixture.hlsl') 2>&1 | Tee-Object -FilePath (Join-Path $out 'host-test.log')
if($LASTEXITCODE -ne 0){throw 'Shader contract host execution failed'}
$fxc='C:/Program Files (x86)/Microsoft Xbox 360 SDK/bin/win32/fxc.exe'
& $fxc /nologo /T ps_3_0 /E PSMain /Fo (Join-Path $out 'lowered-fixture.bin') (Join-Path $out 'lowered-fixture.hlsl') 2>&1 | Tee-Object -FilePath (Join-Path $out 'fxc-fixture.log')
if($LASTEXITCODE -ne 0){throw 'Actual Xenos shader compilation failed'}
& python -m unittest discover -s (Join-Path $root 'tests/graphics') -p 'test_*.py'
if($LASTEXITCODE -ne 0){throw 'Source preparation tests failed'}
