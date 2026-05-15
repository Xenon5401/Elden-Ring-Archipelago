#pragma once
#include "types.h"
#include <atomic>
#include <cstdint>

using AddItemFunc_t = void (*)(void*, ItemData*, void*, uint32_t);

extern std::atomic<uint64_t> g_itemBlockUntil;

void install_hook();
void do_give(void* mgr, ItemData* item, uint8_t* buf);
