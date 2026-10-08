#include "guide_foundation.h"

#include <string.h>

static bool id_zero(const uint8_t id[GUIDE_FOUNDATION_ID_BYTES])
{
    uint8_t value = 0;
    size_t index;
    for (index = 0; index < GUIDE_FOUNDATION_ID_BYTES; ++index) value |= id[index];
    return value == 0;
}

static bool bounded_text(const char *value, size_t limit)
{
    return value != NULL && value[0] != '\0' && strnlen(value, limit) < limit;
}

static struct guide_instance *find_instance(struct guide_foundation *state,
    const uint8_t id[GUIDE_FOUNDATION_ID_BYTES])
{
    size_t index;
    for (index = 0; index < GUIDE_FOUNDATION_MAX_INSTANCES; ++index)
        if (state->instances[index].occupied &&
            memcmp(state->instances[index].instance_id, id, GUIDE_FOUNDATION_ID_BYTES) == 0)
            return &state->instances[index];
    return NULL;
}

static struct guide_grant *find_grant(struct guide_foundation *state,
    const uint8_t id[GUIDE_FOUNDATION_ID_BYTES])
{
    size_t index;
    for (index = 0; index < GUIDE_FOUNDATION_MAX_GRANTS; ++index)
        if (state->grants[index].occupied &&
            memcmp(state->grants[index].grant_id, id, GUIDE_FOUNDATION_ID_BYTES) == 0)
            return &state->grants[index];
    return NULL;
}

void guide_foundation_init(struct guide_foundation *state, uint64_t epoch)
{
    memset(state, 0, sizeof(*state));
    state->epoch = epoch;
    state->registry_revision = 1;
}

void guide_foundation_set_reconciled(struct guide_foundation *state, bool ready)
{
    if (state->reconciled != ready) ++state->registry_revision;
    state->reconciled = ready;
}

enum guide_foundation_result guide_instance_admit(struct guide_foundation *state,
    const uint8_t instance_id[GUIDE_FOUNDATION_ID_BYTES], uint64_t generation,
    uint64_t invocation_hash, uint32_t owner_uid, const char *app_id,
    const char *unit)
{
    size_t index;
    struct guide_instance *slot = NULL;
    if (!state->reconciled) return GUIDE_FOUNDATION_NOT_READY;
    if (id_zero(instance_id) || generation == 0 || invocation_hash == 0 ||
        !bounded_text(app_id, GUIDE_FOUNDATION_APP_ID_MAX) ||
        !bounded_text(unit, GUIDE_FOUNDATION_UNIT_MAX)) return GUIDE_FOUNDATION_INVALID;
    if (find_instance(state, instance_id) != NULL) return GUIDE_FOUNDATION_STALE;
    for (index = 0; index < GUIDE_FOUNDATION_MAX_INSTANCES; ++index)
        if (!state->instances[index].occupied) { slot = &state->instances[index]; break; }
    if (slot == NULL) for (index=0;index<GUIDE_FOUNDATION_MAX_INSTANCES;++index)
        if (state->instances[index].phase==GUIDE_PHASE_EXITED||state->instances[index].phase==GUIDE_PHASE_FAILED) { slot=&state->instances[index]; break; }
    if (slot == NULL) return GUIDE_FOUNDATION_FULL;
    memset(slot, 0, sizeof(*slot));
    slot->occupied = true;
    memcpy(slot->instance_id, instance_id, GUIDE_FOUNDATION_ID_BYTES);
    slot->generation = generation;
    slot->invocation_hash = invocation_hash;
    slot->owner_uid = owner_uid;
    slot->phase = GUIDE_PHASE_ADMITTED;
    slot->checkpoint = GUIDE_CHECKPOINT_UNSUPPORTED;
    memcpy(slot->app_id, app_id, strlen(app_id) + 1);
    memcpy(slot->unit, unit, strlen(unit) + 1);
    ++state->registry_revision;
    return GUIDE_FOUNDATION_OK;
}

