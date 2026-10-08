#include "guide_control_codec.h"
#include "guide_foundation.h"
#include "guide_ipc_transport.h"

#include <errno.h>
#include <poll.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/random.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <time.h>
#include <unistd.h>
#include <sys/un.h>

#define SUPERVISOR_SOCKET "/run/guideos/supervisor/control.sock"
#define HEALTH_CAPABILITY 1u
#define MAX_CAPABILITY 8u
static volatile sig_atomic_t stopping;
static struct guide_foundation state;
static void stop_handler(int value){(void)value;stopping=1;}
static uint64_t boottime_ns(void){struct timespec value;if(clock_gettime(CLOCK_BOOTTIME,&value)!=0)return 0;return (uint64_t)value.tv_sec*1000000000ULL+(uint64_t)value.tv_nsec;}

static int connect_supervisor(void){int fd=socket(AF_UNIX,SOCK_SEQPACKET|SOCK_CLOEXEC,0);struct sockaddr_un address;if(fd<0)return -1;struct timeval timeout={0,200000};setsockopt(fd,SOL_SOCKET,SO_RCVTIMEO,&timeout,sizeof(timeout));setsockopt(fd,SOL_SOCKET,SO_SNDTIMEO,&timeout,sizeof(timeout));memset(&address,0,sizeof(address));address.sun_family=AF_UNIX;strcpy(address.sun_path,SUPERVISOR_SOCKET);if(connect(fd,(struct sockaddr*)&address,sizeof(address))<0){close(fd);return -1;}return fd;}
static int supervisor_resolve(const struct ucred *credentials,uint8_t instance_id[16],uint64_t *generation,uint64_t *app_code,uint64_t *policy_mask)
{
    struct guide_control_value args[3]={{0,GUIDE_CONTROL_UINT,(uint64_t)credentials->pid,{0}},{1,GUIDE_CONTROL_UINT,(uint64_t)credentials->uid,{0}},{2,GUIDE_CONTROL_UINT,(uint64_t)credentials->gid,{0}}};uint8_t payload[128];size_t length;int fd;struct guide_ipc_header header={1,0,GUIDE_IPC_REQUEST,0,1,0,1,0,0,0};struct guide_ipc_message message;struct guide_ipc_header response;enum guide_ipc_error protocol;struct guide_control_reply reply;
    length=guide_control_encode_request(payload,sizeof(payload),2,args,3,boottime_ns()+2000000000ULL);if(length==0||(fd=connect_supervisor())<0)return -1;header.payload_length=(uint16_t)length;if(guide_ipc_send(fd,&header,payload,NULL)!=GUIDE_IPC_IO_OK){close(fd);return -1;}memset(&message,0,sizeof(message));if(guide_ipc_receive(fd,&message,&response,&protocol)!=GUIDE_IPC_IO_OK){close(fd);return -1;}close(fd);if(response.message_class!=GUIDE_IPC_REPLY||response.request_id!=1||guide_control_decode_reply(message.bytes+GUIDE_IPC_HEADER_SIZE,response.payload_length,&reply)<0||reply.outcome!=0||guide_control_reply_bytes16(&reply,0,instance_id)<0||guide_control_reply_uint(&reply,1,generation)<0||guide_control_reply_uint(&reply,2,app_code)<0||guide_control_reply_uint(&reply,3,policy_mask)<0){guide_ipc_message_close(&message);return -1;}guide_ipc_message_close(&message);return 0;
}

