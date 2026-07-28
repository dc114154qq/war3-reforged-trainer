EXTERN g_original_DirectInput8Create:QWORD
EXTERN g_original_DllCanUnloadNow:QWORD
EXTERN g_original_DllGetClassObject:QWORD
EXTERN g_original_DllRegisterServer:QWORD
EXTERN g_original_DllUnregisterServer:QWORD
EXTERN g_original_GetdfDIJoystick:QWORD
EXTERN War3DInput8ProxyEnsureInitialized:PROC

PUBLIC DirectInput8Create
PUBLIC DllCanUnloadNow
PUBLIC DllGetClassObject
PUBLIC DllRegisterServer
PUBLIC DllUnregisterServer
PUBLIC GetdfDIJoystick

.code

; Preserve every volatile argument register before the one-time bootstrap.
; 0x88 bytes keeps RSP 16-byte aligned for the call and leaves the required
; 32-byte shadow space at [RSP, RSP+20h). The caller's stack arguments remain
; untouched and become visible to the real function again after ADD RSP,88h.
DINPUT_PROXY_HRESULT_WRAPPER MACRO export_name:req, original_pointer:req
export_name PROC
    sub rsp, 88h
    mov [rsp+20h], rcx
    mov [rsp+28h], rdx
    mov [rsp+30h], r8
    mov [rsp+38h], r9
    movdqu XMMWORD PTR [rsp+40h], xmm0
    movdqu XMMWORD PTR [rsp+50h], xmm1
    movdqu XMMWORD PTR [rsp+60h], xmm2
    movdqu XMMWORD PTR [rsp+70h], xmm3
    call War3DInput8ProxyEnsureInitialized
    movdqu xmm0, XMMWORD PTR [rsp+40h]
    movdqu xmm1, XMMWORD PTR [rsp+50h]
    movdqu xmm2, XMMWORD PTR [rsp+60h]
    movdqu xmm3, XMMWORD PTR [rsp+70h]
    mov rcx, [rsp+20h]
    mov rdx, [rsp+28h]
    mov r8, [rsp+30h]
    mov r9, [rsp+38h]
    add rsp, 88h
    cmp QWORD PTR [original_pointer], 0
    je export_name&_missing
    jmp QWORD PTR [original_pointer]
export_name&_missing:
    mov eax, 8007007Eh
    ret
export_name ENDP
ENDM

DINPUT_PROXY_POINTER_WRAPPER MACRO export_name:req, original_pointer:req
export_name PROC
    sub rsp, 88h
    mov [rsp+20h], rcx
    mov [rsp+28h], rdx
    mov [rsp+30h], r8
    mov [rsp+38h], r9
    movdqu XMMWORD PTR [rsp+40h], xmm0
    movdqu XMMWORD PTR [rsp+50h], xmm1
    movdqu XMMWORD PTR [rsp+60h], xmm2
    movdqu XMMWORD PTR [rsp+70h], xmm3
    call War3DInput8ProxyEnsureInitialized
    movdqu xmm0, XMMWORD PTR [rsp+40h]
    movdqu xmm1, XMMWORD PTR [rsp+50h]
    movdqu xmm2, XMMWORD PTR [rsp+60h]
    movdqu xmm3, XMMWORD PTR [rsp+70h]
    mov rcx, [rsp+20h]
    mov rdx, [rsp+28h]
    mov r8, [rsp+30h]
    mov r9, [rsp+38h]
    add rsp, 88h
    cmp QWORD PTR [original_pointer], 0
    je export_name&_missing
    jmp QWORD PTR [original_pointer]
export_name&_missing:
    xor eax, eax
    ret
export_name ENDP
ENDM

DINPUT_PROXY_HRESULT_WRAPPER DirectInput8Create, g_original_DirectInput8Create
DINPUT_PROXY_HRESULT_WRAPPER DllCanUnloadNow, g_original_DllCanUnloadNow
DINPUT_PROXY_HRESULT_WRAPPER DllGetClassObject, g_original_DllGetClassObject
DINPUT_PROXY_HRESULT_WRAPPER DllRegisterServer, g_original_DllRegisterServer
DINPUT_PROXY_HRESULT_WRAPPER DllUnregisterServer, g_original_DllUnregisterServer
DINPUT_PROXY_POINTER_WRAPPER GetdfDIJoystick, g_original_GetdfDIJoystick

END
