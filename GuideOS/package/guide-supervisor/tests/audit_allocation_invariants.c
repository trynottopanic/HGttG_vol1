/* Deterministic wide-integer audit; checks observable accounting invariants. */
#include "guide_resource_policy.h"
#include <assert.h>
#include <inttypes.h>
#include <stdio.h>

static uint64_t state = UINT64_C(0x20260924b7a501e3);
static uint64_t random64(void) {
    state ^= state << 13;
    state ^= state >> 7;
    state ^= state << 17;
    return state;
}
static uint64_t min64(uint64_t a, uint64_t b) { return a < b ? a : b; }
int main(void) {
    const unsigned weights[5] = {0, 8, 4, 2, 1};
    unsigned successes = 0, shortfalls = 0;
    for (unsigned run = 0; run < 1000000; ++run) {
        uint64_t capacity = random64();
        uint64_t reserve = (run % 3) ? 0 : min64(random64(), capacity);
        struct guide_tier_budget tiers[5];
        struct guide_capacity_plan plan;
        for (unsigned i = 0; i < 5; ++i) {
            uint64_t ceiling = random64() | 1;
            uint64_t demand = min64(random64(), ceiling);
            uint64_t floor = min64((random64() >> 4) | 1, ceiling);
            if (i == 0) demand = min64(demand, capacity / 4);
            tiers[i] = (struct guide_tier_budget){demand, ceiling, floor, weights[i]};
        }
        bool emergency = (run % 5 == 0) && tiers[0].demand;
        enum guide_policy_result result = guide_plan_capacity(capacity, reserve, emergency, tiers, &plan);
        assert(result != GUIDE_POLICY_INVALID);
        if (result == GUIDE_POLICY_CAPACITY_SHORTFALL) {
            ++shortfalls;
            for (unsigned i = 0; i < 5; ++i) assert(plan.assigned[i] == 0);
            continue;
        }
        ++successes;
        uint64_t remaining = capacity;
        for (unsigned i = 0; i < 5; ++i) {
            assert(plan.assigned[i] <= tiers[i].demand);
            assert(plan.assigned[i] <= tiers[i].ceiling);
            assert(plan.assigned[i] <= remaining);
            remaining -= plan.assigned[i];
            if (i && !emergency) assert(plan.assigned[i] >= min64(tiers[i].demand, tiers[i].minimum));
        }
        assert(plan.assigned[0] == tiers[0].demand);
        assert(plan.held_for_critical <= remaining);
        remaining -= plan.held_for_critical;
        assert(plan.spare == remaining);
        assert(plan.progress_floors_suspended == emergency);
    }
    printf("PASS 1000000 deterministic wide-integer plans: %u admitted, %u shortfalls; conservation, floors, bounds and critical allocation\n", successes, shortfalls);
}
