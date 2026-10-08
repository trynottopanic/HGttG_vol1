// SPDX-License-Identifier: AGPL-3.0-or-later
#include "guide_resource_policy.h"
#include <stddef.h>
#include <string.h>

static uint64_t smaller(uint64_t a, uint64_t b) { return a < b ? a : b; }

enum guide_policy_result guide_plan_capacity(
    uint64_t capacity, uint64_t headroom, bool emergency,
    const struct guide_tier_budget tiers[GUIDE_TIER_COUNT],
    struct guide_capacity_plan *plan)
{
    struct guide_capacity_plan next = {0};
    uint64_t demand[GUIDE_TIER_COUNT], remaining, floor_total = 0;
    unsigned i;
    if (!plan) return GUIDE_POLICY_INVALID;
    memset(plan, 0, sizeof(*plan));
    if (!tiers || headroom > capacity) return GUIDE_POLICY_INVALID;
    for (i = 0; i < GUIDE_TIER_COUNT; ++i) {
        if (tiers[i].minimum > tiers[i].ceiling ||
            tiers[i].demand > tiers[i].ceiling ||
            (i && (!tiers[i].weight || tiers[i].weight > 10000)) ||
            (i > 1 && tiers[i].weight >= tiers[i - 1].weight) ||
            (i && tiers[i].demand && !tiers[i].minimum))
            return GUIDE_POLICY_INVALID;
        demand[i] = tiers[i].demand;
    }
    if (demand[0] > capacity) return GUIDE_POLICY_CAPACITY_SHORTFALL;
    if (emergency && !demand[0]) return GUIDE_POLICY_INVALID;
    next.assigned[0] = demand[0];
    next.held_for_critical = headroom > demand[0] ? headroom - demand[0] : 0;
    remaining = capacity - next.assigned[0] - next.held_for_critical;
    next.progress_floors_suspended = emergency;
    if (emergency) {
        for (i = 1; i < GUIDE_TIER_COUNT; ++i) {
            next.assigned[i] = smaller(demand[i], remaining);
            remaining -= next.assigned[i];
        }
    } else {
        for (i = 1; i < GUIDE_TIER_COUNT; ++i) {
            uint64_t floor = smaller(demand[i], tiers[i].minimum);
            if (floor > remaining - floor_total)
                return GUIDE_POLICY_CAPACITY_SHORTFALL;
            next.assigned[i] = floor;
            floor_total += floor;
        }
        remaining -= floor_total;
        while (remaining) {
            uint64_t weights = 0, spent = 0, round = remaining;
            for (i = 1; i < GUIDE_TIER_COUNT; ++i)
                if (next.assigned[i] < demand[i]) weights += tiers[i].weight;
            if (!weights) break;
            for (i = 1; i < GUIDE_TIER_COUNT; ++i) {
                uint64_t share;
                if (next.assigned[i] == demand[i]) continue;
                /* weights <= 40000; the remainder product cannot overflow. */
                share = (round / weights) * tiers[i].weight +
                    ((round % weights) * tiers[i].weight) / weights;
                share = smaller(share, demand[i] - next.assigned[i]);
                next.assigned[i] += share;
                spent += share;
            }
            if (!spent) {
                /* Deterministic priority order for indivisible residual units. */
                for (i = 1; i < GUIDE_TIER_COUNT && !spent; ++i)
                    if (next.assigned[i] < demand[i]) {
                        ++next.assigned[i];
                        spent = 1;
                    }
            }
            remaining -= spent;
        }
    }
    next.spare = remaining;
    *plan = next;
    return GUIDE_POLICY_OK;
}

enum guide_policy_result guide_plan_stream_download(uint64_t capacity,
    uint64_t headroom, bool emergency,
    const struct guide_tier_budget tiers[GUIDE_TIER_COUNT],
    struct guide_stream_download_plan *plan)
{
    struct guide_tier_budget deferred[GUIDE_TIER_COUNT];
    enum guide_policy_result result;
    if (!plan) return GUIDE_POLICY_INVALID;
    memset(plan, 0, sizeof(*plan));
    if (!tiers || tiers[GUIDE_TIER_COMMUNICATION].demand ||
        tiers[GUIDE_TIER_SPARE].demand) return GUIDE_POLICY_INVALID;
    result = guide_plan_capacity(capacity, headroom, emergency, tiers, &plan->capacity);
    if (result == GUIDE_POLICY_CAPACITY_SHORTFALL &&
        tiers[GUIDE_TIER_BACKGROUND].demand && tiers[GUIDE_TIER_FOREGROUND].demand) {
        memcpy(deferred, tiers, sizeof(deferred));
        deferred[GUIDE_TIER_BACKGROUND].demand = 0;
        result = guide_plan_capacity(capacity, headroom, emergency, deferred, &plan->capacity);
    }
    if (result == GUIDE_POLICY_OK) {
        plan->pause_download = tiers[GUIDE_TIER_BACKGROUND].demand &&
            !plan->capacity.assigned[GUIDE_TIER_BACKGROUND];
        plan->playback_below_floor = plan->capacity.assigned[GUIDE_TIER_FOREGROUND] <
            smaller(tiers[GUIDE_TIER_FOREGROUND].demand,
                    tiers[GUIDE_TIER_FOREGROUND].minimum);
    }
    return result;
}

static bool allowed(const struct guide_contention_episode *e,
                    enum guide_contention_action action)
{
    return (e->agreement.allowed_actions & GUIDE_ALLOW(action)) != 0;
}