static bool transition_allowed(enum guide_lifecycle_phase from,
                               enum guide_lifecycle_phase to)
{
    if (to == GUIDE_PHASE_FAILED && from != GUIDE_PHASE_EMPTY &&
        from != GUIDE_PHASE_EXITED && from != GUIDE_PHASE_FAILED) return true;
    if (from == GUIDE_PHASE_ADMITTED && to == GUIDE_PHASE_STARTING) return true;
    if (from == GUIDE_PHASE_STARTING && (to == GUIDE_PHASE_RUNNING || to == GUIDE_PHASE_STOPPING)) return true;
    if (from == GUIDE_PHASE_RUNNING && (to == GUIDE_PHASE_QUIESCING || to == GUIDE_PHASE_STOPPING)) return true;
    if (from == GUIDE_PHASE_QUIESCING && (to == GUIDE_PHASE_PAUSED || to == GUIDE_PHASE_RUNNING || to == GUIDE_PHASE_STOPPING)) return true;
    if (from == GUIDE_PHASE_PAUSED && (to == GUIDE_PHASE_RUNNING || to == GUIDE_PHASE_STOPPING)) return true;
    if (from == GUIDE_PHASE_STOPPING && to == GUIDE_PHASE_EXITED) return true;
    return false;
}

enum guide_foundation_result guide_instance_transition(struct guide_foundation *state,
    const uint8_t instance_id[GUIDE_FOUNDATION_ID_BYTES], uint64_t generation,
    enum guide_lifecycle_phase next)
{
    struct guide_instance *instance = find_instance(state, instance_id);
    if (instance == NULL) return GUIDE_FOUNDATION_NOT_FOUND;
    if (instance->generation != generation) return GUIDE_FOUNDATION_STALE;
    if (!transition_allowed(instance->phase, next)) return GUIDE_FOUNDATION_INVALID;
    instance->phase = next;
    if (next == GUIDE_PHASE_EXITED || next == GUIDE_PHASE_FAILED)
        (void)guide_grants_revoke_instance(state, instance_id, generation);
    ++state->registry_revision;
    return GUIDE_FOUNDATION_OK;
}

enum guide_foundation_result guide_instance_resolve(const struct guide_foundation *state,
    const uint8_t instance_id[GUIDE_FOUNDATION_ID_BYTES], uint64_t generation,
    uint64_t invocation_hash, uint32_t owner_uid, const char *unit,
    const struct guide_instance **out)
{
    size_t index;
    if (!state->reconciled) return GUIDE_FOUNDATION_NOT_READY;
    for (index = 0; index < GUIDE_FOUNDATION_MAX_INSTANCES; ++index) {
        const struct guide_instance *instance = &state->instances[index];
        if (!instance->occupied || memcmp(instance->instance_id, instance_id, GUIDE_FOUNDATION_ID_BYTES) != 0) continue;
        if (instance->generation != generation || instance->invocation_hash != invocation_hash ||
            instance->owner_uid != owner_uid || unit == NULL || strcmp(instance->unit, unit) != 0)
            return GUIDE_FOUNDATION_STALE;
        if (instance->phase == GUIDE_PHASE_EXITED || instance->phase == GUIDE_PHASE_FAILED)
            return GUIDE_FOUNDATION_STALE;
        if (out != NULL) *out = instance;
        return GUIDE_FOUNDATION_OK;
    }
    return GUIDE_FOUNDATION_NOT_FOUND;
}

enum guide_foundation_result guide_grant_issue(struct guide_foundation *state,
    const uint8_t grant_id[GUIDE_FOUNDATION_ID_BYTES],
    const uint8_t instance_id[GUIDE_FOUNDATION_ID_BYTES], uint64_t generation,
    uint16_t interface_major, uint32_t operation_mask, uint64_t expires_ns)
{
    size_t index;
    struct guide_instance *instance = find_instance(state, instance_id);
    struct guide_grant *slot = NULL;
    if (!state->reconciled) return GUIDE_FOUNDATION_NOT_READY;
    if (instance == NULL || instance->generation != generation) return GUIDE_FOUNDATION_STALE;
    if (id_zero(grant_id) || interface_major == 0 || operation_mask == 0 || expires_ns == 0)
        return GUIDE_FOUNDATION_INVALID;
    if (find_grant(state, grant_id) != NULL) return GUIDE_FOUNDATION_STALE;
    for (index = 0; index < GUIDE_FOUNDATION_MAX_GRANTS; ++index)
        if (!state->grants[index].occupied) { slot = &state->grants[index]; break; }
    if (slot == NULL) for (index=0;index<GUIDE_FOUNDATION_MAX_GRANTS;++index)
        if(state->grants[index].revoked){slot=&state->grants[index];break;}
    if (slot == NULL) return GUIDE_FOUNDATION_FULL;
    memset(slot, 0, sizeof(*slot)); slot->occupied = true;
    memcpy(slot->grant_id, grant_id, GUIDE_FOUNDATION_ID_BYTES);
    memcpy(slot->instance_id, instance_id, GUIDE_FOUNDATION_ID_BYTES);
    slot->generation = generation; slot->interface_major = interface_major;
    slot->operation_mask = operation_mask; slot->expires_ns = expires_ns;
    ++state->registry_revision;
    return GUIDE_FOUNDATION_OK;
}

