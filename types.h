#pragma once
#include <cstdint>

#pragma pack(push, 1)
struct ItemData {
    uint32_t entryCount;
    uint32_t encodedID;
    uint32_t quantity;
    uint32_t unknown;
    int32_t  ashOfWarID;
};
#pragma pack(pop)

enum ItemType : uint32_t {
    ItemType_Weapon   = 0x0,
    ItemType_Armor    = 0x1,
    ItemType_Talisman = 0x2,
    ItemType_Goods    = 0x4,
    ItemType_AshOfWar = 0x8,
};

// Encode un item au format interne FromSoft pour AddItem.
// bits 0-27 = base_id, bits 28-31 = type_bit, + upgrade ajouté en offset.
// type_bit: 0=Weapon, 1=Armor, 2=Talisman, 4=Goods, 8=AshOfWar
static inline uint32_t encode_item_id(uint32_t base_id, uint32_t type_bit, uint32_t upgrade) {
    return (base_id | (type_bit << 28)) + upgrade;
}
