#include "hook.h"
#include "game.h"
#include "flag.h"
#include <windows.h>
#include <cstring>

std::atomic<uint64_t> g_itemBlockUntil{0};
static bool   g_bypass_block  = false;
static bool   g_hook_installed  = false;
static uint8_t g_original_bytes[12];

static void addItemHook(void* mgr, ItemData* data, void* buf, uint32_t flags);

static void call_original(void* mgr, ItemData* data, void* buf, uint32_t flags) {
    DWORD old;
    VirtualProtect((void*)g_addItemFunc, 12, PAGE_EXECUTE_READWRITE, &old);
    memcpy((void*)g_addItemFunc, g_original_bytes, 12);
    VirtualProtect((void*)g_addItemFunc, 12, old, &old);

    ((AddItemFunc_t)g_addItemFunc)(mgr, data, buf, flags);

    uint8_t patch[12];
    uintptr_t hook_addr = (uintptr_t)&addItemHook;
    patch[0] = 0x48; patch[1] = 0xB8;
    memcpy(patch + 2, &hook_addr, 8);
    patch[10] = 0xFF; patch[11] = 0xE0;

    VirtualProtect((void*)g_addItemFunc, 12, PAGE_EXECUTE_READWRITE, &old);
    memcpy((void*)g_addItemFunc, patch, 12);
    VirtualProtect((void*)g_addItemFunc, 12, old, &old);
}

static void __attribute__((noinline)) addItemHook(void* mgr, ItemData* data, void* buf, uint32_t flags) {
    if (g_bypass_block) {
        call_original(mgr, data, buf, flags);
        return;
    }
    if (GetTickCount64() < g_itemBlockUntil.load())
        return;
    call_original(mgr, data, buf, flags);
}

void install_hook() {
    if (g_hook_installed) return;
    DWORD old;
    VirtualProtect((void*)g_addItemFunc, 12, PAGE_EXECUTE_READWRITE, &old);
    memcpy(g_original_bytes, (void*)g_addItemFunc, 12);

    uint8_t patch[12];
    uintptr_t hook_addr = (uintptr_t)&addItemHook;
    patch[0] = 0x48; patch[1] = 0xB8;
    memcpy(patch + 2, &hook_addr, 8);
    patch[10] = 0xFF; patch[11] = 0xE0;

    memcpy((void*)g_addItemFunc, patch, 12);
    VirtualProtect((void*)g_addItemFunc, 12, old, &old);
    g_hook_installed = true;
    dbg("[hook] installed at 0x%llX\n", (unsigned long long)g_addItemFunc);
}

void do_give(void* mgr, ItemData* item, uint8_t* buf) {
    if (!g_hook_installed) install_hook();
    if (!g_flag_hook_installed) install_flag_hook();
    g_bypass_block = true;
    ((AddItemFunc_t)g_addItemFunc)(mgr, item, buf, 0);
    g_bypass_block = false;
}