enum guide_foundation_result guide_grant_validate(const struct guide_foundation *state,
    const uint8_t grant_id[GUIDE_FOUNDATION_ID_BYTES],
    const uint8_t instance_id[GUIDE_FOUNDATION_ID_BYTES], uint64_t generation,
    uint16_t interface_major, uint16_t operation, uint64_t now_ns)
{
    size_t index;
    if (!state->reconciled) return GUIDE_FOUNDATION_NOT_READY;
    if (operation == 0 || operation > 32) return GUIDE_FOUNDATION_INVALID;
    for (index = 0; index < GUIDE_FOUNDATION_MAX_GRANTS; ++index) {
        const struct guide_grant *grant = &state->grants[index];
        if (!grant->occupied || memcmp(grant->grant_id, grant_id, GUIDE_FOUNDATION_ID_BYTES) != 0) continue;
        if (grant->revoked) return GUIDE_FOUNDATION_DENIED;
        if (now_ns >= grant->expires_ns) return GUIDE_FOUNDATION_EXPIRED;
        if (grant->generation != generation || grant->interface_major != interface_major ||
            memcmp(grant->instance_id, instance_id, GUIDE_FOUNDATION_ID_BYTES) != 0)
            return GUIDE_FOUNDATION_STALE;
        return (grant->operation_mask & (1u << (operation - 1u))) != 0
            ? GUIDE_FOUNDATION_OK : GUIDE_FOUNDATION_DENIED;
    }
    return GUIDE_FOUNDATION_NOT_FOUND;
}

size_t guide_grants_revoke_instance(struct guide_foundation *state,
    const uint8_t instance_id[GUIDE_FOUNDATION_ID_BYTES], uint64_t generation)
{
    size_t index, count = 0;
    for (index = 0; index < GUIDE_FOUNDATION_MAX_GRANTS; ++index) {
        struct guide_grant *grant = &state->grants[index];
        if (grant->occupied && !grant->revoked && grant->generation == generation &&
            memcmp(grant->instance_id, instance_id, GUIDE_FOUNDATION_ID_BYTES) == 0) {
            grant->revoked = true; ++count;
        }
    }
    if (count != 0) ++state->registry_revision;
    return count;
}

enum guide_foundation_result guide_grant_revoke(struct guide_foundation *state,
    const uint8_t grant_id[GUIDE_FOUNDATION_ID_BYTES])
{
    struct guide_grant *grant = find_grant(state, grant_id);
    if (grant == NULL) return GUIDE_FOUNDATION_NOT_FOUND;
    if (!grant->revoked) { grant->revoked = true; ++state->registry_revision; }
    return GUIDE_FOUNDATION_OK;
}

enum guide_foundation_result guide_watch_revision(const struct guide_foundation *state,
    uint64_t after_revision, uint64_t *current_revision)
{
    if (!state->reconciled) return GUIDE_FOUNDATION_NOT_READY;
    if (current_revision != NULL) *current_revision = state->registry_revision;
    if (after_revision > state->registry_revision) return GUIDE_FOUNDATION_STALE;
    if (state->registry_revision - after_revision > GUIDE_FOUNDATION_EVENT_WINDOW)
        return GUIDE_FOUNDATION_STALE;
    return GUIDE_FOUNDATION_OK;
}

const char *guide_foundation_result_name(enum guide_foundation_result result)
{
    static const char *names[] = {"ok","invalid","full","stale","denied","expired","not-found","not-ready"};
    return (unsigned)result < sizeof(names) / sizeof(names[0]) ? names[result] : "unknown";
}
