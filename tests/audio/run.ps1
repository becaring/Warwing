$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$out = Join-Path $root 'scratch/audio-xdk'
New-Item -ItemType Directory -Force -Path $out | Out-Null
& python (Join-Path $root 'tools/prepare_audio_xdk.py')
if ($LASTEXITCODE -ne 0) { throw 'Audio source generation failed' }
$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
$vs = & $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
$vcvars = Join-Path $vs 'VC/Auxiliary/Build/vcvars64.bat'
$platform = Join-Path $root 'platform/xbox360/audio'
$shipyardRoot = (& python (Join-Path $root 'tools/platform_base.py') | Select-Object -Last 1).Trim()
if ($LASTEXITCODE -ne 0) { throw 'Shipyard base verification failed' }
$shipyardSources = Join-Path $shipyardRoot 'sources'
$test = Join-Path $PSScriptRoot 'audio_tests.cpp'
$pool = Join-Path $shipyardSources 'audio/PcmBufferPool.cpp'
foreach ($variant in @('original','generated')) {
    $include = Join-Path $out ($variant+'/include')
    $player = Join-Path $out ($variant+'/AudioPlayer.cpp')
    $decoder = Join-Path $out ($variant+'/SoundMatrixDecoder.cpp')
    $exe = Join-Path $out ($variant+'-tests.exe')
    $batch = Join-Path $out ('build-'+$variant+'.cmd')
@"
@echo off
call "$vcvars" >nul
if errorlevel 1 exit /b 1
cl /nologo /std:c++17 /EHsc /W4 /WX /wd4267 /MT /I"$include" /I"$platform" /I"$shipyardRoot" /I"$shipyardSources" "$test" "$player" "$decoder" "$pool" /Fo"$out\\" /Fe"$exe"
exit /b %errorlevel%
"@ | Set-Content -LiteralPath $batch -Encoding Ascii
    & $env:ComSpec /d /c $batch 2>&1 | Tee-Object -FilePath (Join-Path $out ($variant+'-compile.log'))
    if ($LASTEXITCODE -ne 0) { throw "$variant audio host compilation failed" }
    $pcmPath = Join-Path $out ($variant+'-decoder.pcm')
    $start = New-Object System.Diagnostics.ProcessStartInfo
    $start.FileName = $exe
    $start.Arguments = '"'+$pcmPath+'"'
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    $start.RedirectStandardOutput = $true
    $start.RedirectStandardError = $true
    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $start
    [void]$process.Start()
    if (!$process.WaitForExit(30000)) { $process.Kill(); throw "$variant audio tests exceeded deadline" }
    $process.WaitForExit()
    $stdout = $process.StandardOutput.ReadToEnd()
    $stderr = $process.StandardError.ReadToEnd()
    Set-Content -LiteralPath (Join-Path $out ($variant+'-test.log')) -Value $stdout
    Set-Content -LiteralPath (Join-Path $out ($variant+'-test-errors.log')) -Value $stderr
    Write-Output $stdout
    Write-Output $stderr
    if ($process.ExitCode -ne 0) { throw "$variant audio contract tests failed" }
}
$reference = (Get-FileHash (Join-Path $out 'original-decoder.pcm')).Hash
$generated = (Get-FileHash (Join-Path $out 'generated-decoder.pcm')).Hash
if ($reference -ne $generated) { throw 'Generated decoder output differs from original source' }
Write-Output "PASS identical original/generated nonzero 32000 Hz decoder PCM: $reference"
$xdk = if ($env:XEDK) { $env:XEDK } else { 'C:/Program Files (x86)/Microsoft Xbox 360 SDK' }
$compiler = Join-Path $xdk 'bin/win32/cl.exe'
foreach ($source in @((Join-Path $out 'generated/AudioPlayer.cpp'),(Join-Path $out 'generated/SoundMatrixDecoder.cpp'),$pool,(Join-Path $shipyardSources 'audio/XAudio2AudioPlayer.cpp'),(Join-Path $platform 'shipyard_audio_services.cpp'))) {
    $obj = Join-Path $out (([IO.Path]::GetFileNameWithoutExtension($source))+'-xdk.obj')
    & $compiler /nologo /c /TP /EHsc /MT /W4 /D_XBOX /DNOMINMAX ('/I'+(Join-Path $xdk 'include/xbox')) ('/I'+(Join-Path $out 'generated/include')) ('/I'+$platform) ('/I'+(Join-Path $root 'platform/xbox360')) ('/I'+$shipyardRoot) ('/I'+$shipyardSources) ('/Fo'+$obj) $source 2>&1 | Tee-Object -FilePath ($obj+'.log')
    if ($LASTEXITCODE -ne 0) { throw "XDK audio object compile failed: $source" }
}
Write-Output 'Audio XDK object compilation only; no voice execution, XEX, or audible-output claim.'