static void issue(struct guide_contention_episode *e,
                  enum guide_contention_action action, uint64_t now)
{
    uint64_t duration = e->agreement.action_timeout_ms[action];
    e->action = action;
    ++e->sequence;
    e->deadline_ms = duration > UINT64_MAX - now ? UINT64_MAX : now + duration;
    if (action != GUIDE_ACTION_FORCE_STOP && e->critical_deadline_ms &&
        e->critical_deadline_ms < e->deadline_ms)
        e->deadline_ms = e->critical_deadline_ms;
}

static void finish(struct guide_contention_episode *e,
                   enum guide_contention_state state)
{
    e->state = state;
    e->action = GUIDE_ACTION_NONE;
}

static void next_cooperative(struct guide_contention_episode *e, uint64_t now)
{
    unsigned next;
    for (next = (unsigned)e->action + 1; next <= GUIDE_ACTION_UNLOAD; ++next) {
        if (!allowed(e, (enum guide_contention_action)next)) continue;
        if (next == GUIDE_ACTION_CHECKPOINT && !e->agreement.needs_checkpoint)
            continue;
        if (next == GUIDE_ACTION_UNLOAD && e->agreement.needs_checkpoint &&
            (!e->checkpoint_durable || !e->quiescent)) continue;
        issue(e, (enum guide_contention_action)next, now);
        return;
    }
    finish(e, GUIDE_CONTENTION_BLOCKED);
}

bool guide_contention_begin(struct guide_contention_episode *e,
    uint64_t id, uint32_t requester_tier, uint64_t critical_deadline,
    uint64_t now, bool dependency_held,
    const struct guide_contention_agreement *agreement)
{
    unsigned action;
    const uint32_t mask = GUIDE_ALLOW(GUIDE_ACTION_REDUCE_OPTIONAL) |
        GUIDE_ALLOW(GUIDE_ACTION_YIELD) | GUIDE_ALLOW(GUIDE_ACTION_CHECKPOINT) |
        GUIDE_ALLOW(GUIDE_ACTION_UNLOAD) | GUIDE_ALLOW(GUIDE_ACTION_FORCE_STOP);
    if (!e || !agreement || dependency_held || !id || !agreement->instance || !agreement->revision ||
        agreement->tier >= GUIDE_TIER_COUNT || requester_tier >= agreement->tier ||
        (critical_deadline && requester_tier != GUIDE_TIER_CRITICAL) ||
        (agreement->allowed_actions & ~mask)) return false;
    for (action = GUIDE_ACTION_REDUCE_OPTIONAL; action <= GUIDE_ACTION_FORCE_STOP; ++action)
        if ((agreement->allowed_actions & GUIDE_ALLOW(action)) &&
            !agreement->action_timeout_ms[action]) return false;
    memset(e, 0, sizeof(*e));
    e->agreement = *agreement;
    e->id = id;
    e->last_now_ms = now;
    e->critical_deadline_ms = critical_deadline;
    e->state = GUIDE_CONTENTION_ACTIVE;
    if (critical_deadline && now >= critical_deadline) {
        if (allowed(e, GUIDE_ACTION_FORCE_STOP)) issue(e, GUIDE_ACTION_FORCE_STOP, now);
        else finish(e, GUIDE_CONTENTION_BLOCKED);
    } else next_cooperative(e, now);
    return true;
}

bool guide_contention_observe(struct guide_contention_episode *e,
    const struct guide_contention_observation *o, uint64_t now)
{
    bool timed_out, urgent;
    if (!e || !o || !e->id || !e->agreement.instance ||
        e->action == GUIDE_ACTION_NONE || e->state != GUIDE_CONTENTION_ACTIVE ||
        o->episode != e->id || o->sequence != e->sequence ||
        o->instance != e->agreement.instance ||
        o->agreement_revision != e->agreement.revision ||
        o->outcome < GUIDE_OUTCOME_PENDING || o->outcome > GUIDE_OUTCOME_UNSUPPORTED ||
        now < e->last_now_ms ||
        (o->durable && (e->action != GUIDE_ACTION_CHECKPOINT ||
                        o->outcome != GUIDE_OUTCOME_DONE))) return false;
    e->last_now_ms = now;
    e->quiescent = o->quiescent;
    if (e->action == GUIDE_ACTION_CHECKPOINT &&
        o->outcome == GUIDE_OUTCOME_DONE && o->durable)
        e->checkpoint_durable = true;
    if (o->capacity_satisfied) {
        finish(e, GUIDE_CONTENTION_RESOLVED);
        return true;
    }
    if (o->dependency_held) {
        finish(e, GUIDE_CONTENTION_BLOCKED);
        return true;
    }
    timed_out = now >= e->deadline_ms;
    urgent = e->critical_deadline_ms && now >= e->critical_deadline_ms;
    if (o->outcome == GUIDE_OUTCOME_PENDING && !timed_out) return true;
    if (e->action == GUIDE_ACTION_FORCE_STOP) {
        /* Wait for observed capacity, without reissuing the same stop. */
        if (o->outcome == GUIDE_OUTCOME_DONE && !timed_out) return true;
        finish(e, GUIDE_CONTENTION_BLOCKED);
        return true;
    }
    if (e->action == GUIDE_ACTION_UNLOAD && o->outcome == GUIDE_OUTCOME_DONE &&
        !timed_out && !urgent) return true;
    if (timed_out && o->outcome == GUIDE_OUTCOME_PENDING) e->unresponsive = true;
    if ((urgent || e->unresponsive) && allowed(e, GUIDE_ACTION_FORCE_STOP)) {
        issue(e, GUIDE_ACTION_FORCE_STOP, now);
        return true;
    }
    if (urgent) finish(e, GUIDE_CONTENTION_BLOCKED);
    else next_cooperative(e, now);
    return true;
}
