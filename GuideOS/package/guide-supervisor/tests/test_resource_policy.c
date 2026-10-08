// SPDX-License-Identifier: AGPL-3.0-or-later
#include "guide_resource_policy.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

/* Synthetic units and deadlines: deliberately NOT deployment defaults. */
static void profile(struct guide_tier_budget t[GUIDE_TIER_COUNT])
{
    memset(t, 0, sizeof(*t) * GUIDE_TIER_COUNT);
    t[0].ceiling = UINT64_MAX;
    t[1] = (struct guide_tier_budget){14, 30, 12, 8};
    t[2] = (struct guide_tier_budget){0, 30, 1, 4};
    t[3] = (struct guide_tier_budget){30, 30, 1, 2};
    t[4] = (struct guide_tier_budget){0, 30, 1, 1};
}

static void streaming_scenario(void)
{
    struct guide_tier_budget t[GUIDE_TIER_COUNT], saved[GUIDE_TIER_COUNT];
    struct guide_stream_download_plan p;
    unsigned i;
    uint64_t received = 0;
    profile(t);
    memcpy(saved, t, sizeof(t));
    for (i = 0; i < 1000; ++i) {
        assert(guide_plan_stream_download(20, 1, false, t, &p) == GUIDE_POLICY_OK);
        assert(p.capacity.assigned[1] == 14 && p.capacity.assigned[3] == 5);
        assert(!p.pause_download && !p.playback_below_floor);
        received += p.capacity.assigned[3];
    }
    assert(received == 5000);
    puts("PASS stream + download: sustained playback and download progress");
    assert(guide_plan_stream_download(13, 1, false, t, &p) == GUIDE_POLICY_OK);
    assert(p.capacity.assigned[1] == 12 && p.capacity.assigned[3] == 0);
    assert(p.pause_download && !p.playback_below_floor);
    assert(guide_plan_stream_download(20, 1, false, t, &p) == GUIDE_POLICY_OK);
    assert(!p.pause_download && p.capacity.assigned[3] == 5);
    assert(memcmp(saved, t, sizeof(t)) == 0);
    puts("PASS link drops and recovers: download defers and returns; agreement unchanged");
    assert(guide_plan_stream_download(12, 1, false, t, &p) == GUIDE_POLICY_CAPACITY_SHORTFALL);
    assert(p.capacity.assigned[1] == 0 && p.capacity.assigned[3] == 0);
    puts("PASS playback alone cannot fit: explicit shortfall, no fabricated success");
    t[0].demand = 17;
    assert(guide_plan_stream_download(20, 1, true, t, &p) == GUIDE_POLICY_OK);
    assert(p.capacity.assigned[0] == 17 && p.capacity.assigned[1] == 3);
    assert(p.pause_download && p.playback_below_floor && p.capacity.progress_floors_suspended);
    t[0].demand = 0;
    assert(guide_plan_stream_download(20, 1, true, t, &p) == GUIDE_POLICY_INVALID);
    puts("PASS critical deadline: explicit floor suspension and affected-playback result");
    t[1].demand = 0;
    assert(guide_plan_stream_download(20, 1, false, t, &p) == GUIDE_POLICY_OK);
    assert(p.capacity.assigned[3] == 19 && !p.pause_download);
    puts("PASS stream ends: download uses available link capacity");
}

