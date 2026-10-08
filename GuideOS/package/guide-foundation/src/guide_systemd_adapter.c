#include "guide_systemd_adapter.h"

#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include "guide_application_policy.h"

#define DEST "org.freedesktop.systemd1"
#define MANAGER_PATH "/org/freedesktop/systemd1"
#define MANAGER_IFACE "org.freedesktop.systemd1.Manager"

static int property_string(sd_bus_message *message, const char *name, const char *value)
{
    int result;
    if ((result=sd_bus_message_open_container(message,'r',"sv"))<0 ||
        (result=sd_bus_message_append(message,"s",name))<0 ||
        (result=sd_bus_message_open_container(message,'v',"s"))<0 ||
        (result=sd_bus_message_append(message,"s",value))<0 ||
        (result=sd_bus_message_close_container(message))<0 ||
        (result=sd_bus_message_close_container(message))<0) return result;
    return 0;
}

static int property_bool(sd_bus_message *message, const char *name, int value)
{
    int result;
    if ((result=sd_bus_message_open_container(message,'r',"sv"))<0 ||
        (result=sd_bus_message_append(message,"s",name))<0 ||
        (result=sd_bus_message_open_container(message,'v',"b"))<0 ||
        (result=sd_bus_message_append(message,"b",value))<0 ||
        (result=sd_bus_message_close_container(message))<0 ||
        (result=sd_bus_message_close_container(message))<0) return result;
    return 0;
}

static int property_u64(sd_bus_message *message, const char *name, uint64_t value)
{
    int result;
    if ((result=sd_bus_message_open_container(message,'r',"sv"))<0 ||
        (result=sd_bus_message_append(message,"s",name))<0 ||
        (result=sd_bus_message_open_container(message,'v',"t"))<0 ||
        (result=sd_bus_message_append(message,"t",value))<0 ||
        (result=sd_bus_message_close_container(message))<0 ||
        (result=sd_bus_message_close_container(message))<0) return result;
    return 0;
}

static int property_exec_args(sd_bus_message *message, const char *path, const char *argument)
{
    int result;
    if ((result=sd_bus_message_open_container(message,'r',"sv"))<0 ||
        (result=sd_bus_message_append(message,"s","ExecStart"))<0 ||
        (result=sd_bus_message_open_container(message,'v',"a(sasb)"))<0 ||
        (result=sd_bus_message_open_container(message,'a',"(sasb)"))<0 ||
        (result=sd_bus_message_open_container(message,'r',"sasb"))<0 ||
        (result=sd_bus_message_append(message,"s",path))<0 ||
        (result=sd_bus_message_open_container(message,'a',"s"))<0 ||
        (result=sd_bus_message_append(message,"s",path))<0 ||
        (argument&&(result=sd_bus_message_append(message,"s",argument))<0) ||
        (result=sd_bus_message_close_container(message))<0 ||
        (result=sd_bus_message_append(message,"b",0))<0 ||
        (result=sd_bus_message_close_container(message))<0 ||
        (result=sd_bus_message_close_container(message))<0 ||
        (result=sd_bus_message_close_container(message))<0 ||
        (result=sd_bus_message_close_container(message))<0) return result;
    return 0;
}

int guide_systemd_connect(sd_bus **bus)
{
    const char *unique_name;
    int result;
    if (bus == NULL) return -EINVAL;
    result = sd_bus_default_system(bus);
    if (result < 0) return result;
    /* Finish the asynchronous handshake before an idle Supervisor waits for
     * its first application, avoiding the bus daemon authentication timeout. */
    result = sd_bus_get_unique_name(*bus, &unique_name);
    if (result < 0) *bus = sd_bus_unref(*bus);
    return result;
}

