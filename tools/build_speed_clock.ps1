param([string]$OutputDirectory=(Join-Path $PSScriptRoot '..\build\speed-clock-runtime'))
$ErrorActionPreference='Stop'
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$vendor=Join-Path $root 'third_party\minhook'
$directory=[IO.Path]::GetFullPath($OutputDirectory)
[IO.Directory]::CreateDirectory($directory) | Out-Null
$temporary=Join-Path $directory ('speed-clock.'+[guid]::NewGuid().ToString('N')+'.dll')
$destination=Join-Path $directory 'war3_speed_clock.dll'
$compile=@('--target=x86_64-pc-windows-msvc','-shared','-O2','-fno-stack-protector',
 '-fno-builtin','-nostdlib',(Join-Path $PSScriptRoot 'war3_speed_clock.c'),
 (Join-Path $vendor 'src\buffer.c'),(Join-Path $vendor 'src\hook.c'),
 (Join-Path $vendor 'src\trampoline.c'),(Join-Path $vendor 'src\hde\hde64.c'),
 '-o',$temporary,'-Wl,/entry:DllMain,/nodefaultlib','-lkernel32')
& clang @compile
if($LASTEXITCODE -ne 0){throw 'Speed clock compilation failed; previous image preserved'}
& python (Join-Path $PSScriptRoot 'verify_speed_clock.py') $temporary
if($LASTEXITCODE -ne 0){throw 'Speed clock verification failed; previous image preserved'}
Move-Item -LiteralPath $temporary -Destination $destination -Force
Write-Output $destination
