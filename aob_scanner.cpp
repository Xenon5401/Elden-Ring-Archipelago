#include "aob_scanner.h"
#include <windows.h>
#include <cstring>
#include <cstdlib>

struct PatternByte {
    uint8_t value;
    int wildcard;
};

static int parse_pattern(const char* hex, PatternByte* out, int max) {
    int count = 0;
    while (*hex && count < max) {
        while (*hex == ' ') hex++;
        if (!*hex) break;
        if (hex[0] == '?' && hex[1] == '?') {
            out[count].wildcard = 1;
            hex += 2;
        } else if (hex[0] == '?') {
            out[count].wildcard = 1;
            hex += 1;
        } else {
            out[count].wildcard = 0;
            out[count].value = (uint8_t)strtoul(hex, (char**)&hex, 16);
        }
        count++;
    }
    return count;
}

uintptr_t find_pattern(const char* module_name, const char* pattern_hex) {
    HMODULE hMod = GetModuleHandleA(module_name);
    if (!hMod) return 0;

    IMAGE_DOS_HEADER* dos = (IMAGE_DOS_HEADER*)hMod;
    IMAGE_NT_HEADERS* nt = (IMAGE_NT_HEADERS*)((uint8_t*)hMod + dos->e_lfanew);

    uintptr_t base = (uintptr_t)hMod;
    uintptr_t scan_start = 0;
    size_t scan_size = 0;

    IMAGE_SECTION_HEADER* sec = IMAGE_FIRST_SECTION(nt);
    for (WORD i = 0; i < nt->FileHeader.NumberOfSections; i++) {
        if (memcmp(sec->Name, ".text", 5) == 0) {
            scan_start = base + sec->VirtualAddress;
            scan_size = sec->SizeOfRawData;
            break;
        }
        sec++;
    }
    if (!scan_size) {
        scan_start = base;
        scan_size = nt->OptionalHeader.SizeOfImage;
    }

    PatternByte pat[256];
    int pat_len = parse_pattern(pattern_hex, pat, 256);
    if (pat_len == 0) return 0;

    uint8_t* scan = (uint8_t*)scan_start;
    for (size_t i = 0; i < scan_size - pat_len; i++) {
        int match = 1;
        for (int j = 0; j < pat_len; j++) {
            if (!pat[j].wildcard && scan[i + j] != pat[j].value) {
                match = 0;
                break;
            }
        }
        if (match) return scan_start + i;
    }
    return 0;
}
