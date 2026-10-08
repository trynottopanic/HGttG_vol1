#include "guide_control_codec.h"
#include "guide_ipc_transport.h"

#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <sys/un.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

static uint64_t next_request=1;
static uint64_t boottime_ns(void){struct timespec value;if(clock_gettime(CLOCK_BOOTTIME,&value)!=0)return 0;return (uint64_t)value.tv_sec*1000000000ULL+(uint64_t)value.tv_nsec;}
static int connect_path(const char *path){int fd=socket(AF_UNIX,SOCK_SEQPACKET|SOCK_CLOEXEC,0);struct sockaddr_un address;if(fd<0){perror("probe socket");return -1;}memset(&address,0,sizeof(address));address.sun_family=AF_UNIX;if(strlen(path)>=sizeof(address.sun_path)){close(fd);return -1;}strcpy(address.sun_path,path);if(connect(fd,(struct sockaddr*)&address,sizeof(address))<0){fprintf(stderr,"probe connect %s: ",path);perror("");close(fd);return -1;}return fd;}
static int exchange(const char *path,uint16_t operation,const struct guide_control_value *arguments,size_t count,struct guide_control_reply *reply)
{
    uint8_t payload[256];size_t length=guide_control_encode_request(payload,sizeof(payload),operation,arguments,count,boottime_ns()+3000000000ULL);int fd;struct guide_ipc_header request={1,0,GUIDE_IPC_REQUEST,0,1,0,0,0,0,0},response;struct guide_ipc_message message;enum guide_ipc_error protocol;if(length==0||(fd=connect_path(path))<0)return -1;request.request_id=next_request++;request.payload_length=(uint16_t)length;if(guide_ipc_send(fd,&request,payload,NULL)!=GUIDE_IPC_IO_OK){close(fd);return -1;}memset(&message,0,sizeof(message));if(guide_ipc_receive(fd,&message,&response,&protocol)!=GUIDE_IPC_IO_OK){close(fd);return -1;}close(fd);if(response.message_class!=GUIDE_IPC_REPLY||response.request_id!=request.request_id||guide_control_decode_reply(message.bytes+GUIDE_IPC_HEADER_SIZE,response.payload_length,reply)<0){guide_ipc_message_close(&message);return -1;}guide_ipc_message_close(&message);return reply->outcome==0?0:-1;
}
int main(void)
{
    const char *control="/run/guideos/brokers/control.sock",*health="/run/guideos/brokers/health.sock";struct guide_control_reply reply;struct guide_control_value argument;uint64_t revision,offered,major,expiry;uint8_t grant[16],missing[16]={0};pid_t worker=fork();if(worker<0)return 1;if(worker==0){usleep(300000);_exit(0);}
    if(exchange(control,1,NULL,0,&reply)<0||guide_control_reply_uint(&reply,0,&revision)<0){fputs("probe stage snapshot\n",stderr);goto fail;}
    argument=(struct guide_control_value){0,GUIDE_CONTROL_UINT,1,{0}};if(exchange(control,2,&argument,1,&reply)<0||guide_control_reply_uint(&reply,0,&offered)<0||guide_control_reply_uint(&reply,1,&major)<0||offered!=1||major!=1){fputs("probe stage resolve\n",stderr);goto fail;}
    argument=(struct guide_control_value){0,GUIDE_CONTROL_BYTES16,0,{0}};memcpy(argument.bytes,missing,16);if(exchange(health,1,&argument,1,&reply)==0){fputs("probe accepted missing grant\n",stderr);goto fail;}
    argument=(struct guide_control_value){0,GUIDE_CONTROL_UINT,1,{0}};
    if(exchange(control,3,&argument,1,&reply)<0||guide_control_reply_bytes16(&reply,0,grant)<0||guide_control_reply_uint(&reply,1,&expiry)<0||expiry<=boottime_ns()){fputs("probe stage acquire\n",stderr);goto fail;}
    puts("GUIDE_GRANT_ACQUIRED");fflush(stdout);sleep(5);
    argument.key=0;argument.type=GUIDE_CONTROL_BYTES16;memcpy(argument.bytes,grant,16);if(exchange(health,1,&argument,1,&reply)==0){fputs("probe retained grant across broker restart\n",stderr);goto fail;}
    argument=(struct guide_control_value){0,GUIDE_CONTROL_UINT,1,{0}};if(exchange(control,3,&argument,1,&reply)<0||guide_control_reply_bytes16(&reply,0,grant)<0){fputs("probe stage reacquire\n",stderr);goto fail;}
    argument.key=0;argument.type=GUIDE_CONTROL_BYTES16;memcpy(argument.bytes,grant,16);if(exchange(health,1,&argument,1,&reply)<0){fputs("probe stage health\n",stderr);goto fail;}
    argument=(struct guide_control_value){0,GUIDE_CONTROL_UINT,revision,{0}};if(exchange(control,4,&argument,1,&reply)<0){
        if(reply.outcome!=11||exchange(control,1,NULL,0,&reply)<0||guide_control_reply_uint(&reply,0,&revision)<0){fputs("probe stage resnapshot\n",stderr);goto fail;}
        puts("GUIDE_RESNAPSHOT_REQUIRED_PASS");fflush(stdout);argument=(struct guide_control_value){0,GUIDE_CONTROL_UINT,revision,{0}};if(exchange(control,4,&argument,1,&reply)<0){fputs("probe stage watch\n",stderr);goto fail;}
    }
    argument.key=0;argument.type=GUIDE_CONTROL_BYTES16;memcpy(argument.bytes,grant,16);if(exchange(control,5,&argument,1,&reply)<0){fputs("probe stage release\n",stderr);goto fail;}
    if(exchange(health,1,&argument,1,&reply)==0){fputs("probe accepted released grant\n",stderr);goto fail;}
    if(waitpid(worker,NULL,0)!=worker)return 1;
    puts("GUIDE_IPC_PROBE_PASS");fflush(stdout);sleep(10);return 0;
fail:kill(worker,SIGTERM);(void)waitpid(worker,NULL,0);fputs("GUIDE_IPC_PROBE_FAIL\n",stderr);return 1;
}
