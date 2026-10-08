#include "guide_control_codec.h"
#include "guide_foundation.h"
#include "guide_ipc_transport.h"
#include "guide_systemd_adapter.h"
#include "guide_application_policy.h"

#include <errno.h>
#include <dirent.h>
#include <fcntl.h>
#include <poll.h>
#include <pwd.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/random.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <sys/types.h>
#include <time.h>
#include <unistd.h>

#define PROBE_APP 9001u
#define PROBE_PATH "/usr/libexec/guideos/guide-ipc-probe"
#define STATE_DIR "/var/lib/guideos/supervisor"
#define RUN_DIR "/run/guideos/supervisor"
static volatile sig_atomic_t stopping;
static struct guide_foundation state;
static sd_bus *system_bus;

static void stop_handler(int value){(void)value;stopping=1;}
static const char *configured_user(const char *variable,const char *fallback){const char *value=getenv(variable);return value&&value[0]?value:fallback;}
static uint64_t invocation_hash(const char *text){uint64_t value=1469598103934665603ULL;while(*text){value^=(uint8_t)*text++;value*=1099511628211ULL;}return value?value:1;}
static void hex_id(const uint8_t id[16],char text[33]){static const char h[]="0123456789abcdef";for(size_t i=0;i<16;++i){text[i*2]=h[id[i]>>4];text[i*2+1]=h[id[i]&15];}text[32]=0;}
static uint64_t boottime_ns(void){struct timespec value;if(clock_gettime(CLOCK_BOOTTIME,&value)!=0)return 0;return (uint64_t)value.tv_sec*1000000000ULL+(uint64_t)value.tv_nsec;}

static struct guide_instance *find_instance_id(const uint8_t id[16],uint64_t generation)
{
    for(size_t i=0;i<GUIDE_FOUNDATION_MAX_INSTANCES;++i)if(state.instances[i].occupied&&state.instances[i].generation==generation&&memcmp(state.instances[i].instance_id,id,16)==0)return &state.instances[i];
    return NULL;
}

static int parse_hex_id(const char *text,uint8_t id[16])
{
    if(text==NULL||strlen(text)!=32)return -1;
    for(size_t i=0;i<16;++i){unsigned value;if(sscanf(text+i*2,"%2x",&value)!=1)return -1;id[i]=(uint8_t)value;}
    return 0;
}

static int atomic_text(const char *path,const char *body)
{
    char temporary[256];int fd,length=(int)strlen(body);snprintf(temporary,sizeof(temporary),"%s.tmp.%ld",path,(long)getpid());
    fd=open(temporary,O_WRONLY|O_CREAT|O_EXCL|O_CLOEXEC|O_NOFOLLOW,0600);if(fd<0)return -1;
    if(write(fd,body,(size_t)length)!=length||fsync(fd)!=0||close(fd)!=0||rename(temporary,path)!=0){int saved=errno;close(fd);unlink(temporary);errno=saved;return -1;}char parent[256];snprintf(parent,sizeof(parent),"%s",path);char *slash=strrchr(parent,'/');if(!slash)return -1;*slash=0;int directory=open(parent,O_DIRECTORY|O_CLOEXEC);if(directory<0)return -1;int synced=fsync(directory);close(directory);return synced;
}

static int next_generation(uint64_t code,uint64_t *generation)
{
    char path[256],body[160],current[160]={0};unsigned long long value=0,stored_code=0;int fd;ssize_t count;
    snprintf(path,sizeof(path),"%s/%llu.json",STATE_DIR,(unsigned long long)code);fd=open(path,O_RDONLY|O_CLOEXEC|O_NOFOLLOW);
    if(fd>=0){count=read(fd,current,sizeof(current)-1);close(fd);if(count<=0||sscanf(current,"{\"format\":1,\"application_id\":\"%llu\",\"generation\":%llu}\n",&stored_code,&value)!=2||stored_code!=code)return -1;}
    if(fd<0&&errno!=ENOENT)return -1;
    if(value==UINT64_MAX)return -1;
    *generation=(uint64_t)value+1;
    snprintf(body,sizeof(body),"{\"format\":1,\"application_id\":\"%llu\",\"generation\":%llu}\n",(unsigned long long)code,(unsigned long long)*generation);
    return atomic_text(path,body);
}

