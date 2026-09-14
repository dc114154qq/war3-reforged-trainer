param([string]$OutputDirectory=$PSScriptRoot,[switch]$Fixture)
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
& clang @compile
if($LASTEXITCODE -ne 0){throw "Bridge compiler failed: $LASTEXITCODE; previous artifact preserved"}
$verify='import pefile,struct,sys; p=pefile.PE(sys.argv[1]); e={s.name:s.address for s in p.DIRECTORY_ENTRY_EXPORT.symbols}; assert p.FILE_HEADER.Machine==0x8664; assert p.get_data(e[b"bridge_abi"],12)==struct.pack("<3I",0x24268010,216,608); assert all(n in e for n in (b"BridgeInstall",b"BridgeUninstall",b"BridgeHeroQuery")); assert (b"BridgeTestRun" in e)==(sys.argv[2]=="True"); print("x64 bridge ABI verified")'
& python -c $verify $temporary ([string]$Fixture.IsPresent)
if($LASTEXITCODE -ne 0){throw "Bridge ABI validation failed; previous artifact preserved"}
Move-Item -LiteralPath $temporary -Destination $destination -Force
Write-Output $destination
