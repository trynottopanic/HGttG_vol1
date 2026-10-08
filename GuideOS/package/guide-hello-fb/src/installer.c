// SPDX-License-Identifier: AGPL-3.0-or-later

#include "installer.h"

#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/utsname.h>
#include <sys/wait.h>
#include <unistd.h>

#define WIFI_ID "guide.prototype.wifi"
#define WIFI_VERSION "0.1.0"
#define WIFI_ACTION "feature.wifi.rg35xxh"
#define WIFI_ARCHIVE "/media/guide-card/GUIDE/CARTRIDGES/guide.prototype.wifi-0.1.0.guide"
#define WIFI_ARCHIVE_SHA256 "34b017ab9b82a669dd30f5332db172e8fa2de95f3a1ed47b03f61478d7cb9687"
#define WIFI_RECORD "/var/lib/guideos/features/guide.prototype.wifi.json"
#define WIFI_MODULE "/lib/modules/4.9.170/kernel/drivers/net/wireless/8821cs.ko"

#define DEVELOPER_ID "guide.prototype.developer-link"
#define DEVELOPER_VERSION "0.1.0"
#define DEVELOPER_ACTION "feature.developer-link.rg35xxh"
#define DEVELOPER_ARCHIVE "/media/guide-card/GUIDE/CARTRIDGES/guide.prototype.developer-link-0.1.0.guide"
#define DEVELOPER_ARCHIVE_SHA256 "a2a8ba52d4fe73fde8a57ca344da3cb69f4fbf8062c92083c445098bde7a361a"
#define DEVELOPER_RECORD "/var/lib/guideos/features/guide.prototype.developer-link.json"

#define WIKIPEDIA_ID "guide.wikipedia"
#define WIKIPEDIA_VERSION "0.3.0"
#define WIKIPEDIA_ACTION "application.wikipedia.rg35xxh"
#define WIKIPEDIA_ARCHIVE "/media/guide-card/GUIDE/CARTRIDGES/guide.wikipedia-0.3.0.guide"
#define WIKIPEDIA_ARCHIVE_SHA256 "33825e585ff53f4be01ad001d89be845f728ab09a9e9dc243507178d0d448f96"
#define WIKIPEDIA_RECORD "/var/lib/guideos/features/guide.wikipedia-0.3.json"
#define GUIDE_WIKI_APP_DIR "/usr/lib/guideos/apps/wikipedia-0.3"

#define SEMIOTIC_ID "guide.semiotic-engine.interface"
#define SEMIOTIC_VERSION "0.1.0"
#define SEMIOTIC_ACTION "application.semiotic-engine.rg35xxh"
#define SEMIOTIC_ARCHIVE "/media/guide-card/GUIDE/CARTRIDGES/guide.semiotic-engine.interface-0.1.0.guide"
#define SEMIOTIC_ARCHIVE_SHA256 "89f2e1802404dcdb28b4a1e93c6a80834af39d9b50dfa0a52eec3d238f824722"
#define SEMIOTIC_RECORD "/var/lib/guideos/features/guide.semiotic-engine.interface.json"

#define EMULATION_ID "guide.emulation"
#define EMULATION_VERSION "0.1.3"
#define EMULATION_ACTION "application.emulation.rg35xxh"
#define EMULATION_ARCHIVE "/media/guide-card/GUIDE/CARTRIDGES/guide.emulation-0.1.3.guide"
#define EMULATION_ARCHIVE_SHA256 "5871994b52cf257781f2f5fc93037db3f59c2be77ee4d78dad4afa931e84d5ea"
#define EMULATION_RECORD "/var/lib/guideos/features/guide.emulation.json"

struct install_file {
    const char *entry;
    const char *destination;
    const char *sha256;
    mode_t mode;
};

static const struct install_file wifi_files[] = {
    {"CONTENT/driver/8821cs.ko", WIFI_MODULE,
     "443ea375e61d8ab1dd9849a2a837c446d83a22812a728243d11d8653418811f8", 0644},
    {"CONTENT/bin/iw", "/usr/sbin/iw",
     "8f19eacf0ff3bfa1d20f533e84c1beb4f8c79deddcf14643911ac6f0856a69a8", 0755},
    {"CONTENT/bin/wpa_supplicant", "/usr/sbin/wpa_supplicant",
     "8193b166460a01ab8e8af6d0faad61d6297b91e80a6253314385ffbd93532bdd", 0755},
    {"CONTENT/bin/wpa_cli", "/usr/sbin/wpa_cli",
     "35a5a13079a029873711057b9240e830ef996010c73c3e879a48162655174f5a", 0755},
    {"CONTENT/bin/wpa_passphrase", "/usr/sbin/wpa_passphrase",
     "1643737d362d7bbe14be57717c0fa271df1715970aa67a712520b4772dee5615", 0755},
    {"CONTENT/lib/libnl-3.so.200.26.0", "/usr/lib/libnl-3.so.200.26.0",
     "e5d3030518b758671e05379948469d9151f9fcb3114f26b8b7101a08bc55c224", 0755},
    {"CONTENT/lib/libnl-genl-3.so.200.26.0", "/usr/lib/libnl-genl-3.so.200.26.0",
     "909eda5780e30b1faca35892fa581ff78924e749236f38a87d7c13fb6058f243", 0755}
};

static const struct install_file developer_files[] = {
    {"CONTENT/bin/dropbear", "/usr/sbin/dropbear",
     "66f1cb722862fbf84420d36a5bbb03aced3cc94149a85971f945091138cec619", 0755},
    {"CONTENT/bin/dropbearkey", "/usr/bin/dropbearkey",
     "66f1cb722862fbf84420d36a5bbb03aced3cc94149a85971f945091138cec619", 0755},
    {"CONTENT/bin/guide-devlink-control", "/usr/sbin/guide-devlink-control",
     "6aed0f853315c44341ab3350a31981233e8bd68c15fc2df9786c2bd0d2e0dc24", 0755},
    {"CONTENT/config/authorized_keys", "/root/.ssh/authorized_keys",
     "f7c755ae7538e34ead246e1e59810d7cb7140fc061f7df89842e9a7297993c41", 0600},
    {"CONTENT/licenses/dropbear-LICENSE", "/usr/share/licenses/dropbear/LICENSE",
     "a99ce657d790b761c132ee7e0de18edb437ae6361e536d991c6a12f36e770445", 0644},
    {"CONTENT/README.txt", "/usr/share/guideos/developer-link.txt",
     "44c0b26d05d093404e3c3421a83ff4db037b6e666ffb1bca00acf3a899568b7c", 0644}
};