static int write_ledger(const struct guide_instance *instance,const struct guide_systemd_observation *observed)
{
    char id[33],path[256],body[768];hex_id(instance->instance_id,id);snprintf(path,sizeof(path),"%s/%s.record",RUN_DIR,id);
    snprintf(body,sizeof(body),"format=1\ninstance=%s\ngeneration=%llu\napp=%s\nuid=%u\nunit=%s\ninvocation=%s\ncgroup=%s\nrelease=%s\npolicy=%llu\n",id,(unsigned long long)instance->generation,instance->app_id,instance->owner_uid,instance->unit,observed->invocation_id,observed->control_group,instance->release_digest,(unsigned long long)instance->policy_mask);
    return atomic_text(path,body);
}

static int reconcile_record(const char *name)
{
    char path[320],line[384],id_text[33]="",app[32]="",unit[96]="",invocation[33]="",cgroup[256]="",digest[65]="";unsigned long long policy_mask=0;uint8_t id[16];unsigned uid=0;unsigned long long generation=0;FILE *stream;struct guide_systemd_observation observed;
    if(strlen(name)!=39||strcmp(name+32,".record")!=0)return 0;
    snprintf(path,sizeof(path),"%s/%s",RUN_DIR,name);stream=fopen(path,"re");if(stream==NULL)return -1;
    while(fgets(line,sizeof(line),stream)!=NULL){char *newline=strchr(line,'\n');if(newline)*newline=0;if(sscanf(line,"instance=%32s",id_text)==1)continue;if(sscanf(line,"generation=%llu",&generation)==1)continue;if(sscanf(line,"app=%31s",app)==1)continue;if(sscanf(line,"uid=%u",&uid)==1)continue;if(sscanf(line,"unit=%95s",unit)==1)continue;if(sscanf(line,"invocation=%32s",invocation)==1)continue;if(sscanf(line,"cgroup=%255s",cgroup)==1)continue;if(sscanf(line,"release=%64s",digest)==1)continue;if(sscanf(line,"policy=%llu",&policy_mask)==1)continue;}
    fclose(stream);
    if(parse_hex_id(id_text,id)<0||generation==0||app[0]==0||unit[0]==0||invocation[0]==0||cgroup[0]==0||guide_systemd_observe(system_bus,unit,&observed)<0||strcmp(observed.invocation_id,invocation)!=0||strcmp(observed.control_group,cgroup)!=0||strcmp(observed.active_state,"active")!=0){(void)unlink(path);return 0;}
    struct guide_application_policy policy;uint64_t code=strtoull(app,NULL,10);if(code!=PROBE_APP&&(guide_application_policy_load(code,&policy)<0||strcmp(policy.binding,digest)||policy.capabilities!=policy_mask)){(void)unlink(path);return 0;}
    if(guide_systemd_reference(system_bus,unit,1)<0)return -1;
    if(guide_instance_admit(&state,id,(uint64_t)generation,invocation_hash(invocation),(uint32_t)uid,app,unit)!=GUIDE_FOUNDATION_OK)return -1;
    struct guide_instance *restored=find_instance_id(id,generation);restored->health_check=!strncmp(unit,"guide-health-",13);restored->policy_mask=code==PROBE_APP?1:policy_mask;snprintf(restored->release_digest,sizeof(restored->release_digest),"%s",digest);
    if(guide_instance_transition(&state,id,(uint64_t)generation,GUIDE_PHASE_STARTING)!=GUIDE_FOUNDATION_OK||guide_instance_transition(&state,id,(uint64_t)generation,GUIDE_PHASE_RUNNING)!=GUIDE_FOUNDATION_OK)return -1;
    return 0;
}

static int reconcile_runtime(void)
{
    DIR *directory=opendir(RUN_DIR);struct dirent *entry;if(directory==NULL)return errno==ENOENT?0:-1;
    while((entry=readdir(directory))!=NULL)if(entry->d_name[0]!='.'&&reconcile_record(entry->d_name)<0){closedir(directory);return -1;}
    closedir(directory);return 0;
}

static int reply_message(int peer,const struct guide_ipc_header *request,uint16_t outcome,const struct guide_control_value *values,size_t count)
{
    uint8_t payload[256];size_t length=guide_control_encode_reply(payload,sizeof(payload),outcome,values,count);struct guide_ipc_header header=*request;
    if(length==0)return -1;
    header.message_class=GUIDE_IPC_REPLY;header.payload_length=(uint16_t)length;header.descriptor_count=0;return guide_ipc_send(peer,&header,payload,NULL)==GUIDE_IPC_IO_OK?0:-1;
}

