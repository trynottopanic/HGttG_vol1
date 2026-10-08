#define _POSIX_C_SOURCE 200809L
#include "guide_ipc_envelope.h"
#include <stdint.h>
#include <stdio.h>
#include <time.h>

static uint64_t ns(void) {
    struct timespec value;
    clock_gettime(CLOCK_MONOTONIC, &value);
    return (uint64_t)value.tv_sec * 1000000000u + value.tv_nsec;
}

int main(void) {
    static const uint8_t payload[] = {
        0xA3, 0x00, 0x01, 0x01, 0xA0, 0x02, 0x1B,
        0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00
    };
    const unsigned iterations = 1000000;
    uint64_t start = ns();
    unsigned accepted = 0;
    for (unsigned i = 0; i < iterations; ++i)
        accepted += guide_ipc_validate_cbor(payload, sizeof(payload));
    uint64_t elapsed = ns() - start;
    if (accepted != iterations) return 2;
    printf("C_PROFILE_BENCH iterations=%u elapsed_ms=%.3f ns_per_validation=%.1f\n",
           iterations, elapsed / 1000000.0, (double)elapsed / iterations);
    return 0;
}
