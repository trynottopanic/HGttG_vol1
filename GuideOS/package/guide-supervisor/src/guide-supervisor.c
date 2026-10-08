// SPDX-License-Identifier: AGPL-3.0-or-later

#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <linux/ioprio.h>
#include <poll.h>
#include <signal.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mount.h>
#include <sys/prctl.h>
#include <sys/reboot.h>
#include <sys/resource.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

#include "guide_supervisor_protocol.h"

#define GUIDE_SHELL "/usr/sbin/guide-hello-fb"
#define GUIDE_EMULATOR "/usr/bin/guide-emulator"
#define GUIDE_DOOM "/usr/bin/guide-doom"
#define GUIDE_WEB_BROWSER "/usr/bin/guide-web-browser"
#define GUIDE_WIKIPEDIA "/usr/bin/guide-wikipedia-rich"
#define GUIDE_PROCESS_LIMIT 64

enum process_kind { PROCESS_SHELL = 1, PROCESS_SESSION = 2, PROCESS_ORPHAN = 3 };

struct process_record {
    pid_t pid;
    pid_t pgid;
    enum process_kind kind;
    enum guide_priority_class priority;
    char name[48];
};

static struct process_record processes[GUIDE_PROCESS_LIMIT];
static pid_t shell_pid = -1;
static pid_t shell_pgid = -1;
static int shell_socket = -1;
static pid_t session_pid = -1;
static pid_t session_pgid = -1;
static FILE *log_file;
static volatile sig_atomic_t child_changed;
static volatile sig_atomic_t terminate_requested;

static void log_line(const char *format, ...)
{
    va_list arguments;
    time_t now = time(NULL);
    FILE *output = log_file ? log_file : stderr;
    fprintf(output, "%lld ", (long long)now);
    va_start(arguments, format);
    vfprintf(output, format, arguments);
    va_end(arguments);
    fputc('\n', output);
    fflush(output);
}

static void signal_handler(int signal_number)
{
    if (signal_number == SIGCHLD) child_changed = 1;
    else terminate_requested = 1;
}

static int priority_nice(enum guide_priority_class priority)
{
    static const int values[] = {-5, 0, 4, 10, 15};
    if ((unsigned)priority >= sizeof(values) / sizeof(values[0]))
        return values[GUIDE_PRIORITY_BACKGROUND];
    return values[priority];
}

static int priority_ioprio(enum guide_priority_class priority)
{
    if (priority == GUIDE_PRIORITY_SAFETY)
        return IOPRIO_PRIO_VALUE(IOPRIO_CLASS_BE, 0);
    if (priority == GUIDE_PRIORITY_FOREGROUND)
        return IOPRIO_PRIO_VALUE(IOPRIO_CLASS_BE, 3);
    if (priority == GUIDE_PRIORITY_COMMUNICATION)
        return IOPRIO_PRIO_VALUE(IOPRIO_CLASS_BE, 5);
    return IOPRIO_PRIO_VALUE(IOPRIO_CLASS_IDLE, 0);
}

static void apply_priority(enum guide_priority_class priority)
{
    (void)setpriority(PRIO_PROCESS, 0, priority_nice(priority));
#ifdef SYS_ioprio_set
    (void)syscall(SYS_ioprio_set, IOPRIO_WHO_PROCESS, 0, priority_ioprio(priority));
#endif
}

static void register_process(pid_t pid, pid_t pgid, enum process_kind kind,
                             enum guide_priority_class priority, const char *name)
{
    unsigned index;
    for (index = 0; index < GUIDE_PROCESS_LIMIT; ++index) {
        if (processes[index].pid != 0) continue;
        processes[index].pid = pid;
        processes[index].pgid = pgid;
        processes[index].kind = kind;
        processes[index].priority = priority;
        snprintf(processes[index].name, sizeof(processes[index].name), "%s", name);
        return;
    }
    log_line("registry full pid=%ld name=%s", (long)pid, name);
}

static struct process_record unregister_process(pid_t pid)
{
    struct process_record missing = {0};
    unsigned index;
    for (index = 0; index < GUIDE_PROCESS_LIMIT; ++index) {
        if (processes[index].pid != pid) continue;
        {
            struct process_record result = processes[index];
            memset(&processes[index], 0, sizeof(processes[index]));
            return result;
        }
    }
    return missing;
}

