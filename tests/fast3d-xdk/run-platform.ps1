$ErrorActionPreference='Stop'
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$out=Join-Path $root 'scratch/fast3d-xdk'
$hostDir=Join-Path $out 'platform-host'
New-Item -ItemType Directory -Force -Path $hostDir | Out-Null
$base=Join-Path $root 'platform/xbox360/cpp-compat'
$shipyardRoot = if ($env:XBOX360_PLATFORM_BASE) { $env:XBOX360_PLATFORM_BASE } else {
    Join-Path $root ((Get-Content -LiteralPath (Join-Path $root 'platform-base.lock.json') -Raw | ConvertFrom-Json).base)
}
$source=Join-Path $PSScriptRoot 'platform.cpp'
$xdk='C:/Program Files (x86)/Microsoft Xbox 360 SDK'
& "$xdk/bin/win32/cl.exe" /nologo /TP /EHsc /MT /D_XBOX /DNOMINMAX "/I$base" "/I$shipyardRoot" "/I$shipyardRoot/sources" "/I$xdk/include/xbox" /c "/Fo$out/platform-xdk.obj" $source 2>&1 | Tee-Object -FilePath "$out/platform-xdk.log"
if($LASTEXITCODE -ne 0){throw 'Fast3D platform arithmetic XDK compile failed'}
$vswhere=Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
$vs=& $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
$vcvars=Join-Path $vs 'VC/Auxiliary/Build/vcvars64.bat'
$batch=Join-Path $hostDir 'build.cmd'
@"
@echo off
call "$vcvars" >nul
if errorlevel 1 exit /b 1
cl /nologo /std:c++20 /EHsc /MT /W4 /WX /fp:strict /DNOMINMAX /I"$base" /I"$shipyardRoot" /I"$shipyardRoot/sources" "$source" /Fo"$hostDir\\" /Fe"$hostDir/platform.exe"
exit /b %errorlevel%
"@ | Set-Content -LiteralPath $batch -Encoding Ascii
& $env:ComSpec /d /c $batch 2>&1 | Tee-Object -FilePath "$hostDir/compile.log"
if($LASTEXITCODE -ne 0){throw 'Fast3D helper host compile failed'}
& "$hostDir/platform.exe"
if($LASTEXITCODE -ne 0){throw 'Fast3D platform arithmetic differential failed'}
Write-Output 'Fast3D platform arithmetic tests passed; XDK instructions require target execution for runtime validation.'