static int supervisor_terminal(const struct guide_instance *app) {
    struct guide_control_value args[2]={{0,GUIDE_CONTROL_BYTES16,0,{0}},{1,GUIDE_CONTROL_UINT,app->generation,{0}}};
    memcpy(args[0].bytes,app->instance_id,16);uint8_t payload[128];size_t length=guide_control_encode_request(payload,sizeof(payload),4,args,2,boottime_ns()+2000000000ULL);
    int fd=connect_supervisor();if(fd<0)return 0;
    struct guide_ipc_header header={1,0,GUIDE_IPC_REQUEST,0,1,0,1,0,0,0},response;header.payload_length=(uint16_t)length;
    struct guide_ipc_message message={0};enum guide_ipc_error protocol;struct guide_control_reply reply;uint64_t phase=0;int terminal=0;
    if(guide_ipc_send(fd,&header,payload,NULL)==GUIDE_IPC_IO_OK&&guide_ipc_receive(fd,&message,&response,&protocol)==GUIDE_IPC_IO_OK&&response.message_class==GUIDE_IPC_REPLY&&response.request_id==1&&guide_control_decode_reply(message.bytes+GUIDE_IPC_HEADER_SIZE,response.payload_length,&reply)==0){
        if(reply.outcome==6)terminal=1;
        else if(reply.outcome==0&&guide_control_reply_uint(&reply,0,&phase)==0)terminal=phase==GUIDE_PHASE_EXITED||phase==GUIDE_PHASE_FAILED;
    }
    guide_ipc_message_close(&message);close(fd);return terminal;
}

static int ensure_instance(const struct ucred *credentials,uint8_t instance[16],uint64_t *generation,uint64_t *app_code,uint64_t *policy_mask)
{
    enum guide_foundation_result status;if(supervisor_resolve(credentials,instance,generation,app_code,policy_mask)<0)return -1;
    char app[32];snprintf(app,sizeof(app),"%llu",(unsigned long long)*app_code);
    for(size_t i=0;i<GUIDE_FOUNDATION_MAX_INSTANCES;++i){struct guide_instance *old=&state.instances[i];if(old->occupied&&!strcmp(old->app_id,app)&&old->generation!=*generation&&old->phase!=GUIDE_PHASE_FAILED&&old->phase!=GUIDE_PHASE_EXITED)(void)guide_instance_transition(&state,old->instance_id,old->generation,GUIDE_PHASE_FAILED);}
    /* Reclaim observed terminal identities across different package IDs too. */
    size_t used=0;for(size_t i=0;i<GUIDE_FOUNDATION_MAX_INSTANCES;++i)if(state.instances[i].occupied&&state.instances[i].phase!=GUIDE_PHASE_EXITED&&state.instances[i].phase!=GUIDE_PHASE_FAILED)++used;
    if(used>=GUIDE_FOUNDATION_MAX_INSTANCES-1)for(size_t i=0;i<GUIDE_FOUNDATION_MAX_INSTANCES;++i){struct guide_instance *old=&state.instances[i];if(old->occupied&&old->phase!=GUIDE_PHASE_EXITED&&old->phase!=GUIDE_PHASE_FAILED&&supervisor_terminal(old))(void)guide_instance_transition(&state,old->instance_id,old->generation,GUIDE_PHASE_FAILED);}
    status=guide_instance_admit(&state,instance,*generation,1,(uint32_t)credentials->uid,app,"resolved-application.service");
    if(status==GUIDE_FOUNDATION_OK){(void)guide_instance_transition(&state,instance,*generation,GUIDE_PHASE_STARTING);(void)guide_instance_transition(&state,instance,*generation,GUIDE_PHASE_RUNNING);}
    else if(status!=GUIDE_FOUNDATION_STALE)return -1;
    return 0;
}

static int send_reply(int peer,const struct guide_ipc_header *request,uint16_t outcome,const struct guide_control_value *values,size_t count)
{
    uint8_t payload[256];size_t length=guide_control_encode_reply(payload,sizeof(payload),outcome,values,count);struct guide_ipc_header response=*request;if(length==0)return -1;response.message_class=GUIDE_IPC_REPLY;response.payload_length=(uint16_t)length;response.descriptor_count=0;return guide_ipc_send(peer,&response,payload,NULL)==GUIDE_IPC_IO_OK?0:-1;
}