static void terminate_group(pid_t pgid, int grace_milliseconds)
{
    struct timespec pause = {0, 25000000};
    int elapsed = 0;
    if (pgid <= 1) return;
    if (kill(-pgid, SIGTERM) != 0 && errno == ESRCH) return;
    while (elapsed < grace_milliseconds) {
        if (kill(-pgid, 0) != 0 && errno == ESRCH) return;
        nanosleep(&pause, NULL);
        elapsed += 25;
    }
    if (kill(-pgid, 0) == 0) {
        (void)kill(-pgid, SIGKILL);
        log_line("process group forced pgid=%ld", (long)pgid);
    }
}

static void reap_available(void)
{
    int status;
    pid_t ended;
    child_changed = 0;
    while ((ended = waitpid(-1, &status, WNOHANG)) > 0) {
        struct process_record record = unregister_process(ended);
        if (ended == shell_pid) shell_pid = -1;
        if (ended == session_pid) session_pid = -1;
        log_line("reaped pid=%ld kind=%d name=%s status=%d", (long)ended,
                 record.kind, record.name[0] ? record.name : "unregistered", status);
    }
}

static int send_response(int descriptor, enum guide_supervisor_result result,
                         int status, int error_number, const char *message)
{
    struct guide_supervisor_response response;
    memset(&response, 0, sizeof(response));
    response.magic = GUIDE_SUPERVISOR_MAGIC;
    response.version = GUIDE_SUPERVISOR_VERSION;
    response.result = result;
    response.wait_status = status;
    response.error_number = error_number;
    snprintf(response.message, sizeof(response.message), "%s", message ? message : "");
    return send(descriptor, &response, sizeof(response), MSG_NOSIGNAL) ==
           (ssize_t)sizeof(response) ? 0 : -1;
}

static int request_valid(const struct guide_supervisor_request *request)
{
    return request->magic == GUIDE_SUPERVISOR_MAGIC &&
           request->version == GUIDE_SUPERVISOR_VERSION &&
           request->command >= GUIDE_SUPERVISOR_RUN &&
           request->command <= GUIDE_SUPERVISOR_SHUTDOWN &&
           request->argument0[sizeof(request->argument0) - 1] == '\0' &&
           request->argument1[sizeof(request->argument1) - 1] == '\0';
}

static const char *application_path(uint32_t application)
{
    if (application == GUIDE_APPLICATION_EMULATOR) return GUIDE_EMULATOR;
    if (application == GUIDE_APPLICATION_DOOM) return GUIDE_DOOM;
    if (application == GUIDE_APPLICATION_WEB_BROWSER) return GUIDE_WEB_BROWSER;
    if (application == GUIDE_APPLICATION_WIKIPEDIA) return GUIDE_WIKIPEDIA;
    return NULL;
}

static void session_exec(const struct guide_supervisor_request *request)
{
    const char *program = application_path(request->application);
    int descriptor;
    (void)setpgid(0, 0);
    apply_priority(GUIDE_PRIORITY_FOREGROUND);
    descriptor = open("/var/log/guide-session.log",
                      O_WRONLY | O_CREAT | O_APPEND | O_NOFOLLOW, 0600);
    if (descriptor >= 0) {
        (void)dup2(descriptor, STDOUT_FILENO);
        (void)dup2(descriptor, STDERR_FILENO);
        if (descriptor > STDERR_FILENO) close(descriptor);
    }
    if (request->application == GUIDE_APPLICATION_EMULATOR)
        execl(program, "guide-emulator", request->argument0,
              request->argument1, (char *)NULL);
    else if (request->application == GUIDE_APPLICATION_WEB_BROWSER)
        execl(program, "guide-web-browser", request->argument0, (char *)NULL);
    else if (request->application == GUIDE_APPLICATION_DOOM)
        execl(program, "guide-doom", request->argument0, (char *)NULL);
    else
        execl(program, "guide-wikipedia-rich", (char *)NULL);
    _exit(127);
}

