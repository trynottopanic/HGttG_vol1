#include "guide_foundation.h"

#include <assert.h>
#include <stdio.h>
#include <string.h>

static void fill(uint8_t id[16], uint8_t value) { memset(id, value, 16); }

int main(void)
{
    struct guide_foundation state, capacity;
    const struct guide_instance *resolved = NULL;
    uint8_t instance[16], other[16], grant[16];
    fill(instance, 0x11); fill(other, 0x22); fill(grant, 0x33);
    guide_foundation_init(&state, 77);
    assert(guide_instance_admit(&state, instance, 1, 9, 1001, "9001", "guide-app-9001-1.service") == GUIDE_FOUNDATION_NOT_READY);
    guide_foundation_set_reconciled(&state, true);
    assert(guide_instance_admit(&state, instance, 1, 9, 1001, "9001", "guide-app-9001-1.service") == GUIDE_FOUNDATION_OK);
    assert(guide_instance_admit(&state, instance, 2, 10, 1001, "9001", "guide-app-9001-2.service") == GUIDE_FOUNDATION_STALE);
    assert(guide_instance_resolve(&state, instance, 1, 9, 1001, "guide-app-9001-1.service", &resolved) == GUIDE_FOUNDATION_OK);
    assert(resolved != NULL && resolved->phase == GUIDE_PHASE_ADMITTED);
    assert(guide_instance_resolve(&state, instance, 1, 8, 1001, "guide-app-9001-1.service", NULL) == GUIDE_FOUNDATION_STALE);
    assert(guide_instance_transition(&state, instance, 1, GUIDE_PHASE_RUNNING) == GUIDE_FOUNDATION_INVALID);
    assert(guide_instance_transition(&state, instance, 1, GUIDE_PHASE_STARTING) == GUIDE_FOUNDATION_OK);
    assert(guide_instance_transition(&state, instance, 1, GUIDE_PHASE_RUNNING) == GUIDE_FOUNDATION_OK);
    assert(guide_grant_issue(&state, grant, instance, 1, 1, 1u, 1000) == GUIDE_FOUNDATION_OK);
    assert(guide_grant_validate(&state, grant, instance, 1, 1, 1, 999) == GUIDE_FOUNDATION_OK);
    assert(guide_grant_validate(&state, grant, other, 1, 1, 1, 999) == GUIDE_FOUNDATION_STALE);
    assert(guide_grant_validate(&state, grant, instance, 1, 1, 2, 999) == GUIDE_FOUNDATION_DENIED);
    assert(guide_grant_validate(&state, grant, instance, 1, 1, 1, 1000) == GUIDE_FOUNDATION_EXPIRED);
    assert(guide_grant_revoke(&state, grant) == GUIDE_FOUNDATION_OK);
    assert(guide_grant_validate(&state, grant, instance, 1, 1, 1, 500) == GUIDE_FOUNDATION_DENIED);
    assert(guide_instance_transition(&state, instance, 1, GUIDE_PHASE_STOPPING) == GUIDE_FOUNDATION_OK);
    assert(guide_instance_transition(&state, instance, 1, GUIDE_PHASE_EXITED) == GUIDE_FOUNDATION_OK);
    assert(guide_instance_resolve(&state, instance, 1, 9, 1001, "guide-app-9001-1.service", NULL) == GUIDE_FOUNDATION_STALE);
    guide_foundation_init(&capacity, 88);
    guide_foundation_set_reconciled(&capacity, true);
    assert(guide_instance_admit(&capacity, instance, 1, 9, 1001, "9001", "guide-app-capacity.service") == GUIDE_FOUNDATION_OK);
    assert(guide_instance_transition(&capacity, instance, 1, GUIDE_PHASE_STARTING) == GUIDE_FOUNDATION_OK);
    assert(guide_instance_transition(&capacity, instance, 1, GUIDE_PHASE_RUNNING) == GUIDE_FOUNDATION_OK);
    {
        uint64_t before, current;
        size_t index;
        for(index=0;index<GUIDE_FOUNDATION_MAX_GRANTS;++index){memset(grant,0,16);grant[0]=(uint8_t)(index+1);grant[1]=(uint8_t)((index+1)>>8);assert(guide_grant_issue(&capacity,grant,instance,1,1,1u,1000)==GUIDE_FOUNDATION_OK);}
        before=capacity.registry_revision;memset(grant,0x7f,16);
        assert(guide_grant_issue(&capacity,grant,instance,1,1,1u,1000)==GUIDE_FOUNDATION_FULL);
        assert(capacity.registry_revision==before);
        assert(guide_watch_revision(&capacity,1,&current)==GUIDE_FOUNDATION_STALE);
        assert(current==capacity.registry_revision);
        assert(guide_watch_revision(&capacity,current,&current)==GUIDE_FOUNDATION_OK);
    }
    /* Startup cancellation is a real transition, and completed identities do
       not exhaust the bounded table after repeated launches. */
    guide_foundation_init(&capacity,88);guide_foundation_set_reconciled(&capacity,true);
    for(size_t i=0;i<GUIDE_FOUNDATION_MAX_INSTANCES+10;++i){
        memset(instance,0,sizeof(instance));instance[0]=(uint8_t)(i+1);
        assert(guide_instance_admit(&capacity,instance,i+1,1,1000,"10001","app.service")==GUIDE_FOUNDATION_OK);
        assert(guide_instance_transition(&capacity,instance,i+1,GUIDE_PHASE_STARTING)==GUIDE_FOUNDATION_OK);
        assert(guide_instance_transition(&capacity,instance,i+1,GUIDE_PHASE_STOPPING)==GUIDE_FOUNDATION_OK);
        assert(guide_instance_transition(&capacity,instance,i+1,GUIDE_PHASE_EXITED)==GUIDE_FOUNDATION_OK);
    }
    puts("GUIDE_FOUNDATION_CORE_PASS");
    return 0;
}