static int launch_probe(struct guide_control_value results[4])
{
    uint8_t id[16];uint64_t generation;char text[33],unit[96];struct guide_systemd_observation observed;struct guide_instance *instance=NULL;int status;
    if(getrandom(id,sizeof(id),0)!=(ssize_t)sizeof(id)||next_generation(PROBE_APP,&generation)<0)return -1;
    hex_id(id,text);snprintf(unit,sizeof(unit),"guide-app-%s-g%llu.service",text,(unsigned long long)generation);
    status=guide_instance_admit(&state,id,generation,1,0,"9001",unit);if(status!=GUIDE_FOUNDATION_OK)return -1;
    (void)guide_instance_transition(&state,id,generation,GUIDE_PHASE_STARTING);
    status=guide_systemd_start_probe(system_bus,unit,PROBE_PATH,configured_user("GUIDE_PROBE_USER","guide-probe"),4u*1024u*1024u,8u*1024u*1024u,4);if(status<0){(void)guide_instance_transition(&state,id,generation,GUIDE_PHASE_FAILED);return -1;}
    for(int attempt=0;attempt<100;++attempt){if(guide_systemd_observe(system_bus,unit,&observed)>=0&&observed.invocation_id[0]&&observed.control_group[0])break;usleep(20000);if(attempt==99)return -1;}
    for(size_t i=0;i<GUIDE_FOUNDATION_MAX_INSTANCES;++i)if(state.instances[i].occupied&&memcmp(state.instances[i].instance_id,id,16)==0){instance=&state.instances[i];break;}
    if(instance==NULL||getpwnam(configured_user("GUIDE_PROBE_USER","guide-probe"))==NULL)return -1;
    instance->invocation_hash=invocation_hash(observed.invocation_id);instance->owner_uid=(uint32_t)getpwnam(configured_user("GUIDE_PROBE_USER","guide-probe"))->pw_uid;(void)guide_instance_transition(&state,id,generation,GUIDE_PHASE_RUNNING);if(write_ledger(instance,&observed)<0)return -1;
    memset(results,0,sizeof(*results)*2);results[0].key=0;results[0].type=GUIDE_CONTROL_BYTES16;memcpy(results[0].bytes,id,16);results[1].key=1;results[1].type=GUIDE_CONTROL_UINT;results[1].number=generation;return 0;
}

static int launch_application(uint64_t code,int health,struct guide_control_value results[4])
{
    struct guide_application_policy policy;uint8_t id[16];uint64_t generation;char text[33],unit[96],app[32];
    size_t active=0;for(size_t i=0;i<GUIDE_FOUNDATION_MAX_INSTANCES;++i)if(state.instances[i].occupied&&state.instances[i].phase!=GUIDE_PHASE_EXITED&&state.instances[i].phase!=GUIDE_PHASE_FAILED)++active;if(active>=4)return -1;
    if(guide_application_policy_load(code,&policy)<0||(!health&&policy.testing)||(health&&policy.testing!=1))return -1;
    snprintf(app,sizeof(app),"%llu",(unsigned long long)code);
    for(size_t i=0;i<GUIDE_FOUNDATION_MAX_INSTANCES;++i)if(state.instances[i].occupied&&!strcmp(state.instances[i].app_id,app)&&state.instances[i].phase!=GUIDE_PHASE_EXITED&&state.instances[i].phase!=GUIDE_PHASE_FAILED)return -1;
    if(getrandom(id,16,0)!=16||next_generation(code,&generation)<0)return -1;
    hex_id(id,text);snprintf(unit,sizeof(unit),"guide-%s-%s-g%llu.service",health?"health":"app",text,(unsigned long long)generation);
    if(guide_instance_admit(&state,id,generation,1,UINT32_MAX,app,unit)!=GUIDE_FOUNDATION_OK)return -1;
    struct guide_instance *admitted=find_instance_id(id,generation);admitted->policy_mask=policy.capabilities;strcpy(admitted->release_digest,policy.binding);admitted->health_check=health;
    (void)guide_instance_transition(&state,id,generation,GUIDE_PHASE_STARTING);
    if(guide_systemd_start_application(system_bus,unit,code,health)<0){(void)guide_instance_transition(&state,id,generation,GUIDE_PHASE_FAILED);return -1;}
    memset(results,0,sizeof(*results)*4);results[0].type=GUIDE_CONTROL_BYTES16;memcpy(results[0].bytes,id,16);results[1]=(struct guide_control_value){1,GUIDE_CONTROL_UINT,generation,{0}};return 0;
}

