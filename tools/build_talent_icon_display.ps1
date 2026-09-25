param([string]$OutputDirectory=$PSScriptRoot)
$ErrorActionPreference='Stop'
$directory=[IO.Path]::GetFullPath($OutputDirectory)
[IO.Directory]::CreateDirectory($directory) | Out-Null
$temporary=Join-Path $directory ('talent-icon.'+[guid]::NewGuid().ToString('N')+'.dll')
$destination=Join-Path $directory 'war3_talent_icon_display.dll'
$compile=@('--target=x86_64-pc-windows-msvc','-shared','-O2','-fexceptions','-fasync-exceptions',
 '-fno-stack-protector','-fno-builtin','-nostdlib',
 (Join-Path $PSScriptRoot 'war3_talent_icon_display.c'),
 (Join-Path $PSScriptRoot 'war3_talent_icon_thunk.S'),'-o',$temporary,
 '-Wl,/entry:DllMain,/nodefaultlib,/alternatename:__C_specific_handler=IconSpecificHandler')
& clang @compile
if($LASTEXITCODE -ne 0){throw 'Talent icon module compilation failed; previous module preserved'}
& python (Join-Path $PSScriptRoot 'verify_talent_icon_display.py') $temporary
if($LASTEXITCODE -ne 0){throw 'Talent icon module validation failed; previous module preserved'}
Move-Item -LiteralPath $temporary -Destination $destination -Force
Write-Output $destination
