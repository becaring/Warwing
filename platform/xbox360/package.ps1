param([switch]$ProfileDetail, [switch]$ProfileDisabled, [switch]$TriangleTrace, [switch]$CommandTrace, [switch]$Zip, [Parameter(Mandatory)][string]$Destination)
$ErrorActionPreference = 'Stop'
if ($ProfileDetail -and $ProfileDisabled) { throw 'Choose detailed profiling or disabled profiling, not both' }
$smashRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$smashBuild = Join-Path $smashRoot 'scratch/application-xdk/native/build'
$smashPackage = [IO.Path]::GetFullPath((Join-Path $smashRoot $Destination))
$smashReceipt = Get-Content -LiteralPath (Join-Path $smashBuild 'native-link-verification.json') -Raw | ConvertFrom-Json
$smashHash = (Get-FileHash -LiteralPath (Join-Path $smashBuild 'Warwing.xex') -Algorithm SHA256).Hash
if ($smashHash -ne $smashReceipt.sha256) { throw 'Current XEX does not match the production link audit' }
$smashOptions = Get-Content -LiteralPath (Join-Path $smashBuild 'build-options.json') -Raw | ConvertFrom-Json
if ($smashOptions.sha256 -ne $smashHash) { throw 'Build options do not match this XEX' }
if ($ProfileDetail -and !$smashOptions.fullProfiling) { throw 'Rebuild with build.ps1 -FullProfiling before requesting detailed profiling' }
# The game folder holds only what the console loads; README.txt and SHA256SUMS.txt sit beside it.
if (Test-Path -LiteralPath $smashPackage) { throw "Package folder exists: $smashPackage" }
if ($Zip -and (Test-Path -LiteralPath "$smashPackage.zip")) { throw "Package zip exists: $smashPackage.zip" }
# A binary release must carry the license text of every component compiled into it.
$shipyardRoot = & python -B -X utf8 (Join-Path $smashRoot 'tools\platform_base.py')
if ($LASTEXITCODE -ne 0) { throw 'Shipyard checkout not found' }
$smashLicenseList = Get-Content -LiteralPath (Join-Path $smashRoot 'release-licenses.json') -Raw | ConvertFrom-Json
$smashLicenses = @()
foreach ($smashSet in @(@($smashLicenseList.repository, $smashRoot), @($smashLicenseList.platform, $shipyardRoot))) {
    foreach ($smashEntry in $smashSet[0].PSObject.Properties) {
        $smashSource = Join-Path $smashSet[1] $smashEntry.Value
        if (!(Test-Path -LiteralPath $smashSource -PathType Leaf)) { throw "Missing license file: $smashSource" }
        $smashLicenses += ,@($smashEntry.Name, $smashSource)
    }
}
$smashGame = Join-Path $smashPackage 'Warwing'
New-Item -ItemType Directory -Path (Join-Path $smashGame 'shaders') -Force | Out-Null
foreach ($smashFile in @('Warwing.xex','f3d.o2r')) {
    $smashSource = Join-Path $smashBuild $smashFile
    if (!(Test-Path -LiteralPath $smashSource -PathType Leaf)) { throw "Missing runtime file: $smashFile" }
    Copy-Item -LiteralPath $smashSource -Destination (Join-Path $smashGame $smashFile)
}
# tools/build_shader_pack.py output; the XEX verifies each program and compiles at runtime without it.
$smashPack = Join-Path $smashRoot 'scratch/shader-pack/warwing.shaderpack'
if (Test-Path -LiteralPath $smashPack -PathType Leaf) {
    Copy-Item -LiteralPath $smashPack -Destination (Join-Path $smashGame 'shaders/warwing.shaderpack')
} else {
    Write-Output 'No shader pack packaged: run python tools/build_shader_pack.py first'
}
$smashProfileEnv = "# Full profiler compiled in: $($smashOptions.fullProfiling). Requires build.ps1 -FullProfiling to enable.`r`n# WARWING_PROFILE=0 runtime-disables compiled-in scopes; triangle sampling is independent.`r`n"
if ($ProfileDetail) { $smashProfileEnv += "WARWING_PROFILE_DETAIL=1`r`n" }
if ($ProfileDisabled) { $smashProfileEnv += "WARWING_PROFILE=0`r`nWARWING_PROFILE_DETAIL=0`r`n" }
if ($TriangleTrace) { $smashProfileEnv += "WARWING_TRIANGLE_TRACE=1`r`n" }
if ($CommandTrace) { $smashProfileEnv += "WARWING_COMMAND_TRACE=1`r`n" }
[IO.File]::WriteAllText((Join-Path $smashGame 'warwing.env'), $smashProfileEnv)
$smashLicenseFolder = Join-Path $smashPackage 'licenses'
New-Item -ItemType Directory -Path $smashLicenseFolder | Out-Null
foreach ($smashLicense in $smashLicenses) { Copy-Item -LiteralPath $smashLicense[1] -Destination (Join-Path $smashLicenseFolder $smashLicense[0]) }
$smashPackaged = @(Get-ChildItem -LiteralPath $smashGame -Recurse -File) + @(Get-ChildItem -LiteralPath $smashLicenseFolder -File)
$smashSums = foreach ($smashItem in $smashPackaged | Sort-Object FullName) {
    $smashRelative = $smashItem.FullName.Substring($smashPackage.Length + 1).Replace('\', '/')
    (Get-FileHash -LiteralPath $smashItem.FullName -Algorithm SHA256).Hash.ToLower() + '  ' + $smashRelative
}
[IO.File]::WriteAllText((Join-Path $smashPackage 'SHA256SUMS.txt'), (($smashSums -join "`n") + "`n"))
@'
Warwing for Xbox 360

Copy the Warwing folder to your console and put your own US v1.0 Super Smash
Bros. ROM (.z64, .n64 or .v64) beside Warwing.xex. The first launch builds the
game data from your ROM, and later launches reuse it. The package contains no
ROM data. SHA256SUMS.txt lists the hashes of the files in the Warwing folder.

Back opens or closes the menu. The right stick moves the cursor, A clicks or
drags, B right-clicks, LT and RT scroll, and R3 switches between the cursor and
D-pad navigation.

To report a problem, open a bug report at
https://github.com/becaring/Warwing/issues and attach warwing.log from the
Warwing folder.

warwing.env holds diagnostic settings. docs/BUILDING.md in the repository
explains them.

The licenses folder holds the licenses of Warwing, Shipyard and the components
they include.
'@ | Set-Content -LiteralPath (Join-Path $smashPackage 'README.txt') -Encoding Ascii
Write-Output "Hardware package: $smashPackage"
# Python's zipfile writes forward-slash entry names; Windows PowerShell's Compress-Archive writes backslashes.
if ($Zip) {
    & python -B -c 'import shutil, sys; print(shutil.make_archive(sys.argv[1], ''zip'', sys.argv[1]))' $smashPackage
    if ($LASTEXITCODE -ne 0) { throw 'Package zip failed' }
}
Write-Output "XEX SHA256: $smashHash"
