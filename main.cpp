#include "server.h"
#include <windows.h>
#include <thread>

extern "C" BOOL WINAPI DllMain(HINSTANCE hinstDLL, DWORD fdwReason, LPVOID lpvReserved) {
    if (fdwReason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(hinstDLL);
        std::thread(run_server).detach();
    }
    return TRUE;
}
