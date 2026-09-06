// SPDX-License-Identifier: AGPL-3.0-or-later

#include "wifi.h"

#include <ctype.h>
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

#define WIFI_DIR "/var/lib/guideos/wifi"
#define WIFI_CONFIG WIFI_DIR "/saved.conf"
#define WIFI_PENDING WIFI_DIR "/pending.conf"
#define WIFI_PID WIFI_DIR "/wpa_supplicant.pid"

static void set_message(char *message, size_t size, const char *format, ...)
{
    va_list arguments;
    if (!message || size == 0) return;
    va_start(arguments, format);
    (void)vsnprintf(message, size, format, arguments);
    va_end(arguments);
}

static int run_capture(char *const arguments[], const char *input,
                       char *output, size_t output_size, FILE *log)
{
    int out_pipe[2], in_pipe[2] = {-1, -1}, status = -1;
    pid_t child;
    size_t used = 0;
    if (pipe(out_pipe) != 0 || (input && pipe(in_pipe) != 0)) return -1;
    child = fork();
    if (child == 0) {
        int nullfd;
        (void)dup2(out_pipe[1], STDOUT_FILENO);
        if (input) (void)dup2(in_pipe[0], STDIN_FILENO);
        else {
            nullfd = open("/dev/null", O_RDONLY);
            if (nullfd >= 0) (void)dup2(nullfd, STDIN_FILENO);
        }
        (void)dup2(out_pipe[1], STDERR_FILENO);
        close(out_pipe[0]); close(out_pipe[1]);
        if (input) { close(in_pipe[0]); close(in_pipe[1]); }
        execv(arguments[0], arguments);
        _exit(127);
    }
    close(out_pipe[1]);
    if (input) {
        size_t length = strlen(input), sent = 0;
        close(in_pipe[0]);
        while (sent < length) {
            ssize_t count = write(in_pipe[1], input + sent, length - sent);
            if (count <= 0) break;
            sent += (size_t)count;
        }
        close(in_pipe[1]);
    }
    if (child < 0) { close(out_pipe[0]); return -1; }
    for (;;) {
        char discard[1024];
        char *destination = used + 1 < output_size ? output + used : discard;
        size_t capacity = used + 1 < output_size ? output_size - used - 1 : sizeof(discard);
        ssize_t count = read(out_pipe[0], destination, capacity);
        if (count <= 0) break;
        if (destination != discard) used += (size_t)count;
    }
    close(out_pipe[0]);
    if (output_size) output[used < output_size ? used : output_size - 1] = '\0';
    if (waitpid(child, &status, 0) < 0) return -1;
    if (!WIFEXITED(status) || WEXITSTATUS(status) != 0) {
        fprintf(log, "wifi command failed program=%s status=%d\n", arguments[0], status);
        return -1;
    }
    return 0;
}

static int busybox(char *const arguments[], char *output, size_t size, FILE *log)
{
    return run_capture(arguments, NULL, output, size, log);
}

static int sanitize_resolver(FILE *log)
{
    char input[4096], output[4096], *line, *save = NULL;
    size_t used = 0;
    ssize_t count;
    int source = -1, destination = -1;
    source = open("/etc/resolv.conf", O_RDONLY | O_NOFOLLOW);
    if (source < 0) return -1;
    count = read(source, input, sizeof(input) - 1);
    close(source);
    if (count <= 0) return -1;
    input[count] = '\0';
    for (line = strtok_r(input, "\n", &save); line; line = strtok_r(NULL, "\n", &save)) {
        char *comment = strchr(line, '#');
        size_t length;
        if (comment) *comment = '\0';
        length = strlen(line);
        while (length && (line[length - 1] == ' ' || line[length - 1] == '\t' ||
                          line[length - 1] == '\r')) --length;
        if (!length) continue;
        if (used + length + 1 >= sizeof(output)) return -1;
        memcpy(output + used, line, length); used += length; output[used++] = '\n';
    }
    if (!used) return -1;
    unlink("/etc/resolv.conf.guide-new");
    destination = open("/etc/resolv.conf.guide-new",
                       O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW, 0644);
    if (destination < 0 || write(destination, output, used) != (ssize_t)used ||
        fsync(destination) != 0) {
        if (destination >= 0) close(destination);
        unlink("/etc/resolv.conf.guide-new");
        return -1;
    }
    close(destination);
    if (rename("/etc/resolv.conf.guide-new", "/etc/resolv.conf") != 0) {
        unlink("/etc/resolv.conf.guide-new");
        return -1;
    }
    fprintf(log, "wifi resolver configuration sanitized\n"); fflush(log);
    return 0;
}

