$ErrorActionPreference='Stop'
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$out=Join-Path $root 'scratch/platform-constants'
New-Item -ItemType Directory -Force $out | Out-Null
$vswhere=Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
$vs=& $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
$batch=Join-Path $out 'build.cmd'
@"
@echo off
call "$vs/VC/Auxiliary/Build/vcvars64.bat" >nul
if errorlevel 1 exit /b 1
cl /nologo /EHsc /MT "$root/platform/xbox360/math_constants.cpp" "$PSScriptRoot/contract.cpp" /Fo"$out\\" /Fe"$out/constants.exe"
exit /b %errorlevel%
"@ | Set-Content -LiteralPath $batch -Encoding ascii
& $env:ComSpec /d /c $batch *> (Join-Path $out 'host-build.log')
if ($LASTEXITCODE) { throw 'Platform constants host compile failed' }
& (Join-Path $out 'constants.exe') *> (Join-Path $out 'host-result.txt')
if ($LASTEXITCODE) { throw 'Actual NaN symbol/initialization changed' }
$xdk=if($env:XEDK){$env:XEDK}else{'C:/Program Files (x86)/Microsoft Xbox 360 SDK'}
& (Join-Path $xdk 'bin/win32/cl.exe') /nologo /c /TP /EHsc /MT /D_XBOX ('/I'+$xdk+'/include/xbox') ('/Fo'+$out+'/math_constants-xdk.obj') (Join-Path $root 'platform/xbox360/math_constants.cpp') *> (Join-Path $out 'native-build.log')
if ($LASTEXITCODE) { throw 'Actual NaN source XDK compile failed' }
Get-Content -LiteralPath (Join-Path $out 'host-result.txt')
