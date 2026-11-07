param(
    [switch]$Rebuild,
    [switch]$Regenerate,
    [switch]$PrepareOnly,
    [switch]$FullProfiling,
    [ValidateSet('Smash360','Libultraship360')][string]$Project = 'Smash360',
    [string]$CompileOnly = ''
)
$ErrorActionPreference = 'Stop'
$smashRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$smashNative = Join-Path $smashRoot 'scratch\application-xdk\native'
$env:TEMP = Join-Path $smashNative 'tmp'
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Force -Path $env:TEMP,(Join-Path $smashNative 'logs') | Out-Null
$smashSdk = if ($env:XEDK) { $env:XEDK } else { 'C:\Program Files (x86)\Microsoft Xbox 360 SDK' }
if (!(Test-Path -LiteralPath (Join-Path $smashSdk 'bin\win32\cl.exe'))) { throw "Xbox SDK compiler missing: $smashSdk" }
if ($Regenerate) { & (Join-Path $smashRoot 'tools\prepare-native.ps1') }
& python -B -X utf8 (Join-Path $smashRoot 'tools\prepare_application_xdk.py')
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& python -B -X utf8 (Join-Path $smashRoot 'tools\prepare_application_xdk.py') --verify
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$shipyardRoot = & python -B -X utf8 (Join-Path $smashRoot 'tools\platform_base.py')
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
if ($PrepareOnly) { exit 0 }
if ($CompileOnly) {
    $smashItems = Get-Content -LiteralPath (Join-Path $smashNative 'project-items.json') -Raw | ConvertFrom-Json
    if (!($smashItems.$Project.path -contains $CompileOnly)) { throw "CompileOnly source is not a production item in ${Project}: $CompileOnly" }
}
$smashMsbuild = 'C:\Windows\Microsoft.NET\Framework\v4.0.30319\MSBuild.exe'
if (!(Test-Path -LiteralPath $smashMsbuild)) { throw "SDK-compatible MSBuild missing: $smashMsbuild" }
if ($CompileOnly) {
    $smashArguments = @((Join-Path $PSScriptRoot "$Project.vcxproj"), '/t:ClCompile', '/p:Configuration=Release', '/p:Platform=Xbox 360',
        '/p:PlatformToolset=2010-01', "/p:TargetPlatformSdkPath=$smashSdk", '/p:VCTargetsPath=C:\Program Files (x86)\MSBuild\Microsoft.Cpp\v4.0',
        '/verbosity:minimal', '/nologo', '/fl', "/flp:logfile=$smashNative\logs\$Project.log;verbosity=normal",
        "/p:SmashCompileOnly=$CompileOnly", '/p:BuildProjectReferences=false',
        "/p:SmashFullProfiling=$([int][bool]$FullProfiling)", "/p:ShipyardRoot=$shipyardRoot")
    & $smashMsbuild @smashArguments
    $smashExit = $LASTEXITCODE
} else {
    $smashArguments = @('-B', '-X', 'utf8', (Join-Path $smashRoot 'tools\build_parallel_xdk.py'), '--build', '--project', $Project, '--jobs', '8')
    if ($Rebuild) { $smashArguments += '--rebuild' }
    if ($FullProfiling) { $smashArguments += '--full-profiling' }
    & python @smashArguments
    $smashExit = $LASTEXITCODE
}
if ($smashExit -ne 0) { exit $smashExit }
if ($Project -eq 'Smash360' -and !$CompileOnly) {
    $smashOutput = Join-Path $smashNative 'build'
    if (!(Test-Path -LiteralPath (Join-Path $smashOutput 'Smash360.xex'))) { throw 'SDK build returned without the application XEX' }
    & python -B -X utf8 (Join-Path $smashRoot 'tools\verify_native_link.py')
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & python -B -X utf8 (Join-Path $smashRoot 'tests\logging\check_xdk_control_flow.py')
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & python -B -X utf8 (Join-Path $smashRoot 'tests\graphics\check_rdp_value_init.py') --output-dir (Join-Path $smashNative 'logs') --label rdp-value-init
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    # BattleShip.o2r holds ROM data, so the XEX builds it on first launch from the player's ROM.
    $smashAsset = Join-Path $smashRoot 'scratch\assets\f3d.o2r'
    if (!(Test-Path -LiteralPath $smashAsset)) { throw "Required host-generated archive missing: $smashAsset" }
    Copy-Item -LiteralPath $smashAsset -Destination (Join-Path $smashOutput 'f3d.o2r') -Force
    @{ fullProfiling = [bool]$FullProfiling; sha256 = (Get-FileHash -LiteralPath (Join-Path $smashOutput 'Smash360.xex')).Hash } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $smashOutput 'build-options.json') -Encoding Ascii
}
exit 0
