#define _GNU_SOURCE
#include "guide_ipc_envelope.h"

#include <cbor.h>
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <sys/un.h>
#include <time.h>
#include <unistd.h>

#define CONTROL_SIZE CMSG_SPACE(sizeof(int) * GUIDE_IPC_MAX_DESCRIPTORS)

static void die(const char *message) { perror(message); exit(2); }

static int seqpacket_socket(void) {
    int fd = socket(AF_UNIX, SOCK_SEQPACKET | SOCK_CLOEXEC, 0);
    if (fd < 0) die("socket");
    return fd;
}

static void address(struct sockaddr_un *addr, const char *path) {
    size_t n = strlen(path);
    if (n == 0 || n >= sizeof(addr->sun_path)) {
        fprintf(stderr, "invalid socket path\n"); exit(2);
    }
    memset(addr, 0, sizeof(*addr));
    addr->sun_family = AF_UNIX;
    memcpy(addr->sun_path, path, n + 1);
}

static int listen_socket(const char *path) {
    const char *listen_pid = getenv("LISTEN_PID");
    const char *listen_fds = getenv("LISTEN_FDS");
    if (listen_pid && listen_fds && strtol(listen_pid, NULL, 10) == getpid() &&
        strcmp(listen_fds, "1") == 0) return 3;
    int fd = seqpacket_socket();
    struct sockaddr_un addr;
    address(&addr, path);
    unlink(path);
    if (bind(fd, (struct sockaddr *)&addr, sizeof(addr)) < 0) die("bind");
    if (listen(fd, 8) < 0) die("listen");
    return fd;
}

static int connect_socket(const char *path) {
    int fd = seqpacket_socket();
    struct sockaddr_un addr;
    address(&addr, path);
    if (connect(fd, (struct sockaddr *)&addr, sizeof(addr)) < 0) die("connect");
    return fd;
}

static size_t receive(int fd, uint8_t packet[GUIDE_IPC_MAX_PACKET], int descriptors[4],
                      uint8_t *descriptor_count, int *message_flags) {
    struct iovec iov = {.iov_base = packet, .iov_len = GUIDE_IPC_MAX_PACKET};
    char control[CONTROL_SIZE];
    struct msghdr msg = {0};
    msg.msg_iov = &iov; msg.msg_iovlen = 1;
    msg.msg_control = control; msg.msg_controllen = sizeof(control);
    ssize_t got = recvmsg(fd, &msg, MSG_CMSG_CLOEXEC | MSG_TRUNC);
    if (got < 0) die("recvmsg");
    *descriptor_count = 0;
    *message_flags = msg.msg_flags;
    for (struct cmsghdr *cmsg = CMSG_FIRSTHDR(&msg); cmsg;
         cmsg = CMSG_NXTHDR(&msg, cmsg)) {
        if (cmsg->cmsg_level != SOL_SOCKET || cmsg->cmsg_type != SCM_RIGHTS) {
            *message_flags |= MSG_CTRUNC; continue;
        }
        size_t bytes = cmsg->cmsg_len - CMSG_LEN(0);
        size_t count = bytes / sizeof(int);
        int *values = (int *)CMSG_DATA(cmsg);
        for (size_t i = 0; i < count; ++i) {
            if (*descriptor_count < GUIDE_IPC_MAX_DESCRIPTORS)
                descriptors[(*descriptor_count)++] = values[i];
            else { close(values[i]); *message_flags |= MSG_CTRUNC; }
        }
    }
    return (size_t)got;
}

static void send_one(int fd, const uint8_t *packet, size_t length, int descriptor) {
    struct iovec iov = {.iov_base = (void *)packet, .iov_len = length};
    char control[CMSG_SPACE(sizeof(int))];
    struct msghdr msg = {0};
    msg.msg_iov = &iov; msg.msg_iovlen = 1;
    if (descriptor >= 0) {
        memset(control, 0, sizeof(control));
        msg.msg_control = control; msg.msg_controllen = sizeof(control);
        struct cmsghdr *cmsg = CMSG_FIRSTHDR(&msg);
        cmsg->cmsg_level = SOL_SOCKET; cmsg->cmsg_type = SCM_RIGHTS;
        cmsg->cmsg_len = CMSG_LEN(sizeof(int));
        memcpy(CMSG_DATA(cmsg), &descriptor, sizeof(descriptor));
    }
    ssize_t sent = sendmsg(fd, &msg, MSG_NOSIGNAL);
    if (sent < 0 || (size_t)sent != length) die("sendmsg");
}

