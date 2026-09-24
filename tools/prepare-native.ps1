# Regenerate production compiler inputs after fetching sources/dependencies and
# running setup-host-deps.ps1 and build-assets.ps1. No reference tree is written.
$ErrorActionPreference = 'Stop'
$smashPrepareRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
function Invoke-SmashPreparation {
    param([string]$Script, [string[]]$Options = @())
    Write-Output "Preparing $Script"
    & python -B -X utf8 (Join-Path $smashPrepareRoot $Script) @Options
    if ($LASTEXITCODE -ne 0) { throw "Production preparation failed: $Script" }
}
Push-Location $smashPrepareRoot
try {
    Invoke-SmashPreparation 'tools/audit_sources.py'
    Invoke-SmashPreparation 'tools/application_source_manifest.py'
    foreach ($smashStage in @('value_types','binary_reader_xdk','thread_pool_xdk','json_xdk','logging_xdk',
                              'audio_xdk','config_xdk','resources_xdk','filesystem_xdk','graphics_xdk',
                              'prism_xdk','runtime_xdk','imgui_xdk','fast3d_xdk','fast_resources_xdk',
                              'endian_xdk','crt_xdk')) {
        Invoke-SmashPreparation ("tools/prepare_$smashStage.py")
    }
    Invoke-SmashPreparation 'tools/prepare_game_xdk.py' -Options @('--source-overlay','scratch/endian-xdk/source',
        '--generated-include','scratch/generated/include','--generated-include','scratch/generated/decomp/src',
        '--keep-going','--archive')
    foreach ($smashStage in @('input_xdk','controllers_xdk','startup_xdk','gui_widgets_xdk',
                              'input_editor_xdk','gui_xdk','context_xdk','hires_xdk','libultra_xdk',
                              'postprocess_xdk','stb_xdk')) {
        Invoke-SmashPreparation ("tools/prepare_$smashStage.py")
    }
    Invoke-SmashPreparation 'tools/prepare_port_xdk.py' -Options @('--prepare-only')
    Invoke-SmashPreparation 'tools/build_native_archives.py'
} finally {
    Pop-Location
}
