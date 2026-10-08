#include "guide_ipc_envelope.h"
#include <stdint.h>
#include <stdio.h>
#include <string.h>

static uint32_t state = 0x47554944u;
static uint32_t next_u32(void) {
    state ^= state << 13; state ^= state >> 17; state ^= state << 5; return state;
}

int main(void) {
    uint8_t data[256];
    static const uint8_t seed[] = {0xA3,0x00,0x01,0x01,0xA0,0x02,0x1B,
        0x00,0x00,0x00,0x01,0x00,0x00,0x00,0x00};
    unsigned accepted = 0;
    for (unsigned round = 0; round < 250000; ++round) {
        size_t length;
        if ((round & 1u) == 0) {
            length = sizeof(seed);
            memcpy(data, seed, length);
            unsigned edits = 1u + next_u32() % 4u;
            while (edits--) data[next_u32() % length] ^= (uint8_t)(1u << (next_u32() & 7u));
        } else {
            length = next_u32() % sizeof(data);
            for (size_t i = 0; i < length; ++i) data[i] = (uint8_t)next_u32();
        }
        accepted += (unsigned)guide_ipc_validate_cbor(data, length);
    }
    printf("C_MUTATION_PASS cases=250000 accepted=%u\n", accepted);
    return 0;
}