static const struct install_file wikipedia_files[] = {
    {"CONTENT/LICENSES.txt", "/usr/share/guideos/wikipedia-0.3/LICENSES.txt", "73e7475336e90096b8679553680a04459c138dd9da82a18dc0022cafc1a3dbdd", 0644},
    {"CONTENT/PROVENANCE.txt", "/usr/share/guideos/wikipedia-0.3/PROVENANCE.txt", "783785f3626898555df87ad0180fb5ccdec471af5cfda66da512e1ae155b750b", 0644},
    {"CONTENT/README.txt", "/usr/share/guideos/wikipedia-0.3/README.txt", "d876362370b1c4f65b0a2ddf3b25ad410651f4d53d9cd541735105cdf03e2fa6", 0644},
    {"CONTENT/RUNTIME-MAP.json", "/usr/share/guideos/wikipedia-0.3/RUNTIME-MAP.json", "9b239750693b3b2c9896a81da66aa668948695b5709ac1d39a17e6c507b3d07d", 0644},
    {"CONTENT/app/guide_wikipedia_app.py", GUIDE_WIKI_APP_DIR "/guide_wikipedia_app.py", "0d561c403c29b3090256a627945104a31f92e18e1ae1d271664a211f77ccd1b3", 0644},
    {"CONTENT/app/guide_wikipedia_bridge.py", GUIDE_WIKI_APP_DIR "/guide_wikipedia_bridge.py", "ed0ad49a287da1701075f2d6a985a8c79bf0d3acd70662320468cdc22500103c", 0644},
    {"CONTENT/app/guide_wikipedia_client.py", GUIDE_WIKI_APP_DIR "/guide_wikipedia_client.py", "7ed45e15241e4f6976fcfbdaee05345a38e97225f8937f925bdbf886dd7a8cb2", 0644},
    {"CONTENT/app/guide_wikipedia_model.py", GUIDE_WIKI_APP_DIR "/guide_wikipedia_model.py", "af8607defe70c8aa50e53120e461a0275f0190c2d6f914cc114d70777e62a20a", 0644},
    {"CONTENT/app/guide_wikipedia_store.py", GUIDE_WIKI_APP_DIR "/guide_wikipedia_store.py", "45e428609cfb992313e57b8ae5abfaf6490d02c0873b3a2341245fbf1a231709", 0644},
    {"CONTENT/runtime/certs/ca-certificates.crt", GUIDE_WIKI_APP_DIR "/runtime/certs/ca-certificates.crt", "3d664e3fa39e5d3e95f653127b067ef02e5d450112b2f4d65f1ad89b0a62a506", 0644},
    {"CONTENT/runtime/lib/libcrypto.so.3", GUIDE_WIKI_APP_DIR "/runtime/lib/libcrypto.so.3", "d61a6564b9c2c175b7ab60f3c3838c30bfa0bf8d9f254fe6b8f256a2cbdde6c0", 0755},
    {"CONTENT/runtime/lib/libssl.so.3", GUIDE_WIKI_APP_DIR "/runtime/lib/libssl.so.3", "9caeda74e38bdc70e18d529cdd34c195fa51895896f95bba176e4cf7d9a0a80c", 0755},
    {"CONTENT/runtime/python3.12/lib-dynload/_hashlib.cpython-312-aarch64-linux-gnu.so", GUIDE_WIKI_APP_DIR "/runtime/python3.12/lib-dynload/_hashlib.cpython-312-aarch64-linux-gnu.so", "61d5b08a3e2545f4d929ad9b6aa8c5d7894d69e0c8137152b8896bab787f95db", 0755},
    {"CONTENT/runtime/python3.12/lib-dynload/_ssl.cpython-312-aarch64-linux-gnu.so", GUIDE_WIKI_APP_DIR "/runtime/python3.12/lib-dynload/_ssl.cpython-312-aarch64-linux-gnu.so", "0d48525ad51140fea4f04049ca1b9422a27d2126569a6cd665a08ab99e57f4b3", 0755}
};

/* These files form the Wikipedia reader built into the verified GuideOS
 * image.  Keep this separate from wikipedia_files: that table is the signed
 * 0.3 cartridge contract and must remain capable of validating old media. */
static const struct install_file wikipedia_system_files[] = {
    {"", GUIDE_WIKI_APP_DIR "/guide_wikipedia_client.py", "691737a06d0a0f87597d0d3a22036e5e052e02a2037c6614c49cac01a6f6bb92", 0644},
    {"", GUIDE_WIKI_APP_DIR "/guide_wikipedia_html.py", "50aede20da65f3d8ca480ee9dc51891e84f798b7c33a054e4e4cc02cab411426", 0644},
    {"", GUIDE_WIKI_APP_DIR "/guide_wikipedia_netsurf.py", "f3e7c2de2b9ab8d0a29603f6118caf2fd7693efa06cab3cc12d086913715eda2", 0644},
    {"", "/usr/bin/guide-wikipedia-rich", "8d21e29e9f77d4895f0daf01c82c56f2aea8b46883073b39767c59a39b2ebf10", 0755},
    {"", "/usr/lib/guideos/netsurf/netsurf-fb", "20f0fe6bd9570c034e320c3361194b97f208ef41cc8e94badd6a4672857f0d9c", 0755}
};

static const struct install_file semiotic_files[] = {
    {"CONTENT/LICENSES.txt", "/usr/share/guideos/semiotic-engine/LICENSES.txt", "8a37812401410d248df9e0de64b6176c4de6c7b0a9e86df42d6042fd79877495", 0644},
    {"CONTENT/PROVENANCE.txt", "/usr/share/guideos/semiotic-engine/PROVENANCE.txt", "f4167df96d6fc99ecf842b610d24c8f6b802a58e2a30f6aee06fbd26ae8e95f4", 0644},
    {"CONTENT/README.txt", "/usr/share/guideos/semiotic-engine/README.txt", "b0870fedf611ad3e4d9ed3dec6af896a9582ed0c09b7b669b2afab91bd12166d", 0644},
    {"CONTENT/RUNTIME-MAP.json", "/usr/share/guideos/semiotic-engine/RUNTIME-MAP.json", "eb13dc73ce2ca815ce1b9521954cd6c7714b603a5f5ef5c3a78abe0370fe8e44", 0644},
    {"CONTENT/app/guide_se_deck.py", "/usr/bin/guide-se-deck", "0c6bb7bb7f9f36f712ac65dd63b29200e29d04a32e524b0bdb4d56bdc6e17c6e", 0755}
};