static void allocation_invariants(void)
{
    struct guide_tier_budget t[GUIDE_TIER_COUNT];
    struct guide_capacity_plan p;
    unsigned mask, capacity, i;
    for (mask = 0; mask < 16; ++mask) {
        profile(t);
        for (i = 1; i < GUIDE_TIER_COUNT; ++i) {
            t[i].demand = mask & (1u << (i - 1)) ? 30 : 0;
            t[i].minimum = i;
        }
        for (capacity = 1; capacity < 140; ++capacity) {
            uint64_t total, floors = 0;
            enum guide_policy_result result = guide_plan_capacity(capacity, 1, false, t, &p);
            for (i = 1; i < GUIDE_TIER_COUNT; ++i)
                if (t[i].demand) floors += t[i].minimum;
            if (floors > capacity - 1) {
                assert(result == GUIDE_POLICY_CAPACITY_SHORTFALL);
                continue;
            }
            assert(result == GUIDE_POLICY_OK);
            total = p.held_for_critical + p.spare;
            for (i = 0; i < GUIDE_TIER_COUNT; ++i) {
                total += p.assigned[i];
                assert(p.assigned[i] <= t[i].demand);
                if (i && t[i].demand) assert(p.assigned[i] >= t[i].minimum);
            }
            assert(total == capacity);
        }
    }
    puts("PASS 2224 allocation cases: conservation, floors, ceilings and idle tiers");
    profile(t);
    t[1].demand = t[1].ceiling = UINT64_MAX;
    t[3].demand = t[3].ceiling = UINT64_MAX;
    assert(guide_plan_capacity(UINT64_MAX, 1, false, t, &p) == GUIDE_POLICY_OK);
    assert(p.assigned[1] + p.assigned[3] == UINT64_MAX - 1);
    t[3].minimum = UINT64_MAX;
    assert(guide_plan_capacity(UINT64_MAX, 1, false, t, &p) == GUIDE_POLICY_CAPACITY_SHORTFALL);
    profile(t);
    t[3].demand = 31;
    assert(guide_plan_capacity(100, 1, false, t, &p) == GUIDE_POLICY_INVALID);
    t[3].demand = 30;
    t[3].weight = 8;
    assert(guide_plan_capacity(100, 1, false, t, &p) == GUIDE_POLICY_INVALID);
    assert(guide_plan_capacity(1, 2, false, t, &p) == GUIDE_POLICY_INVALID);
    assert(guide_plan_capacity(100, 1, false, NULL, &p) == GUIDE_POLICY_INVALID);
    puts("PASS invalid profiles and 64-bit allocation boundaries");
}

static struct guide_contention_agreement agreement(void)
{
    struct guide_contention_agreement a = {0};
    unsigned i;
    a.instance = 41;
    a.revision = 7;
    a.tier = GUIDE_TIER_BACKGROUND;
    a.needs_checkpoint = true;
    for (i = GUIDE_ACTION_REDUCE_OPTIONAL; i <= GUIDE_ACTION_FORCE_STOP; ++i) {
        a.allowed_actions |= GUIDE_ALLOW(i);
        a.action_timeout_ms[i] = 10;
    }
    return a;
}

static struct guide_contention_observation observation(
    const struct guide_contention_episode *e, enum guide_action_outcome outcome)
{
    struct guide_contention_observation o = {0};
    o.episode = e->id;
    o.sequence = e->sequence;
    o.instance = e->agreement.instance;
    o.agreement_revision = e->agreement.revision;
    o.outcome = outcome;
    return o;
}

static void advance(struct guide_contention_episode *e, enum guide_action_outcome outcome,
                    bool durable, bool capacity, uint64_t now)
{
    struct guide_contention_observation o = observation(e, outcome);
    o.durable = durable;
    o.quiescent = e->action == GUIDE_ACTION_CHECKPOINT ||
        e->action == GUIDE_ACTION_UNLOAD;
    o.capacity_satisfied = capacity;
    assert(guide_contention_observe(e, &o, now));
}

