#include "guide_ipc_transport.h"
#include <errno.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/uio.h>
#include <unistd.h>

void guide_ipc_message_close(struct guide_ipc_message *m) {
    if (!m) return;
    for (uint8_t i=0;i<m->descriptor_count;i++) if (m->descriptors[i]>=0) close(m->descriptors[i]);
    m->descriptor_count=0; m->size=0;
}

enum guide_ipc_io_result guide_ipc_receive(int fd, struct guide_ipc_message *m, struct guide_ipc_header *h, enum guide_ipc_error *pe) {
    union { struct cmsghdr align; unsigned char bytes[CMSG_SPACE(sizeof(int)*GUIDE_IPC_MAX_DESCRIPTORS)]; } control;
    struct iovec iov; struct msghdr msg; ssize_t got;
    if (!m || !h || !pe) { errno=EINVAL; return GUIDE_IPC_IO_SYSTEM; }
    memset(m,0,sizeof(*m)); for (unsigned i=0;i<GUIDE_IPC_MAX_DESCRIPTORS;i++) m->descriptors[i]=-1;
    memset(&msg,0,sizeof(msg)); memset(&control,0,sizeof(control));
    iov.iov_base=m->bytes; iov.iov_len=sizeof(m->bytes); msg.msg_iov=&iov; msg.msg_iovlen=1; msg.msg_control=control.bytes; msg.msg_controllen=sizeof(control.bytes);
    do got=recvmsg(fd,&msg,MSG_CMSG_CLOEXEC); while (got<0 && errno==EINTR);
    if (got==0) return GUIDE_IPC_IO_CLOSED;
    if (got<0) return GUIDE_IPC_IO_SYSTEM;
    m->size=(size_t)got;
    for (struct cmsghdr *c=CMSG_FIRSTHDR(&msg);c;c=CMSG_NXTHDR(&msg,c)) {
        if (c->cmsg_level!=SOL_SOCKET || c->cmsg_type!=SCM_RIGHTS || c->cmsg_len<CMSG_LEN(0)) { guide_ipc_message_close(m); return GUIDE_IPC_IO_ANCILLARY; }
        size_t bytes=c->cmsg_len-CMSG_LEN(0); if (bytes%sizeof(int) || bytes/sizeof(int)>GUIDE_IPC_MAX_DESCRIPTORS-m->descriptor_count) { guide_ipc_message_close(m); return GUIDE_IPC_IO_ANCILLARY; }
        memcpy(m->descriptors+m->descriptor_count,CMSG_DATA(c),bytes); m->descriptor_count+=(uint8_t)(bytes/sizeof(int));
    }
    if (msg.msg_flags&(MSG_TRUNC|MSG_CTRUNC)) { guide_ipc_message_close(m); return GUIDE_IPC_IO_TRUNCATED; }
    *pe=guide_ipc_decode_packet(m->bytes,m->size,m->descriptor_count,h);
    if (*pe!=GUIDE_IPC_VALID) { guide_ipc_message_close(m); return GUIDE_IPC_IO_PROTOCOL; }
    return GUIDE_IPC_IO_OK;
}

enum guide_ipc_io_result guide_ipc_send(int fd,const struct guide_ipc_header *h,const uint8_t *payload,const int *fds) {
    uint8_t header[GUIDE_IPC_HEADER_SIZE]; struct iovec iov[2]; struct msghdr msg; union { struct cmsghdr align; unsigned char bytes[CMSG_SPACE(sizeof(int)*GUIDE_IPC_MAX_DESCRIPTORS)]; } control; ssize_t sent;
    if (!h || (!payload && h->payload_length) || h->descriptor_count>GUIDE_IPC_MAX_DESCRIPTORS || (h->descriptor_count && !fds) || !guide_ipc_validate_cbor(payload,h->payload_length)) { errno=EINVAL; return GUIDE_IPC_IO_PROTOCOL; }
    guide_ipc_encode_header(header,h); memset(&msg,0,sizeof(msg)); iov[0]=(struct iovec){header,sizeof(header)}; iov[1]=(struct iovec){(void*)payload,h->payload_length}; msg.msg_iov=iov; msg.msg_iovlen=2;
    if (h->descriptor_count) { memset(&control,0,sizeof(control)); msg.msg_control=control.bytes; msg.msg_controllen=CMSG_SPACE(sizeof(int)*h->descriptor_count); struct cmsghdr *c=CMSG_FIRSTHDR(&msg); c->cmsg_level=SOL_SOCKET; c->cmsg_type=SCM_RIGHTS; c->cmsg_len=CMSG_LEN(sizeof(int)*h->descriptor_count); memcpy(CMSG_DATA(c),fds,sizeof(int)*h->descriptor_count); }
    do sent=sendmsg(fd,&msg,MSG_NOSIGNAL); while(sent<0 && errno==EINTR);
    if(sent<0) return GUIDE_IPC_IO_SYSTEM;
    return (size_t)sent==GUIDE_IPC_HEADER_SIZE+h->payload_length?GUIDE_IPC_IO_OK:GUIDE_IPC_IO_PARTIAL;
}