static const struct install_file emulation_files[] = {
    {"CONTENT/bin/guide-emulator", "/usr/bin/guide-emulator", "760034b45c7bc4e24ee09b217875750e0476dffe1ce3c9e841b564a253242205", 0755},
    {"CONTENT/cores/fceumm_libretro.so", "/usr/lib/guideos/emulation/cores/fceumm_libretro.so", "c0ceb31c045b6bacb053170f37c37e921d81d6f8e4abaf98725e961f009615b1", 0755},
    {"CONTENT/cores/gambatte_libretro.so", "/usr/lib/guideos/emulation/cores/gambatte_libretro.so", "d8ebb32ff41f80f687105362d2cf238dfe497fc77ff03ac1ff1246fb6046c099", 0755},
    {"CONTENT/cores/genesis_plus_gx_libretro.so", "/usr/lib/guideos/emulation/cores/genesis_plus_gx_libretro.so", "77f31e62a453c105a2b83d859224c638c07f46184275d49efb215d497fae22b8", 0755},
    {"CONTENT/cores/mgba_libretro.so", "/usr/lib/guideos/emulation/cores/mgba_libretro.so", "2599b2abbbebed5df948a0da662d0892c79043b087e03137beeeb09ec3ba90e5", 0755},
    {"CONTENT/cores/pcsx_rearmed_libretro.so", "/usr/lib/guideos/emulation/cores/pcsx_rearmed_libretro.so", "0b7f089774aee66a275ef98ef94d7f43f3247969ec2857b55686a381c13779d9", 0755},
    {"CONTENT/cores/snes9x2010_libretro.so", "/usr/lib/guideos/emulation/cores/snes9x2010_libretro.so", "482104e5a2ecf7ca1915aa54678913f99566572ec53cec61b8193a89d4b7e30c", 0755},
    {"CONTENT/licenses/FCEUmm-Copying.txt", "/usr/share/guideos/emulation/FCEUmm-Copying.txt", "a6996dcf0c334281f734560926e079b2dbbd5b78e81c0ca00a413ec01e1cd2fb", 0644},
    {"CONTENT/licenses/Gambatte-COPYING.txt", "/usr/share/guideos/emulation/Gambatte-COPYING.txt", "ab15fd526bd8dd18a9e77ebc139656bf4d33e97fc7238cd11bf60e2b9b8666c6", 0644},
    {"CONTENT/licenses/Genesis-Plus-GX-LICENSE.txt", "/usr/share/guideos/emulation/Genesis-Plus-GX-LICENSE.txt", "642c163624269243d1f6b29d759d4e3a2d161bdc272c90d82ecbeec82ae26755", 0644},
    {"CONTENT/licenses/mGBA-LICENSE.txt", "/usr/share/guideos/emulation/mGBA-LICENSE.txt", "fab3dd6bdab226f1c08630b1dd917e11fcb4ec5e1e020e2c16f83a0a13863e85", 0644},
    {"CONTENT/licenses/PCSX-ReARMed-COPYING.txt", "/usr/share/guideos/emulation/PCSX-ReARMed-COPYING.txt", "0efb4db8000c609bd2f06e61fcbc59af05519d122f5b3597b7c493224946c61d", 0644},
    {"CONTENT/licenses/Snes9x-LICENSE.txt", "/usr/share/guideos/emulation/Snes9x-LICENSE.txt", "2d5875c99c5895e9e8d104dd777dc7fdeee0fd96bed0bca38e83b90b480d2523", 0644},
    {"CONTENT/PROVENANCE.txt", "/usr/share/guideos/emulation/PROVENANCE.txt", "454f05621c115fd144ccaa0560bf0d791888aee89c557f1c7440fb7774d0ce13", 0644},
    {"CONTENT/README.txt", "/usr/share/guideos/emulation/README.txt", "7812e55269eebdc6125e05fe99bcced6ee8feefbb7b2b2bdfe4776bd014944eb", 0644}
};

static void result(char *message, size_t size, const char *format, ...)
{
    va_list arguments;
    if (!message || size == 0) return;
    va_start(arguments, format);
    (void)vsnprintf(message, size, format, arguments);
    va_end(arguments);
}

static int make_directory(const char *path)
{
    if (mkdir(path, 0755) == 0 || errno == EEXIST) return 0;
    return -1;
}

static int prepare_directories(void)
{
    static const char *paths[] = {
        "/var/lib/guideos", "/var/lib/guideos/install-staging",
        "/var/lib/guideos/features", "/lib/modules",
        "/lib/modules/4.9.170", "/lib/modules/4.9.170/kernel",
        "/lib/modules/4.9.170/kernel/drivers",
        "/lib/modules/4.9.170/kernel/drivers/net",
        "/lib/modules/4.9.170/kernel/drivers/net/wireless"
    };
    size_t index;
    for (index = 0; index < sizeof(paths) / sizeof(paths[0]); ++index)
        if (make_directory(paths[index]) != 0) return -1;
    return 0;
}

static int run_program(const char *first, const char *second,
                       const char *argument, FILE *log)
{
    pid_t child = fork();
    int status;
    if (child < 0) return -1;
    if (child == 0) {
        execl(first, first, argument, (char *)NULL);
        if (second) execl(second, second, argument, (char *)NULL);
        _exit(127);
    }
    if (waitpid(child, &status, 0) < 0 || !WIFEXITED(status)) return -1;
    fprintf(log, "installer program=%s argument=%s status=%d\n",
            first, argument, WEXITSTATUS(status));
    fflush(log);
    return WEXITSTATUS(status) == 0 ? 0 : -1;
}

static int extract_entry(const char *archive, const char *entry, const char *destination)
{
    int output = open(destination, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW, 0600);
    pid_t child;
    int status;
    if (output < 0) return -1;
    child = fork();
    if (child == 0) {
        if (dup2(output, STDOUT_FILENO) < 0) _exit(126);
        close(output);
        execl("/usr/bin/unzip", "unzip", "-p", archive, entry, (char *)NULL);
        execl("/bin/unzip", "unzip", "-p", archive, entry, (char *)NULL);
        _exit(127);
    }
    close(output);
    if (child < 0 || waitpid(child, &status, 0) < 0 ||
        !WIFEXITED(status) || WEXITSTATUS(status) != 0) {
        unlink(destination);
        return -1;
    }
    return 0;
}

static int copy_new_file(const char *source, const char *destination, mode_t mode)
{
    char temporary[PATH_MAX];
    char buffer[65536];
    int input = -1, output = -1, saved_errno = 0;
    ssize_t count;
    if (snprintf(temporary, sizeof(temporary), "%s.guide-new", destination) >=
        (int)sizeof(temporary)) return -1;
    input = open(source, O_RDONLY | O_NOFOLLOW);
    output = open(temporary, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW, mode);
    if (input < 0 || output < 0) goto failed;
    while ((count = read(input, buffer, sizeof(buffer))) > 0) {
        ssize_t offset = 0;
        while (offset < count) {
            ssize_t written = write(output, buffer + offset, (size_t)(count - offset));
            if (written <= 0) goto failed;
            offset += written;
        }
    }
    if (count < 0 || fsync(output) != 0 || fchmod(output, mode) != 0) goto failed;
    close(input); input = -1;
    close(output); output = -1;
    if (link(temporary, destination) != 0) goto failed;
    unlink(temporary);
    return 0;
failed:
    saved_errno = errno;
    if (input >= 0) close(input);
    if (output >= 0) close(output);
    unlink(temporary);
    errno = saved_errno;
    return -1;
}