int guide_systemd_start_probe(sd_bus *bus, const char *unit, const char *executable,
                              const char *user,
                              uint64_t memory_high, uint64_t memory_max,
                              uint64_t tasks_max)
{
    sd_bus_message *request=NULL,*reply=NULL;
    sd_bus_error error=SD_BUS_ERROR_NULL;
    int result;
    if (bus==NULL || unit==NULL || executable==NULL || user==NULL || unit[0]=='\0' || executable[0]!='/' || user[0]=='\0' ||
        memory_high==0 || memory_max<memory_high || tasks_max==0) return -EINVAL;
    result=sd_bus_message_new_method_call(bus,&request,DEST,MANAGER_PATH,MANAGER_IFACE,"StartTransientUnit");
    if (result<0) goto done;
    if ((result=sd_bus_message_append(request,"ss",unit,"fail"))<0 ||
        (result=sd_bus_message_open_container(request,'a',"(sv)"))<0 ||
        (result=property_string(request,"Description","Guide harmless foundation probe"))<0 ||
        (result=property_string(request,"Type","exec"))<0 ||
        (result=property_string(request,"ExitType","cgroup"))<0 ||
        (result=property_string(request,"Restart","no"))<0 ||
        (result=property_string(request,"KillMode","control-group"))<0 ||
        (result=property_string(request,"User",user))<0 ||
        (result=property_string(request,"StandardInput","null"))<0 ||
        (result=property_string(request,"StandardOutput","journal"))<0 ||
        (result=property_string(request,"StandardError","journal"))<0 ||
        (result=property_bool(request,"NoNewPrivileges",1))<0 ||
        (result=property_bool(request,"PrivateDevices",1))<0 ||
        (result=property_bool(request,"PrivateTmp",1))<0 ||
        (result=property_bool(request,"MemoryDenyWriteExecute",1))<0 ||
        (result=property_string(request,"ProtectSystem","strict"))<0 ||
        (result=property_string(request,"ProtectHome","yes"))<0 ||
        (result=property_u64(request,"MemoryHigh",memory_high))<0 ||
        (result=property_u64(request,"MemoryMax",memory_max))<0 ||
        (result=property_u64(request,"TasksMax",tasks_max))<0 ||
        (result=property_exec_args(request,executable,NULL))<0 ||
        (result=sd_bus_message_close_container(request))<0 ||
        (result=sd_bus_message_open_container(request,'a',"(sa(sv))"))<0 ||
        (result=sd_bus_message_close_container(request))<0) goto done;
    result=sd_bus_call(bus,request,15000000,&error,&reply);
    if(result<0 && sd_bus_error_is_set(&error))
        fprintf(stderr,"StartTransientUnit: %s: %s\n",error.name,error.message);
done:
    sd_bus_error_free(&error); sd_bus_message_unref(request); sd_bus_message_unref(reply);
    return result<0?result:0;
}