static void serve(int listener_index,int peer)
{
    struct ucred credentials;socklen_t credential_length=sizeof(credentials);struct guide_ipc_message message;struct guide_ipc_header header;enum guide_ipc_error protocol;struct guide_control_request request;struct guide_control_value results[3];uint8_t instance[16],grant[16];uint64_t generation=0,capability=0,app_code=0,policy_mask=0;uint16_t outcome=1;size_t count=0;
    memset(&message,0,sizeof(message));if(getsockopt(peer,SOL_SOCKET,SO_PEERCRED,&credentials,&credential_length)!=0){perror("broker peer credentials");return;}if(listener_index!=2&&ensure_instance(&credentials,instance,&generation,&app_code,&policy_mask)<0){fprintf(stderr,"broker resolve failed pid=%ld uid=%lu gid=%lu\n",(long)credentials.pid,(unsigned long)credentials.uid,(unsigned long)credentials.gid);return;}
    if(guide_ipc_receive(peer,&message,&header,&protocol)!=GUIDE_IPC_IO_OK)return;
    if(header.message_class!=GUIDE_IPC_REQUEST||header.interface_major!=1||guide_control_decode_request(message.bytes+GUIDE_IPC_HEADER_SIZE,header.payload_length,&request)<0||request.deadline_ns<=boottime_ns())goto done;
    memset(results,0,sizeof(results));
    if(listener_index==0){
        if(request.operation==1){results[0]=(struct guide_control_value){0,GUIDE_CONTROL_UINT,state.registry_revision,{0}};outcome=0;count=1;}
        else if(request.operation==2&&guide_control_get_uint(&request,0,&capability)==0){results[0]=(struct guide_control_value){0,GUIDE_CONTROL_UINT,capability>=1&&capability<=MAX_CAPABILITY&&(policy_mask&(1u<<(capability-1))),{0}};results[1]=(struct guide_control_value){1,GUIDE_CONTROL_UINT,1,{0}};outcome=0;count=2;}
        else if(request.operation==3&&guide_control_get_uint(&request,0,&capability)==0&&capability>=1&&capability<=MAX_CAPABILITY&&(policy_mask&(1u<<(capability-1)))&&getrandom(grant,16,0)==16){uint64_t expiry=boottime_ns()+60000000000ULL;if(guide_grant_issue(&state,grant,instance,generation,1,1u<<(capability-1),expiry)==GUIDE_FOUNDATION_OK){results[0].key=0;results[0].type=GUIDE_CONTROL_BYTES16;memcpy(results[0].bytes,grant,16);results[1]=(struct guide_control_value){1,GUIDE_CONTROL_UINT,expiry,{0}};outcome=0;count=2;}}
        else if(request.operation==4&&guide_control_get_uint(&request,0,&capability)==0){uint64_t current=0;enum guide_foundation_result watch=guide_watch_revision(&state,capability,&current);results[0]=(struct guide_control_value){0,GUIDE_CONTROL_UINT,current,{0}};outcome=watch==GUIDE_FOUNDATION_OK?0:11;count=1;}
        else if(request.operation==5&&guide_control_get_bytes16(&request,0,grant)==0){for(size_t i=0;i<GUIDE_FOUNDATION_MAX_GRANTS;++i){struct guide_grant *g=&state.grants[i];if(g->occupied&&g->generation==generation&&!memcmp(g->instance_id,instance,16)&&!memcmp(g->grant_id,grant,16)){if(!g->revoked)(void)guide_grant_revoke(&state,grant);results[0]=(struct guide_control_value){0,GUIDE_CONTROL_UINT,1,{0}};outcome=0;count=1;break;}}}
        else if(request.operation==6&&guide_control_get_bytes16(&request,0,grant)==0&&guide_control_get_uint(&request,1,&capability)==0&&capability>=1&&capability<=MAX_CAPABILITY&&(policy_mask&(1u<<(capability-1)))&&guide_grant_validate(&state,grant,instance,generation,1,(uint16_t)capability,boottime_ns())==GUIDE_FOUNDATION_OK){results[0]=(struct guide_control_value){0,GUIDE_CONTROL_UINT,1,{0}};outcome=0;count=1;}
        else if(request.operation==7&&guide_control_get_bytes16(&request,0,grant)==0&&guide_control_get_uint(&request,1,&capability)==0&&capability>=1&&capability<=MAX_CAPABILITY&&(policy_mask&(1u<<(capability-1)))&&guide_grant_validate(&state,grant,instance,generation,1,(uint16_t)capability,boottime_ns())==GUIDE_FOUNDATION_OK){for(size_t i=0;i<GUIDE_FOUNDATION_MAX_GRANTS;++i)if(state.grants[i].occupied&&!memcmp(state.grants[i].grant_id,grant,16)){state.grants[i].expires_ns=boottime_ns()+60000000000ULL;results[0]=(struct guide_control_value){0,GUIDE_CONTROL_UINT,state.grants[i].expires_ns,{0}};outcome=0;count=1;break;}}
        else outcome=6;
    } else if(listener_index==1){if(request.operation==1&&guide_control_get_bytes16(&request,0,grant)==0&&guide_grant_validate(&state,grant,instance,generation,1,1,boottime_ns())==GUIDE_FOUNDATION_OK){results[0]=(struct guide_control_value){0,GUIDE_CONTROL_UINT,1,{0}};results[1]=(struct guide_control_value){1,GUIDE_CONTROL_UINT,state.registry_revision,{0}};outcome=0;count=2;}else outcome=6;
    } else {uint64_t pid=0,uid=0,gid=0;struct ucred target;if(request.operation==1&&guide_control_get_bytes16(&request,0,grant)==0&&guide_control_get_uint(&request,1,&capability)==0&&guide_control_get_uint(&request,2,&pid)==0&&guide_control_get_uint(&request,3,&uid)==0&&guide_control_get_uint(&request,4,&gid)==0&&pid>0&&pid<=INT32_MAX&&uid<=UINT32_MAX&&gid<=UINT32_MAX&&capability>=1&&capability<=MAX_CAPABILITY){target.pid=(pid_t)pid;target.uid=(uid_t)uid;target.gid=(gid_t)gid;if(supervisor_resolve(&target,instance,&generation,&app_code,&policy_mask)==0&&(policy_mask&(1u<<(capability-1)))&&guide_grant_validate(&state,grant,instance,generation,1,(uint16_t)capability,boottime_ns())==GUIDE_FOUNDATION_OK){results[0]=(struct guide_control_value){0,GUIDE_CONTROL_UINT,1,{0}};results[1].key=1;results[1].type=GUIDE_CONTROL_BYTES16;memcpy(results[1].bytes,instance,16);results[2]=(struct guide_control_value){2,GUIDE_CONTROL_UINT,generation,{0}};outcome=0;count=3;}}else outcome=6;}
done:(void)send_reply(peer,&header,outcome,results,count);guide_ipc_message_close(&message);
}