static int exact_installed_files(void)
{
    size_t index;
    char actual[65];
    for (index = 0; index < sizeof(wifi_files) / sizeof(wifi_files[0]); ++index)
        if (guide_sha256_file(wifi_files[index].destination, actual) != 0 ||
            strcmp(actual, wifi_files[index].sha256) != 0) return 0;
    return access(WIFI_RECORD, F_OK) == 0;
}

static int create_link(const char *path, const char *target)
{
    char temporary[PATH_MAX];
    if (snprintf(temporary, sizeof(temporary), "%s.guide-new", path) >=
        (int)sizeof(temporary)) return -1;
    unlink(temporary);
    if (symlink(target, temporary) != 0) return -1;
    if (link(temporary, path) != 0) {
        unlink(temporary);
        return -1;
    }
    unlink(temporary);
    return 0;
}

static int staging_path(char *path, size_t capacity,
                        const char *transaction, size_t index)
{
    int written = snprintf(path, capacity, "%s/%zu", transaction, index);
    return written >= 0 && (size_t)written < capacity ? 0 : -1;
}

static void cleanup_staging(const char *transaction)
{
    size_t index;
    char path[PATH_MAX];
    if (!transaction) return;
    for (index = 0; index < sizeof(wifi_files) / sizeof(wifi_files[0]); ++index)
        if (staging_path(path, sizeof(path), transaction, index) == 0)
            unlink(path);
    rmdir(transaction);
}

static void rollback(size_t installed_files, int first_link, int second_link,
                     const char *transaction, FILE *log)
{
    while (installed_files > 0) {
        --installed_files;
        unlink(wifi_files[installed_files].destination);
    }
    if (first_link) unlink("/usr/lib/libnl-3.so.200");
    if (second_link) unlink("/usr/lib/libnl-genl-3.so.200");
    cleanup_staging(transaction);
    fprintf(log, "wifi installer rollback complete\n");
    fflush(log);
}

int guide_wifi_install_supported(const struct guide_cartridge *item)
{
    return item && item->verification == GUIDE_CARTRIDGE_VERIFIED &&
           strcmp(item->id, WIFI_ID) == 0 &&
           strcmp(item->version, WIFI_VERSION) == 0 &&
           strcmp(item->action, WIFI_ACTION) == 0 &&
           strcmp(item->sha256, WIFI_ARCHIVE_SHA256) == 0;
}

void guide_wifi_start_installed(FILE *log)
{
    if (exact_installed_files())
        (void)run_program("/sbin/insmod", "/usr/sbin/insmod", WIFI_MODULE, log);
}

int guide_wifi_install(const struct guide_cartridge *item, FILE *log,
                       char *message, size_t message_size)
{
    struct utsname system_name;
    char archive_hash[65], transaction[128], staged[160], actual[65];
    size_t index, installed = 0;
    int first_link = 0, second_link = 0;
    int record = -1;
    const char *record_text =
        "{\"id\":\"guide.prototype.wifi\",\"version\":\"0.1.0\","
        "\"archiveSha256\":\"" WIFI_ARCHIVE_SHA256 "\"}\n";

    if (!guide_wifi_install_supported(item)) {
        result(message, message_size, "PACKAGE NOT TRUSTED FOR INSTALL");
        return -1;
    }
    if (exact_installed_files()) {
        guide_wifi_start_installed(log);
        result(message, message_size, "WIFI ALREADY INSTALLED");
        return 0;
    }
    if (uname(&system_name) != 0 || strcmp(system_name.machine, "aarch64") != 0 ||
        strcmp(system_name.release, "4.9.170") != 0) {
        result(message, message_size, "WRONG DECK OR KERNEL");
        return -1;
    }
    if (guide_sha256_file(WIFI_ARCHIVE, archive_hash) != 0 ||
        strcmp(archive_hash, WIFI_ARCHIVE_SHA256) != 0) {
        result(message, message_size, "CARTRIDGE HASH CHANGED");
        return -1;
    }
    if (prepare_directories() != 0) {
        result(message, message_size, "COULD NOT PREPARE STORAGE");
        return -1;
    }
    for (index = 0; index < sizeof(wifi_files) / sizeof(wifi_files[0]); ++index)
        if (lstat(wifi_files[index].destination, &(struct stat){0}) == 0 || errno != ENOENT) {
            result(message, message_size, "EXISTING SYSTEM FILE REFUSED");
            return -1;
        }
    errno = 0;
    if (lstat("/usr/lib/libnl-3.so.200", &(struct stat){0}) == 0 || errno != ENOENT) {
        result(message, message_size, "EXISTING SYSTEM LINK REFUSED");
        return -1;
    }
    errno = 0;
    if (lstat("/usr/lib/libnl-genl-3.so.200", &(struct stat){0}) == 0 || errno != ENOENT) {
        result(message, message_size, "EXISTING SYSTEM LINK REFUSED");
        return -1;
    }
    snprintf(transaction, sizeof(transaction),
             "/var/lib/guideos/install-staging/wifi-%ld", (long)getpid());
    if (mkdir(transaction, 0700) != 0) {
        result(message, message_size, "COULD NOT CREATE SAFE STAGING");
        return -1;
    }
    for (index = 0; index < sizeof(wifi_files) / sizeof(wifi_files[0]); ++index) {
        if (staging_path(staged, sizeof(staged), transaction, index) != 0) {
            result(message, message_size, "INTERNAL STAGING ERROR");
            rollback(installed, first_link, second_link, transaction, log);
            return -1;
        }
        if (extract_entry(WIFI_ARCHIVE, wifi_files[index].entry, staged) != 0 ||
            guide_sha256_file(staged, actual) != 0 ||
            strcmp(actual, wifi_files[index].sha256) != 0) {
            result(message, message_size, "PAYLOAD FILE FAILED VERIFICATION");
            rollback(installed, first_link, second_link, transaction, log);
            return -1;
        }
    }
    for (index = 0; index < sizeof(wifi_files) / sizeof(wifi_files[0]); ++index) {
        if (staging_path(staged, sizeof(staged), transaction, index) != 0) {
            result(message, message_size, "INTERNAL STAGING ERROR");
            rollback(installed, first_link, second_link, transaction, log);
            return -1;
        }
        if (copy_new_file(staged, wifi_files[index].destination, wifi_files[index].mode) != 0) {
            result(message, message_size, "INSTALL FAILED AND WAS UNDONE");
            rollback(installed, first_link, second_link, transaction, log);
            return -1;
        }
        ++installed;
    }
    if (create_link("/usr/lib/libnl-3.so.200", "libnl-3.so.200.26.0") != 0) goto activate_failed;
    first_link = 1;
    if (create_link("/usr/lib/libnl-genl-3.so.200", "libnl-genl-3.so.200.26.0") != 0) goto activate_failed;
    second_link = 1;
    record = open(WIFI_RECORD ".new", O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW, 0644);
    if (record < 0 || write(record, record_text, strlen(record_text)) != (ssize_t)strlen(record_text) ||
        fsync(record) != 0) goto activate_failed;
    close(record); record = -1;
    if (link(WIFI_RECORD ".new", WIFI_RECORD) != 0) goto activate_failed;
    unlink(WIFI_RECORD ".new");
    sync();
    guide_wifi_start_installed(log);
    cleanup_staging(transaction);
    result(message, message_size,
           access("/sys/class/net/wlan0", F_OK) == 0 ? "WIFI INSTALLED AND READY" :
           "INSTALLED  RADIO NEEDS RESTART");
    fprintf(log, "wifi installer success wlan0=%d\n",
            access("/sys/class/net/wlan0", F_OK) == 0); fflush(log);
    return 0;

activate_failed:
    if (record >= 0) close(record);
    unlink(WIFI_RECORD ".new");
    unlink(WIFI_RECORD);
    rollback(installed, first_link, second_link, transaction, log);
    result(message, message_size, "INSTALL FAILED AND WAS UNDONE");
    return -1;
}