int guide_wifi_available(void)
{
    return access("/sys/class/net/wlan0", F_OK) == 0 &&
           access("/usr/sbin/iw", X_OK) == 0 &&
           access("/usr/sbin/wpa_supplicant", X_OK) == 0;
}

int guide_wifi_link_up(void)
{
    char value[4] = "";
    int fd = open("/sys/class/net/wlan0/carrier", O_RDONLY | O_NOFOLLOW);
    ssize_t count;
    if (fd < 0) return 0;
    count = read(fd, value, sizeof(value) - 1);
    close(fd);
    return count > 0 && value[0] == '1';
}

static void add_network(struct guide_wifi_list *list, const char *ssid,
                        int signal, int secured)
{
    unsigned i;
    if (!ssid[0]) return;
    for (i = 0; i < list->count; ++i) {
        if (strcmp(list->networks[i].ssid, ssid) == 0) {
            if (signal > list->networks[i].signal_dbm) {
                list->networks[i].signal_dbm = signal;
                list->networks[i].secured = secured;
            }
            return;
        }
    }
    if (list->count < GUIDE_WIFI_MAX_NETWORKS) {
        struct guide_wifi_network *item = &list->networks[list->count++];
        (void)snprintf(item->ssid, sizeof(item->ssid), "%s", ssid);
        item->signal_dbm = signal;
        item->secured = secured;
    }
}

static int compare_signal(const void *left, const void *right)
{
    const struct guide_wifi_network *a = left, *b = right;
    return b->signal_dbm - a->signal_dbm;
}

int guide_wifi_scan(struct guide_wifi_list *list, FILE *log)
{
    char output[131072], *line, *save = NULL, ssid[GUIDE_WIFI_SSID_MAX + 1] = "";
    char *up[] = {"/bin/busybox", "ip", "link", "set", "wlan0", "up", NULL};
    char *scan[] = {"/usr/sbin/iw", "dev", "wlan0", "scan", NULL};
    int signal = -100, secured = 0, active = 0;
    memset(list, 0, sizeof(*list));
    if (!guide_wifi_available()) {
        set_message(list->message, sizeof(list->message), "WIFI RADIO NOT READY");
        return -1;
    }
    (void)busybox(up, output, sizeof(output), log);
    if (run_capture(scan, NULL, output, sizeof(output), log) != 0) {
        set_message(list->message, sizeof(list->message), "SCAN FAILED - TRY AGAIN");
        return -1;
    }
    for (line = strtok_r(output, "\n", &save); line; line = strtok_r(NULL, "\n", &save)) {
        while (*line == ' ' || *line == '\t') ++line;
        if (strncmp(line, "BSS ", 4) == 0) {
            if (active) add_network(list, ssid, signal, secured);
            ssid[0] = '\0'; signal = -100; secured = 0; active = 1;
        } else if (strncmp(line, "signal:", 7) == 0) {
            signal = (int)strtol(line + 7, NULL, 10);
        } else if (strncmp(line, "capability:", 11) == 0 && strstr(line, "Privacy")) {
            secured = 1;
        } else if (strncmp(line, "RSN:", 4) == 0 || strncmp(line, "WPA:", 4) == 0) {
            secured = 1;
        } else if (strncmp(line, "SSID:", 5) == 0) {
            const char *value = line + 5;
            while (*value == ' ') ++value;
            (void)snprintf(ssid, sizeof(ssid), "%s", value);
        }
    }
    if (active) add_network(list, ssid, signal, secured);
    qsort(list->networks, list->count, sizeof(list->networks[0]), compare_signal);
    set_message(list->message, sizeof(list->message), list->count ?
                "SELECT A NETWORK" : "NO NETWORKS FOUND");
    fprintf(log, "wifi scan complete networks=%u\n", list->count);
    fflush(log);
    return list->count ? 0 : -1;
}

