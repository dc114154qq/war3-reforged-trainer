#include <windows.h>

/*
 * Deliberately inert.
 *
 * Earlier builds used this DLL to run Warcraft III JASS/native functions from a
 * remote thread. Reforged is not safe under that calling convention and can
 * crash even for read-only natives. Keep the bundled DLL as a no-op so stale
 * packaging references cannot execute game code.
 */
BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)instance;
    (void)reason;
    (void)reserved;
    return TRUE;
}