static int prepare_developer_directories(void)
{
    static const char *paths[] = {
        "/var/lib/guideos", "/var/lib/guideos/install-staging",
        "/var/lib/guideos/features", "/root/.ssh", "/usr/share/licenses",
        "/usr/share/licenses/dropbear", "/usr/share/guideos"
    };
    size_t index;
    for (index = 0; index < sizeof(paths) / sizeof(paths[0]); ++index)
        if (make_directory(paths[index]) != 0) return -1;
    return chmod("/root/.ssh", 0700);
}

int guide_developer_link_installed(void)
{
    size_t index;
    char actual[65];
    for (index = 0; index < sizeof(developer_files) / sizeof(developer_files[0]); ++index)
        if (guide_sha256_file(developer_files[index].destination, actual) != 0 ||
            strcmp(actual, developer_files[index].sha256) != 0) return 0;
    return access(DEVELOPER_RECORD, F_OK) == 0;
}

int guide_developer_link_install_supported(const struct guide_cartridge *item)
{
    return item && item->verification == GUIDE_CARTRIDGE_VERIFIED &&
           strcmp(item->id, DEVELOPER_ID) == 0 &&
           strcmp(item->version, DEVELOPER_VERSION) == 0 &&
           strcmp(item->action, DEVELOPER_ACTION) == 0 &&
           strcmp(item->sha256, DEVELOPER_ARCHIVE_SHA256) == 0;
}

static void developer_cleanup(const char *transaction)
{
    size_t index;
    char path[PATH_MAX];
    for (index = 0; index < sizeof(developer_files) / sizeof(developer_files[0]); ++index)
        if (staging_path(path, sizeof(path), transaction, index) == 0) unlink(path);
    rmdir(transaction);
}

static void developer_rollback(size_t installed, const char *transaction, FILE *log)
{
    while (installed > 0) unlink(developer_files[--installed].destination);
    developer_cleanup(transaction);
    fprintf(log, "developer link installer rollback complete\n");
    fflush(log);
}

int guide_developer_link_install(const struct guide_cartridge *item, FILE *log,
                                 char *message, size_t message_size)
{
    struct utsname system_name;
    char archive_hash[65], transaction[128], staged[160], actual[65];
    size_t index, installed = 0;
    int record = -1;
    const char *record_text =
        "{\"id\":\"guide.prototype.developer-link\",\"version\":\"0.1.0\","
        "\"archiveSha256\":\"" DEVELOPER_ARCHIVE_SHA256 "\"}\n";

    if (!guide_developer_link_install_supported(item)) {
        result(message, message_size, "PACKAGE NOT TRUSTED FOR INSTALL");
        return -1;
    }
    if (guide_developer_link_installed()) {
        result(message, message_size, "LINK ALREADY INSTALLED");
        return 0;
    }
    if (uname(&system_name) != 0 || strcmp(system_name.machine, "aarch64") != 0 ||
        strcmp(system_name.release, "4.9.170") != 0) {
        result(message, message_size, "WRONG DECK OR KERNEL");
        return -1;
    }
    if (guide_sha256_file(DEVELOPER_ARCHIVE, archive_hash) != 0 ||
        strcmp(archive_hash, DEVELOPER_ARCHIVE_SHA256) != 0) {
        result(message, message_size, "CARTRIDGE HASH CHANGED");
        return -1;
    }
    if (prepare_developer_directories() != 0) {
        result(message, message_size, "COULD NOT PREPARE STORAGE");
        return -1;
    }
    for (index = 0; index < sizeof(developer_files) / sizeof(developer_files[0]); ++index) {
        errno = 0;
        if (lstat(developer_files[index].destination, &(struct stat){0}) == 0 || errno != ENOENT) {
            result(message, message_size, "EXISTING SYSTEM FILE REFUSED");
            return -1;
        }
    }
    snprintf(transaction, sizeof(transaction),
             "/var/lib/guideos/install-staging/developer-link-%ld", (long)getpid());
    if (mkdir(transaction, 0700) != 0) {
        result(message, message_size, "COULD NOT CREATE SAFE STAGING");
        return -1;
    }
    for (index = 0; index < sizeof(developer_files) / sizeof(developer_files[0]); ++index) {
        if (staging_path(staged, sizeof(staged), transaction, index) != 0 ||
            extract_entry(DEVELOPER_ARCHIVE, developer_files[index].entry, staged) != 0 ||
            guide_sha256_file(staged, actual) != 0 ||
            strcmp(actual, developer_files[index].sha256) != 0) {
            result(message, message_size, "PAYLOAD FILE FAILED VERIFICATION");
            developer_rollback(installed, transaction, log);
            return -1;
        }
    }
    for (index = 0; index < sizeof(developer_files) / sizeof(developer_files[0]); ++index) {
        if (staging_path(staged, sizeof(staged), transaction, index) != 0 ||
            copy_new_file(staged, developer_files[index].destination,
                          developer_files[index].mode) != 0) {
            result(message, message_size, "INSTALL FAILED AND WAS UNDONE");
            developer_rollback(installed, transaction, log);
            return -1;
        }
        ++installed;
    }
    record = open(DEVELOPER_RECORD ".new", O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW, 0644);
    if (record < 0 || write(record, record_text, strlen(record_text)) != (ssize_t)strlen(record_text) ||
        fsync(record) != 0) goto developer_activate_failed;
    close(record); record = -1;
    if (link(DEVELOPER_RECORD ".new", DEVELOPER_RECORD) != 0) goto developer_activate_failed;
    unlink(DEVELOPER_RECORD ".new");
    sync();
    developer_cleanup(transaction);
    result(message, message_size, "LINK INSTALLED  OFF BY DEFAULT");
    fprintf(log, "developer link installer success active=0\n"); fflush(log);
    return 0;

developer_activate_failed:
    if (record >= 0) close(record);
    unlink(DEVELOPER_RECORD ".new");
    unlink(DEVELOPER_RECORD);
    developer_rollback(installed, transaction, log);
    result(message, message_size, "INSTALL FAILED AND WAS UNDONE");
    return -1;
}