static int property_strings(sd_bus_message *m,const char *name,const char *value) {
    int r;
    if((r=sd_bus_message_open_container(m,'r',"sv"))<0||(r=sd_bus_message_append(m,"s",name))<0||(r=sd_bus_message_open_container(m,'v',"as"))<0||(r=sd_bus_message_open_container(m,'a',"s"))<0||(r=sd_bus_message_append(m,"s",value))<0||(r=sd_bus_message_close_container(m))<0||(r=sd_bus_message_close_container(m))<0||(r=sd_bus_message_close_container(m))<0)return r;
    return 0;
}
int guide_systemd_start_application(sd_bus *bus,const char *unit,uint64_t code,int health) {
    struct guide_application_policy p;sd_bus_message *m=NULL,*reply=NULL;sd_bus_error e=SD_BUS_ERROR_NULL;int r;char arg[128],dir[128],state_dir[160],user[32];
    if(!bus||!unit||guide_application_policy_load(code,&p)<0)return -EINVAL;
    if(p.format==3)snprintf(arg,sizeof(arg),"%s",unit);else snprintf(arg,sizeof(arg),"%llu%s",(unsigned long long)code,health?":health":"");snprintf(dir,sizeof(dir),"guideos/%s/%u",health?"health":"apps",(unsigned)code);snprintf(user,sizeof(user),"guide-%c%u",health?'h':'a',(unsigned)code);snprintf(state_dir,sizeof(state_dir),p.format==3?"guideos/system-applications/%s/private":"guideos/applications/%s/private",p.id);
    if((r=sd_bus_message_new_method_call(bus,&m,DEST,MANAGER_PATH,MANAGER_IFACE,"StartTransientUnit"))<0)goto done;
#define P(call) do{if((r=(call))<0)goto done;}while(0)
    P(sd_bus_message_append(m,"ss",unit,"fail"));P(sd_bus_message_open_container(m,'a',"(sv)"));
    P(property_string(m,"Description","Guide installed Python application"));P(property_string(m,"Type","notify"));P(property_string(m,"NotifyAccess","main"));
    /* Queue startup, then return to the Supervisor loop so the broker can
     * resolve peer identities. Cold activation is outside capability RPCs. */
    P(property_strings(m,"Requires","guide-capability-broker0.service"));
    P(property_strings(m,"After","guide-capability-broker0.service"));
    P(property_string(m,"User",user));P(property_bool(m,"DynamicUser",1));P(property_strings(m,"SupplementaryGroups","guide-apps"));
    if(!health)P(property_strings(m,"StateDirectory",state_dir));
    P(property_strings(m,"RuntimeDirectory",dir));
    P(property_string(m,"Restart","no"));P(property_string(m,"KillMode","mixed"));
    P(property_string(m,"StandardInput","null"));P(property_string(m,"StandardOutput","null"));P(property_string(m,"StandardError","journal"));
    P(property_bool(m,"NoNewPrivileges",1));P(property_bool(m,"MemoryDenyWriteExecute",1));P(property_bool(m,"PrivateDevices",1));P(property_bool(m,"PrivateTmp",1));P(property_bool(m,"PrivateNetwork",1));P(property_bool(m,"RestrictSUIDSGID",1));
    P(property_string(m,"ProtectSystem","strict"));P(property_string(m,"ProtectHome","yes"));P(property_bool(m,"ProtectControlGroups",1));P(property_bool(m,"ProtectKernelTunables",1));P(property_bool(m,"ProtectKernelModules",1));
    P(property_u64(m,"MemoryHigh",(p.format==3?64u:48u)*1024u*1024u));P(property_u64(m,"MemoryMax",(p.format==3?96u:64u)*1024u*1024u));P(property_u64(m,"TasksMax",5));P(property_u64(m,"LimitNOFILE",32));
    if(p.format==3){
        P(property_u64(m,"CPUWeight",25));
        /* Prototype ceiling: 25% of one CPU, shared by the whole worker cgroup.
         * Weight alone is relative priority, not a bound on catch-up work. */
        P(property_u64(m,"CPUQuotaPerSecUSec",250000));
        P(property_u64(m,"CPUQuotaPeriodUSec",100000));
        P(property_string(m,"OOMPolicy","kill"));
    }
    P(property_u64(m,"TimeoutStartUSec",2000000));P(property_u64(m,"TimeoutStopUSec",2000000));P(property_exec_args(m,p.format==3?"/usr/libexec/guideos/guide-planegotchi-host":"/usr/libexec/guideos/guide-application-host",arg));
    P(sd_bus_message_close_container(m));P(sd_bus_message_open_container(m,'a',"(sa(sv))"));P(sd_bus_message_close_container(m));
    r=sd_bus_call(bus,m,3000000,&e,&reply);
    if(r>=0)r=guide_systemd_reference(bus,unit,1);
#undef P
done: if(r<0&&sd_bus_error_is_set(&e))fprintf(stderr,"application start: %s\n",e.name);sd_bus_error_free(&e);sd_bus_message_unref(m);sd_bus_message_unref(reply);return r<0?r:0;
}

static int get_unit_path(sd_bus *bus,const char *unit,char **path)
{
    sd_bus_error error=SD_BUS_ERROR_NULL;sd_bus_message *reply=NULL;const char *value=NULL;int result;
    result=sd_bus_call_method(bus,DEST,MANAGER_PATH,MANAGER_IFACE,"GetUnit",&error,&reply,"s",unit);
    if(result>=0)result=sd_bus_message_read(reply,"o",&value);
    if(result>=0){*path=strdup(value);if(*path==NULL)result=-ENOMEM;}
    sd_bus_error_free(&error);sd_bus_message_unref(reply);return result<0?result:0;
}

static int copy_property(sd_bus *bus,const char *path,const char *interface,const char *name,
                         char *output,size_t capacity)
{
    char *value=NULL;int result=sd_bus_get_property_string(bus,DEST,path,interface,name,NULL,&value);
    if(result<0)return result;
    if(strlen(value)>=capacity){free(value);return -EOVERFLOW;}
    memcpy(output,value,strlen(value)+1);free(value);return 0;
}