static cbor_item_t *build_uint(uint64_t value) {
    return value <= UINT8_MAX ? cbor_build_uint8((uint8_t)value) :
           value <= UINT16_MAX ? cbor_build_uint16((uint16_t)value) :
           value <= UINT32_MAX ? cbor_build_uint32((uint32_t)value) :
                                 cbor_build_uint64(value);
}

static bool map_add_uint(cbor_item_t *map, uint64_t key, cbor_item_t *value) {
    cbor_item_t *key_item = key <= UINT8_MAX ? cbor_build_uint8((uint8_t)key) :
                            key <= UINT16_MAX ? cbor_build_uint16((uint16_t)key) :
                            key <= UINT32_MAX ? cbor_build_uint32((uint32_t)key) :
                                                cbor_build_uint64(key);
    if (!key_item || !value) return false;
    bool ok = cbor_map_add(map, (struct cbor_pair){key_item, value});
    cbor_decref(&key_item); cbor_decref(&value);
    return ok;
}

static cbor_item_t *make_request(void) {
    struct timespec now;
    clock_gettime(CLOCK_BOOTTIME, &now);
    uint64_t deadline = (uint64_t)now.tv_sec * 1000000000u + now.tv_nsec + 30000000000u;
    cbor_item_t *map = cbor_new_definite_map(3);
    if (!map || !map_add_uint(map, 0, cbor_build_uint8(1)) ||
        !map_add_uint(map, 1, cbor_new_definite_map(0)) ||
        !map_add_uint(map, 2, cbor_build_uint64(deadline))) {
        if (map) cbor_decref(&map);
        return NULL;
    }
    return map;
}

static cbor_item_t *make_reply(pid_t peer_pid) {
    cbor_item_t *body = cbor_new_definite_map(2);
    cbor_item_t *top = cbor_new_definite_map(2);
    if (!body || !top || !map_add_uint(body, 0, build_uint((uint32_t)peer_pid)) ||
        !map_add_uint(body, 1, cbor_build_bool(true)) ||
        !map_add_uint(top, 0, cbor_build_uint8(0)) || !map_add_uint(top, 1, body)) {
        if (body) cbor_decref(&body);
        if (top) cbor_decref(&top);
        return NULL;
    }
    return top;
}

static uint8_t *packet_from_item(uint8_t message_class, uint64_t request_id,
                                 uint8_t descriptor_count, cbor_item_t *item,
                                 size_t *packet_size) {
    unsigned char *payload = NULL;
    size_t payload_size = 0;
    cbor_serialize_alloc(item, &payload, &payload_size);
    if (!payload || payload_size > GUIDE_IPC_MAX_PAYLOAD ||
        !guide_ipc_validate_cbor(payload, payload_size)) {
        free(payload); return NULL;
    }
    *packet_size = GUIDE_IPC_HEADER_SIZE + payload_size;
    uint8_t *packet = malloc(*packet_size);
    if (!packet) { free(payload); return NULL; }
    struct guide_ipc_header h = {GUIDE_IPC_ENVELOPE_MAJOR, GUIDE_IPC_ENVELOPE_MINOR,
        message_class, 0, GUIDE_IPC_INTERFACE_MAJOR, GUIDE_IPC_INTERFACE_MINOR,
        request_id, (uint16_t)payload_size, descriptor_count, 0};
    guide_ipc_encode_header(packet, &h);
    memcpy(packet + GUIDE_IPC_HEADER_SIZE, payload, payload_size);
    free(payload);
    return packet;
}

