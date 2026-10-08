"""Bound startup ordering until the private session bus accepts connections."""
import time
import dbus

deadline = time.monotonic() + 5
while True:
    try:
        connection = dbus.bus.BusConnection('unix:path=/run/guide-audio/bus')
        connection.close()
        break
    except dbus.DBusException:
        if time.monotonic() >= deadline:
            raise SystemExit('Guide audio session bus did not become ready')
        time.sleep(.05)
