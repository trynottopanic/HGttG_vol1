#include "guide_systemd_adapter.h"

#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <systemd/sd-bus.h>
#include <unistd.h>

int main(int argc,char **argv)
{
    sd_bus *bus=NULL;struct guide_systemd_observation observed;const char *unit="guide-foundation-integration.service";int result,index;
    if(argc!=2||argv[1][0]!='/')return 2;
    assert(guide_systemd_connect(&bus)>=0);
    assert(sd_bus_is_ready(bus)>0);
    (void)guide_systemd_stop(bus,unit);(void)guide_systemd_reset_failed(bus,unit);
    result=guide_systemd_start_probe(bus,unit,argv[1],"nobody",4u*1024u*1024u,8u*1024u*1024u,4);
    if(result<0){fprintf(stderr,"start failed %d\n",result);return 1;}
    for(index=0;index<100;++index){
        result=guide_systemd_observe(bus,unit,&observed);
        if(result>=0&&observed.invocation_id[0]&&observed.control_group[0])break;
        usleep(20000);
    }
    if(result<0){fprintf(stderr,"observe failed %d\n",result);return 1;}
    assert(strlen(observed.invocation_id)==32);assert(strstr(observed.control_group,unit)!=NULL);
    assert(guide_systemd_stop(bus,unit)>=0);
    for(index=0;index<100;++index){
        result=guide_systemd_observe(bus,unit,&observed);
        if(result<0||strcmp(observed.active_state,"inactive")==0||strcmp(observed.active_state,"failed")==0)break;
        usleep(20000);
    }
    (void)guide_systemd_reset_failed(bus,unit);sd_bus_unref(bus);
    puts("GUIDE_SYSTEMD_ADAPTER_PASS");return 0;
}
