param(
    [string]$Xex = 'scratch/application-xdk/native/build/Warwing.xex',
    [ValidateRange(1,60)][int]$Seconds = 20,
    [switch]$KeepRunning,
    [switch]$KeyboardController,
    [switch]$TraceKernel,
    [switch]$TraceGpu,
    [ValidateSet('default','rtv','rov')][string]$RenderTargetPath = 'default'
)
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
if (![IO.Path]::IsPathRooted($Xex)) { $Xex = Join-Path $root $Xex }
$Xex = [IO.Path]::GetFullPath($Xex)
if (!$Xex.StartsWith($root+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)) {
    throw 'Only the owned Smash360 build can be launched by this script'
}
if (!(Test-Path -LiteralPath $Xex -PathType Leaf)) { throw 'No real application XEX exists yet' }
$reference = 'D:/3Shipsty/Xenia/xenia_canary.exe'
$emulatorDir = Join-Path $root 'scratch/xenia-emulator'
$storage = Join-Path $root 'scratch/xenia-storage'
$run = Join-Path $root ('scratch/xenia-runs/'+(Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
New-Item -ItemType Directory -Force $emulatorDir,$storage,$run | Out-Null
$emulator = Join-Path $emulatorDir 'xenia_canary.exe'
# Xenia is copied so config, recent-file and cache writes cannot touch references.
$expected = (Get-FileHash -LiteralPath $reference -Algorithm SHA256).Hash
if (!(Test-Path -LiteralPath $emulator) -or (Get-FileHash -LiteralPath $emulator -Algorithm SHA256).Hash -ne $expected) {
    Copy-Item -LiteralPath $reference -Destination $emulator -Force
}
[IO.File]::WriteAllText((Join-Path $emulatorDir 'portable.txt'),'')
$log = Join-Path $run 'xenia.log'
# SoH360's validated emulator flags: don't skip first-use GPU draws while host
# shaders compile; preserve full resolve/readback. No game-state advancement.
$arguments = @(('"'+$Xex+'"'),'--headless=false','--async_shader_compilation=false',
               '--readback_resolve=full','--logged_profile_slot_0_xuid=E03000006A1364EF',('--storage_root="'+$storage+'"'),('--log_file="'+$log+'"'))
if ($KeyboardController) { $arguments += '--hid=keyboard'; $arguments += '--keyboard_mode=1' }
else { $arguments += '--hid=xinput'; $arguments += '--keyboard_mode=2' }
if ($TraceKernel) { $arguments += '--log_level=3' }
if ($RenderTargetPath -ne 'default') { $arguments += ('--render_target_path_d3d12='+$RenderTargetPath) }
if ($TraceGpu) {
    $arguments += '--log_level=3'
    # This canary release compiles packet trace writing out. Kickoff stacks
    # remain available and show whether the SDK reaches the command processor.
    $arguments += '--log_ringbuffer_kickoff_initiator_bts=true'
}
# The mission explicitly requests an interactive Xenia launch for visible proof.
$process = Start-Process -FilePath $emulator -ArgumentList $arguments -WorkingDirectory $emulatorDir -WindowStyle Normal -PassThru
$record = [ordered]@{ xex=$Xex; xex_sha256=(Get-FileHash -LiteralPath $Xex -Algorithm SHA256).Hash;
    emulator=$emulator; emulator_sha256=$expected; arguments=$arguments; pid=$process.Id;
    started_utc=[DateTime]::UtcNow.ToString('o'); log=$log; visible_boot_verified=$false }
$record | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $run 'launch.json')
Start-Sleep -Seconds $Seconds
$process.Refresh()
$record['exited'] = $process.HasExited
if ($process.HasExited) { $record['exit_code'] = $process.ExitCode }
$record['log_exists'] = Test-Path -LiteralPath $log
$record | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $run 'launch.json')
if (!$KeepRunning -and !$process.HasExited) { $process.Kill(); $process.WaitForExit(5000) | Out-Null }
Write-Output ('Xenia evidence directory: '+$run)
Write-Output 'Launch capture is not visible boot verification; inspect the real runtime and framebuffer.'