static void ssid_hex(const char *ssid, char *hex, size_t size)
{
    static const char digits[] = "0123456789abcdef";
    size_t i, length = strlen(ssid);
    if (length * 2 + 1 > size) length = (size - 1) / 2;
    for (i = 0; i < length; ++i) {
        unsigned char value = (unsigned char)ssid[i];
        hex[i * 2] = digits[value >> 4];
        hex[i * 2 + 1] = digits[value & 15];
    }
    hex[length * 2] = '\0';
}

static int write_config(const struct guide_wifi_network *network,
                        const char *password, FILE *log)
{
    char generated[4096], filtered[4096], input[GUIDE_WIFI_PASSWORD_MAX + 2];
    char hex[GUIDE_WIFI_SSID_MAX * 2 + 1];
    char *passphrase[] = {"/usr/sbin/wpa_passphrase", (char *)network->ssid, NULL};
    size_t used = 0;
    int fd;
    if (mkdir("/var/lib/guideos", 0755) != 0 && errno != EEXIST) return -1;
    if (mkdir(WIFI_DIR, 0700) != 0 && errno != EEXIST) return -1;
    (void)chmod(WIFI_DIR, 0700);
    if (network->secured) {
        if (!password || strlen(password) < 8 || strlen(password) > GUIDE_WIFI_PASSWORD_MAX)
            return -1;
        (void)snprintf(input, sizeof(input), "%s\n", password);
        if (run_capture(passphrase, input, generated, sizeof(generated), log) != 0) return -1;
        {
            char *line, *save = NULL;
            for (line = strtok_r(generated, "\n", &save); line; line = strtok_r(NULL, "\n", &save)) {
                size_t length;
                while (*line == ' ' || *line == '\t') {
                    if (strncmp(line, "#psk=", 5) == 0) break;
                    ++line;
                }
                if (strncmp(line, "#psk=", 5) == 0) continue;
                length = strlen(line);
                if (used + length + 2 >= sizeof(filtered)) return -1;
                memcpy(filtered + used, line, length); used += length;
                filtered[used++] = '\n';
            }
            filtered[used] = '\0';
            {
                static const char prefix[] = "ctrl_interface=" WIFI_DIR "\nupdate_config=0\n";
                size_t prefix_length = sizeof(prefix) - 1;
                if (used + prefix_length + 1 >= sizeof(filtered)) return -1;
                memmove(filtered + prefix_length, filtered, used + 1);
                memcpy(filtered, prefix, prefix_length);
                used += prefix_length;
            }
        }
    } else {
        ssid_hex(network->ssid, hex, sizeof(hex));
        (void)snprintf(filtered, sizeof(filtered),
                       "ctrl_interface=" WIFI_DIR "\nupdate_config=0\nnetwork={\nssid=%s\nkey_mgmt=NONE\n}\n", hex);
        used = strlen(filtered);
    }
    unlink(WIFI_PENDING);
    fd = open(WIFI_PENDING, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW, 0600);
    if (fd < 0 || write(fd, filtered, used) != (ssize_t)used || fsync(fd) != 0) {
        if (fd >= 0) close(fd);
        unlink(WIFI_PENDING);
        return -1;
    }
    close(fd);
    return 0;
}

