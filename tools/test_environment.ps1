$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$out = Join-Path $root 'scratch/environment-tests'
New-Item -ItemType Directory -Force $out | Out-Null
$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
$vs = & $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
$vcvars = Join-Path $vs 'VC/Auxiliary/Build/vcvars64.bat'
$inc = Join-Path $root 'platform/xbox360'
$platformLock = Get-Content -LiteralPath (Join-Path $root 'platform-base.lock.json') -Raw | ConvertFrom-Json
$platformBase = if ($env:XBOX360_PLATFORM_BASE) { $env:XBOX360_PLATFORM_BASE } else {
    Join-Path $root ((Get-Content -LiteralPath (Join-Path $root 'platform-base.lock.json') -Raw | ConvertFrom-Json).base)
}
$sharedInc = Join-Path $platformBase 'sources'
$source = Join-Path $inc 'environment.cpp'
$test = Join-Path $root 'tests/environment/environment_tests.cpp'
$exe = Join-Path $out 'environment_tests.exe'
$batch = Join-Path $out 'build.cmd'
@"
@echo off
call "$vcvars" >nul
if errorlevel 1 exit /b 1
cl /nologo /EHsc /W4 /WX /MT /I"$inc" /I"$sharedInc" "$source" "$test" /Fo"$out\\" /Fe"$exe"
exit /b %errorlevel%
"@ | Set-Content -LiteralPath $batch -Encoding Ascii
& $env:ComSpec /d /c $batch 2>&1 | Tee-Object -FilePath (Join-Path $out 'host-build.log')
if ($LASTEXITCODE -ne 0) { throw 'Environment compilation failed' }
$cases = @(
    @{ Name='valid'; Text="# comment`r`nSSB64_MAX_FRAMES=123`r`nVALUE= a=b #literal `nEMPTY="; Status=0 },
    @{ Name='duplicate'; Text="SSB64_MAX_FRAMES=123`nSSB64_MAX_FRAMES=456"; Status=3 },
    @{ Name='malformed'; Text="SSB64_MAX_FRAMES=123`nnot an assignment"; Status=3 },
    @{ Name='null'; Text="SSB64_MAX_FRAMES=123`nBAD=x`0y"; Status=3 },
    @{ Name='name'; Text="BAD-NAME=value"; Status=3 }
)
foreach ($case in $cases) {
    $path = Join-Path $out ($case.Name+'.env')
    [IO.File]::WriteAllText($path, $case.Text, [Text.Encoding]::ASCII)
    & $exe $path $case.Status
    if ($LASTEXITCODE -ne 0) { throw "Failed case: $($case.Name)" }
}
$oversize = Join-Path $out 'oversize.env'
[IO.File]::WriteAllBytes($oversize, (New-Object byte[] (1024 * 1024 + 1)))
& $exe $oversize 3
if ($LASTEXITCODE -ne 0) { throw 'Oversized file test failed' }
$missing = Join-Path $out ([guid]::NewGuid().ToString()+'.env')
& $exe $missing 1
if ($LASTEXITCODE -ne 0) { throw 'Missing file test failed' }
& $exe $out 2
if ($LASTEXITCODE -ne 0) { throw 'IO error test failed' }
$xdk = if ($env:XEDK) { $env:XEDK } else { 'C:/Program Files (x86)/Microsoft Xbox 360 SDK' }
& (Join-Path $xdk 'bin/win32/cl.exe') /nologo /c /TP /EHsc /MT /W4 /D_XBOX ('/I'+(Join-Path $xdk 'include/xbox')) ('/I'+$inc) ('/I'+$sharedInc) ('/Fo'+(Join-Path $out 'environment-xdk.obj')) $source
if ($LASTEXITCODE -ne 0) { throw 'XDK compilation failed' }
