#include "guide_foundation.h"

#include <stdint.h>
#include <stdlib.h>
#include <string.h>

int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size)
{
    struct guide_foundation state;
    uint8_t instance[16] = {1}, grant[16] = {2};
    size_t index;
    guide_foundation_init(&state, 1);
    guide_foundation_set_reconciled(&state, true);
    (void)guide_instance_admit(&state, instance, 1, 1, 1001, "9001", "guide-app-9001-1.service");
    for (index = 0; index < size; ++index) {
        switch (data[index] % 5u) {
        case 0: (void)guide_instance_transition(&state, instance, 1, (enum guide_lifecycle_phase)(data[index] % 10u)); break;
        case 1: grant[15] = data[index]; (void)guide_grant_issue(&state, grant, instance, 1, 1, 1u, (uint64_t)index + 1u); break;
        case 2: (void)guide_grant_validate(&state, grant, instance, 1, 1, 1, index); break;
        case 3: (void)guide_grant_revoke(&state, grant); break;
        default: guide_foundation_set_reconciled(&state, (data[index] & 1u) != 0); break;
        }
    }
    return 0;
}
