#include "flag.h"
#include "game.h"
#include "hook.h"
#include "aob_scanner.h"
#include <windows.h>
#include <cstring>

// --- AOB patterns (Elden Ring v1.12, du CT HeXinton) ---

static const char* EVENTFLAG_FUNC_PATTERN =
    "48 89 5C 24 08 48 89 74 24 18 57 48 83 EC 30 "
    "48 8B DA 41 0F B6 F8 8B 12 48 8B F1 85 D2 "
    "0F 84 ?? ?? ?? ??";

FlagEventQueue               g_flagQueue;
uintptr_t                    g_eventFlagFunc = 0;
std::unordered_set<uint32_t> g_FlagLoot;
std::unordered_set<uint32_t> g_WatchedFlag;

bool           g_flag_hook_installed = false;
static uint8_t g_original_flag_bytes[15];

using EventFlagFunc_t = void (*)(void*, uint32_t*, uint8_t);

static void eventFlagHook(void*, uint32_t*, uint8_t);

bool ensure_flag_patterns() {
    if (g_eventFlagFunc) return true;
    g_eventFlagFunc = find_pattern("eldenring.exe", EVENTFLAG_FUNC_PATTERN);
    if (!g_eventFlagFunc) {
        dbg("[flag] EventFlagFunc pattern not found\n");
        return false;
    }
    dbg("[flag] EventFlagFunc resolved at 0x%llX\n",
        (unsigned long long)g_eventFlagFunc);
    return true;
}

static void call_original_event_flag(void* mgr, uint32_t* flagId, uint8_t value) { // Call the original function by restoring bytes
    DWORD old;
    VirtualProtect((void*)g_eventFlagFunc, 15, PAGE_EXECUTE_READWRITE, &old);
    memcpy((void*)g_eventFlagFunc, g_original_flag_bytes, 15);
    VirtualProtect((void*)g_eventFlagFunc, 15, old, &old);

    ((EventFlagFunc_t)g_eventFlagFunc)(mgr, flagId, value);

    uint8_t patch[15];
    uintptr_t hook_addr = (uintptr_t)&eventFlagHook;
    patch[0] = 0x48; patch[1] = 0xB8;
    memcpy(patch + 2, &hook_addr, 8);
    patch[10] = 0xFF; patch[11] = 0xE0;
    patch[12] = 0x90; patch[13] = 0x90; patch[14] = 0x90;

    VirtualProtect((void*)g_eventFlagFunc, 15, PAGE_EXECUTE_READWRITE, &old);
    memcpy((void*)g_eventFlagFunc, patch, 15);
    VirtualProtect((void*)g_eventFlagFunc, 15, old, &old);
}

static void __attribute__((noinline)) eventFlagHook(void* mgr, uint32_t* flagId, uint8_t value) {
    uint32_t id = *flagId;
    bool loot  = g_FlagLoot.count(id);
    bool watch = g_WatchedFlag.count(id);

    if (loot || watch) {
        g_flagQueue.push({id, value});
    }

    if (loot && value && GetTickCount64() >= g_itemBlockUntil.load()) {
        g_itemBlockUntil.store(GetTickCount64() + 40);
        dbg("[flag] loot flag %u set, blocking items\n", id);
    }

    call_original_event_flag(mgr, flagId, value);
}

void install_flag_hook() {
    if (g_flag_hook_installed) return;
    if (!ensure_flag_patterns()) return;

    DWORD old;
    VirtualProtect((void*)g_eventFlagFunc, 15, PAGE_EXECUTE_READWRITE, &old);
    memcpy(g_original_flag_bytes, (void*)g_eventFlagFunc, 15);

    uint8_t patch[15];
    uintptr_t hook_addr = (uintptr_t)&eventFlagHook;
    patch[0] = 0x48; patch[1] = 0xB8;
    memcpy(patch + 2, &hook_addr, 8);
    patch[10] = 0xFF; patch[11] = 0xE0;
    patch[12] = 0x90; patch[13] = 0x90; patch[14] = 0x90;

    memcpy((void*)g_eventFlagFunc, patch, 15);
    VirtualProtect((void*)g_eventFlagFunc, 15, old, &old);

    g_flag_hook_installed = true;
    dbg("[flag] hook installed at 0x%llX\n", (unsigned long long)g_eventFlagFunc);
}
