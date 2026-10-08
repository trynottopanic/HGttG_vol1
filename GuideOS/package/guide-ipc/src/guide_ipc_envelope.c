#include "guide_ipc_envelope.h"

#include <stdbool.h>
#include <string.h>

#define PROFILE_MAX_DEPTH 6u
#define PROFILE_MAX_MAP 32u
#define PROFILE_MAX_ARRAY 64u
#define PROFILE_MAX_VALUES 256u
#define PROFILE_MAX_STRING 24576u

struct cursor {
    const uint8_t *data;
    size_t size;
    size_t pos;
    size_t values;
};

static uint16_t read_be16(const uint8_t *p) {
    return (uint16_t)(((uint16_t)p[0] << 8) | p[1]);
}

static uint64_t read_be64(const uint8_t *p) {
    uint64_t value = 0;
    for (unsigned i = 0; i < 8; ++i) value = (value << 8) | p[i];
    return value;
}

static void write_be16(uint8_t *p, uint16_t value) {
    p[0] = (uint8_t)(value >> 8);
    p[1] = (uint8_t)value;
}

static void write_be64(uint8_t *p, uint64_t value) {
    for (int i = 7; i >= 0; --i) {
        p[i] = (uint8_t)value;
        value >>= 8;
    }
}

void guide_ipc_encode_header(uint8_t out[GUIDE_IPC_HEADER_SIZE],
                             const struct guide_ipc_header *h) {
    out[0] = GUIDE_IPC_MAGIC_0;
    out[1] = GUIDE_IPC_MAGIC_1;
    out[2] = GUIDE_IPC_MAGIC_2;
    out[3] = GUIDE_IPC_MAGIC_3;
    out[4] = h->envelope_major;
    out[5] = h->envelope_minor;
    out[6] = h->message_class;
    out[7] = h->flags;
    write_be16(out + 8, h->interface_major);
    write_be16(out + 10, h->interface_minor);
    write_be64(out + 12, h->request_id);
    write_be16(out + 20, h->payload_length);
    out[22] = h->descriptor_count;
    out[23] = h->reserved;
}

static bool take(struct cursor *c, size_t amount, const uint8_t **out) {
    if (amount > c->size - c->pos) return false;
    *out = c->data + c->pos;
    c->pos += amount;
    return true;
}

static bool head(struct cursor *c, uint8_t *major, uint64_t *value) {
    const uint8_t *p;
    uint8_t initial, ai;
    if (!take(c, 1, &p)) return false;
    initial = *p;
    *major = initial >> 5;
    ai = initial & 31u;
    if (ai < 24u) { *value = ai; return true; }
    if (ai == 24u) {
        if (!take(c, 1, &p) || p[0] < 24u) return false;
        *value = p[0]; return true;
    }
    if (ai == 25u) {
        if (!take(c, 2, &p)) return false;
        *value = ((uint64_t)p[0] << 8) | p[1];
        return *value > UINT8_MAX;
    }
    if (ai == 26u) {
        if (!take(c, 4, &p)) return false;
        *value = ((uint64_t)p[0] << 24) | ((uint64_t)p[1] << 16) |
                 ((uint64_t)p[2] << 8) | p[3];
        return *value > UINT16_MAX;
    }
    if (ai == 27u) {
        if (!take(c, 8, &p)) return false;
        *value = read_be64(p);
        return *value > UINT32_MAX;
    }
    return false;
}

static bool utf8_valid(const uint8_t *s, size_t n) {
    size_t i = 0;
    while (i < n) {
        uint8_t a = s[i++];
        uint32_t cp;
        unsigned need;
        if (a < 0x80) continue;
        if (a >= 0xC2 && a <= 0xDF) { cp = a & 0x1F; need = 1; }
        else if (a >= 0xE0 && a <= 0xEF) { cp = a & 0x0F; need = 2; }
        else if (a >= 0xF0 && a <= 0xF4) { cp = a & 0x07; need = 3; }
        else return false;
        if (need > n - i) return false;
        for (unsigned j = 0; j < need; ++j) {
            uint8_t b = s[i++];
            if ((b & 0xC0) != 0x80) return false;
            cp = (cp << 6) | (b & 0x3F);
        }
        if ((need == 2 && cp < 0x800) || (need == 3 && cp < 0x10000) ||
            cp > 0x10FFFF || (cp >= 0xD800 && cp <= 0xDFFF)) return false;
    }
    return true;
}