static int process_cgroup(pid_t pid,char *unit,size_t capacity)
{
    char path[64],line[512];FILE *stream;snprintf(path,sizeof(path),"/proc/%ld/cgroup",(long)pid);stream=fopen(path,"re");if(stream==NULL)return -1;
    while(fgets(line,sizeof(line),stream)!=NULL){if(strncmp(line,"0::",3)==0){char *last,*end=strchr(line,'\n');if(end)*end=0;last=strrchr(line,'/');if(last&&strlen(last+1)<capacity){strcpy(unit,last+1);fclose(stream);return 0;}}}fclose(stream);return -1;
}

static int resolve_peer(uint64_t pid_value,uint64_t uid_value,uint64_t gid_value,struct guide_control_value results[4])
{
    char unit[96];int pidfd;struct guide_instance *match=NULL;(void)gid_value;if(pid_value==0||pid_value>INT32_MAX||uid_value>UINT32_MAX||process_cgroup((pid_t)pid_value,unit,sizeof(unit))<0){fprintf(stderr,"supervisor resolve invalid peer pid=%llu uid=%llu\n",(unsigned long long)pid_value,(unsigned long long)uid_value);return -1;}
    pidfd=(int)syscall(SYS_pidfd_open,(pid_t)pid_value,0);if(pidfd<0)return -1;
    for(size_t i=0;i<GUIDE_FOUNDATION_MAX_INSTANCES;++i){struct guide_instance *candidate=&state.instances[i];if(candidate->occupied&&strcmp(candidate->unit,unit)==0){if(match){close(pidfd);return -1;}match=candidate;}}
    if(match){struct guide_systemd_observation current;if(guide_systemd_observe(system_bus,unit,&current)<0||!current.main_pid||current.main_uid!=(uint32_t)uid_value||(match->invocation_hash!=1&&match->invocation_hash!=invocation_hash(current.invocation_id))){close(pidfd);return -1;}match->owner_uid=(uint32_t)uid_value;match->invocation_hash=invocation_hash(current.invocation_id);if(match->phase==GUIDE_PHASE_STARTING&&!strcmp(current.active_state,"active"))(void)guide_instance_transition(&state,match->instance_id,match->generation,GUIDE_PHASE_RUNNING);if(write_ledger(match,&current)<0){close(pidfd);return -1;}}
    close(pidfd);if(match==NULL||(match->phase!=GUIDE_PHASE_RUNNING&&match->phase!=GUIDE_PHASE_STARTING&&match->phase!=GUIDE_PHASE_STOPPING)){fprintf(stderr,"supervisor resolve miss pid=%llu uid=%llu unit=%s\n",(unsigned long long)pid_value,(unsigned long long)uid_value,unit);return -1;}memset(results,0,sizeof(*results)*2);results[0].key=0;results[0].type=GUIDE_CONTROL_BYTES16;memcpy(results[0].bytes,match->instance_id,16);results[1].key=1;results[1].type=GUIDE_CONTROL_UINT;results[1].number=match->generation;uint64_t code=strtoull(match->app_id,NULL,10);struct guide_application_policy policy;uint64_t mask=code==PROBE_APP?1:0;if(code!=PROBE_APP){if(guide_application_policy_load(code,&policy)<0||strcmp(policy.binding,match->release_digest)||policy.capabilities!=match->policy_mask)return -1;mask=match->policy_mask;if(match->phase==GUIDE_PHASE_STOPPING)mask&=2;}results[2]=(struct guide_control_value){2,GUIDE_CONTROL_UINT,code,{0}};results[3]=(struct guide_control_value){3,GUIDE_CONTROL_UINT,mask,{0}};return 0;
}