static int wait_for_session(pid_t child, int *status)
{
    for (;;) {
        pid_t ended = waitpid(-1, status, 0);
        if (ended < 0) {
            if (errno == EINTR) {
                if (terminate_requested) return -1;
                continue;
            }
            return -1;
        }
        if (ended == child) {
            (void)unregister_process(ended);
            session_pid = -1;
            return 0;
        }
        {
            struct process_record record = unregister_process(ended);
            log_line("reaped during session pid=%ld kind=%d name=%s status=%d",
                     (long)ended, record.kind,
                     record.name[0] ? record.name : "orphan", *status);
        }
        if (ended == shell_pid) {
            shell_pid = -1;
            return -1;
        }
    }
    return 0;
}

static void handle_run(const struct guide_supervisor_request *request)
{
    const char *program = application_path(request->application);
    pid_t child;
    int status = 0;
    if (!program || access(program, X_OK) != 0 || session_pid > 0) {
        (void)send_response(shell_socket, GUIDE_RESULT_REJECTED, 0,
                            program ? errno : EINVAL, "SESSION REJECTED");
        return;
    }
    child = fork();
    if (child == 0) session_exec(request);
    if (child < 0) {
        (void)send_response(shell_socket, GUIDE_RESULT_FAILED, 0, errno,
                            "SESSION COULD NOT START");
        return;
    }
    (void)setpgid(child, child);
    session_pid = session_pgid = child;
    register_process(child, child, PROCESS_SESSION, GUIDE_PRIORITY_FOREGROUND, program);
    log_line("session started pid=%ld app=%u arg0=%s", (long)child,
             request->application, request->argument0);
    if (wait_for_session(child, &status) != 0) {
        terminate_group(session_pgid, 750);
        session_pid = session_pgid = -1;
        (void)send_response(shell_socket, GUIDE_RESULT_FAILED, status, ECHILD,
                            "SESSION OWNER LOST");
        return;
    }
    terminate_group(session_pgid, 250);
    session_pgid = -1;
    reap_available();
    if (WIFEXITED(status) && WEXITSTATUS(status) == GUIDE_SUPERVISOR_POWER_EXIT)
        (void)send_response(shell_socket, GUIDE_RESULT_POWER_REQUESTED, status, 0,
                            "POWER REQUESTED");
    else if (WIFEXITED(status) && WEXITSTATUS(status) == 0)
        (void)send_response(shell_socket, GUIDE_RESULT_COMPLETE, status, 0,
                            "SESSION CLOSED SAFELY");
    else
        (void)send_response(shell_socket, GUIDE_RESULT_FAILED, status, 0,
                            "SESSION STOPPED");
    log_line("session ended pid=%ld status=%d", (long)child, status);
}

static int spawn_shell(void)
{
    int sockets[2], flags;
    pid_t child;
    char descriptor[32];
    if (socketpair(AF_UNIX, SOCK_SEQPACKET, 0, sockets) != 0) return -1;
    child = fork();
    if (child == 0) {
        close(sockets[0]);
        (void)setpgid(0, 0);
        apply_priority(GUIDE_PRIORITY_FOREGROUND);
        snprintf(descriptor, sizeof(descriptor), "%d", sockets[1]);
        (void)setenv(GUIDE_SUPERVISOR_FD_ENV, descriptor, 1);
        flags = fcntl(sockets[1], F_GETFD);
        if (flags >= 0) (void)fcntl(sockets[1], F_SETFD, flags & ~FD_CLOEXEC);
        execl(GUIDE_SHELL, "guide-shell", (char *)NULL);
        _exit(127);
    }
    close(sockets[1]);
    if (child < 0) { close(sockets[0]); return -1; }
    (void)setpgid(child, child);
    shell_pid = shell_pgid = child;
    shell_socket = sockets[0];
    register_process(child, child, PROCESS_SHELL, GUIDE_PRIORITY_FOREGROUND, "guide-shell");
    log_line("shell started pid=%ld", (long)child);
    return 0;
}

static void perform_shutdown(void)
{
    log_line("shutdown requested");
    if (session_pgid > 1) terminate_group(session_pgid, 1000);
    if (shell_pgid > 1) terminate_group(shell_pgid, 1000);
    reap_available();
    sync();
    (void)mount(NULL, "/", NULL, MS_REMOUNT | MS_RDONLY, NULL);
    sync();
    if (log_file) { fflush(log_file); (void)fsync(fileno(log_file)); }
    (void)reboot(RB_POWER_OFF);
    log_line("kernel power-off returned error=%s", strerror(errno));
    for (;;) pause();
}

