.intel_syntax noprefix
.text
.globl IconThunk
IconThunk:
    # Entered by jump at the verified original predicate, not a C call.
    mov rax, [rsp + 0x20]
    mov ecx, [rsp + 0x90]
    cmp ecx, [rdi + rax]
    sete dl
    or dl, sil
    movzx edx, dl
    mov r9d, [rdi + rax]
    mov r8, r12
    mov rcx, rbx
    sub rsp, 0x20
    call IconEnable
    add rsp, 0x20
    jmp qword ptr [rip + icon_resume]

#ifdef ICON_TEST
.globl IconTestThunk
.globl IconTestResume
IconTestThunk:
    push rbx
    push rsi
    push rdi
    push r12
    sub rsp, 0xa8
    mov rbx, rcx
    mov r12, rdx
    xor edi, edi
    mov [rsp + 0x20], r8
    mov [rsp + 0x90], r9d
    mov sil, byte ptr [rsp + 0xf0]
    jmp IconThunk
IconTestResume:
    add rsp, 0xa8
    pop r12
    pop rdi
    pop rsi
    pop rbx
    ret
#endif
