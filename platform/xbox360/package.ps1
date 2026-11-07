param([switch]$ProfileDetail, [switch]$ProfileDisabled, [switch]$TriangleTrace, [switch]$CommandTrace, [string]$Destination = "dist/Smash360")
$ErrorActionPreference = 'Stop'
if ($ProfileDetail -and $ProfileDisabled) { throw 'Choose detailed profiling or disabled profiling, not both' }
$smashRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$smashBuild = Join-Path $smashRoot 'scratch/application-xdk/native/build'
$smashPackage = Join-Path $smashRoot $Destination
$smashReceipt = Get-Content -LiteralPath (Join-Path $smashBuild 'native-link-verification.json') -Raw | ConvertFrom-Json
$smashHash = (Get-FileHash -LiteralPath (Join-Path $smashBuild 'Smash360.xex') -Algorithm SHA256).Hash
if ($smashHash -ne $smashReceipt.sha256) { throw 'Current XEX does not match the production link audit' }
$smashOptions = Get-Content -LiteralPath (Join-Path $smashBuild 'build-options.json') -Raw | ConvertFrom-Json
if ($smashOptions.sha256 -ne $smashHash) { throw 'Build options do not match this XEX' }
if ($ProfileDetail -and !$smashOptions.fullProfiling) { throw 'Rebuild with build.ps1 -FullProfiling before requesting detailed profiling' }
$smashFiles = @('Smash360.xex','f3d.o2r')
foreach ($smashFile in $smashFiles) {
    if (!(Test-Path -LiteralPath (Join-Path $smashBuild $smashFile) -PathType Leaf)) { throw "Missing runtime file: $smashFile" }
}
New-Item -ItemType Directory -Path $smashPackage -Force | Out-Null
# ROM data never ships; an older package may still hold an archive built on the PC.
Remove-Item -LiteralPath (Join-Path $smashPackage 'BattleShip.o2r') -Force -ErrorAction SilentlyContinue
$smashHashes = [ordered]@{}
foreach ($smashFile in $smashFiles) {
    $smashSource = Join-Path $smashBuild $smashFile
    $smashDestination = Join-Path $smashPackage $smashFile
    Copy-Item -LiteralPath $smashSource -Destination $smashDestination -Force
    $smashFileHash = (Get-FileHash -LiteralPath $smashDestination -Algorithm SHA256).Hash
    if ($smashFileHash -ne (Get-FileHash -LiteralPath $smashSource -Algorithm SHA256).Hash) { throw "Package copy mismatch: $smashFile" }
    $smashHashes[$smashFile] = $smashFileHash
}
# tools/build_shader_pack.py output; the XEX verifies each program and compiles at runtime without it.
$smashPack = Join-Path $smashRoot 'scratch/shader-pack/smash360.shaderpack'
$smashPackDestination = Join-Path $smashPackage 'smash360.shaderpack'
if (Test-Path -LiteralPath $smashPack -PathType Leaf) {
    Copy-Item -LiteralPath $smashPack -Destination $smashPackDestination -Force
    $smashHashes['smash360.shaderpack'] = (Get-FileHash -LiteralPath $smashPackDestination -Algorithm SHA256).Hash
} else {
    Remove-Item -LiteralPath $smashPackDestination -Force -ErrorAction SilentlyContinue
    Write-Output 'No shader pack packaged: run python tools/build_shader_pack.py first'
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
Warwing Xbox 360 package

Copy this folder intact and add your own US v1.0 Super Smash Bros. ROM (.z64,
.n64 or .v64) beside Smash360.xex. The first launch builds BattleShip.o2r from
the ROM; later launches reuse it. f3d.o2r must remain beside the XEX.
SHA256.json records the package file hashes. No ROM data, SDK files, Xenia
settings, or PC save data are included.

Back/View: enhancements. Right stick: cursor. A: click/drag. B: right-click.
LT/RT: scroll. R3: switch cursor/D-pad navigation.

Check smash360.env for this package's build and diagnostic modes. Full-profiler
scopes require a build made with build.ps1 -FullProfiling; environment switches
cannot restore compiled-out scopes. package.ps1 -ProfileDetail requests detailed
profiling and requires that build option. Command and triangle sampling are
separate options and add diagnostic overhead.

For performance comparisons, keep scene, fighters, camera, resolution, MSAA,
shader-cache state, and diagnostic settings comparable. Save the package hash
with the results. Build verification does not establish complete gameplay,
rendering, audio, or performance validation on the console.

Source and build documentation: README.md and docs/XBOX360_BUILDING.md in the
Warwing repository. Profiling: platform/xbox360/runtime/PROFILING.md.
'@ | Set-Content -LiteralPath (Join-Path $smashPackage 'README.txt') -Encoding Ascii
Write-Output "Hardware package: $smashPackage"
Write-Output "XEX SHA256: $smashHash"