static void interruption_scenarios(void)
{
    struct guide_contention_agreement a = agreement();
    struct guide_contention_episode e, saved;
    struct guide_contention_observation o;
    assert(guide_contention_begin(&e, 99, 1, 0, 0, false, &a));
    assert(e.action == GUIDE_ACTION_REDUCE_OPTIONAL);
    advance(&e, GUIDE_OUTCOME_DONE, false, false, 1);
    assert(e.action == GUIDE_ACTION_YIELD);
    advance(&e, GUIDE_OUTCOME_DONE, false, false, 2);
    assert(e.action == GUIDE_ACTION_CHECKPOINT);
    advance(&e, GUIDE_OUTCOME_DONE, true, false, 3);
    assert(e.action == GUIDE_ACTION_UNLOAD && e.checkpoint_durable);
    advance(&e, GUIDE_OUTCOME_DONE, false, true, 4);
    assert(e.state == GUIDE_CONTENTION_RESOLVED);
    puts("PASS memory handoff: pause alone is insufficient; checkpoint then unload");
    assert(guide_contention_begin(&e, 100, 1, 0, 0, false, &a));
    advance(&e, GUIDE_OUTCOME_DONE, false, false, 1);
    advance(&e, GUIDE_OUTCOME_DONE, false, false, 2);
    advance(&e, GUIDE_OUTCOME_FAILED, false, false, 3);
    assert(e.state == GUIDE_CONTENTION_BLOCKED && !e.checkpoint_durable);
    puts("PASS failed checkpoint: no ordinary unload or false saved state");
    assert(guide_contention_begin(&e, 110, 1, 0, 0, false, &a));
    advance(&e, GUIDE_OUTCOME_DONE, false, false, 1);
    advance(&e, GUIDE_OUTCOME_DONE, false, false, 2);
    o = observation(&e, GUIDE_OUTCOME_DONE);
    o.durable = true;
    o.quiescent = false;
    assert(guide_contention_observe(&e, &o, 3));
    assert(e.state == GUIDE_CONTENTION_BLOCKED && e.checkpoint_durable);
    puts("PASS saved but still running: no ordinary unload without quiescence");
    assert(guide_contention_begin(&e, 101, 1, 0, 0, false, &a));
    saved = e;
    o = observation(&e, GUIDE_OUTCOME_DONE);
    o.instance++;
    assert(!guide_contention_observe(&e, &o, 1));
    assert(memcmp(&e, &saved, sizeof(e)) == 0);
    o = observation(&e, GUIDE_OUTCOME_DONE);
    o.agreement_revision++;
    assert(!guide_contention_observe(&e, &o, 1));
    o = observation(&e, GUIDE_OUTCOME_DONE);
    assert(guide_contention_observe(&e, &o, 1));
    assert(!guide_contention_observe(&e, &o, 2));
    o = observation(&e, GUIDE_OUTCOME_PENDING);
    assert(!guide_contention_observe(&e, &o, 0));
    assert(guide_contention_observe(&e, &o, 2));
    assert(e.sequence == 2 && e.deadline_ms == 11);
    puts("PASS stale/duplicate results and backwards time cannot advance or extend deadlines");
    advance(&e, GUIDE_OUTCOME_PENDING, false, false, 11);
    assert(e.action == GUIDE_ACTION_FORCE_STOP && e.unresponsive);
    advance(&e, GUIDE_OUTCOME_DONE, false, false, 12);
    assert(e.state == GUIDE_CONTENTION_ACTIVE);
    advance(&e, GUIDE_OUTCOME_DONE, false, true, 13);
    assert(e.state == GUIDE_CONTENTION_RESOLVED);
    puts("PASS unresponsive escalation: stop acknowledgement does not prove capacity reclaimed");
    a.allowed_actions &= ~GUIDE_ALLOW(GUIDE_ACTION_FORCE_STOP);
    assert(guide_contention_begin(&e, 102, 0, 5, 0, false, &a));
    advance(&e, GUIDE_OUTCOME_PENDING, false, false, 5);
    assert(e.state == GUIDE_CONTENTION_BLOCKED);
    a = agreement();
    assert(guide_contention_begin(&e, 103, 0, 5, 0, false, &a));
    advance(&e, GUIDE_OUTCOME_PENDING, false, false, 5);
    assert(e.action == GUIDE_ACTION_FORCE_STOP && !e.checkpoint_durable);
    advance(&e, GUIDE_OUTCOME_PENDING, false, false, 15);
    assert(e.state == GUIDE_CONTENTION_BLOCKED);
    puts("PASS critical deadline respects force permission and bounds force-stop wait");
    assert(!guide_contention_begin(&e, 104, 1, 5, 0, false, &a));
    assert(!guide_contention_begin(&e, 104, 3, 0, 0, false, &a));
    assert(!guide_contention_begin(&e, 104, 0, 1, 2, true, &a));
    assert(guide_contention_begin(&e, 104, 1, 0, 0, false, &a));
    o = observation(&e, GUIDE_OUTCOME_PENDING);
    o.dependency_held = true;
    assert(guide_contention_observe(&e, &o, 1));
    assert(e.state == GUIDE_CONTENTION_BLOCKED);
    puts("PASS dependency and priority checks prevent blind victim termination");
    a.action_timeout_ms[GUIDE_ACTION_YIELD] = 0;
    assert(!guide_contention_begin(&e, 105, 1, 0, 0, false, &a));
    a = agreement();
    assert(guide_contention_begin(&e, 105, 1, 0, UINT64_MAX - 5, false, &a));
    assert(e.deadline_ms == UINT64_MAX);
    puts("PASS missing deadline rejected and deadline arithmetic saturates safely");
}

int main(void)
{
    streaming_scenario();
    allocation_invariants();
    interruption_scenarios();
    puts("Resource policy contract tests: PASS (synthetic host evidence only)");
    return 0;
}
