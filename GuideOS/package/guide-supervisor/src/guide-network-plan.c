// SPDX-License-Identifier: AGPL-3.0-or-later
/* Small host bridge to the existing policy. Units: payload bytes per interval.
 * No networking or privilege operations. Works as a static ARM executable. */
#include "guide_resource_policy.h"
#include <errno.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>

int main(int argc, char **argv)
{
    uint64_t v[12];
    struct guide_tier_budget tiers[GUIDE_TIER_COUNT] = {{0}};
    struct guide_stream_download_plan plan;
    enum guide_policy_result result;
    int i;
    if (argc != 13) {
        fputs("Expected capacity reserve stream-demand ceiling floor download-demand ceiling floor and four tier weights\n", stderr);
        return 2;
    }
    for (i = 0; i < 12; ++i) {
        char *end;
        if (argv[i + 1][0] < '0' || argv[i + 1][0] > '9') return 2;
        errno = 0;
        v[i] = strtoull(argv[i + 1], &end, 10);
        if (errno || *end) return 2;
    }
    for (i = 1; i < GUIDE_TIER_COUNT; ++i) {
        if (v[7 + i] > 10000) return 2;
        tiers[i].weight = (uint32_t)v[7 + i];
    }
    tiers[1].demand = v[2]; tiers[1].ceiling = v[3]; tiers[1].minimum = v[4];
    tiers[3].demand = v[5]; tiers[3].ceiling = v[6]; tiers[3].minimum = v[7];
    result = guide_plan_stream_download(v[0], v[1], false, tiers, &plan);
    if (result != GUIDE_POLICY_OK) {
        printf("{\"status\":\"%s\"}\n", result == GUIDE_POLICY_CAPACITY_SHORTFALL
               ? "shortfall" : "invalid");
        return result == GUIDE_POLICY_CAPACITY_SHORTFALL ? 1 : 2;
    }
    printf("{\"status\":\"ok\",\"stream\":%" PRIu64 ",\"download\":%" PRIu64
           ",\"pause_download\":%s}\n", plan.capacity.assigned[1],
           plan.capacity.assigned[3], plan.pause_download ? "true" : "false");
    return 0;
}
