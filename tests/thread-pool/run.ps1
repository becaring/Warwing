param([switch]$HostOnly)
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$output = Join-Path $root 'scratch/thread-pool-xdk'
New-Item -ItemType Directory -Force -Path $output | Out-Null
& python (Join-Path $PSScriptRoot 'test_generator.py')
if ($LASTEXITCODE -ne 0) { throw 'BS generator behavior tests failed' }
& python (Join-Path $root 'tools/prepare_thread_pool_xdk.py')
if ($LASTEXITCODE -ne 0) { throw 'BS generation failed' }
$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
$vs = & $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if (!$vs) { throw 'Host MSVC required' }
$vcvars = Join-Path $vs 'VC/Auxiliary/Build/vcvars64.bat'
$async = Join-Path $root 'platform/xbox360/cpp-compat/async'
$shipyardRoot = Join-Path (Split-Path $root -Parent) 'LibUltraShip+Fast3D360'
$shipyard = Join-Path $shipyardRoot 'sources'
$support = Join-Path $root 'platform/xbox360/cpp-compat/thread-pool'
$test = Join-Path $PSScriptRoot 'pool_tests.cpp'
$native = Join-Path $shipyard 'async/native.cpp'
foreach ($variant in @('generated','upstream')) {
    $include = if ($variant -eq 'generated') { $output } else { Join-Path $root 'upstream/dependencies/thread-pool/include' }
    $define = if ($variant -eq 'upstream') { '/DTEST_UPSTREAM /std:c++17' } else { '' }
    $exe = Join-Path $output ($variant+'-tests.exe')
    $batch = Join-Path $output ('build-'+$variant+'.cmd')
@"
@echo off
call "$vcvars" >nul
if errorlevel 1 exit /b 1
cl /nologo /EHsc /W4 /WX /MT $define /I"$include" /I"$async" /I"$support" /I"$shipyardRoot" /I"$shipyard" "$test" "$native" /Fo"$output\\" /Fe"$exe"
exit /b %errorlevel%
"@ | Set-Content -LiteralPath $batch -Encoding Ascii
    & $env:ComSpec /d /c $batch 2>&1 | Tee-Object -FilePath (Join-Path $output ($variant+'-compile.log'))
    if ($LASTEXITCODE -ne 0) { throw "$variant host compilation failed" }
    $start = New-Object System.Diagnostics.ProcessStartInfo
    $start.FileName = $exe
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    $start.RedirectStandardOutput = $true
    $start.RedirectStandardError = $true
    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $start
    [void]$process.Start()
    if (!$process.WaitForExit(30000)) { $process.Kill(); throw "$variant tests deadlocked" }
    $process.WaitForExit()
    $stdout = $process.StandardOutput.ReadToEnd()
    $stderr = $process.StandardError.ReadToEnd()
    Set-Content -LiteralPath (Join-Path $output ($variant+'-test.log')) -Value $stdout
    Set-Content -LiteralPath (Join-Path $output ($variant+'-errors.log')) -Value $stderr
    Write-Output $stdout
    if ($stderr) { Write-Output $stderr }
    if ($process.ExitCode -ne 0) { throw "$variant tests failed (exit $($process.ExitCode))" }
}
$negative = Join-Path $PSScriptRoot 'unsupported.cpp'
$negativeBatch = Join-Path $output 'reject-unsupported.cmd'
@"
@echo off
call "$vcvars" >nul
if errorlevel 1 exit /b 1
cl /nologo /EHsc /MT /c /I"$output" /I"$async" /I"$support" /I"$shipyardRoot" /I"$shipyard" "$negative" /Fo"$output\unsupported.obj"
exit /b %errorlevel%
"@ | Set-Content -LiteralPath $negativeBatch -Encoding Ascii
$negativeLog = Join-Path $output 'unsupported-compile.log'
& $env:ComSpec /d /c $negativeBatch 2>&1 | Out-File -LiteralPath $negativeLog
if ($LASTEXITCODE -eq 0) { throw 'Unsupported reset API was silently accepted' }
if (!(Select-String -LiteralPath $negativeLog -Pattern "C2039: 'reset'" -Quiet)) { throw 'Negative API compilation failed for an unexpected reason' }
Write-Output 'PASS unsupported reset API rejected with missing-member diagnostic'
if (!$HostOnly) {
    $xdk = if ($env:XEDK) { $env:XEDK } else { 'C:/Program Files (x86)/Microsoft Xbox 360 SDK' }
    $compiler = Join-Path $xdk 'bin/win32/cl.exe'
    foreach ($source in @($test,$native)) {
        $object = Join-Path $output (([IO.Path]::GetFileNameWithoutExtension($source))+'-xdk.obj')
        & $compiler /nologo /TP /D_XBOX /D_WIN32 /EHsc /MT /W4 /c ('/I'+(Join-Path $xdk 'include/xbox')) ('/I'+$output) ('/I'+$async) ('/I'+$support) ('/I'+$shipyardRoot) ('/I'+$shipyard) ('/Fo'+$object) $source 2>&1 | Tee-Object -FilePath ($object+'.log')
        if ($LASTEXITCODE -ne 0) { throw "XDK object compile failed: $source" }
    }
    Write-Output 'BS pool XDK objects only; no XEX, Xbox runtime or ResourceManager integration claim.'
}
