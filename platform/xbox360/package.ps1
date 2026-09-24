param([switch]$ProfileDetail, [switch]$ProfileDisabled, [switch]$TriangleTrace, [switch]$CommandTrace)
$ErrorActionPreference = 'Stop'
if ($ProfileDetail -and $ProfileDisabled) { throw 'Choose detailed profiling or disabled profiling, not both' }
$smashRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$smashBuild = Join-Path $smashRoot 'scratch/application-xdk/native/build'
$smashPackage = Join-Path $smashRoot 'dist/Smash360'
$smashReceipt = Get-Content -LiteralPath (Join-Path $smashBuild 'native-link-verification.json') -Raw | ConvertFrom-Json
$smashHash = (Get-FileHash -LiteralPath (Join-Path $smashBuild 'Smash360.xex') -Algorithm SHA256).Hash
if ($smashHash -ne $smashReceipt.sha256) { throw 'Current XEX does not match the production link audit' }
$smashOptions = Get-Content -LiteralPath (Join-Path $smashBuild 'build-options.json') -Raw | ConvertFrom-Json
if ($smashOptions.sha256 -ne $smashHash) { throw 'Build options do not match this XEX' }
if ($ProfileDetail -and !$smashOptions.fullProfiling) { throw 'Rebuild with build.ps1 -FullProfiling before requesting detailed profiling' }
$smashFiles = @('Smash360.xex','BattleShip.o2r','f3d.o2r')
foreach ($smashFile in $smashFiles) {
    if (!(Test-Path -LiteralPath (Join-Path $smashBuild $smashFile) -PathType Leaf)) { throw "Missing runtime file: $smashFile" }
}
New-Item -ItemType Directory -Path $smashPackage -Force | Out-Null
$smashHashes = [ordered]@{}
foreach ($smashFile in $smashFiles) {
    $smashSource = Join-Path $smashBuild $smashFile
    $smashDestination = Join-Path $smashPackage $smashFile
    Copy-Item -LiteralPath $smashSource -Destination $smashDestination -Force
    $smashFileHash = (Get-FileHash -LiteralPath $smashDestination -Algorithm SHA256).Hash
    if ($smashFileHash -ne (Get-FileHash -LiteralPath $smashSource -Algorithm SHA256).Hash) { throw "Package copy mismatch: $smashFile" }
    $smashHashes[$smashFile] = $smashFileHash
}
# Keep diagnostic overrides out of the hardware package, including on reruns.
$smashProfileEnv = "# Full profiler compiled in: $($smashOptions.fullProfiling). Requires build.ps1 -FullProfiling to enable.`r`n# SMASH360_PROFILE=0 runtime-disables compiled-in scopes; triangle sampling is independent.`r`n"
if ($ProfileDetail) { $smashProfileEnv += "SMASH360_PROFILE_DETAIL=1`r`n" }
if ($ProfileDisabled) { $smashProfileEnv += "SMASH360_PROFILE=0`r`nSMASH360_PROFILE_DETAIL=0`r`n" }
if ($TriangleTrace) { $smashProfileEnv += "SMASH360_TRIANGLE_TRACE=1`r`n" }
if ($CommandTrace) { $smashProfileEnv += "SMASH360_COMMAND_TRACE=1`r`n" }
[IO.File]::WriteAllText((Join-Path $smashPackage 'smash360.env'), $smashProfileEnv)
$smashHashes['smash360.env'] = (Get-FileHash -LiteralPath (Join-Path $smashPackage 'smash360.env') -Algorithm SHA256).Hash
$smashHashes | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $smashPackage 'SHA256.json') -Encoding Ascii
@'
Smash360 hardware test package

Copy this folder intact. Launch Smash360.xex on your homebrew-capable Xbox 360.
BattleShip.o2r and f3d.o2r must remain beside the XEX.
No Xenia settings or PC save data are included. Native boot and gameplay have
been observed on physical Xbox 360; performance/audio and broader testing remain.

Back/View: enhancements. Right stick: cursor. A: click/drag. B: right-click.
LT/RT: scroll. R3: switch cursor/D-pad navigation.

Start hardware comparisons at 100% internal resolution and native 1x MSAA.
Then test resolution and 2x/4x MSAA separately. Audio/pacing issues remain open.
This build transfers current SoH vertex, lighting, shader/material reuse,
texture-binding and native XDK optimizations through BattleShip's real runtime.
Smash near-plane clipping, positional lights, fog/blend alpha, framebuffer UVs,
resource content verification and the game's scheduler remain authoritative.
The latest appended hardware run had mixed heavy windows around 56/55 FPS;
that does not isolate the full Yoshi scene. No speed result is claimed for this
new package yet. FRAME_WORKLOAD separates frames by command-count bands.

Full-profiler scopes remain compiled out. FRAME timing and optional command/
triangle samplers remain available; sampling adds diagnostic overhead.
This build passes native XDK/link guards and differential contract tests.
Console performance and visual validation of these new changes are pending.
Check smash360.env for this package's build and diagnostic modes.
Repeat the fully populated Yoshi intro test and return the log.
For full opcode/bounds/reloc attribution first rebuild with build.ps1
-FullProfiling, then package.ps1 -ProfileDetail. Environment switches cannot
restore compiled-out scopes. Match build and env modes in comparisons.
Source/build instructions and evidence: D:\Projects\Smash360\BRINGUP.md
'@ | Set-Content -LiteralPath (Join-Path $smashPackage 'README.txt') -Encoding Ascii
Write-Output "Hardware package: $smashPackage"
Write-Output "XEX SHA256: $smashHash"