static int server(const char *path) {
    int listener = listen_socket(path);
    int client = accept4(listener, NULL, NULL, SOCK_CLOEXEC);
    if (client < 0) die("accept4");
    struct ucred cred; socklen_t cred_len = sizeof(cred);
    if (getsockopt(client, SOL_SOCKET, SO_PEERCRED, &cred, &cred_len) < 0)
        die("SO_PEERCRED");
    int pidfd = (int)syscall(SYS_pidfd_open, cred.pid, 0);
    if (pidfd < 0) die("pidfd_open");

    uint8_t packet[GUIDE_IPC_MAX_PACKET]; int fds[4], flags;
    uint8_t fd_count;
    size_t length = receive(client, packet, fds, &fd_count, &flags);
    if (flags & (MSG_TRUNC | MSG_CTRUNC)) {
        fprintf(stderr, "protocol: truncation\n"); goto reject;
    }
    struct guide_ipc_header header;
    enum guide_ipc_error error = guide_ipc_decode_packet(packet, length, fd_count, &header);
    if (error != GUIDE_IPC_VALID || header.message_class != GUIDE_IPC_REQUEST) {
        fprintf(stderr, "protocol: %s\n", guide_ipc_error_name(error)); goto reject;
    }
    struct cbor_load_result result;
    cbor_item_t *decoded = cbor_load(packet + GUIDE_IPC_HEADER_SIZE,
                                     header.payload_length, &result);
    if (!decoded || result.error.code != CBOR_ERR_NONE || !cbor_isa_map(decoded)) {
        fprintf(stderr, "libcbor decode failure\n"); if (decoded) cbor_decref(&decoded); goto reject;
    }
    cbor_decref(&decoded);
    if (fd_count != 1) { fprintf(stderr, "descriptor proof missing\n"); goto reject; }
    struct stat status;
    if (fstat(fds[0], &status) < 0) die("fstat transferred descriptor");

    cbor_item_t *reply = make_reply(cred.pid);
    size_t reply_size;
    uint8_t *reply_packet = packet_from_item(GUIDE_IPC_REPLY, header.request_id, 0,
                                             reply, &reply_size);
    if (!reply_packet) { fprintf(stderr, "reply encode failure\n"); exit(2); }
    send_one(client, reply_packet, reply_size, -1);
    printf("C_SERVER_PASS peer_pid=%ld pidfd=%d descriptor_mode=%o\n",
           (long)cred.pid, pidfd, status.st_mode & S_IFMT);
    free(reply_packet); cbor_decref(&reply);
    close(fds[0]); close(pidfd); close(client); close(listener);
    if (!(getenv("LISTEN_FDS"))) unlink(path);
    return 0;
reject:
    for (uint8_t i = 0; i < fd_count; ++i) close(fds[i]);
    close(pidfd); close(client); close(listener);
    if (!(getenv("LISTEN_FDS"))) unlink(path);
    return 3;
}

static int client(const char *path) {
    int fd = connect_socket(path);
    cbor_item_t *request = make_request();
    size_t packet_size;
    uint8_t *packet = packet_from_item(GUIDE_IPC_REQUEST, 0x1020304050607080ULL, 1,
                                       request, &packet_size);
    if (!packet) { fprintf(stderr, "request encode failure\n"); return 2; }
    int transferred = open("/dev/null", O_RDONLY | O_CLOEXEC);
    if (transferred < 0) die("open /dev/null");
    send_one(fd, packet, packet_size, transferred);
    close(transferred); free(packet); cbor_decref(&request);

    uint8_t response[GUIDE_IPC_MAX_PACKET]; int fds[4], flags;
    uint8_t fd_count;
    size_t length = receive(fd, response, fds, &fd_count, &flags);
    struct guide_ipc_header header;
    enum guide_ipc_error error = guide_ipc_decode_packet(response, length, fd_count, &header);
    if ((flags & (MSG_TRUNC | MSG_CTRUNC)) || error != GUIDE_IPC_VALID ||
        header.message_class != GUIDE_IPC_REPLY ||
        header.request_id != 0x1020304050607080ULL) {
        fprintf(stderr, "C client response validation failed: %s\n", guide_ipc_error_name(error));
        return 3;
    }
    struct cbor_load_result result;
    cbor_item_t *decoded = cbor_load(response + GUIDE_IPC_HEADER_SIZE,
                                     header.payload_length, &result);
    if (!decoded || result.error.code != CBOR_ERR_NONE) return 3;
    cbor_decref(&decoded);
    printf("C_CLIENT_PASS reply_bytes=%zu\n", length);
    close(fd);
    return 0;
}

int main(int argc, char **argv) {
    signal(SIGPIPE, SIG_IGN);
    if (argc != 3) { fprintf(stderr, "usage: %s server|client SOCKET\n", argv[0]); return 2; }
    if (strcmp(argv[1], "server") == 0) return server(argv[2]);
    if (strcmp(argv[1], "client") == 0) return client(argv[2]);
    fprintf(stderr, "unknown mode\n"); return 2;
}
