# Guide browser prototype for 0.4.0

WebKitGTK is the owner-selected engine integration. Home remains the existing
shell. Read [INTEGRATION.md](INTEGRATION.md) for frontend hooks, controller mapping,
image staging and known limitations.

Uses packaged GTK 4/WebKitGTK 6.0 APIs and Weston. No custom engine/compositor.
Run `python3 guide_browser.py https://example.org` in a graphical session as an
ordinary user. Never disable WebKit sandboxing to run it as root.

Host checks:

- `dbus-run-session -- xvfb-run -a python3 test_runtime.py`
- `python3 test_session.py`
- `python3 -m unittest test_frontend -v`

These cover a real web process, reversible adaptation and text entry, intercepted
downloads, a real headless Weston session and safe display-lease recovery logic.
They do not establish ARM64/Deck graphics, controller or physical acceptance.
The service and frontend adapter are staged source, not installed on the Seed.

The prototype has ephemeral website state, a basic text-chunk keyboard and one
page. HTTP/HTTPS GET downloads now use the Guide transfer/storage service with a
destination picker, progress, cancellation and explicit collision choices.
POST/blob downloads, uploads and FTP are not supported. See
[downloads/update integration](../../../docs/DOWNLOADS_UPDATES_0_4_0.md).
