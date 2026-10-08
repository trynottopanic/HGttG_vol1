#ifndef GUIDE_IPC_TRANSPORT_H
#define GUIDE_IPC_TRANSPORT_H
#include "guide_ipc_envelope.h"
#include <stddef.h>
#include <stdint.h>

struct guide_ipc_message {
    uint8_t bytes[GUIDE_IPC_MAX_PACKET];
    size_t size;
    int descriptors[GUIDE_IPC_MAX_DESCRIPTORS];
    uint8_t descriptor_count;
};

enum guide_ipc_io_result {
    GUIDE_IPC_IO_OK=0,
    GUIDE_IPC_IO_CLOSED,
    GUIDE_IPC_IO_SYSTEM,
    GUIDE_IPC_IO_TRUNCATED,
    GUIDE_IPC_IO_ANCILLARY,
    GUIDE_IPC_IO_PROTOCOL,
    GUIDE_IPC_IO_PARTIAL
};

void guide_ipc_message_close(struct guide_ipc_message *message);
enum guide_ipc_io_result guide_ipc_receive(int socket_fd, struct guide_ipc_message *message, struct guide_ipc_header *header, enum guide_ipc_error *protocol_error);
enum guide_ipc_io_result guide_ipc_send(int socket_fd, const struct guide_ipc_header *header, const uint8_t *payload, const int *descriptors);
#endif