static void stop_owned_supplicant(FILE *log)
{
    FILE *file = fopen(WIFI_PID, "r");
    long pid = -1;
    if (file) { (void)fscanf(file, "%ld", &pid); fclose(file); }
    if (pid > 1 && pid < 4194304) {
        char path[64], command[256] = "";
        int fd;
        ssize_t count;
        (void)snprintf(path, sizeof(path), "/proc/%ld/cmdline", pid);
        fd = open(path, O_RDONLY | O_NOFOLLOW);
        count = fd >= 0 ? read(fd, command, sizeof(command) - 1) : -1;
        if (fd >= 0) close(fd);
        if (count <= 0 || !strstr(command, "wpa_supplicant")) {
            fprintf(log, "wifi ignored stale or foreign pid file pid=%ld\n", pid);
            unlink(WIFI_PID);
            return;
        }
        if (kill((pid_t)pid, SIGTERM) == 0) {
            struct timespec pause = {0, 300000000};
            nanosleep(&pause, NULL);
            fprintf(log, "wifi stopped owned supplicant pid=%ld\n", pid);
        }
    }
    unlink(WIFI_PID);
}

int guide_wifi_connect(const struct guide_wifi_network *network,
                       const char *password, FILE *log,
                       char *message, size_t message_size)
{
    char output[8192];
    char *up[] = {"/bin/busybox", "ip", "link", "set", "wlan0", "up", NULL};
    char *wpa[] = {"/usr/sbin/wpa_supplicant", "-B", "-i", "wlan0", "-c",
                   WIFI_PENDING, "-P", WIFI_PID, NULL};
    char *link[] = {"/usr/sbin/iw", "dev", "wlan0", "link", NULL};
    char *dhcp[] = {"/bin/busybox", "udhcpc", "-i", "wlan0", "-q", "-n", "-t", "5", NULL};
    char connected_ssid[GUIDE_WIFI_SSID_MAX + 1], address[32];
    int attempt, associated = 0;
    if (write_config(network, password, log) != 0) {
        set_message(message, message_size, "PASSWORD MUST BE 8 TO 63 CHARACTERS");
        return -1;
    }
    stop_owned_supplicant(log);
    (void)busybox(up, output, sizeof(output), log);
    if (run_capture(wpa, NULL, output, sizeof(output), log) != 0) goto failed;
    for (attempt = 0; attempt < 20; ++attempt) {
        struct timespec pause = {1, 0};
        if (run_capture(link, NULL, output, sizeof(output), log) == 0 &&
            strstr(output, "Connected to")) { associated = 1; break; }
        nanosleep(&pause, NULL);
    }
    if (!associated || busybox(dhcp, output, sizeof(output), log) != 0) goto failed;
    if (sanitize_resolver(log) != 0) goto failed;
    if (!guide_wifi_status(connected_ssid, sizeof(connected_ssid), address, sizeof(address)) ||
        !address[0]) goto failed;
    if (rename(WIFI_PENDING, WIFI_CONFIG) != 0) goto failed;
    (void)chmod(WIFI_CONFIG, 0600);
    set_message(message, message_size, "CONNECTED");
    fprintf(log, "wifi connection established and saved\n"); fflush(log);
    return 0;
failed:
    stop_owned_supplicant(log); unlink(WIFI_PENDING);
    set_message(message, message_size, "CONNECTION FAILED - CHECK PASSWORD");
    return -1;
}

