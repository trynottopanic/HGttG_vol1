#include <errno.h>
#include <fcntl.h>
#include <linux/input-event-codes.h>
#include <linux/joystick.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>

int main(int argc, char **argv)
{
    const char *path = argc > 1 ? argv[1] : "/dev/input/js0";
    unsigned char axes = 0;
    __u8 axis_map[ABS_CNT] = {0};
    int descriptor = open(path, O_RDONLY | O_NONBLOCK);
    unsigned index;

    if (descriptor < 0) {
        fprintf(stderr, "%s: %s\n", path, strerror(errno));
        return 1;
    }
    if (ioctl(descriptor, JSIOCGAXES, &axes) != 0 ||
        ioctl(descriptor, JSIOCGAXMAP, axis_map) != 0) {
        fprintf(stderr, "%s: joystick metadata unavailable: %s\n",
                path, strerror(errno));
        close(descriptor);
        return 1;
    }
    printf("device=%s axes=%u\n", path, axes);
    for (index = 0; index < axes; ++index)
        printf("sdl-axis=%u linux-abs-code=%u\n", index, axis_map[index]);
    close(descriptor);
    return 0;
}
