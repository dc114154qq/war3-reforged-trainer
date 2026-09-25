param([string]$OutputDirectory=$PSScriptRoot,[switch]$Fixture,[switch]$Diagnostic)
$ErrorActionPreference='Stop'
$source=Join-Path $PSScriptRoot 'war3_bridge_24268.c'
$directory=[IO.Path]::GetFullPath($OutputDirectory)
[IO.Directory]::CreateDirectory($directory) | Out-Null
$name=if($Fixture){'engine-hero-fixture.dll'}else{'war3_bridge_24268.dll'}
$temporary=Join-Path $directory (([IO.Path]::GetFileNameWithoutExtension($name))+'.'+[guid]::NewGuid().ToString('N')+'.dll')
$destination=Join-Path $directory $name
$compile=@('--target=x86_64-pc-windows-msvc','-shared','-O2','-fexceptions','-fasync-exceptions',
 '-fno-stack-protector','-fno-builtin','-nostdlib',$source,'-o',$temporary,
 '-Wl,/entry:DllMain,/nodefaultlib,/alternatename:__C_specific_handler=BridgeSpecificHandler','-luser32','-lkernel32')
if($Fixture){$compile=@('-DBRIDGE_TEST')+$compile}
if($Diagnostic){$compile=@('-DBRIDGE_DIAGNOSTIC')+$compile}
& clang @compile
if($LASTEXITCODE -ne 0){throw "Bridge compiler failed: $LASTEXITCODE; previous artifact preserved"}
$verify=Join-Path $PSScriptRoot 'verify_engine_bridge.py'
& python $verify $temporary ([string]$Fixture.IsPresent)
if($LASTEXITCODE -ne 0){throw "Bridge ABI validation failed; previous artifact preserved"}
Move-Item -LiteralPath $temporary -Destination $destination -Force
Write-Output $destination
