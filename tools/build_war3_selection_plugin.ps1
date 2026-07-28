param(
    [string]$OutputDirectory = "$PSScriptRoot\dinput8-plugin-build"
)

$ErrorActionPreference = 'Stop'

$visualStudio = 'C:\Program Files\Microsoft Visual Studio\2022\Community'
$vcvars = Join-Path $visualStudio 'VC\Auxiliary\Build\vcvars64.bat'
$source = Join-Path $PSScriptRoot 'war3_selection_limit_helper.c'
$runnerSource = Join-Path $PSScriptRoot 'war3_selection_selftest_runner.c'
$output = [System.IO.Path]::GetFullPath($OutputDirectory)

foreach ($path in @($vcvars, $source, $runnerSource)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Required build input not found: $path"
    }
}

New-Item -ItemType Directory -Path $output -Force | Out-Null

$commonCompile = (
    '/nologo /c /MT /W4 /WX /O2 /GS /guard:cf ' +
    '/DUNICODE /D_UNICODE ' +
    '/DWAR3_PERSISTENT_SELECTION_BREAKPOINTS_ENABLED=1'
)
$commonLink = '/nologo /dll /guard:cf /dynamicbase /nxcompat /machine:x64'
$selfTestObject = Join-Path $output 'War3SelectionPlugin_selftest.obj'
$selfTestDll = Join-Path $output 'War3SelectionPlugin_selftest.dll'
$productionObject = Join-Path $output 'War3SelectionPlugin.obj'
$productionDll = Join-Path $output 'War3SelectionPlugin.dll'
$runner = Join-Path $output 'war3_selection_selftest_runner.exe'

$commands = @(
    "cl $commonCompile /Fo`"$selfTestObject`" `"$source`"",
    (
        "link $commonLink /out:`"$selfTestDll`" " +
        "/map:`"$output\War3SelectionPlugin_selftest.map`" " +
        "`"$selfTestObject`" user32.lib"
    ),
    (
        "cl $commonCompile /DWAR3_AUTO_ENABLE_ON_LOAD=1 " +
        "/Fo`"$productionObject`" `"$source`""
    ),
    (
        "link $commonLink /out:`"$productionDll`" " +
        "/map:`"$output\War3SelectionPlugin.map`" " +
        "`"$productionObject`" user32.lib"
    ),
    (
        "cl /nologo /MT /W4 /WX /O2 /GS /guard:cf " +
        "/DUNICODE /D_UNICODE " +
        "/Fo`"$output\war3_selection_selftest_runner.obj`" " +
        "/Fe`"$runner`" `"$runnerSource`" " +
        "/link /guard:cf /dynamicbase /nxcompat"
    )
)

foreach ($command in $commands) {
    $fullCommand = "call `"$vcvars`" >nul && $command"
    & $env:ComSpec /d /s /c $fullCommand
    if ($LASTEXITCODE -ne 0) {
        throw "Build command failed with exit code ${LASTEXITCODE}: $command"
    }
}

foreach ($scenario in 0..8) {
    & $runner $selfTestDll $output $scenario
    if ($LASTEXITCODE -ne 0) {
        throw "Self-test scenario $scenario failed with exit code $LASTEXITCODE"
    }
}

[pscustomobject]@{
    Status = 'PASS'
    OutputDirectory = $output
    ProductionDll = $productionDll
    ProductionSha256 = (
        Get-FileHash -Algorithm SHA256 -LiteralPath $productionDll
    ).Hash
    SelfTestDll = $selfTestDll
    SelfTestSha256 = (
        Get-FileHash -Algorithm SHA256 -LiteralPath $selfTestDll
    ).Hash
    Scenarios = '0-8'
}