static int prepare_wikipedia_directories(void)
{
    static const char *paths[] = {
        "/var/lib/guideos", "/var/lib/guideos/install-staging",
        "/var/lib/guideos/features", "/var/lib/guideos/wikipedia",
        "/usr/lib/guideos", "/usr/lib/guideos/apps",
        GUIDE_WIKI_APP_DIR, GUIDE_WIKI_APP_DIR "/runtime",
        GUIDE_WIKI_APP_DIR "/runtime/lib",
        GUIDE_WIKI_APP_DIR "/runtime/certs",
        GUIDE_WIKI_APP_DIR "/runtime/python3.12",
        GUIDE_WIKI_APP_DIR "/runtime/python3.12/lib-dynload",
        "/usr/share/guideos", "/usr/share/guideos/wikipedia-0.3"
    };
    size_t index;
    for (index = 0; index < sizeof(paths) / sizeof(paths[0]); ++index)
        if (make_directory(paths[index]) != 0) return -1;
    return chmod("/var/lib/guideos/wikipedia", 0700);
}

int guide_wikipedia_installed(void)
{
    size_t index;
    char actual[65];

    for (index = 0;
         index < sizeof(wikipedia_system_files) / sizeof(wikipedia_system_files[0]);
         ++index) {
        if (guide_sha256_file(wikipedia_system_files[index].destination, actual) != 0 ||
            strcmp(actual, wikipedia_system_files[index].sha256) != 0)
            break;
    }
    if (index == sizeof(wikipedia_system_files) / sizeof(wikipedia_system_files[0]))
        return 1;

    for (index = 0; index < sizeof(wikipedia_files) / sizeof(wikipedia_files[0]); ++index)
        if (guide_sha256_file(wikipedia_files[index].destination, actual) != 0 ||
            strcmp(actual, wikipedia_files[index].sha256) != 0) return 0;
    return access(WIKIPEDIA_RECORD, F_OK) == 0;
}

int guide_wikipedia_install_supported(const struct guide_cartridge *item)
{
    return item && item->verification == GUIDE_CARTRIDGE_VERIFIED &&
           strcmp(item->id, WIKIPEDIA_ID) == 0 &&
           strcmp(item->version, WIKIPEDIA_VERSION) == 0 &&
           strcmp(item->action, WIKIPEDIA_ACTION) == 0 &&
           strcmp(item->sha256, WIKIPEDIA_ARCHIVE_SHA256) == 0;
}

static void wikipedia_cleanup(const char *transaction)
{
    size_t index;
    char path[PATH_MAX];
    for (index = 0; index < sizeof(wikipedia_files) / sizeof(wikipedia_files[0]); ++index)
        if (staging_path(path, sizeof(path), transaction, index) == 0) unlink(path);
    rmdir(transaction);
}

static void wikipedia_rollback(size_t installed, const char *transaction, FILE *log)
{
    while (installed > 0) unlink(wikipedia_files[--installed].destination);
    wikipedia_cleanup(transaction);
    fprintf(log, "wikipedia installer rollback complete\n");
    fflush(log);
}

int guide_wikipedia_install(const struct guide_cartridge *item, FILE *log,
                            char *message, size_t message_size)
{
    struct utsname system_name;
    char archive_hash[65], transaction[128], staged[160], actual[65];
    size_t index, installed = 0;
    int record = -1;
    const char *record_text =
        "{\"id\":\"guide.wikipedia\",\"version\":\"0.3.0\"," 
        "\"archiveSha256\":\"" WIKIPEDIA_ARCHIVE_SHA256 "\"}\n";

    if (!guide_wikipedia_install_supported(item)) {
        result(message, message_size, "PACKAGE NOT TRUSTED FOR INSTALL"); return -1;
    }
    if (guide_wikipedia_installed()) {
        result(message, message_size, "WIKIPEDIA ALREADY INSTALLED"); return 0;
    }
    if (uname(&system_name) != 0 || strcmp(system_name.machine, "aarch64") != 0 ||
        strcmp(system_name.release, "4.9.170") != 0) {
        result(message, message_size, "WRONG DECK OR KERNEL"); return -1;
    }
    if (guide_sha256_file(WIKIPEDIA_ARCHIVE, archive_hash) != 0 ||
        strcmp(archive_hash, WIKIPEDIA_ARCHIVE_SHA256) != 0) {
        result(message, message_size, "CARTRIDGE HASH CHANGED"); return -1;
    }
    if (prepare_wikipedia_directories() != 0) {
        result(message, message_size, "COULD NOT PREPARE STORAGE"); return -1;
    }
    for (index = 0; index < sizeof(wikipedia_files) / sizeof(wikipedia_files[0]); ++index) {
        errno = 0;
        if (lstat(wikipedia_files[index].destination, &(struct stat){0}) == 0 || errno != ENOENT) {
            result(message, message_size, "EXISTING SYSTEM FILE REFUSED"); return -1;
        }
    }
    snprintf(transaction, sizeof(transaction),
             "/var/lib/guideos/install-staging/wikipedia-%ld", (long)getpid());
    if (mkdir(transaction, 0700) != 0) {
        result(message, message_size, "COULD NOT CREATE SAFE STAGING"); return -1;
    }
    for (index = 0; index < sizeof(wikipedia_files) / sizeof(wikipedia_files[0]); ++index) {
        if (staging_path(staged, sizeof(staged), transaction, index) != 0 ||
            extract_entry(WIKIPEDIA_ARCHIVE, wikipedia_files[index].entry, staged) != 0 ||
            guide_sha256_file(staged, actual) != 0 ||
            strcmp(actual, wikipedia_files[index].sha256) != 0) {
            result(message, message_size, "PAYLOAD FILE FAILED VERIFICATION");
            wikipedia_rollback(installed, transaction, log); return -1;
        }
    }
    for (index = 0; index < sizeof(wikipedia_files) / sizeof(wikipedia_files[0]); ++index) {
        if (staging_path(staged, sizeof(staged), transaction, index) != 0 ||
            copy_new_file(staged, wikipedia_files[index].destination,
                          wikipedia_files[index].mode) != 0) {
            result(message, message_size, "INSTALL FAILED AND WAS UNDONE");
            wikipedia_rollback(installed, transaction, log); return -1;
        }
        ++installed;
    }
    record = open(WIKIPEDIA_RECORD ".new", O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW, 0644);
    if (record < 0 || write(record, record_text, strlen(record_text)) != (ssize_t)strlen(record_text) ||
        fsync(record) != 0) goto wikipedia_activate_failed;
    close(record); record = -1;
    if (link(WIKIPEDIA_RECORD ".new", WIKIPEDIA_RECORD) != 0) goto wikipedia_activate_failed;
    unlink(WIKIPEDIA_RECORD ".new");
    sync(); wikipedia_cleanup(transaction);
    result(message, message_size, "WIKIPEDIA INSTALLED AND READY");
    fprintf(log, "wikipedia installer success\n"); fflush(log); return 0;

wikipedia_activate_failed:
    if (record >= 0) close(record);
    unlink(WIKIPEDIA_RECORD ".new"); unlink(WIKIPEDIA_RECORD);
    wikipedia_rollback(installed, transaction, log);
    result(message, message_size, "INSTALL FAILED AND WAS UNDONE"); return -1;
}