int main(void)
{
    struct stat info;struct pollfd listeners[3]={{-1,POLLIN,0},{-1,POLLIN,0},{-1,POLLIN,0}};
    const char *paths[3]={"/run/guideos/brokers/control.sock","/run/guideos/brokers/health.sock","/run/guideos/brokers/provider.sock"};
    /* systemd does not promise ordering across separately activated sockets. */
    for(int fd=3;fd<6;++fd){struct sockaddr_un address;memset(&address,0,sizeof(address));socklen_t length=sizeof(address);if(fstat(fd,&info)!=0||!S_ISSOCK(info.st_mode)||getsockname(fd,(struct sockaddr *)&address,&length)!=0||address.sun_family!=AF_UNIX)return 1;address.sun_path[sizeof(address.sun_path)-1]=0;int found=0;for(int i=0;i<3;++i)if(!strcmp(address.sun_path,paths[i])){if(listeners[i].fd!=-1)return 1;listeners[i].fd=fd;found=1;break;}if(!found)return 1;}
    for(int i=0;i<3;++i){if(listeners[i].fd<0)return 1;}
    guide_foundation_init(&state,boottime_ns()^(uint64_t)getpid());guide_foundation_set_reconciled(&state,true);signal(SIGTERM,stop_handler);signal(SIGINT,stop_handler);
    while(!stopping){int status=poll(listeners,3,1000);if(status<0&&errno!=EINTR)return 1;if(status>0)for(int i=0;i<3;++i)if(listeners[i].revents&POLLIN){int peer=accept4(listeners[i].fd,NULL,NULL,SOCK_CLOEXEC);if(peer>=0){struct timeval timeout={0,200000};setsockopt(peer,SOL_SOCKET,SO_RCVTIMEO,&timeout,sizeof(timeout));setsockopt(peer,SOL_SOCKET,SO_SNDTIMEO,&timeout,sizeof(timeout));serve(i,peer);close(peer);}}}return 0;
}
