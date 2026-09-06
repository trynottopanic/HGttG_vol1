// SPDX-License-Identifier: AGPL-3.0-or-later
// Initialize and report the RG35XX H prototype's ALSA speaker signal path.

#include <alsa/asoundlib.h>
#include <stdio.h>
#include <string.h>

static int is_speaker_path(const char *name)
{
    return strcmp(name, "LINEOUT") == 0 ||
           strcmp(name, "OutputL Mixer DACL") == 0 ||
           strcmp(name, "OutputR Mixer DACR") == 0 ||
           strcmp(name, "SPK") == 0;
}

static int requested_delta(int argc, char **argv)
{
    if (argc == 2 && strcmp(argv[1], "--volume-up") == 0) return 1;
    if (argc == 2 && strcmp(argv[1], "--volume-down") == 0) return -1;
    return 0;
}

int main(int argc, char **argv)
{
    snd_mixer_t *mixer = NULL;
    snd_mixer_elem_t *element;
    int initialize = argc == 2 && strcmp(argv[1], "--initialize-speaker") == 0;
    int delta = requested_delta(argc, argv);
    int volume_percent = -1;
    int result;

    if ((result = snd_mixer_open(&mixer, 0)) < 0 ||
        (result = snd_mixer_attach(mixer, "hw:0")) < 0 ||
        (result = snd_mixer_selem_register(mixer, NULL, NULL)) < 0 ||
        (result = snd_mixer_load(mixer)) < 0) {
        fprintf(stderr, "audio-control error=%s\n", snd_strerror(result));
        if (mixer) snd_mixer_close(mixer);
        return 1;
    }

    for (element = snd_mixer_first_elem(mixer); element;
         element = snd_mixer_elem_next(element)) {
        const char *name = snd_mixer_selem_get_name(element);
        int has_switch = snd_mixer_selem_has_playback_switch(element);
        int enabled = -1;

        if (strcmp(name, "lineout volume") == 0 &&
            snd_mixer_selem_has_playback_volume(element)) {
            long minimum = 0, maximum = 0, current = 0;
            snd_mixer_selem_get_playback_volume_range(element, &minimum, &maximum);
            if (snd_mixer_selem_get_playback_volume(
                    element, SND_MIXER_SCHN_FRONT_LEFT, &current) >= 0) {
                if (delta && maximum > minimum) {
                    int current_percent = (int)((current - minimum) * 100 /
                                                (maximum - minimum));
                    int target_percent = current_percent + delta * 10;
                    if (target_percent < 0) target_percent = 0;
                    if (target_percent > 100) target_percent = 100;
                    current = minimum +
                        (target_percent * (maximum - minimum) + 50) / 100;
                }
                if (delta && snd_mixer_selem_set_playback_volume_all(element, current) < 0) {
                    fprintf(stderr, "audio-control could-not-set-volume\n");
                    snd_mixer_close(mixer);
                    return 1;
                }
                volume_percent = maximum > minimum ?
                    (int)((current - minimum) * 100 / (maximum - minimum)) : 100;
            }
        }

        if ((initialize || delta) && has_switch && is_speaker_path(name) &&
            snd_mixer_selem_set_playback_switch_all(element, 1) < 0) {
            fprintf(stderr, "audio-control could-not-enable=%s\n", name);
            snd_mixer_close(mixer);
            return 1;
        }
        if (has_switch &&
            snd_mixer_selem_get_playback_switch(element, SND_MIXER_SCHN_FRONT_LEFT,
                                                &enabled) < 0)
            enabled = -1;
        if (is_speaker_path(name))
            fprintf(stderr, "audio-control path=%s enabled=%d\n", name, enabled);
    }
    snd_mixer_close(mixer);
    if (volume_percent < 0) {
        fprintf(stderr, "audio-control volume-unavailable\n");
        return 1;
    }
    printf("VOLUME=%d\n", volume_percent);
    return 0;
}