int guide_semiotic_installed(void)
{
    size_t index;
    char actual[65];
    for (index = 0; index < sizeof(semiotic_files) / sizeof(semiotic_files[0]); ++index)
        if (guide_sha256_file(semiotic_files[index].destination, actual) != 0 ||
            strcmp(actual, semiotic_files[index].sha256) != 0) return 0;
    return access(SEMIOTIC_RECORD, F_OK) == 0;
}

int guide_semiotic_install_supported(const struct guide_cartridge *item)
{
    return item && item->verification == GUIDE_CARTRIDGE_VERIFIED &&
           strcmp(item->id, SEMIOTIC_ID) == 0 &&
           strcmp(item->version, SEMIOTIC_VERSION) == 0 &&
           strcmp(item->action, SEMIOTIC_ACTION) == 0 &&
           strcmp(item->sha256, SEMIOTIC_ARCHIVE_SHA256) == 0;
}

static void semiotic_cleanup(const char *transaction)
{
    size_t index;
    char path[PATH_MAX];
    for (index = 0; index < sizeof(semiotic_files) / sizeof(semiotic_files[0]); ++index)
        if (staging_path(path, sizeof(path), transaction, index) == 0) unlink(path);
    rmdir(transaction);
}

static void semiotic_rollback(size_t installed, const char *transaction, FILE *log)
{
    while (installed > 0) unlink(semiotic_files[--installed].destination);
    semiotic_cleanup(transaction);
    fprintf(log, "semiotic interface installer rollback complete\n");
    fflush(log);
}

int guide_semiotic_install(const struct guide_cartridge *item, FILE *log,
                           char *message, size_t message_size)
{
    struct utsname system_name;
    char archive_hash[65], transaction[128], staged[160], actual[65];
    size_t index, installed = 0;
    int record = -1;
    const char *record_text =
        "{\"id\":\"guide.semiotic-engine.interface\",\"version\":\"0.1.0\","
        "\"archiveSha256\":\"" SEMIOTIC_ARCHIVE_SHA256 "\"}\n";
    static const char *paths[] = {
        "/var/lib/guideos", "/var/lib/guideos/install-staging",
        "/var/lib/guideos/features", "/usr/share/guideos",
        "/usr/share/guideos/semiotic-engine"
    };

    if (!guide_semiotic_install_supported(item)) {
        result(message, message_size, "PACKAGE NOT TRUSTED FOR INSTALL"); return -1;
    }
    if (guide_semiotic_installed()) {
        result(message, message_size, "ENGINE INTERFACE ALREADY INSTALLED"); return 0;
    }
    if (uname(&system_name) != 0 || strcmp(system_name.machine, "aarch64") != 0 ||
        strcmp(system_name.release, "4.9.170") != 0) {
        result(message, message_size, "WRONG DECK OR KERNEL"); return -1;
    }
    if (guide_sha256_file(SEMIOTIC_ARCHIVE, archive_hash) != 0 ||
        strcmp(archive_hash, SEMIOTIC_ARCHIVE_SHA256) != 0) {
        result(message, message_size, "CARTRIDGE HASH CHANGED"); return -1;
    }
    for (index = 0; index < sizeof(paths) / sizeof(paths[0]); ++index)
        if (make_directory(paths[index]) != 0) {
            result(message, message_size, "COULD NOT PREPARE STORAGE"); return -1;
        }
    for (index = 0; index < sizeof(semiotic_files) / sizeof(semiotic_files[0]); ++index) {
        errno = 0;
        if (lstat(semiotic_files[index].destination, &(struct stat){0}) == 0 || errno != ENOENT) {
            result(message, message_size, "EXISTING SYSTEM FILE REFUSED"); return -1;
        }
    }
    snprintf(transaction, sizeof(transaction),
             "/var/lib/guideos/install-staging/semiotic-%ld", (long)getpid());
    if (mkdir(transaction, 0700) != 0) {
        result(message, message_size, "COULD NOT CREATE SAFE STAGING"); return -1;
    }
    for (index = 0; index < sizeof(semiotic_files) / sizeof(semiotic_files[0]); ++index) {
        if (staging_path(staged, sizeof(staged), transaction, index) != 0 ||
            extract_entry(SEMIOTIC_ARCHIVE, semiotic_files[index].entry, staged) != 0 ||
            guide_sha256_file(staged, actual) != 0 ||
            strcmp(actual, semiotic_files[index].sha256) != 0) {
            result(message, message_size, "PAYLOAD FILE FAILED VERIFICATION");
            semiotic_rollback(installed, transaction, log); return -1;
        }
    }
    for (index = 0; index < sizeof(semiotic_files) / sizeof(semiotic_files[0]); ++index) {
        if (staging_path(staged, sizeof(staged), transaction, index) != 0 ||
            copy_new_file(staged, semiotic_files[index].destination,
                          semiotic_files[index].mode) != 0) {
            result(message, message_size, "INSTALL FAILED AND WAS UNDONE");
            semiotic_rollback(installed, transaction, log); return -1;
        }
        ++installed;
    }
    record = open(SEMIOTIC_RECORD ".new", O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW, 0644);
    if (record < 0 || write(record, record_text, strlen(record_text)) != (ssize_t)strlen(record_text) ||
        fsync(record) != 0) goto semiotic_activate_failed;
    close(record); record = -1;
    if (link(SEMIOTIC_RECORD ".new", SEMIOTIC_RECORD) != 0) goto semiotic_activate_failed;
    unlink(SEMIOTIC_RECORD ".new");
    sync(); semiotic_cleanup(transaction);
    result(message, message_size, "ENGINE INTERFACE INSTALLED");
    fprintf(log, "semiotic interface installer success\n"); fflush(log); return 0;

semiotic_activate_failed:
    if (record >= 0) close(record);
    unlink(SEMIOTIC_RECORD ".new"); unlink(SEMIOTIC_RECORD);
    semiotic_rollback(installed, transaction, log);
    result(message, message_size, "INSTALL FAILED AND WAS UNDONE"); return -1;
}