int guide_systemd_observe(sd_bus *bus, const char *unit,
                          struct guide_systemd_observation *observation)
{
    char *path=NULL;int result;size_t index;
    static const char hex[]="0123456789abcdef";
    if(bus==NULL||unit==NULL||observation==NULL)return -EINVAL;
    memset(observation,0,sizeof(*observation));
    if((result=get_unit_path(bus,unit,&path))<0)return result;
    {
        sd_bus_message *reply=NULL;sd_bus_error error=SD_BUS_ERROR_NULL;
        result=sd_bus_get_property(bus,DEST,path,"org.freedesktop.systemd1.Unit","InvocationID",&error,&reply,"ay");
        if(result>=0)result=sd_bus_message_enter_container(reply,'a',"y");
        for(index=0;result>=0&&index<16;++index){uint8_t byte=0;result=sd_bus_message_read_basic(reply,'y',&byte);if(result>0){observation->invocation_id[index*2]=hex[byte>>4];observation->invocation_id[index*2+1]=hex[byte&15];}}
        if(result>=0&&index==16){uint8_t extra=0;result=sd_bus_message_read_basic(reply,'y',&extra);if(result==0)result=0;else if(result>0)result=-EBADMSG;}
        if(result>=0&&index!=16)result=-EBADMSG;
        sd_bus_error_free(&error);sd_bus_message_unref(reply);
    }
    if(result>=0)result=copy_property(bus,path,"org.freedesktop.systemd1.Service","ControlGroup",observation->control_group,sizeof(observation->control_group));
    if(result>=0)result=copy_property(bus,path,"org.freedesktop.systemd1.Unit","ActiveState",observation->active_state,sizeof(observation->active_state));
    if(result>=0)result=copy_property(bus,path,"org.freedesktop.systemd1.Unit","SubState",observation->sub_state,sizeof(observation->sub_state));
    if(result>=0)result=sd_bus_get_property_trivial(bus,DEST,path,"org.freedesktop.systemd1.Service","MainPID",NULL,'u',&observation->main_pid);
    if(result>=0&&observation->main_pid){char proc[64];struct stat st;snprintf(proc,sizeof(proc),"/proc/%u",observation->main_pid);if(stat(proc,&st)<0)result=-errno;else observation->main_uid=st.st_uid;}
    if(result>=0)result=sd_bus_get_property_trivial(bus,DEST,path,"org.freedesktop.systemd1.Service","ExecMainStatus",NULL,'i',&observation->main_status);
    if(result>=0)result=sd_bus_get_property_trivial(bus,DEST,path,"org.freedesktop.systemd1.Service","ExecMainStartTimestampMonotonic",NULL,'t',&observation->main_started);
    if(result>=0){
        sd_bus_message *job=NULL;const char *job_path;
        result=sd_bus_get_property(bus,DEST,path,"org.freedesktop.systemd1.Unit","Job",NULL,&job,"(uo)");
        if(result>=0)result=sd_bus_message_read(job,"(uo)",&observation->job_id,&job_path);
        sd_bus_message_unref(job);
    }
    free(path);return result;
}

int guide_systemd_stop(sd_bus *bus,const char *unit)
{
    sd_bus_error error=SD_BUS_ERROR_NULL;sd_bus_message *reply=NULL;int result;
    if(bus==NULL||unit==NULL)return -EINVAL;
    result=sd_bus_call_method(bus,DEST,MANAGER_PATH,MANAGER_IFACE,"StopUnit",&error,&reply,"ss",unit,"replace");
    sd_bus_error_free(&error);sd_bus_message_unref(reply);return result<0?result:0;
}

int guide_systemd_reset_failed(sd_bus *bus,const char *unit)
{
    sd_bus_error error=SD_BUS_ERROR_NULL;sd_bus_message *reply=NULL;int result;
    if(bus==NULL||unit==NULL)return -EINVAL;
    result=sd_bus_call_method(bus,DEST,MANAGER_PATH,MANAGER_IFACE,"ResetFailedUnit",&error,&reply,"s",unit);
    sd_bus_error_free(&error);sd_bus_message_unref(reply);return result<0?result:0;
}

int guide_systemd_reference(sd_bus *bus,const char *unit,int retain) {
    return sd_bus_call_method(bus,DEST,MANAGER_PATH,MANAGER_IFACE,retain?"RefUnit":"UnrefUnit",NULL,NULL,"s",unit);
}