static int stop_instance(const uint8_t id[16],uint64_t generation,struct guide_control_value results[4])
{
    struct guide_instance *instance=find_instance_id(id,generation);
    if(instance==NULL)return -1;
    if(instance->phase==GUIDE_PHASE_EXITED||instance->phase==GUIDE_PHASE_FAILED||instance->phase==GUIDE_PHASE_STOPPING){results[0]=(struct guide_control_value){0,GUIDE_CONTROL_UINT,1,{0}};return 0;}
    if(guide_instance_transition(&state,id,generation,GUIDE_PHASE_STOPPING)!=GUIDE_FOUNDATION_OK||guide_systemd_stop(system_bus,instance->unit)<0)return -1;
    instance->checkpoint=GUIDE_CHECKPOINT_PENDING;results[0]=(struct guide_control_value){0,GUIDE_CONTROL_UINT,1,{0}};return 0;
}

static void refresh_instances(void) {
    for(size_t i=0;i<GUIDE_FOUNDATION_MAX_INSTANCES;++i){
        struct guide_instance *app=&state.instances[i];struct guide_systemd_observation observed={0};char path[256],id[33];
        if(!app->occupied||app->phase==GUIDE_PHASE_EXITED||app->phase==GUIDE_PHASE_FAILED)continue;
        int observation=guide_systemd_observe(system_bus,app->unit,&observed);
        /* Inactive with a queued start job is waiting for its provider, not
         * an exited application. Never commit an unexecuted health check. */
        if(observation>=0&&observed.job_id&&!strcmp(observed.active_state,"inactive")&&app->phase==GUIDE_PHASE_STARTING)continue;
        if(observation<0||!strcmp(observed.active_state,"inactive")||!strcmp(observed.active_state,"failed")||(app->invocation_hash!=1&&app->invocation_hash!=invocation_hash(observed.invocation_id))){
            if(app->phase==GUIDE_PHASE_STOPPING||app->health_check){if(app->health_check&&app->phase!=GUIDE_PHASE_STOPPING)(void)guide_instance_transition(&state,app->instance_id,app->generation,GUIDE_PHASE_STOPPING);app->checkpoint=observation>=0&&observed.main_started&&observed.main_status==0&&!strcmp(observed.active_state,"inactive")?GUIDE_CHECKPOINT_DURABLE:GUIDE_CHECKPOINT_FAILED;if(!strcmp(app->app_id,"9001"))app->checkpoint=GUIDE_CHECKPOINT_UNSUPPORTED;(void)guide_instance_transition(&state,app->instance_id,app->generation,GUIDE_PHASE_EXITED);}
            else (void)guide_instance_transition(&state,app->instance_id,app->generation,GUIDE_PHASE_FAILED);
            (void)guide_systemd_reference(system_bus,app->unit,0);hex_id(app->instance_id,id);snprintf(path,sizeof(path),"%s/%s.record",RUN_DIR,id);(void)unlink(path);
        }else if(observed.main_pid){int changed=app->owner_uid!=observed.main_uid||app->invocation_hash!=invocation_hash(observed.invocation_id);app->owner_uid=observed.main_uid;app->invocation_hash=invocation_hash(observed.invocation_id);if(app->phase==GUIDE_PHASE_STARTING&&!strcmp(observed.active_state,"active")){(void)guide_instance_transition(&state,app->instance_id,app->generation,GUIDE_PHASE_RUNNING);changed=1;}if(changed)(void)write_ledger(app,&observed);}
    }
}