static bool item(struct cursor *c, unsigned depth) {
    uint8_t major;
    uint64_t value;
    const uint8_t *bytes;
    if (depth > PROFILE_MAX_DEPTH || ++c->values > PROFILE_MAX_VALUES) return false;
    if (!head(c, &major, &value)) return false;
    switch (major) {
    case 0: return true;
    case 1: return value <= INT64_MAX;
    case 2:
        return value <= PROFILE_MAX_STRING && take(c, (size_t)value, &bytes);
    case 3:
        return value <= PROFILE_MAX_STRING && take(c, (size_t)value, &bytes) &&
               utf8_valid(bytes, (size_t)value);
    case 4:
        if (value > PROFILE_MAX_ARRAY) return false;
        for (uint64_t i = 0; i < value; ++i) if (!item(c, depth + 1)) return false;
        return true;
    case 5: {
        uint64_t previous = 0;
        bool have_previous = false;
        if (value > PROFILE_MAX_MAP) return false;
        for (uint64_t i = 0; i < value; ++i) {
            uint8_t key_major;
            uint64_t key;
            if (++c->values > PROFILE_MAX_VALUES || !head(c, &key_major, &key) ||
                key_major != 0 || (have_previous && key <= previous)) return false;
            previous = key;
            have_previous = true;
            if (!item(c, depth + 1)) return false;
        }
        return true;
    }
    case 7:
        return value == 20u || value == 21u || value == 22u;
    default:
        return false;
    }
}

int guide_ipc_validate_cbor(const uint8_t *payload, size_t payload_size) {
    struct cursor c = {payload, payload_size, 0, 0};
    uint8_t initial;
    if (!payload || payload_size == 0) return 0;
    initial = payload[0];
    if ((initial >> 5) != 5u) return 0;
    if (!item(&c, 1)) return 0;
    return c.pos == c.size;
}

enum guide_ipc_error guide_ipc_decode_packet(const uint8_t *packet,
                                              size_t packet_size,
                                              uint8_t received_descriptors,
                                              struct guide_ipc_header *h) {
    if (!packet || !h || packet_size < GUIDE_IPC_HEADER_SIZE ||
        packet_size > GUIDE_IPC_MAX_PACKET) return GUIDE_IPC_BAD_LENGTH;
    if (packet[0] != GUIDE_IPC_MAGIC_0 || packet[1] != GUIDE_IPC_MAGIC_1 ||
        packet[2] != GUIDE_IPC_MAGIC_2 || packet[3] != GUIDE_IPC_MAGIC_3)
        return GUIDE_IPC_BAD_MAGIC;
    h->envelope_major = packet[4]; h->envelope_minor = packet[5];
    h->message_class = packet[6]; h->flags = packet[7];
    h->interface_major = read_be16(packet + 8);
    h->interface_minor = read_be16(packet + 10);
    h->request_id = read_be64(packet + 12);
    h->payload_length = read_be16(packet + 20);
    h->descriptor_count = packet[22]; h->reserved = packet[23];
    if (h->envelope_major != GUIDE_IPC_ENVELOPE_MAJOR)
        return GUIDE_IPC_BAD_ENVELOPE_VERSION;
    if (h->message_class < GUIDE_IPC_REQUEST || h->message_class > GUIDE_IPC_CANCEL)
        return GUIDE_IPC_BAD_CLASS;
    if (h->flags || h->reserved) return GUIDE_IPC_BAD_RESERVED;
    if (h->interface_major == 0) return GUIDE_IPC_BAD_INTERFACE;
    if ((h->message_class == GUIDE_IPC_EVENT && h->request_id != 0) ||
        (h->message_class != GUIDE_IPC_EVENT && h->request_id == 0))
        return GUIDE_IPC_BAD_REQUEST_ID;
    if (h->descriptor_count > GUIDE_IPC_MAX_DESCRIPTORS ||
        h->descriptor_count != received_descriptors)
        return GUIDE_IPC_BAD_DESCRIPTOR_COUNT;
    if (packet_size != GUIDE_IPC_HEADER_SIZE + h->payload_length)
        return GUIDE_IPC_BAD_LENGTH;
    if (!guide_ipc_validate_cbor(packet + GUIDE_IPC_HEADER_SIZE, h->payload_length))
        return GUIDE_IPC_BAD_CBOR;
    return GUIDE_IPC_VALID;
}

const char *guide_ipc_error_name(enum guide_ipc_error e) {
    static const char *names[] = {"valid", "bad-length", "bad-magic",
        "bad-envelope-version", "bad-class", "bad-reserved", "bad-interface",
        "bad-request-id", "bad-descriptor-count", "bad-cbor"};
    return (unsigned)e < sizeof(names) / sizeof(names[0]) ? names[e] : "unknown";
}
