// SPDX-License-Identifier: AGPL-3.0-or-later
#ifndef GUIDE_RESOURCE_POLICY_H
#define GUIDE_RESOURCE_POLICY_H

#include <stdbool.h>
#include <stdint.h>

/* Internal policy API, not an application wire protocol. All inputs come from
 * authenticated Supervisor state and installed agreements, never raw app claims.
 * Pure decisions only: no PID 1 duties, signals, device access or systemd calls. */
enum guide_resource_tier {
    GUIDE_TIER_CRITICAL = 0,
    GUIDE_TIER_FOREGROUND = 1,
    GUIDE_TIER_COMMUNICATION = 2,
    GUIDE_TIER_BACKGROUND = 3,
    GUIDE_TIER_SPARE = 4,
    GUIDE_TIER_COUNT = 5
};

enum guide_policy_result {
    GUIDE_POLICY_OK,
    GUIDE_POLICY_INVALID,
    GUIDE_POLICY_CAPACITY_SHORTFALL
};

/* Units must be consistent for one divisible resource and one scheduling
 * interval. Demand is bounded work within the stored installation agreement.
 * minimum is the required progress/service floor when active, not a fresh bid. */
struct guide_tier_budget {
    uint64_t demand;
    uint64_t ceiling;
    uint64_t minimum;
    uint32_t weight; /* 1..10000; strictly descending for ordinary tiers. */
};

struct guide_capacity_plan {
    uint64_t assigned[GUIDE_TIER_COUNT];
    uint64_t held_for_critical;
    uint64_t spare;
    bool progress_floors_suspended;
};

enum guide_policy_result guide_plan_capacity(
    uint64_t capacity, uint64_t critical_headroom,
    bool critical_deadline_at_risk,
    const struct guide_tier_budget tiers[GUIDE_TIER_COUNT],
    struct guide_capacity_plan *plan);

struct guide_stream_download_plan {
    struct guide_capacity_plan capacity;
    bool pause_download;
    bool playback_below_floor;
};

/* First approved scenario: foreground streaming and background download on one
 * constrained link. Other ordinary tiers must be inactive. Deferring download
 * changes current demand only; its installed ceiling/minimum remain unchanged. */
enum guide_policy_result guide_plan_stream_download(uint64_t capacity,
    uint64_t critical_headroom, bool critical_deadline_at_risk,
    const struct guide_tier_budget tiers[GUIDE_TIER_COUNT],
    struct guide_stream_download_plan *plan);

enum guide_contention_action {
    GUIDE_ACTION_NONE,
    GUIDE_ACTION_REDUCE_OPTIONAL,
    GUIDE_ACTION_YIELD,
    GUIDE_ACTION_CHECKPOINT,
    GUIDE_ACTION_UNLOAD,
    GUIDE_ACTION_FORCE_STOP
};

enum guide_contention_state {
    GUIDE_CONTENTION_ACTIVE,
    GUIDE_CONTENTION_RESOLVED,
    GUIDE_CONTENTION_BLOCKED
};

enum guide_action_outcome {
    GUIDE_OUTCOME_PENDING,
    GUIDE_OUTCOME_DONE,
    GUIDE_OUTCOME_FAILED,
    GUIDE_OUTCOME_UNSUPPORTED
};

#define GUIDE_ALLOW(action) (1u << (action))

struct guide_contention_agreement {
    uint64_t instance;
    uint64_t revision;
    uint32_t tier;
    uint32_t allowed_actions;
    bool needs_checkpoint;
    uint64_t action_timeout_ms[GUIDE_ACTION_FORCE_STOP + 1];
};

struct guide_contention_episode {
    struct guide_contention_agreement agreement;
    uint64_t id;
    uint64_t sequence;
    uint64_t deadline_ms;
    uint64_t critical_deadline_ms; /* zero means no critical deadline */
    uint64_t last_now_ms;
    enum guide_contention_action action;
    enum guide_contention_state state;
    bool checkpoint_durable;
    bool quiescent;
    bool unresponsive;
};

/* The host must verify checkpoint generation/durability before setting durable.
 * capacity_satisfied is a fresh provider/host observation, not an app assertion.
 * dependency_held means the requester needs work/locks held by this victim: do
 * not stop that dependency blindly; resolve it outside this component. */
struct guide_contention_observation {
    uint64_t episode;
    uint64_t sequence;
    uint64_t instance;
    uint64_t agreement_revision;
    enum guide_action_outcome outcome;
    bool durable;
    bool quiescent;
    bool capacity_satisfied;
    bool dependency_held;
};

bool guide_contention_begin(struct guide_contention_episode *episode,
    uint64_t episode_id, uint32_t requester_tier,
    uint64_t critical_deadline_ms, uint64_t now_ms, bool dependency_held,
    const struct guide_contention_agreement *agreement);

/* Returns false for stale/malformed observations or backwards time. Rejected
 * observations cannot extend a deadline. Repeated pending polls keep the same
 * sequence: adapters execute each (episode, sequence) at most once. */
bool guide_contention_observe(struct guide_contention_episode *episode,
    const struct guide_contention_observation *observation, uint64_t now_ms);

#endif
