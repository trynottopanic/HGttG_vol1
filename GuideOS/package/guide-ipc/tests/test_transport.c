#include "guide_ipc_transport.h"
#include <assert.h>
#include <fcntl.h>
#include <stdio.h>
#include <sys/socket.h>
#include <unistd.h>
int main(void){
 int s[2],p[2]; assert(socketpair(AF_UNIX,SOCK_SEQPACKET|SOCK_CLOEXEC,0,s)==0); assert(pipe2(p,O_CLOEXEC)==0);
 const uint8_t payload[]={0xa1,0x00,0x01}; struct guide_ipc_header out={1,0,GUIDE_IPC_REQUEST,0,1,0,7,sizeof(payload),1,0};
 assert(guide_ipc_send(s[0],&out,payload,&p[0])==GUIDE_IPC_IO_OK);
 struct guide_ipc_message message; struct guide_ipc_header in; enum guide_ipc_error error;
 assert(guide_ipc_receive(s[1],&message,&in,&error)==GUIDE_IPC_IO_OK); assert(in.request_id==7 && message.descriptor_count==1 && message.size==27);
 assert(fcntl(message.descriptors[0],F_GETFD)&FD_CLOEXEC); guide_ipc_message_close(&message); close(p[0]);close(p[1]);close(s[0]);close(s[1]); puts("C_TRANSPORT_PASS"); return 0;
}
