"""Fixed diagnostic vocabulary: never log device names, addresses or raw errors."""
from guide_telemetry import emit

BACKEND_ERRORS = {
    'org.bluez.Error.NotReady', 'org.bluez.Error.Failed',
    'org.bluez.Error.InProgress', 'org.bluez.Error.NotSupported',
    'org.bluez.Error.AuthenticationFailed', 'org.bluez.Error.AuthenticationCanceled',
    'org.bluez.Error.AuthenticationRejected', 'org.bluez.Error.AuthenticationTimeout',
    'org.bluez.Error.ConnectionAttemptFailed', 'org.bluez.Error.NotConnected',
    'org.bluez.Error.AlreadyConnected', 'org.bluez.Error.AlreadyExists',
    'org.freedesktop.DBus.Error.AccessDenied', 'org.freedesktop.DBus.Error.NoReply',
    'org.freedesktop.DBus.Error.ServiceUnknown', 'org.freedesktop.DBus.Error.UnknownObject',
}
ACTIONS = {'refresh','output','play','resume','pause','stop','volume','scan',
           'connect','disconnect','cancel','inventory','scan_stop','pair','unknown'}


def report(action, error):
    name = error.get_dbus_name() if hasattr(error, 'get_dbus_name') else type(error).__name__
    if name not in BACKEND_ERRORS | {'ValueError','TimeoutError','FileNotFoundError'}:
        name = 'other'
    emit('COMMAND_ERROR', component='audio', action=action if isinstance(action,str) and action in ACTIONS else 'unknown',
         backend_error=name, error_number=getattr(error,'errno',0) or 0)
    return name


def bluetooth_message(action, error):
    name = report(action, error)
    if isinstance(error, ValueError):
        return str(error)[:120]
    messages = {
        'org.bluez.Error.NotReady': 'Bluetooth radio not ready. Retry Find earbuds.',
        'org.bluez.Error.InProgress': 'Bluetooth is busy. Cancel, then retry.',
        'org.freedesktop.DBus.Error.AccessDenied': 'Bluetooth permission denied. Diagnostic recorded.',
        'org.freedesktop.DBus.Error.ServiceUnknown': 'Bluetooth service unavailable. Retry shortly.',
        'org.freedesktop.DBus.Error.NoReply': 'Bluetooth did not respond. Cancel, then retry.',
        'org.bluez.Error.AuthenticationFailed': 'Pairing failed. Put the earbud back in pairing mode.',
        'org.bluez.Error.AuthenticationRejected': 'Earbud rejected pairing. Retry pairing mode.',
        'org.bluez.Error.NotSupported': 'This Bluetooth operation is not supported.',
    }
    return messages.get(name, 'Bluetooth operation failed. Retry pairing mode; diagnostic recorded.')
