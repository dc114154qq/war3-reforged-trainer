param(
    [string]$OutputDirectory = "$PSScriptRoot\dinput8-marker-build"
)

$ErrorActionPreference = 'Stop'

$visualStudio = 'C:\Program Files\Microsoft Visual Studio\2022\Community'
$vcvars = Join-Path $visualStudio 'VC\Auxiliary\Build\vcvars64.bat'
$systemDInput = Join-Path $env:SystemRoot 'System32\DINPUT8.dll'
$output = [System.IO.Path]::GetFullPath($OutputDirectory)

if (-not (Test-Path -LiteralPath $vcvars -PathType Leaf)) {
    throw "vcvars64.bat not found: $vcvars"
}
if (-not (Test-Path -LiteralPath $systemDInput -PathType Leaf)) {
    throw "System DINPUT8.dll not found: $systemDInput"
}

New-Item -ItemType Directory -Path $output -Force | Out-Null
Copy-Item -LiteralPath $systemDInput -Destination (Join-Path $output 'DINPUT8Original.dll') -Force

$signature = Get-AuthenticodeSignature -LiteralPath (Join-Path $output 'DINPUT8Original.dll')
if ($signature.Status -ne 'Valid') {
    throw "Copied system DINPUT8 signature is not valid: $($signature.Status)"
}

$commands = @(
    "cl /nologo /c /W4 /WX /O2 /GS /guard:cf /DUNICODE /D_UNICODE /Fo`"$output\war3_dinput8_proxy.obj`" `"$PSScriptRoot\war3_dinput8_proxy.c`"",
    "ml64 /nologo /c /W3 /WX /Fo`"$output\war3_dinput8_proxy_asm.obj`" `"$PSScriptRoot\war3_dinput8_proxy.asm`"",
    "link /nologo /dll /out:`"$output\DINPUT8.dll`" /def:`"$PSScriptRoot\war3_dinput8_proxy.def`" /map:`"$output\DINPUT8.map`" /guard:cf /dynamicbase /nxcompat /machine:x64 `"$output\war3_dinput8_proxy.obj`" `"$output\war3_dinput8_proxy_asm.obj`" kernel32.lib",
    "cl /nologo /W4 /WX /O2 /GS /guard:cf /DUNICODE /D_UNICODE /Fe`"$output\war3_dinput8_proxy_smoke.exe`" `"$PSScriptRoot\war3_dinput8_proxy_smoke.c`" /link /guard:cf /dynamicbase /nxcompat"
)

foreach ($command in $commands) {
    $fullCommand = "call `"$vcvars`" >nul && $command"
    & $env:ComSpec /d /s /c $fullCommand
    if ($LASTEXITCODE -ne 0) {
        throw "Build command failed with exit code ${LASTEXITCODE}: $command"
    }
}

$marker = Join-Path $output 'war3_dinput8_proxy_loaded.bin'
Remove-Item -LiteralPath $marker -Force -ErrorAction SilentlyContinue
& (Join-Path $output 'war3_dinput8_proxy_smoke.exe') (Join-Path $output 'DINPUT8.dll')
if ($LASTEXITCODE -ne 0) {
    throw "Proxy smoke test failed with exit code $LASTEXITCODE"
}
if (-not (Test-Path -LiteralPath $marker -PathType Leaf)) {
    throw "Proxy smoke test did not create the load marker"
}

$markerBytes = [System.IO.File]::ReadAllBytes($marker)
if ($markerBytes.Length -ne 24) {
    throw "Unexpected marker length: $($markerBytes.Length)"
}

[pscustomobject]@{
    Status = 'PASS'
    OutputDirectory = $output
    ProxySha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $output 'DINPUT8.dll')).Hash
    OriginalSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $output 'DINPUT8Original.dll')).Hash
    MarkerMagic = ('0x{0:X8}' -f [BitConverter]::ToUInt32($markerBytes, 0))
    MarkerVersion = [BitConverter]::ToUInt32($markerBytes, 4)
    PluginLoaded = [BitConverter]::ToUInt32($markerBytes, 16)
    LastError = [BitConverter]::ToUInt32($markerBytes, 20)
}