static int run_supervisor(void)
{
    struct sigaction action;
    int crash_count = 0;
    time_t crash_window = time(NULL);
    memset(&action, 0, sizeof(action));
    action.sa_handler = signal_handler;
    sigemptyset(&action.sa_mask);
    (void)sigaction(SIGCHLD, &action, NULL);
    (void)sigaction(SIGTERM, &action, NULL);
    (void)sigaction(SIGINT, &action, NULL);
    (void)prctl(PR_SET_CHILD_SUBREAPER, 1, 0, 0, 0);
    (void)mount("proc", "/proc", "proc", 0, NULL);
    (void)mount("sysfs", "/sys", "sysfs", 0, NULL);
    apply_priority(GUIDE_PRIORITY_SAFETY);
    log_file = fopen("/var/log/guide-supervisor.log", "a");
    log_line("guide-supervisor started pid=%ld", (long)getpid());

    for (;;) {
        struct pollfd descriptor;
        struct guide_supervisor_request request;
        ssize_t received;
        if (terminate_requested) perform_shutdown();
        if (shell_pid <= 0) {
            time_t now = time(NULL);
            if (now - crash_window > 60) { crash_window = now; crash_count = 0; }
            if (++crash_count > 5) {
                log_line("shell crash loop; recovery delay");
                sleep(10);
                crash_window = time(NULL); crash_count = 0;
            }
            if (shell_socket >= 0) close(shell_socket);
            shell_socket = -1;
            if (spawn_shell() != 0) { log_line("shell spawn failed error=%s", strerror(errno)); sleep(1); continue; }
        }
        descriptor.fd = shell_socket;
        descriptor.events = POLLIN | POLLHUP | POLLERR;
        descriptor.revents = 0;
        if (poll(&descriptor, 1, 500) < 0) {
            if (errno != EINTR) log_line("control poll failed error=%s", strerror(errno));
            if (child_changed) reap_available();
            continue;
        }
        if (child_changed) reap_available();
        if (shell_pid <= 0) continue;
        if (descriptor.revents & (POLLHUP | POLLERR)) {
            log_line("shell control channel closed");
            terminate_group(shell_pgid, 500);
            shell_pid = -1;
            continue;
        }
        if (!(descriptor.revents & POLLIN)) continue;
        memset(&request, 0, sizeof(request));
        received = recv(shell_socket, &request, sizeof(request), 0);
        if (received != (ssize_t)sizeof(request) || !request_valid(&request)) {
            (void)send_response(shell_socket, GUIDE_RESULT_REJECTED, 0, EPROTO,
                                "INVALID SUPERVISOR REQUEST");
            continue;
        }
        if (request.command == GUIDE_SUPERVISOR_RUN) handle_run(&request);
        else {
            (void)send_response(shell_socket, GUIDE_RESULT_SHUTTING_DOWN, 0, 0,
                                "SHUTTING DOWN");
            perform_shutdown();
        }
    }
    return 0;
}

static int self_test(void)
{
    int status, reaped = 0;
    pid_t child;
    if (priority_nice(GUIDE_PRIORITY_SAFETY) != -5 ||
        priority_nice(GUIDE_PRIORITY_FOREGROUND) != 0 ||
        priority_nice(GUIDE_PRIORITY_OPPORTUNISTIC) != 15) return 1;
    if (prctl(PR_SET_CHILD_SUBREAPER, 1, 0, 0, 0) != 0) return 2;
    child = fork();
    if (child == 0) {
        pid_t grandchild = fork();
        if (grandchild == 0) { usleep(50000); _exit(23); }
        _exit(7);
    }
    if (child < 0) return 3;
    while (reaped < 2) {
        pid_t ended = waitpid(-1, &status, 0);
        if (ended < 0) return 4;
        ++reaped;
    }
    puts("guide-supervisor self-test: PASS");
    return 0;
}

int main(int argc, char **argv)
{
    if (argc == 2 && strcmp(argv[1], "--self-test") == 0) return self_test();
    if (argc != 1) return 64;
    return run_supervisor();
}