int guide_emulation_installed(void)
{
    size_t index;
    char actual[65];
    for (index = 0; index < sizeof(emulation_files) / sizeof(emulation_files[0]); ++index)
        if (guide_sha256_file(emulation_files[index].destination, actual) != 0 ||
            strcmp(actual, emulation_files[index].sha256) != 0) return 0;
    return access(EMULATION_RECORD, F_OK) == 0;
}

int guide_emulation_install_supported(const struct guide_cartridge *item)
{
    return item && item->verification == GUIDE_CARTRIDGE_VERIFIED &&
           strcmp(item->id, EMULATION_ID) == 0 &&
           strcmp(item->version, EMULATION_VERSION) == 0 &&
           strcmp(item->action, EMULATION_ACTION) == 0 &&
           strcmp(item->sha256, EMULATION_ARCHIVE_SHA256) == 0;
}

static void emulation_cleanup(const char *transaction)
{
    size_t index;
    char path[PATH_MAX];
    for (index = 0; index < sizeof(emulation_files) / sizeof(emulation_files[0]); ++index)
        if (staging_path(path, sizeof(path), transaction, index) == 0) unlink(path);
    rmdir(transaction);
}

static void emulation_rollback(size_t installed, const char *transaction, FILE *log)
{
    while (installed > 0) unlink(emulation_files[--installed].destination);
    emulation_cleanup(transaction);
    fprintf(log, "emulation installer rollback complete\n"); fflush(log);
}

int guide_emulation_install(const struct guide_cartridge *item, FILE *log,
                            char *message, size_t message_size)
{
    struct utsname system_name;
    char archive_hash[65], transaction[128], staged[160], actual[65];
    size_t index, installed = 0;
    int record = -1;
    const char *record_text =
        "{\"id\":\"guide.emulation\",\"version\":\"0.1.3\","
        "\"archiveSha256\":\"" EMULATION_ARCHIVE_SHA256 "\"}\n";
    static const char *paths[] = {
        "/var/lib/guideos", "/var/lib/guideos/install-staging", "/var/lib/guideos/features",
        "/usr/lib/guideos", "/usr/lib/guideos/emulation", "/usr/lib/guideos/emulation/cores",
        "/usr/share/guideos", "/usr/share/guideos/emulation", "/data/guideos",
        "/data/guideos/emulation", "/data/guideos/emulation/saves"
    };

    if (!guide_emulation_install_supported(item)) {
        result(message, message_size, "PACKAGE NOT TRUSTED FOR INSTALL"); return -1;
    }
    if (guide_emulation_installed()) {
        result(message, message_size, "EMULATION ALREADY INSTALLED"); return 0;
    }
    if (uname(&system_name) != 0 || strcmp(system_name.machine, "aarch64") != 0 ||
        strcmp(system_name.release, "4.9.170") != 0) {
        result(message, message_size, "WRONG DECK OR KERNEL"); return -1;
    }
    if (guide_sha256_file(EMULATION_ARCHIVE, archive_hash) != 0 ||
        strcmp(archive_hash, EMULATION_ARCHIVE_SHA256) != 0) {
        result(message, message_size, "CARTRIDGE HASH CHANGED"); return -1;
    }
    for (index = 0; index < sizeof(paths) / sizeof(paths[0]); ++index)
        if (make_directory(paths[index]) != 0) {
            result(message, message_size, "COULD NOT PREPARE STORAGE"); return -1;
        }
    for (index = 0; index < sizeof(emulation_files) / sizeof(emulation_files[0]); ++index) {
        errno = 0;
        if (lstat(emulation_files[index].destination, &(struct stat){0}) == 0 || errno != ENOENT) {
            result(message, message_size, "EXISTING SYSTEM FILE REFUSED"); return -1;
        }
    }
    snprintf(transaction, sizeof(transaction),
             "/var/lib/guideos/install-staging/emulation-%ld", (long)getpid());
    if (mkdir(transaction, 0700) != 0) {
        result(message, message_size, "COULD NOT CREATE SAFE STAGING"); return -1;
    }
    for (index = 0; index < sizeof(emulation_files) / sizeof(emulation_files[0]); ++index) {
        if (staging_path(staged, sizeof(staged), transaction, index) != 0 ||
            extract_entry(EMULATION_ARCHIVE, emulation_files[index].entry, staged) != 0 ||
            guide_sha256_file(staged, actual) != 0 ||
            strcmp(actual, emulation_files[index].sha256) != 0) {
            result(message, message_size, "PAYLOAD FILE FAILED VERIFICATION");
            emulation_rollback(installed, transaction, log); return -1;
        }
    }
    for (index = 0; index < sizeof(emulation_files) / sizeof(emulation_files[0]); ++index) {
        if (staging_path(staged, sizeof(staged), transaction, index) != 0 ||
            copy_new_file(staged, emulation_files[index].destination,
                          emulation_files[index].mode) != 0) {
            result(message, message_size, "INSTALL FAILED AND WAS UNDONE");
            emulation_rollback(installed, transaction, log); return -1;
        }
        ++installed;
    }
    record = open(EMULATION_RECORD ".new", O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW, 0644);
    if (record < 0 || write(record, record_text, strlen(record_text)) != (ssize_t)strlen(record_text) ||
        fsync(record) != 0) goto emulation_activate_failed;
    close(record); record = -1;
    if (link(EMULATION_RECORD ".new", EMULATION_RECORD) != 0) goto emulation_activate_failed;
    unlink(EMULATION_RECORD ".new");
    sync(); emulation_cleanup(transaction);
    result(message, message_size, "EMULATION INSTALLED");
    fprintf(log, "emulation installer success\n"); fflush(log); return 0;

emulation_activate_failed:
    if (record >= 0) close(record);
    unlink(EMULATION_RECORD ".new"); unlink(EMULATION_RECORD);
    emulation_rollback(installed, transaction, log);
    result(message, message_size, "INSTALL FAILED AND WAS UNDONE"); return -1;
}
