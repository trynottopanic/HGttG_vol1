#ifndef GUIDE_FOUNDATION_H
#define GUIDE_FOUNDATION_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define GUIDE_FOUNDATION_MAX_INSTANCES 32u
#define GUIDE_FOUNDATION_MAX_GRANTS 128u
#define GUIDE_FOUNDATION_ID_BYTES 16u
#define GUIDE_FOUNDATION_APP_ID_MAX 64u
#define GUIDE_FOUNDATION_UNIT_MAX 96u
#define GUIDE_FOUNDATION_EVENT_WINDOW 64u

enum guide_lifecycle_phase {
    GUIDE_PHASE_EMPTY = 0,
    GUIDE_PHASE_ADMITTED,
    GUIDE_PHASE_STARTING,
    GUIDE_PHASE_RUNNING,
    GUIDE_PHASE_QUIESCING,
    GUIDE_PHASE_PAUSED,
    GUIDE_PHASE_STOPPING,
    GUIDE_PHASE_EXITED,
    GUIDE_PHASE_FAILED
};

enum guide_checkpoint_state {
    GUIDE_CHECKPOINT_UNSUPPORTED = 0,
    GUIDE_CHECKPOINT_PENDING,
    GUIDE_CHECKPOINT_DURABLE,
    GUIDE_CHECKPOINT_FAILED,
    GUIDE_CHECKPOINT_STALE
};

enum guide_foundation_result {
    GUIDE_FOUNDATION_OK = 0,
    GUIDE_FOUNDATION_INVALID,
    GUIDE_FOUNDATION_FULL,
    GUIDE_FOUNDATION_STALE,
    GUIDE_FOUNDATION_DENIED,
    GUIDE_FOUNDATION_EXPIRED,
    GUIDE_FOUNDATION_NOT_FOUND,
    GUIDE_FOUNDATION_NOT_READY
};

struct guide_instance {
    bool occupied;
    bool health_check;
    uint8_t instance_id[GUIDE_FOUNDATION_ID_BYTES];
    uint64_t generation;
    uint64_t invocation_hash;
    uint32_t owner_uid;
    enum guide_lifecycle_phase phase;
    enum guide_checkpoint_state checkpoint;
    uint64_t policy_mask;
    char release_digest[65];
    char app_id[GUIDE_FOUNDATION_APP_ID_MAX];
    char unit[GUIDE_FOUNDATION_UNIT_MAX];
};

struct guide_grant {
    bool occupied;
    bool revoked;
    uint8_t grant_id[GUIDE_FOUNDATION_ID_BYTES];
    uint8_t instance_id[GUIDE_FOUNDATION_ID_BYTES];
    uint64_t generation;
    uint64_t expires_ns;
    uint32_t operation_mask;
    uint16_t interface_major;
};

struct guide_foundation {
    bool reconciled;
    uint64_t epoch;
    uint64_t registry_revision;
    struct guide_instance instances[GUIDE_FOUNDATION_MAX_INSTANCES];
    struct guide_grant grants[GUIDE_FOUNDATION_MAX_GRANTS];
};

void guide_foundation_init(struct guide_foundation *state, uint64_t epoch);
void guide_foundation_set_reconciled(struct guide_foundation *state, bool ready);
enum guide_foundation_result guide_instance_admit(struct guide_foundation *state,
    const uint8_t instance_id[GUIDE_FOUNDATION_ID_BYTES], uint64_t generation,
    uint64_t invocation_hash, uint32_t owner_uid, const char *app_id,
    const char *unit);
enum guide_foundation_result guide_instance_transition(struct guide_foundation *state,
    const uint8_t instance_id[GUIDE_FOUNDATION_ID_BYTES], uint64_t generation,
    enum guide_lifecycle_phase next);
enum guide_foundation_result guide_instance_resolve(const struct guide_foundation *state,
    const uint8_t instance_id[GUIDE_FOUNDATION_ID_BYTES], uint64_t generation,
    uint64_t invocation_hash, uint32_t owner_uid, const char *unit,
    const struct guide_instance **out);
enum guide_foundation_result guide_grant_issue(struct guide_foundation *state,
    const uint8_t grant_id[GUIDE_FOUNDATION_ID_BYTES],
    const uint8_t instance_id[GUIDE_FOUNDATION_ID_BYTES], uint64_t generation,
    uint16_t interface_major, uint32_t operation_mask, uint64_t expires_ns);
enum guide_foundation_result guide_grant_validate(const struct guide_foundation *state,
    const uint8_t grant_id[GUIDE_FOUNDATION_ID_BYTES],
    const uint8_t instance_id[GUIDE_FOUNDATION_ID_BYTES], uint64_t generation,
    uint16_t interface_major, uint16_t operation, uint64_t now_ns);
size_t guide_grants_revoke_instance(struct guide_foundation *state,
    const uint8_t instance_id[GUIDE_FOUNDATION_ID_BYTES], uint64_t generation);
enum guide_foundation_result guide_grant_revoke(struct guide_foundation *state,
    const uint8_t grant_id[GUIDE_FOUNDATION_ID_BYTES]);
enum guide_foundation_result guide_watch_revision(const struct guide_foundation *state,
    uint64_t after_revision, uint64_t *current_revision);
const char *guide_foundation_result_name(enum guide_foundation_result result);

#endif
