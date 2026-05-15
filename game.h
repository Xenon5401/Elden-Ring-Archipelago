#pragma once
#include <cstdint>

// Adresses résolues depuis eldenring.exe
extern uintptr_t g_addItemFunc;
extern uintptr_t g_accessorPattern;

void     dbg(const char* fmt, ...);
bool     ensure_patterns();
void*    get_inventory_manager();
uint8_t* get_buffer();