static void serve_peer(int peer)
{
    struct guide_ipc_message message;struct guide_ipc_header header;enum guide_ipc_error protocol;struct guide_control_request request;struct ucred credentials;socklen_t credential_length=sizeof(credentials);struct guide_control_value results[4];uint8_t id[16];uint64_t a=0,b=0,c=0;uint16_t outcome=1;size_t result_count=0;
    memset(&message,0,sizeof(message));if(getsockopt(peer,SOL_SOCKET,SO_PEERCRED,&credentials,&credential_length)!=0)return;
    if(guide_ipc_receive(peer,&message,&header,&protocol)!=GUIDE_IPC_IO_OK)return;
    if(header.message_class!=GUIDE_IPC_REQUEST||header.interface_major!=1||guide_control_decode_request(message.bytes+GUIDE_IPC_HEADER_SIZE,header.payload_length,&request)<0||request.deadline_ns<=boottime_ns()){outcome=1;goto done;}
    if(request.operation==1&&credentials.uid==0&&guide_control_get_uint(&request,0,&a)==0&&((a==PROBE_APP&&launch_probe(results)==0)||(a!=PROBE_APP&&launch_application(a,0,results)==0))){outcome=0;result_count=2;}
    else if(request.operation==2&&(credentials.uid==0||(getpwnam(configured_user("GUIDE_BROKER_USER","guide-broker"))&&getpwnam(configured_user("GUIDE_BROKER_USER","guide-broker"))->pw_uid==credentials.uid))&&guide_control_get_uint(&request,0,&a)==0&&guide_control_get_uint(&request,1,&b)==0&&guide_control_get_uint(&request,2,&c)==0&&resolve_peer(a,b,c,results)==0){outcome=0;result_count=4;}
    else if(request.operation==3&&credentials.uid==0&&guide_control_get_bytes16(&request,0,id)==0&&guide_control_get_uint(&request,1,&a)==0&&stop_instance(id,a,results)==0){outcome=0;result_count=1;}
    else if(request.operation==4&&(credentials.uid==0||(getpwnam(configured_user("GUIDE_BROKER_USER","guide-broker"))&&getpwnam(configured_user("GUIDE_BROKER_USER","guide-broker"))->pw_uid==credentials.uid))&&guide_control_get_bytes16(&request,0,id)==0&&guide_control_get_uint(&request,1,&a)==0){struct guide_instance *app=find_instance_id(id,a);if(app){results[0]=(struct guide_control_value){0,GUIDE_CONTROL_UINT,app->phase,{0}};results[1]=(struct guide_control_value){1,GUIDE_CONTROL_UINT,app->checkpoint,{0}};outcome=0;result_count=2;}}
    else if(request.operation==5&&credentials.uid==0&&guide_control_get_uint(&request,0,&a)==0&&launch_application(a,1,results)==0){outcome=0;result_count=2;}
    else if(request.operation==6&&credentials.uid==0&&guide_control_get_uint(&request,0,&a)==0){
        outcome=0;result_count=1;results[0]=(struct guide_control_value){0,GUIDE_CONTROL_UINT,0,{0}};
        for(size_t i=0;i<GUIDE_FOUNDATION_MAX_INSTANCES;++i){struct guide_instance *app=&state.instances[i];if(app->occupied&&strtoull(app->app_id,NULL,10)==a&&app->phase!=GUIDE_PHASE_EXITED&&app->phase!=GUIDE_PHASE_FAILED){results[0].number=1;results[1]=(struct guide_control_value){1,GUIDE_CONTROL_BYTES16,0,{0}};memcpy(results[1].bytes,app->instance_id,16);results[2]=(struct guide_control_value){2,GUIDE_CONTROL_UINT,app->generation,{0}};result_count=3;break;}}
    }
    else outcome=6;
done:(void)reply_message(peer,&header,outcome,results,result_count);guide_ipc_message_close(&message);
}

int main(void)
{
    struct stat info;struct pollfd listener={3,POLLIN,0};struct timespec now;if(fstat(3,&info)!=0||!S_ISSOCK(info.st_mode)||guide_systemd_connect(&system_bus)<0)return 1;
    if(clock_gettime(CLOCK_BOOTTIME,&now)!=0)return 1;
    guide_foundation_init(&state,((uint64_t)now.tv_sec<<32)^(uint64_t)now.tv_nsec^(uint64_t)getpid());
    /* The socket is not accepted until startup returns, so this permits only internal reconciliation. */
    guide_foundation_set_reconciled(&state,true);
    if(reconcile_runtime()<0)return 1;
    signal(SIGTERM,stop_handler);signal(SIGINT,stop_handler);while(!stopping){refresh_instances();int status=poll(&listener,1,50);if(status<0&&errno!=EINTR)return 1;if(status>0&&(listener.revents&POLLIN)){int peer=accept4(3,NULL,NULL,SOCK_CLOEXEC);if(peer>=0){struct timeval timeout={0,200000};setsockopt(peer,SOL_SOCKET,SO_RCVTIMEO,&timeout,sizeof(timeout));setsockopt(peer,SOL_SOCKET,SO_SNDTIMEO,&timeout,sizeof(timeout));serve_peer(peer);close(peer);}}}
    sd_bus_unref(system_bus);return 0;
}
