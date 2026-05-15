#include "game.h"
#include "aob_scanner.h"
#include <windows.h>
#include <cstdio>
#include <cstdarg>

// --- AOB patterns (Elden Ring v1.10.0) ---
static const char* ADDITEM_PATTERN =
    "40 55 56 57 41 54 41 55 41 56 41 57 "
    "48 8D AC 24 70 FF FF FF "
    "48 81 EC 90 01 00 00 "
    "48 C7 45 C8 FE FF FF FF "
    "48 89 9C 24 D8 01 00 00";

static const char* INVENTORY_PATTERN =
    "44 8B 61 1C 41 8B FC C1 EF 07 "
    "40 80 E7 01 41 C1 EC 08 41 80 E4 01 "
    "48 8B 0D";

uintptr_t g_addItemFunc     = 0;
uintptr_t g_accessorPattern = 0;
static uint8_t* g_buffer    = nullptr;

void dbg(const char* fmt, ...) {
    char buf[512];
    va_list args;
    va_start(args, fmt);
    vsnprintf(buf, sizeof(buf), fmt, args);
    va_end(args);
    OutputDebugStringA(buf);
}

bool ensure_patterns() {
    if (g_addItemFunc && g_accessorPattern) return true;
    g_addItemFunc     = find_pattern("eldenring.exe", ADDITEM_PATTERN);
    g_accessorPattern = find_pattern("eldenring.exe", INVENTORY_PATTERN);
    if (!g_addItemFunc)     { dbg("[give] AddItemFunc pattern not found\n");     return false; }
    if (!g_accessorPattern) { dbg("[give] InventoryAccessor pattern not found\n"); return false; }
    dbg("[give] patterns resolved: func=0x%llX accessor=0x%llX\n",
        (unsigned long long)g_addItemFunc, (unsigned long long)g_accessorPattern);
    return true;
}

void* get_inventory_manager() {
    if (!g_accessorPattern) return nullptr;
    int32_t  disp = *(int32_t*)(g_accessorPattern + 0x19);
    uintptr_t rip = g_accessorPattern + 0x1D;
    void* m = *(void**)(rip + disp);
    if ((uintptr_t)m < 0x10000) return nullptr;
    return m;
}

uint8_t* get_buffer() {
    if (!g_buffer) {
        g_buffer = (uint8_t*)VirtualAlloc(nullptr, 4096, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
        if (g_buffer) ZeroMemory(g_buffer, 4096);
    }
    return g_buffer;
}
