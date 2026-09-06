# Android Application Provider 0

## Decision

Android compatibility is a service, not a defining feature of a Deck. GuideOS
applications remain native Guide packages. A compatible Deck may run an
Android provider locally; a smaller Deck may control one on a nearby Node and
receive its picture and sound. Both expose the same Guide capability names, so
the person does not have to understand where the work happens.

This preserves the distinction between the Deck and the Semiotic Engine. An
Android runtime is another optional machine capability; it is not the agent and
does not receive the user's identity or personal data by default.

## Magic: The Gathering Arena feasibility case

The RG35XX H is not a credible local Arena machine. Arena's published Android
minimum calls for Android 6 or newer, 4 GB of memory, OpenGL ES 3.0 with ETC2,
and roughly Snapdragon 835-class hardware. This prototype has 1 GB of memory
and a small framebuffer-oriented Linux environment, without Android, Google
services, or a proven accelerated Android graphics path. Trying to hide that
gap behind a local compatibility layer would create a slow and unreliable
experience.

The current desktop Node is suitable: it has a Ryzen 5 5600X, approximately
48 GiB of usable system memory, firmware virtualization enabled, and a Radeon
RX 6700 XT. The preferred first experiment is to run the native Windows Arena
client on that Node and stream only its picture, sound, and explicitly mapped
controls to the Deck. Running the Android version in a hardware-accelerated
emulator is a viable second route when testing the Android-provider abstraction,
but it adds an emulator and Google Play compatibility boundary without helping
the actual game experience.

An owned Android phone can serve as a third provider: the Node mirrors the
phone's application session and relays it to the Deck. This is useful when an
application exists only on Android or refuses an emulator.

## Three routes

### 1. Guide-native adaptation

For an open-source application, the preferred result is a Guide package using
open file formats and the Guide interface. This produces the smallest and most
reliable experience but requires application-specific adaptation. It is not a
general APK translator.

### 2. Android on a Deck

A future Deck can host an Android container only when its Linux kernel,
graphics, sound, input, isolation, and memory have been proven sufficient.
Container systems also require compatible application CPU architecture. A
dedicated Android boot image is another possibility, but changing operating
systems is not the seamless Guide experience we want.

The current RG35XX H prototype has only 1 GB of memory, an old vendor kernel,
and a framebuffer-oriented GuideOS bridge. We have not yet demonstrated the
Android Binder facilities, container isolation, graphics acceleration, audio,
or hardware video decoding needed for a useful local Android runtime. Native
APK execution is therefore a research path, not a promised feature of this
prototype.

### 3. Android on a Node

This is the first practical route. A Windows Node can run an Android Virtual
Device or connect to a user-owned Android device. The Node renders the
application and gives the Deck a constrained interactive session. The first
display proof may use low-frame-rate images; the useful target is
hardware-encoded H.264 video, synchronized audio, and controller input.

For games, the provider should prefer an application's native Node version
when one exists. The Deck does not need to pretend the native program is an
APK: both native and Android providers can implement the same constrained
`application.session.*` contract.

The Node must not expose ADB or a desktop shell to the Deck. It exposes only:

- `android.apps.list`
- `android.app.launch`
- `android.app.stop`
- `android.session.open`
- `android.session.input`
- `android.session.close`
- `android.package.request-install`, which always needs confirmation on the Node

The general streaming surface is:

- `application.session.open`
- `application.session.video`
- `application.session.audio`
- `application.session.input`
- `application.session.close`

The first Arena proof should map the Deck controls to a deliberate game profile,
not expose an unrestricted remote keyboard, mouse, or Windows desktop.

Installation never silently downloads an APK. The user supplies software they
are entitled to use, and the Node reports CPU architecture and platform
incompatibility plainly.

## Permission translation

Android permissions are not automatically Guide permissions. Camera,
microphone, location, clipboard, personal files, contacts, and network exposure
remain unavailable until separately granted. A Deck session receives only the
application picture, application sound, and the inputs explicitly routed to
that session. Closing the session revokes its temporary credentials.

## Work sequence

1. Complete encrypted Deck-to-Node discovery, identity, and pairing.
2. Add a provider interface to the Node; an unavailable provider must remain a
   valid, understandable state.
3. Detect an installed Android SDK and enumerate AVDs without starting them.
4. Add locally confirmed start, stop, list, and launch operations.
5. Prove a low-frame-rate Deck session, input mapping, and immediate revocation.
6. Integrate an efficient video/audio transport and the Deck's hardware decoder.
7. Audit the RG35XX H kernel and drivers before attempting a local provider.

## Arena proof sequence

1. Install and launch the native Windows Arena client manually on the Node.
2. Prove low-latency H.264 video and synchronized audio to the Deck on local Wi-Fi.
3. Add pointer emulation suitable for Arena's touch/mouse interface and a clear
   on-Deck way to end the session.
4. Measure input-to-picture latency, dropped frames, Node load, and Deck decode load.
5. Add a named Arena profile only after the general session boundary is reliable.
6. Test an Android emulator as a provider separately; do not make it a dependency
   of native Node streaming.

## Non-goals for the first version

- Reimplementing Android or promising every APK will work.
- Bundling Google Play, proprietary applications, or third-party credentials.
- Giving remote Decks unrestricted Android-debug or Windows access.
- Hiding whether an application is running locally or consuming Node resources.

## Technical references

- Android Developers: [Start the emulator from the command line](https://developer.android.com/studio/run/emulator-commandline)
- Android Developers: [Create and manage virtual devices](https://developer.android.com/studio/run/managing-avds)
- Android Developers: [Configure hardware acceleration](https://developer.android.com/studio/run/emulator-acceleration)
- Wizards of the Coast: [Arena supported mobile devices and minimum requirements](https://mtgarena-support.wizards.com/hc/en-us/articles/360054912332-Supported-Mobile-Devices-and-Minimum-Requirements)
- Waydroid: [Architecture overview](https://docs.waydro.id/)
- Waydroid: [Kernel Binder and memory-support check](https://docs.waydro.id/debugging/getting-essential-information)
- scrcpy: [Official project and supported mirroring features](https://github.com/Genymobile/scrcpy/)
