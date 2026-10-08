#ifndef GUIDE_IPC_ENVELOPE_H
#define GUIDE_IPC_ENVELOPE_H

#include <stddef.h>
#include <stdint.h>

#define GUIDE_IPC_HEADER_SIZE 24u
#define GUIDE_IPC_MAX_PAYLOAD 32768u
#define GUIDE_IPC_MAX_PACKET (GUIDE_IPC_HEADER_SIZE + GUIDE_IPC_MAX_PAYLOAD)
#define GUIDE_IPC_MAX_DESCRIPTORS 4u
#define GUIDE_IPC_MAGIC_0 'G'
#define GUIDE_IPC_MAGIC_1 'I'
#define GUIDE_IPC_MAGIC_2 'P'
#define GUIDE_IPC_MAGIC_3 'C'
#define GUIDE_IPC_ENVELOPE_MAJOR 1u
#define GUIDE_IPC_ENVELOPE_MINOR 0u
#define GUIDE_IPC_INTERFACE_MAJOR 1u
#define GUIDE_IPC_INTERFACE_MINOR 0u

enum guide_ipc_message_class {
    GUIDE_IPC_REQUEST = 1,
    GUIDE_IPC_REPLY = 2,
    GUIDE_IPC_EVENT = 3,
    GUIDE_IPC_CANCEL = 4
};

struct guide_ipc_header {
    uint8_t envelope_major;
    uint8_t envelope_minor;
    uint8_t message_class;
    uint8_t flags;
    uint16_t interface_major;
    uint16_t interface_minor;
    uint64_t request_id;
    uint16_t payload_length;
    uint8_t descriptor_count;
    uint8_t reserved;
};

enum guide_ipc_error {
    GUIDE_IPC_VALID = 0,
    GUIDE_IPC_BAD_LENGTH,
    GUIDE_IPC_BAD_MAGIC,
    GUIDE_IPC_BAD_ENVELOPE_VERSION,
    GUIDE_IPC_BAD_CLASS,
    GUIDE_IPC_BAD_RESERVED,
    GUIDE_IPC_BAD_INTERFACE,
    GUIDE_IPC_BAD_REQUEST_ID,
    GUIDE_IPC_BAD_DESCRIPTOR_COUNT,
    GUIDE_IPC_BAD_CBOR
};

void guide_ipc_encode_header(uint8_t out[GUIDE_IPC_HEADER_SIZE],
                             const struct guide_ipc_header *header);
enum guide_ipc_error guide_ipc_decode_packet(const uint8_t *packet,
                                              size_t packet_size,
                                              uint8_t received_descriptors,
                                              struct guide_ipc_header *header);
int guide_ipc_validate_cbor(const uint8_t *payload, size_t payload_size);
const char *guide_ipc_error_name(enum guide_ipc_error error);

#endif
