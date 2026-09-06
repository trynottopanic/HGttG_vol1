// SPDX-License-Identifier: AGPL-3.0-or-later

#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

#define STATE_DIR "/var/lib/guideos/developer-link"
#define HOST_KEY STATE_DIR "/host-ed25519"
#define PID_FILE STATE_DIR "/dropbear.pid"
#define ENABLED_FILE STATE_DIR "/enabled"
#define DROPBEAR "/usr/sbin/dropbear"

static int run(char *const arguments[], char *output, size_t output_size)
{
    int descriptors[2], status;
    pid_t child;
    size_t used = 0;
    if (pipe(descriptors) != 0) return -1;
    child = fork();
    if (child == 0) {
        (void)dup2(descriptors[1], STDOUT_FILENO);
        (void)dup2(descriptors[1], STDERR_FILENO);
        close(descriptors[0]); close(descriptors[1]);
        execv(arguments[0], arguments);
        _exit(127);
    }
    close(descriptors[1]);
    if (child < 0) { close(descriptors[0]); return -1; }
    for (;;) {
        char discard[512];
        char *destination = used + 1 < output_size ? output + used : discard;
        size_t capacity = used + 1 < output_size ? output_size - used - 1 : sizeof(discard);
        ssize_t count = read(descriptors[0], destination, capacity);
        if (count <= 0) break;
        if (destination != discard) used += (size_t)count;
    }
    close(descriptors[0]);
    if (output_size) output[used < output_size ? used : output_size - 1] = '\0';
    return waitpid(child, &status, 0) >= 0 && WIFEXITED(status) && WEXITSTATUS(status) == 0 ? 0 : -1;
}

static int owned_pid(void)
{
    FILE *file = fopen(PID_FILE, "r");
    char path[64], command[256] = "";
    long pid = -1;
    int fd;
    ssize_t count;
    if (file) { (void)fscanf(file, "%ld", &pid); fclose(file); }
    if (pid <= 1 || pid >= 4194304) return -1;
    (void)snprintf(path, sizeof(path), "/proc/%ld/cmdline", pid);
    fd = open(path, O_RDONLY | O_NOFOLLOW);
    count = fd >= 0 ? read(fd, command, sizeof(command) - 1) : -1;
    if (fd >= 0) close(fd);
    return count > 0 && strstr(command, "dropbear") ? (int)pid : -1;
}

static int stop_link(void)
{
    int pid = owned_pid();
    if (pid > 1) {
        struct timespec pause = {0, 300000000};
        if (kill((pid_t)pid, SIGTERM) != 0 && errno != ESRCH) return -1;
        nanosleep(&pause, NULL);
    }
    unlink(PID_FILE);
    unlink(ENABLED_FILE);
    return 0;
}

static int current_address(char address[48])
{
    char output[2048], *start, *end;
    char *arguments[] = {"/bin/busybox", "ip", "-4", "addr", "show", "dev", "wlan0", NULL};
    if (run(arguments, output, sizeof(output)) != 0) return -1;
    start = strstr(output, "inet ");
    if (!start) return -1;
    start += 5; end = strchr(start, '/');
    if (!end || (size_t)(end - start) >= 48) return -1;
    memcpy(address, start, (size_t)(end - start)); address[end - start] = '\0';
    return 0;
}

static int create_empty(const char *path, mode_t mode)
{
    int fd = open(path, O_WRONLY | O_CREAT | O_TRUNC | O_NOFOLLOW, mode);
    if (fd < 0) return -1;
    if (fsync(fd) != 0) { close(fd); return -1; }
    close(fd); return chmod(path, mode);
}

static int start_link(void)
{
    char output[2048], address[48], endpoint[64];
    char *key_arguments[] = {"/usr/bin/dropbearkey", "-t", "ed25519", "-f", HOST_KEY, NULL};
    pid_t child;
    if (owned_pid() > 1) return 0;
    unlink(PID_FILE);
    if (mkdir("/var/lib/guideos", 0755) != 0 && errno != EEXIST) return -1;
    if (mkdir(STATE_DIR, 0700) != 0 && errno != EEXIST) return -1;
    (void)chmod(STATE_DIR, 0700);
    if (access(HOST_KEY, R_OK) != 0) {
        if (run(key_arguments, output, sizeof(output)) != 0) return -1;
        (void)chmod(HOST_KEY, 0600);
    }
    if (current_address(address) != 0) return -1;
    (void)snprintf(endpoint, sizeof(endpoint), "%s:2222", address);
    child = fork();
    if (child == 0) {
        execl(DROPBEAR, "dropbear", "-F", "-E", "-s", "-g", "-j", "-k",
              "-p", endpoint, "-r", HOST_KEY, "-P", PID_FILE, (char *)NULL);
        _exit(127);
    }
    if (child < 0) return -1;
    {
        struct timespec pause = {0, 500000000};
        nanosleep(&pause, NULL);
    }
    if (owned_pid() <= 1) return -1;
    return create_empty(ENABLED_FILE, 0600);
}

int main(int argc, char **argv)
{
    if (argc != 2) return 2;
    if (strcmp(argv[1], "start") == 0) return start_link() == 0 ? 0 : 1;
    if (strcmp(argv[1], "stop") == 0) return stop_link() == 0 ? 0 : 1;
    if (strcmp(argv[1], "status") == 0) return owned_pid() > 1 ? 0 : 1;
    return 2;
}