void guide_wifi_autoconnect(void)
{
    pid_t child;
    if (access(WIFI_CONFIG, R_OK) != 0) return;
    child = fork();
    if (child != 0) return;
    {
        FILE *log = fopen("/guide-wifi-autoconnect.txt", "w");
        char output[8192], connected_ssid[GUIDE_WIFI_SSID_MAX + 1], address[32];
        char *up[] = {"/bin/busybox", "ip", "link", "set", "wlan0", "up", NULL};
        char *wpa[] = {"/usr/sbin/wpa_supplicant", "-B", "-i", "wlan0", "-c",
                       WIFI_CONFIG, "-P", WIFI_PID, NULL};
        char *link[] = {"/usr/sbin/iw", "dev", "wlan0", "link", NULL};
        char *dhcp[] = {"/bin/busybox", "udhcpc", "-i", "wlan0", "-q", "-n", "-t", "5", NULL};
        int wait_count, associated = 0;
        struct timespec pause = {1, 0};
        if (!log) log = stderr;
        for (wait_count = 0; wait_count < 30 && !guide_wifi_available(); ++wait_count)
            nanosleep(&pause, NULL);
        if (!guide_wifi_available()) {
            fprintf(log, "saved network deferred: radio unavailable\n");
            if (log != stderr) fclose(log);
            _exit(1);
        }
        stop_owned_supplicant(log);
        (void)busybox(up, output, sizeof(output), log);
        if (run_capture(wpa, NULL, output, sizeof(output), log) == 0) {
            for (wait_count = 0; wait_count < 20; ++wait_count) {
                if (run_capture(link, NULL, output, sizeof(output), log) == 0 &&
                    strstr(output, "Connected to")) { associated = 1; break; }
                nanosleep(&pause, NULL);
            }
        }
        if (associated && busybox(dhcp, output, sizeof(output), log) == 0 &&
            sanitize_resolver(log) == 0 &&
            guide_wifi_status(connected_ssid, sizeof(connected_ssid), address, sizeof(address)) &&
            address[0]) {
            fprintf(log, "saved network restored with address\n");
        } else {
            fprintf(log, "saved network reconnect failed\n");
            stop_owned_supplicant(log);
        }
        fflush(log);
        if (log != stderr) fclose(log);
        _exit(0);
    }
}

int guide_wifi_disconnect(FILE *log, char *message, size_t message_size)
{
    char output[1024];
    char *flush[] = {"/bin/busybox", "ip", "addr", "flush", "dev", "wlan0", NULL};
    stop_owned_supplicant(log);
    (void)busybox(flush, output, sizeof(output), log);
    set_message(message, message_size, "DISCONNECTED - NETWORK STILL SAVED");
    return 0;
}

int guide_wifi_forget(FILE *log, char *message, size_t message_size)
{
    (void)guide_wifi_disconnect(log, message, message_size);
    if (unlink(WIFI_CONFIG) != 0 && errno != ENOENT) {
        set_message(message, message_size, "COULD NOT FORGET SAVED NETWORK");
        return -1;
    }
    set_message(message, message_size, "SAVED NETWORK FORGOTTEN");
    return 0;
}

int guide_wifi_status(char *ssid, size_t ssid_size,
                      char *address, size_t address_size)
{
    char output[4096], *position, *end;
    FILE *sink = fopen("/dev/null", "w");
    char *link[] = {"/usr/sbin/iw", "dev", "wlan0", "link", NULL};
    char *ip[] = {"/bin/busybox", "ip", "-4", "addr", "show", "dev", "wlan0", NULL};
    if (ssid_size) ssid[0] = '\0';
    if (address_size) address[0] = '\0';
    if (!sink) sink = stderr;
    if (run_capture(link, NULL, output, sizeof(output), sink) != 0 || !strstr(output, "Connected to")) {
        if (sink != stderr) fclose(sink);
        return 0;
    }
    position = strstr(output, "SSID: ");
    if (position) {
        position += 6; end = strchr(position, '\n');
        if (end) *end = '\0';
        (void)snprintf(ssid, ssid_size, "%s", position);
    }
    if (run_capture(ip, NULL, output, sizeof(output), sink) == 0 && (position = strstr(output, "inet ")) != NULL) {
        position += 5; end = strchr(position, '/');
        if (end) *end = '\0';
        (void)snprintf(address, address_size, "%s", position);
    }
    if (sink != stderr) fclose(sink);
    return 1;
}
