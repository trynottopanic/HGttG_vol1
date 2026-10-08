"""Native Windows control panel for the Guide desktop Node.

The first prototype used Tk, which showed severe top-level window drag latency
on the development computer even at zero CPU load. This panel uses ordinary
Win32 controls while retaining the same NodeState and NodeRuntime backend.
"""

from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import statistics
import sys
import threading
import time

from guide_node_core import DEFAULT_DISCOVERY_PORT, DEFAULT_HTTP_PORT, NodeState
from guide_node_server import NodeRuntime
from windows_ui_performance import MovementGovernor
from diagnostic_suite import DiagnosticSuiteRunner
from deck_discovery import discover_decks


if not hasattr(ctypes, "WINFUNCTYPE"):
    raise RuntimeError("The native Node interface requires Windows")

user32 = ctypes.WinDLL("user32", use_last_error=True)
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)

# Windows otherwise treats python/pythonw as DPI-unaware and bitmap-scales the
# complete GDI window. On the prototype's high-DPI display a requested 700 px
# window became roughly 1200 px, looked blurred, and lagged while being moved.
try:
    user32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
    user32.SetProcessDpiAwarenessContext.restype = wintypes.BOOL
    _dpi_aware = bool(user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)))
except (AttributeError, OSError):
    _dpi_aware = False
if not _dpi_aware:
    try:
        shcore = ctypes.WinDLL("shcore", use_last_error=True)
        shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        pass

LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT,
                            wintypes.WPARAM, wintypes.LPARAM)


class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT), ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR),
    ]


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND), ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM), ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD), ("pt", wintypes.POINT),
        ("lPrivate", wintypes.DWORD),
    ]


class PAINTSTRUCT(ctypes.Structure):
    _fields_ = [
        ("hdc", wintypes.HDC), ("fErase", wintypes.BOOL),
        ("rcPaint", wintypes.RECT), ("fRestore", wintypes.BOOL),
        ("fIncUpdate", wintypes.BOOL),
        ("rgbReserved", wintypes.BYTE * 32),
    ]


WS_OVERLAPPEDWINDOW = 0x00CF0000
WS_VISIBLE = 0x10000000
WS_CHILD = 0x40000000
WS_BORDER = 0x00800000
WS_VSCROLL = 0x00200000
BS_AUTOCHECKBOX = 0x00000003
ES_READONLY = 0x00000800
LBS_NOTIFY = 0x00000001
CW_USEDEFAULT = -2147483648
SW_HIDE = 0
SW_SHOW = 5
WM_CREATE = 0x0001
WM_DESTROY = 0x0002
WM_CANCELMODE = 0x001F
WM_PAINT = 0x000F
WM_COMMAND = 0x0111
WM_TIMER = 0x0113
WM_CLOSE = 0x0010
WM_SETFONT = 0x0030
WM_MOUSEMOVE = 0x0200
WM_MOVING = 0x0216
WM_NCMOUSEMOVE = 0x00A0
WM_ENTERSIZEMOVE = 0x0231
WM_EXITSIZEMOVE = 0x0232
WM_APP_STATUS = 0x8001
BM_GETCHECK = 0x00F0
BM_SETCHECK = 0x00F1
BST_CHECKED = 1
LB_ADDSTRING = 0x0180
LB_RESETCONTENT = 0x0184
LB_GETCURSEL = 0x0188
LB_SETCURSEL = 0x0186
LB_ERR = -1
MB_OK = 0
MB_ICONERROR = 0x10
MB_ICONINFORMATION = 0x40
COLOR_BTNFACE = 15
IDC_ARROW = 32512
DEFAULT_GUI_FONT = 17

ID_NEW_CODE = 101
ID_NODE_TOGGLE = 102
ID_MEDIA_CHOOSE = 201
ID_MEDIA_RESCAN = 202
ID_MEDIA_REMOVE = 203
ID_MEDIA_CLEAR = 204
ID_APP_LIST = 301
ID_APP_ADD = 302
ID_APP_REMOVE = 303
ID_APP_APPROVE = 304
ID_APP_DENY = 305
ID_TRUST_ARM = 401
ID_TRUST_LIST = 402
ID_TRUST_REVOKE = 403
ID_DIAGNOSE_MOVEMENT = 501
ID_SE_TOGGLE = 502
ID_AT_FIELD = 503
ID_DECK_DIAGNOSTIC = 504
ID_DECK_DIAGNOSTIC_CANCEL = 505
DIAGNOSTIC_TIMER = 1
MOVE_WATCHDOG_TIMER = 2
PM_REMOVE = 0x0001
VK_LBUTTON = 0x01
VREFRESH = 116


user32.CreateWindowExW.argtypes = [
    wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wintypes.HWND, wintypes.HANDLE, wintypes.HINSTANCE, wintypes.LPVOID,
]
user32.CreateWindowExW.restype = wintypes.HWND
user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT,
                                  wintypes.WPARAM, wintypes.LPARAM]
user32.DefWindowProcW.restype = LRESULT
user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT,
                                wintypes.WPARAM, wintypes.LPARAM]
user32.SendMessageW.restype = LRESULT
user32.SetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPCWSTR]
user32.SetWindowTextW.restype = wintypes.BOOL
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT,
                                wintypes.WPARAM, wintypes.LPARAM]
user32.PostMessageW.restype = wintypes.BOOL
user32.EnableWindow.argtypes = [wintypes.HWND, wintypes.BOOL]
user32.EnableWindow.restype = wintypes.BOOL
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.ShowWindow.restype = wintypes.BOOL
user32.ValidateRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.ValidateRect.restype = wintypes.BOOL
user32.InvalidateRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT),
                                  wintypes.BOOL]
user32.InvalidateRect.restype = wintypes.BOOL
user32.UpdateWindow.argtypes = [wintypes.HWND]
user32.UpdateWindow.restype = wintypes.BOOL
user32.BeginPaint.argtypes = [wintypes.HWND, ctypes.POINTER(PAINTSTRUCT)]
user32.BeginPaint.restype = wintypes.HDC
user32.EndPaint.argtypes = [wintypes.HWND, ctypes.POINTER(PAINTSTRUCT)]
user32.EndPaint.restype = wintypes.BOOL
user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetClientRect.restype = wintypes.BOOL
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetWindowRect.restype = wintypes.BOOL
user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
user32.GetCursorPos.restype = wintypes.BOOL
user32.GetDC.argtypes = [wintypes.HWND]
user32.GetDC.restype = wintypes.HDC
user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
user32.ReleaseDC.restype = ctypes.c_int
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = ctypes.c_short
user32.ReleaseCapture.restype = wintypes.BOOL
user32.FillRect.argtypes = [wintypes.HDC, ctypes.POINTER(wintypes.RECT),
                            wintypes.HBRUSH]
user32.FillRect.restype = ctypes.c_int
user32.SetTimer.argtypes = [wintypes.HWND, wintypes.WPARAM,
                            wintypes.UINT, wintypes.LPVOID]
user32.SetTimer.restype = wintypes.WPARAM
user32.KillTimer.argtypes = [wintypes.HWND, wintypes.WPARAM]
user32.KillTimer.restype = wintypes.BOOL
user32.GetSystemMetrics.argtypes = [ctypes.c_int]
user32.GetSystemMetrics.restype = ctypes.c_int
user32.LoadCursorW.argtypes = [wintypes.HINSTANCE, wintypes.HANDLE]
user32.LoadCursorW.restype = wintypes.HANDLE
user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
user32.RegisterClassW.restype = wintypes.ATOM
user32.GetMessageW.argtypes = [ctypes.POINTER(MSG), wintypes.HWND,
                               wintypes.UINT, wintypes.UINT]
user32.GetMessageW.restype = wintypes.BOOL
user32.PeekMessageW.argtypes = [ctypes.POINTER(MSG), wintypes.HWND,
                                wintypes.UINT, wintypes.UINT, wintypes.UINT]
user32.PeekMessageW.restype = wintypes.BOOL
user32.TranslateMessage.argtypes = [ctypes.POINTER(MSG)]
user32.DispatchMessageW.argtypes = [ctypes.POINTER(MSG)]
user32.DispatchMessageW.restype = LRESULT
user32.GetSysColorBrush.argtypes = [ctypes.c_int]
user32.GetSysColorBrush.restype = wintypes.HBRUSH
user32.GetDpiForSystem.restype = wintypes.UINT
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetModuleHandleW.restype = wintypes.HINSTANCE
gdi32.GetStockObject.argtypes = [ctypes.c_int]
gdi32.GetStockObject.restype = wintypes.HANDLE
gdi32.GetDeviceCaps.argtypes = [wintypes.HDC, ctypes.c_int]
gdi32.GetDeviceCaps.restype = ctypes.c_int
gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HANDLE]
gdi32.SelectObject.restype = wintypes.HANDLE
gdi32.SetBkMode.argtypes = [wintypes.HDC, ctypes.c_int]
gdi32.SetBkMode.restype = ctypes.c_int
gdi32.SetTextColor.argtypes = [wintypes.HDC, wintypes.DWORD]
gdi32.SetTextColor.restype = wintypes.DWORD
user32.DrawTextW.argtypes = [wintypes.HDC, wintypes.LPCWSTR, ctypes.c_int,
                             ctypes.POINTER(wintypes.RECT), wintypes.UINT]
user32.DrawTextW.restype = ctypes.c_int
gdi32.CreateFontW.argtypes = [
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
    wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
    wintypes.LPCWSTR,
]
gdi32.CreateFontW.restype = wintypes.HANDLE

try:
    dwmapi = ctypes.WinDLL("dwmapi", use_last_error=True)
    dwmapi.DwmIsCompositionEnabled.argtypes = [ctypes.POINTER(wintypes.BOOL)]
    dwmapi.DwmIsCompositionEnabled.restype = ctypes.c_long
except OSError:
    dwmapi = None


_window: "NativeGuideNodeWindow | None" = None


@WNDPROC
def _window_procedure(hwnd: int, message: int, wparam: int, lparam: int) -> int:
    if _window is not None:
        return _window.window_procedure(hwnd, message, wparam, lparam)
    return user32.DefWindowProcW(hwnd, message, wparam, lparam)


class NativeGuideNodeWindow:
    def __init__(self, http_port: int, discovery_port: int, media_folder: str = "",
                 semiotic_enabled: bool | None = None, config_path: Path | None = None,
                 deck_address: str = "") -> None:
        self.state = NodeState(auto_prepare=True, semiotic_enabled=semiotic_enabled,
                               config_path=config_path)
        if media_folder:
            self.state.media.set_folder(media_folder)
            self.state.prepare_media()
        self.runtime = NodeRuntime(self.state, http_port, discovery_port)
        self.hwnd = 0
        self.controls: dict[str, int] = {}
        self.child_controls: list[int] = []
        self._closed = False
        self._snapshot_lock = threading.Lock()
        self._snapshot: dict[str, object] = {}
        self._stop = threading.Event()
        self._worker: threading.Thread | None = None
        self.dpi = int(user32.GetDpiForSystem()) or 96
        self.scale = self.dpi / 96.0
        self.font = gdi32.CreateFontW(
            -max(12, round(10 * self.dpi / 72)), 0, 0, 0, 400, 0, 0, 0,
            1, 0, 0, 5, 0, "Segoe UI")
        self._displayed: dict[str, object] = {}
        self.deck_address = deck_address.strip()
        self._deck_runner = None
        self._deck_diag_status = "No Deck diagnostic running."
        self._deck_diag_lock = threading.Lock()
        self._deck_scan_thread = None
        self._diagnostic_active = False
        self._diagnostic_dragging = False
        self._diagnostic_timer_times: list[float] = []
        self._diagnostic_move_times: list[float] = []
        self._diagnostic_pointer_lag: list[float] = []
        self._diagnostic_governed_lag: list[float] = []
        self._diagnostic_discarded_moves = 0
        self._diagnostic_paints = 0
        self._diagnostic_wall_start = 0.0
        self._diagnostic_cpu_start = 0.0
        self._diagnostic_release_at = 0.0
        self._diagnostic_settle_ms = 0.0
        self._moving_optimized = False
        self._drag_offset_x = 0
        self._drag_offset_y = 0
        self._mouse_drag_active = False
        self.refresh_hz = self._display_refresh_hz()
        self.movement_governor = MovementGovernor(self.refresh_hz)

    def _px(self, value: int) -> int:
        return round(value * self.scale)

    @staticmethod
    def _display_refresh_hz() -> int:
        dc = user32.GetDC(None)
        if not dc:
            return 60
        try:
            measured = int(gdi32.GetDeviceCaps(dc, VREFRESH))
            return measured if 30 <= measured <= 240 else 60
        finally:
            user32.ReleaseDC(None, dc)

    @staticmethod
    def _message(text: str, error: bool = False) -> None:
        user32.MessageBoxW(None, text, "Guide Desktop Node",
                           MB_OK | (MB_ICONERROR if error else MB_ICONINFORMATION))

    def _control(self, kind: str, text: str, x: int, y: int, width: int, height: int,
                 control_id: int = 0, style: int = 0) -> int:
        handle = user32.CreateWindowExW(
            0, kind, text, WS_CHILD | WS_VISIBLE | style,
            self._px(x), self._px(y), self._px(width), self._px(height),
            self.hwnd, ctypes.c_void_p(control_id),
            kernel32.GetModuleHandleW(None), None,
        )
        user32.SendMessageW(handle, WM_SETFONT,
                            self.font or gdi32.GetStockObject(DEFAULT_GUI_FONT), 1)
        self.child_controls.append(handle)
        return handle

    def _create_controls(self) -> None:
        self._control("STATIC", "GUIDE DESKTOP NODE", 24, 20, 330, 28)
        self._control("STATIC", "AT Field", 365, 24, 75, 24)
        self.controls["at_field"] = self._control(
            "COMBOBOX", "", 445, 20, 180, 140, ID_AT_FIELD, 0x0003 | WS_VSCROLL | 0x10000)
        for mode in ("closed", "familiar", "open"):
            # Keep the UTF-16 buffer alive until synchronous CB_ADDSTRING returns.
            label = ctypes.c_wchar_p(mode.title())
            user32.SendMessageW(self.controls["at_field"], 0x0143, 0,
                                ctypes.cast(label, ctypes.c_void_p).value)
        user32.SendMessageW(self.controls["at_field"], 0x014E,
                            ("closed", "familiar", "open").index(self.state.at_field.mode.value), 0)
        self._control("STATIC", "Makes selected services on this computer available to a paired Deck.",
                      24, 51, 630, 22)
        self.controls["status"] = self._control("STATIC", "Starting...", 24, 82, 620, 22)
        self.controls["address"] = self._control("STATIC", "", 24, 106, 620, 22)

        self._control("STATIC", "PAIRING CODE", 24, 140, 180, 20)
        self.controls["code"] = self._control("STATIC", self.state.pairing_code, 24, 162, 210, 40)
        self._control("BUTTON", "New pairing code", 250, 163, 145, 30, ID_NEW_CODE)
        self.controls["toggle"] = self._control(
            "BUTTON", "Stop Node", 405, 163, 110, 30, ID_NODE_TOGGLE)

        self._control("STATIC", "MEDIA FOLDERS", 24, 218, 180, 20)
        self.controls["media_folders"] = self._control(
            "LISTBOX", "", 24, 240, 425, 62, 0, WS_BORDER | WS_VSCROLL | LBS_NOTIFY)
        self._control("BUTTON", "Add folder...", 460, 240, 90, 27, ID_MEDIA_CHOOSE)
        self._control("BUTTON", "Remove", 558, 240, 72, 27, ID_MEDIA_REMOVE)
        self._control("BUTTON", "Rescan", 460, 274, 90, 27, ID_MEDIA_RESCAN)
        self._control("BUTTON", "Clear all", 558, 274, 72, 27, ID_MEDIA_CLEAR)
        self.controls["media"] = self._control("STATIC", "No folders selected", 24, 309, 620, 22)

        self._control("STATIC", "STREAMED APPLICATIONS", 24, 338, 230, 20)
        self.controls["applications"] = self._control(
            "LISTBOX", "", 24, 362, 475, 60, ID_APP_LIST, WS_BORDER | WS_VSCROLL | LBS_NOTIFY)
        self._control("BUTTON", "Add...", 510, 362, 105, 28, ID_APP_ADD)
        self._control("BUTTON", "Remove", 510, 394, 105, 28, ID_APP_REMOVE)
        self.controls["request"] = self._control(
            "STATIC", "No application request waiting.", 24, 432, 620, 40)
        self.controls["approve"] = self._control(
            "BUTTON", "Approve request", 24, 476, 135, 30, ID_APP_APPROVE)
        self.controls["deny"] = self._control("BUTTON", "Decline", 168, 476, 90, 30, ID_APP_DENY)

        self._control("STATIC", "TRUSTED COMPANIONS", 24, 522, 220, 20)
        self.controls["trust_arm"] = self._control(
            "BUTTON", "Allow the next paired Deck's trust request", 24, 544, 350, 24,
            ID_TRUST_ARM, BS_AUTOCHECKBOX)
        self.controls["trusted"] = self._control(
            "LISTBOX", "", 24, 574, 475, 60, ID_TRUST_LIST, WS_BORDER | WS_VSCROLL | LBS_NOTIFY)
        self._control("BUTTON", "Revoke selected", 510, 574, 120, 30, ID_TRUST_REVOKE)

        self._control("STATIC", "SEMIOTIC ENGINE", 24, 646, 220, 20)
        self.controls["semiotic_toggle"] = self._control(
            "BUTTON", "Allow this Node to use the separately installed Engine",
            24, 668, 430, 24, ID_SE_TOGGLE, BS_AUTOCHECKBOX)
        self.controls["semiotic_status"] = self._control(
            "STATIC", "Checking optional Engine...", 24, 696, 606, 24)
        self._control("STATIC", "DEVELOPMENT LINK — trusted private networks only.",
                      24, 822, 606, 24)
        self._control("BUTTON", "Diagnose movement", 475, 736, 155, 30,
                      ID_DIAGNOSE_MOVEMENT)
        self._control("STATIC", "DECK DIAGNOSTICS", 24, 716, 180, 20)
        self._control("STATIC", "Deck IP", 24, 742, 64, 22)
        self.controls["deck_address"] = self._control("EDIT", self.deck_address, 90, 738, 145, 28, 0, WS_BORDER | 0x0080)
        self.controls["deck_diag"] = self._control("BUTTON", "Run diagnostics", 245, 738, 125, 28, ID_DECK_DIAGNOSTIC)
        self.controls["deck_cancel"] = self._control("BUTTON", "Cancel", 378, 738, 80, 28, ID_DECK_DIAGNOSTIC_CANCEL)
        self.controls["deck_diag_status"] = self._control("STATIC", self._deck_diag_status, 24, 770, 606, 46)

    @staticmethod
    def _set_text(handle: int, value: str) -> None:
        user32.SetWindowTextW(handle, value)

    def _set_named_text(self, name: str, value: str) -> None:
        if self._displayed.get(name) == value:
            return
        self._set_text(self.controls[name], value)
        self._displayed[name] = value

    @staticmethod
    def _replace_list(handle: int, entries: tuple[str, ...]) -> None:
        selected = int(user32.SendMessageW(handle, LB_GETCURSEL, 0, 0))
        user32.SendMessageW(handle, LB_RESETCONTENT, 0, 0)
        for entry in entries:
            text = ctypes.c_wchar_p(entry)
            user32.SendMessageW(handle, LB_ADDSTRING, 0,
                                ctypes.cast(text, ctypes.c_void_p).value)
        if entries:
            user32.SendMessageW(handle, LB_SETCURSEL, min(max(selected, 0), len(entries) - 1), 0)

    def _status_snapshot(self) -> dict[str, object]:
        folders = self.state.media.folders
        recognized = self.state.media.records()
        preparation = self.state.media_preparation()
        audio_ready = sum(record.kind == "audio" for record in recognized)
        return {
            "running": self.runtime.running,
            "sessions": self.state.session_count(),
            "code": self.state.pairing_code,
            "folders": tuple(str(folder) for folder in folders),
            "recognized": len(recognized),
            "ready": audio_ready + int(preparation["ready"]),
            "preparation": preparation,
            "media_error": self.state.media.last_error,
            "trusted": tuple(self.state.trusted_decks()),
            "trust_armed": self.state.trust_armed,
            "applications": tuple(
                (str(item["name"]), bool(item["available"]))
                for item in self.state.applications.profiles()),
            "pending": tuple(
                (str(item["client_name"]), str(item["application"]))
                for item in self.state.applications.pending()),
            "streaming_ready": self.state.applications.streaming_available,
            "semiotic": self.state.semiotic.status(),
            "semiotic_enabled": self.state.semiotic.enabled,
        }

    def _refresh_worker(self) -> None:
        while not self._stop.is_set():
            try:
                snapshot = self._status_snapshot()
                with self._snapshot_lock:
                    self._snapshot = snapshot
                user32.PostMessageW(self.hwnd, WM_APP_STATUS, 0, 0)
            except (OSError, ValueError):
                pass
            self._stop.wait(1.0)

    def _apply_snapshot(self) -> None:
        if self._diagnostic_active or self._moving_optimized:
            return
        with self._snapshot_lock:
            snapshot = dict(self._snapshot)
        if not snapshot:
            return
        running = bool(snapshot["running"])
        self._set_named_text("status", "Ready for a Deck" if running else "Stopped")
        with self._deck_diag_lock:
            deck_diag_status = self._deck_diag_status
        self._set_named_text("deck_diag_status", deck_diag_status)
        if self.deck_address and self._deck_scan_thread is None:
            field=ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(self.controls["deck_address"],field,len(field))
            if not field.value:self._set_named_text("deck_address",self.deck_address)
        count = int(snapshot["sessions"])
        suffix = "Deck" if count == 1 else "Decks"
        address = (f"{self.runtime.address}:{self.runtime.http_port}  —  {count} {suffix} paired"
                   if running else "All Deck sessions have been revoked.")
        self._set_named_text("address", address)
        self._set_named_text("toggle", "Stop Node" if running else "Start Node")
        self._set_named_text("code", str(snapshot["code"]))

        folders = tuple(snapshot["folders"])
        if self._displayed.get("media_folders") != folders:
            self._replace_list(self.controls["media_folders"], folders)
            self._displayed["media_folders"] = folders
        if not folders:
            media = "No folders selected — no media is available to Decks."
        else:
            media = (f"{len(folders)} folder(s); {snapshot['ready']} files ready; "
                     f"{snapshot['recognized']} recognized.")
            preparation = dict(snapshot["preparation"])
            active = int(preparation["queued"]) + int(preparation["preparing"])
            if active:
                media += f" Preparing {active} video file(s)..."
            if preparation["error"]:
                media += f" Problem: {preparation['last_error']}"
            if snapshot["media_error"]:
                media += f" Scan problem: {snapshot['media_error']}"
        self._set_named_text("media", media)

        semiotic = dict(snapshot["semiotic"])
        enabled = bool(snapshot["semiotic_enabled"])
        if self._displayed.get("semiotic_enabled") != enabled:
            user32.SendMessageW(self.controls["semiotic_toggle"], BM_SETCHECK,
                                BST_CHECKED if enabled else 0, 0)
            self._displayed["semiotic_enabled"] = enabled
        if not enabled:
            engine_text = "Optional Engine access is off. Deck requests cannot use it."
        elif semiotic.get("available"):
            engine_text = "Engine ready — bounded text assistance is available to paired Decks."
        else:
            engine_text = "Engine allowed, but not running. Start the Semiotic Engine control panel."
        self._set_named_text("semiotic_status", engine_text)

        applications = tuple(snapshot["applications"])
        application_entries = tuple(
            f"{name}  —  {'ready' if available else 'file missing'}"
            for name, available in applications)
        if self._displayed.get("applications") != application_entries:
            self._replace_list(self.controls["applications"], application_entries)
            self._displayed["applications"] = application_entries
        trusted = tuple(snapshot["trusted"])
        trusted_entries = tuple(
            f"{name}  —  {client_id[:8]}" for client_id, name in trusted)
        if self._displayed.get("trusted") != trusted_entries:
            self._replace_list(self.controls["trusted"], trusted_entries)
            self._displayed["trusted"] = trusted_entries
        trust_armed = bool(snapshot["trust_armed"])
        if self._displayed.get("trust_armed") != trust_armed:
            user32.SendMessageW(self.controls["trust_arm"], BM_SETCHECK,
                                BST_CHECKED if trust_armed else 0, 0)
            self._displayed["trust_armed"] = trust_armed

        pending = tuple(snapshot["pending"])
        if pending:
            client, application = pending[0]
            request = f"{client} asks to open {application}. Approve only when expected."
            enabled = True
        else:
            request = ("No application request waiting. " +
                       ("Streaming tools ready." if snapshot["streaming_ready"] else
                        "FFmpeg is needed before application streaming can start."))
            enabled = False
        self._set_named_text("request", request)
        if self._displayed.get("request_enabled") != enabled:
            user32.EnableWindow(self.controls["approve"], enabled)
            user32.EnableWindow(self.controls["deny"], enabled)
            self._displayed["request_enabled"] = enabled

    @staticmethod
    def _choose_folder() -> str:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        try:
            return filedialog.askdirectory(title="Choose the folder this Node may share")
        finally:
            root.destroy()

    @staticmethod
    def _choose_application() -> str:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        try:
            return filedialog.askopenfilename(
                title="Choose an application the Deck may request",
                filetypes=(("Windows applications", "*.exe"),),
            )
        finally:
            root.destroy()

    def _selected(self, handle: int) -> int:
        value = int(user32.SendMessageW(handle, LB_GETCURSEL, 0, 0))
        return -1 if value == LB_ERR else value

    @staticmethod
    def _interval_summary(times: list[float]) -> tuple[float, float, float]:
        intervals = [(later - earlier) * 1000.0
                     for earlier, later in zip(times, times[1:])]
        if not intervals:
            return 0.0, 0.0, 0.0
        ordered = sorted(intervals)
        p95 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]
        return statistics.median(intervals), p95, max(intervals)

    @staticmethod
    def _dwm_enabled() -> str:
        if dwmapi is None:
            return "unknown"
        enabled = wintypes.BOOL()
        if dwmapi.DwmIsCompositionEnabled(ctypes.byref(enabled)) != 0:
            return "unknown"
        return "yes" if enabled.value else "no"

    @staticmethod
    def _save_diagnostic(report: str) -> Path:
        base = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "GuideNode"
        base.mkdir(parents=True, exist_ok=True)
        destination = base / "movement-diagnostic.txt"
        destination.write_text(report, encoding="utf-8")
        return destination

    def _start_deck_discovery(self) -> None:
        if self.deck_address or self._deck_scan_thread is not None:
            return
        with self._deck_diag_lock:
            self._deck_diag_status = "Scanning local network for Deck…"
        def scan() -> None:
            try:
                found = discover_decks()
                with self._deck_diag_lock:
                    if len(found)==1:
                        self.deck_address = found[0]
                        self._deck_diag_status = f"Deck found at {found[0]} — press Run diagnostics"
                    elif found:self._deck_diag_status = "Several endpoints found. Enter the Deck IP before running diagnostics."
                    else:self._deck_diag_status = "No Deck found. Enter its Wi-Fi IP, then press Run diagnostics."
            except Exception:
                with self._deck_diag_lock:self._deck_diag_status = "Discovery failed. Enter the Deck IP to continue."
            finally:
                self._deck_scan_thread = None
                user32.PostMessageW(self.hwnd, WM_APP_STATUS, 0, 0)
        self._deck_scan_thread = threading.Thread(target=scan, name="guide-node-deck-discovery", daemon=True)
        self._deck_scan_thread.start()

    def _start_deck_diagnostics(self) -> None:
        if self._deck_runner is not None:
            self._message("Diagnostics are already running. Use Cancel to stop them.")
            return
        address=ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(self.controls["deck_address"],address,len(address))
        selected=address.value.strip() or self.deck_address
        if not selected:
            self._start_deck_discovery()
            self._message("Enter the Deck's Wi-Fi IP, or wait for discovery and press Run diagnostics again.")
            return
        candidates=[Path(__file__).resolve().parents[2]]
        if getattr(sys,'frozen',False):
            candidates.extend([parent / 'HGttG_vol1/GuideOS' for parent in Path(sys.executable).resolve().parents])
        candidates.append(Path('E:/DGttG/HGttG_vol1/GuideOS'))
        script=next((root/'build/Guide-Link.ps1' for root in candidates if (root/'build/Guide-Link.ps1').is_file()),None)
        if script is None:
            self._message("Guide-Link.ps1 was not found. Install the GuideOS development helpers on this paired PC.",True)
            return
        self.deck_address=selected
        self._deck_runner = DiagnosticSuiteRunner(script, selected)
        runner = self._deck_runner
        with self._deck_diag_lock:
            self._deck_diag_status = "Diagnostics running"
        def work() -> None:
            def update(result) -> None:
                with self._deck_diag_lock:
                    self._deck_diag_status = f"{result.command_id}: {result.outcome}"
                user32.PostMessageW(self.hwnd, WM_APP_STATUS, 0, 0)
            try:
                results = runner.run(update)
                passed = sum(r.outcome == "passed" for r in results)
                capture = next((r for r in results if r.action == "Capture" and r.outcome == "passed"), None)
                failed=next((r for r in results if r.outcome!='passed'),None)
                with self._deck_diag_lock:
                    self._deck_diag_status = (capture.detail or "Full capture saved.") if capture else (f"{failed.action}: {failed.outcome}. {failed.detail[:220]}" if failed else f"Diagnostics finished: {passed}/{len(results)} passed")
            except Exception as error:
                with self._deck_diag_lock:self._deck_diag_status = "Diagnostics failed: " + str(error)[:240]
            finally:
                self._deck_runner = None
                user32.PostMessageW(self.hwnd, WM_APP_STATUS, 0, 0)
        threading.Thread(target=work, name="guide-node-deck-diagnostics", daemon=True).start()

    def _start_movement_diagnostic(self) -> None:
        self._diagnostic_active = True
        self._diagnostic_dragging = False
        self._diagnostic_timer_times.clear()
        self._diagnostic_move_times.clear()
        self._diagnostic_pointer_lag.clear()
        self._diagnostic_governed_lag.clear()
        self._diagnostic_discarded_moves = 0
        self._diagnostic_release_at = 0.0
        self._diagnostic_settle_ms = 0.0
        self._diagnostic_paints = 0
        for handle in self.child_controls:
            user32.ShowWindow(handle, SW_HIDE)
        user32.SetWindowTextW(
            self.hwnd,
            "MOVEMENT TEST — drag this blank window, then release it",
        )
        user32.SetTimer(self.hwnd, DIAGNOSTIC_TIMER, 50, None)

    def _start_optimized_move(self) -> None:
        self._moving_optimized = True
        for handle in self.child_controls:
            user32.ShowWindow(handle, SW_HIDE)
        user32.InvalidateRect(self.hwnd, None, True)
        user32.UpdateWindow(self.hwnd)

    def _finish_optimized_move(self) -> None:
        if not self._moving_optimized:
            return
        for handle in self.child_controls:
            user32.ShowWindow(handle, SW_SHOW)
        self._moving_optimized = False
        user32.InvalidateRect(self.hwnd, None, True)
        user32.UpdateWindow(self.hwnd)
        self._apply_snapshot()

    def _paint_movement_placeholder(self) -> None:
        paint = PAINTSTRUCT()
        dc = user32.BeginPaint(self.hwnd, ctypes.byref(paint))
        try:
            client = wintypes.RECT()
            user32.GetClientRect(self.hwnd, ctypes.byref(client))
            user32.FillRect(dc, ctypes.byref(client),
                            user32.GetSysColorBrush(COLOR_BTNFACE))
            gdi32.SelectObject(dc, self.font or gdi32.GetStockObject(DEFAULT_GUI_FONT))
            gdi32.SetBkMode(dc, 1)  # transparent text background
            gdi32.SetTextColor(dc, 0x000000)
            text_area = wintypes.RECT(
                self._px(24), self._px(20), self._px(650), self._px(90))
            user32.DrawTextW(
                dc, "GUIDE DESKTOP NODE\r\nMoving interface…", -1,
                ctypes.byref(text_area), 0x00000010 | 0x00000800)
        finally:
            user32.EndPaint(self.hwnd, ctypes.byref(paint))

    def _begin_diagnostic_drag(self) -> None:
        if not self._diagnostic_active:
            return
        self._diagnostic_dragging = True
        now = time.perf_counter()
        self._diagnostic_timer_times[:] = [now]
        self._diagnostic_move_times.clear()
        self._diagnostic_pointer_lag.clear()
        self._diagnostic_governed_lag.clear()
        self._diagnostic_discarded_moves = 0
        self._diagnostic_paints = 0
        self._diagnostic_wall_start = now
        self._diagnostic_cpu_start = time.process_time()

    def _capture_drag_anchor(self) -> None:
        cursor = wintypes.POINT()
        window = wintypes.RECT()
        if (user32.GetCursorPos(ctypes.byref(cursor)) and
                user32.GetWindowRect(self.hwnd, ctypes.byref(window))):
            self._drag_offset_x = cursor.x - window.left
            self._drag_offset_y = cursor.y - window.top
        self.movement_governor.begin(time.perf_counter())
        self._mouse_drag_active = bool(
            user32.GetAsyncKeyState(VK_LBUTTON) & 0x8000)
        if self._mouse_drag_active:
            user32.SetTimer(self.hwnd, MOVE_WATCHDOG_TIMER, 8, None)

    @staticmethod
    def _discard_superseded_mouse_moves() -> int:
        discarded = 0
        pending = MSG()
        for mouse_message in (WM_MOUSEMOVE, WM_NCMOUSEMOVE):
            while discarded < 4096 and user32.PeekMessageW(
                    ctypes.byref(pending), None, mouse_message,
                    mouse_message, PM_REMOVE):
                discarded += 1
        return discarded

    def _follow_live_pointer(self, rectangle_address: int) -> None:
        if not rectangle_address:
            return
        proposed = ctypes.cast(
            rectangle_address, ctypes.POINTER(wintypes.RECT)).contents
        cursor = wintypes.POINT()
        current = wintypes.RECT()
        if (not user32.GetCursorPos(ctypes.byref(cursor)) or
                not user32.GetWindowRect(self.hwnd, ctypes.byref(current))):
            return
        decision = self.movement_governor.decide(
            proposed_left=proposed.left,
            proposed_top=proposed.top,
            current_left=current.left,
            current_top=current.top,
            cursor_x=cursor.x,
            cursor_y=cursor.y,
            offset_x=self._drag_offset_x,
            offset_y=self._drag_offset_y,
            now=time.perf_counter(),
        )
        if self._diagnostic_dragging:
            self._diagnostic_pointer_lag.append(decision.pointer_lag_px)
            self._diagnostic_governed_lag.append(decision.governed_lag_px)
        width = proposed.right - proposed.left
        height = proposed.bottom - proposed.top
        proposed.left = decision.left
        proposed.top = decision.top
        proposed.right = decision.left + width
        proposed.bottom = decision.top + height
        discarded = self._discard_superseded_mouse_moves()
        if self._diagnostic_dragging:
            self._diagnostic_discarded_moves += discarded

    def _watch_physical_button(self) -> None:
        if not self._mouse_drag_active:
            return
        if user32.GetAsyncKeyState(VK_LBUTTON) & 0x8000:
            return
        self._mouse_drag_active = False
        if self._diagnostic_dragging and not self._diagnostic_release_at:
            self._diagnostic_release_at = time.perf_counter()
        user32.ReleaseCapture()
        user32.SendMessageW(self.hwnd, WM_CANCELMODE, 0, 0)

    def _finish_movement_diagnostic(self) -> None:
        if not self._diagnostic_active or not self._diagnostic_dragging:
            return
        self._diagnostic_dragging = False
        self._diagnostic_active = False
        user32.KillTimer(self.hwnd, DIAGNOSTIC_TIMER)
        ended_at = time.perf_counter()
        if self._diagnostic_release_at:
            self._diagnostic_settle_ms = max(
                0.0, (ended_at - self._diagnostic_release_at) * 1000.0)
        wall = max(ended_at - self._diagnostic_wall_start, 0.001)
        cpu = max(time.process_time() - self._diagnostic_cpu_start, 0.0)
        cpu_percent = 100.0 * cpu / wall
        timer_median, timer_p95, timer_max = self._interval_summary(
            self._diagnostic_timer_times)
        move_median, move_p95, move_max = self._interval_summary(
            self._diagnostic_move_times)
        if self._diagnostic_pointer_lag:
            ordered_lag = sorted(self._diagnostic_pointer_lag)
            lag_median = statistics.median(ordered_lag)
            lag_p95 = ordered_lag[
                min(len(ordered_lag) - 1, int(len(ordered_lag) * 0.95))]
            lag_max = max(ordered_lag)
        else:
            lag_median = lag_p95 = lag_max = 0.0
        if self._diagnostic_governed_lag:
            ordered_governed_lag = sorted(self._diagnostic_governed_lag)
            governed_lag_median = statistics.median(ordered_governed_lag)
            governed_lag_p95 = ordered_governed_lag[
                min(len(ordered_governed_lag) - 1,
                    int(len(ordered_governed_lag) * 0.95))]
            governed_lag_max = max(ordered_governed_lag)
        else:
            governed_lag_median = governed_lag_p95 = governed_lag_max = 0.0

        if len(self._diagnostic_timer_times) < 2:
            timer_median = timer_p95 = timer_max = wall * 1000.0
        if len(self._diagnostic_move_times) < 2:
            move_median = move_p95 = move_max = wall * 1000.0
        paint_rate = self._diagnostic_paints / wall
        movement_rate = len(self._diagnostic_move_times) / wall
        committed_rate = self.movement_governor.committed / wall
        oversubscription = movement_rate / max(self.refresh_hz, 1)

        if len(self._diagnostic_move_times) < 3:
            finding = ("Too few movement samples were received. Run the test again and move "
                       "the blank window continuously for at least five seconds.")
        elif ((lag_p95 >= 24.0 or lag_max >= 120.0) and
              oversubscription > 1.2):
            finding = ("Confirmed unbounded modal-drag input: Windows generated stale movement "
                       f"commands at {oversubscription:.1f} times the display refresh budget. "
                       "The shared governor must sample live input at display rate and cancel "
                       "the modal move on physical button release.")
        elif move_p95 >= 80.0 and timer_p95 >= 80.0:
            finding = ("Windows delivered movement and timer messages late while the Node "
                       "interface was blank. The likely bottleneck is Windows DWM, the display "
                       "driver, capture software, or system-wide load—not Node networking.")
        elif move_p95 >= 80.0:
            finding = ("The interface timer stayed responsive while Windows supplied movement "
                       "updates slowly. This points to desktop composition, the display driver, "
                       "or Windows pointer/window-drag handling.")
        elif timer_p95 >= 80.0:
            finding = ("Movement was regular, but the application message loop was delayed. "
                       "The next target is a blocking call on the UI thread.")
        elif cpu_percent >= 50.0 and paint_rate >= 100.0:
            finding = ("The message loop remained responsive, but high-rate movement caused a "
                       "paint storm that consumed most of one CPU core. Preserve the rendered "
                       "window during dragging and repaint once after release.")
        else:
            finding = ("The blank native window moved responsively. The slowdown comes from "
                       "painting or composing the full set of interface controls.")

        report = "\r\n".join((
            "GUIDE NODE MOVEMENT DIAGNOSTIC",
            f"Finding: {finding}",
            "",
            f"Test duration: {wall:.2f} seconds",
            f"Process CPU during drag: {cpu_percent:.1f}% of one CPU core",
            f"Movement messages: {len(self._diagnostic_move_times)}",
            f"Movement messages per second: {movement_rate:.1f}",
            f"Superseded mouse positions discarded: "
            f"{self._diagnostic_discarded_moves}",
            f"Display refresh budget: {self.refresh_hz} positions per second",
            f"Committed visual positions per second: {committed_rate:.1f}",
            f"Movement oversubscription ratio: {oversubscription:.1f}x",
            f"Display-rate positions committed / suppressed: "
            f"{self.movement_governor.committed} / "
            f"{self.movement_governor.suppressed}",
            f"Movement interval ms (median / p95 / max): "
            f"{move_median:.1f} / {move_p95:.1f} / {move_max:.1f}",
            f"Incoming command staleness px (median / p95 / max): "
            f"{lag_median:.1f} / {lag_p95:.1f} / {lag_max:.1f}",
            f"Governed window-target lag px (median / p95 / max): "
            f"{governed_lag_median:.1f} / {governed_lag_p95:.1f} / "
            f"{governed_lag_max:.1f}",
            f"UI timer interval ms (median / p95 / max): "
            f"{timer_median:.1f} / {timer_p95:.1f} / {timer_max:.1f}",
            f"Paint messages during blank drag: {self._diagnostic_paints}",
            f"Paint messages per second: {paint_rate:.1f}",
            f"Physical-release to modal-end delay: "
            f"{self._diagnostic_settle_ms:.1f} ms",
            f"DPI: {self.dpi} ({self.scale * 100:.0f}%); per-monitor aware: "
            f"{'yes' if _dpi_aware else 'fallback/unknown'}",
            f"DWM composition enabled: {self._dwm_enabled()}",
            f"Remote Windows session: {'yes' if user32.GetSystemMetrics(0x1000) else 'no'}",
        ))
        try:
            destination = self._save_diagnostic(report)
            report += f"\r\n\r\nSaved to: {destination}"
        except OSError as error:
            report += f"\r\n\r\nCould not save report: {error}"

        for handle in self.child_controls:
            user32.ShowWindow(handle, SW_SHOW)
        user32.SetWindowTextW(
            self.hwnd, f"Guide Desktop Node — diagnostic build ({self.dpi} DPI)")
        self._apply_snapshot()
        self._message(report)

    def _command(self, control_id: int) -> None:
        try:
            if control_id == ID_AT_FIELD:
                modes = ("closed", "familiar", "open")
                selection = user32.SendMessageW(self.controls["at_field"], 0x0147, 0, 0)
                if 0 <= selection < len(modes):
                    try:
                        mode = modes[selection]
                        if mode != self.state.at_field.mode.value:
                            preview = self.state.preview_at_field(mode) + "\n\nApply this setting?"
                            if user32.MessageBoxW(self.hwnd, preview, "AT Field", 0x0004 | 0x0020) == 6:
                                self.state.set_at_field(mode)
                    finally:
                        user32.SendMessageW(self.controls["at_field"], 0x014E,
                                            modes.index(self.state.at_field.mode.value), 0)
            elif control_id == ID_NEW_CODE:
                self.state.rotate_pairing_code()
            elif control_id == ID_NODE_TOGGLE:
                if self.runtime.running:
                    self.runtime.stop()
                else:
                    self.runtime.start()
            elif control_id == ID_MEDIA_CHOOSE:
                selected = self._choose_folder()
                if selected:
                    self.state.media.add_folder(selected)
                    self.state.prepare_media()
            elif control_id == ID_MEDIA_REMOVE:
                index = self._selected(self.controls["media_folders"])
                if index < 0:
                    raise ValueError("Select a media folder to remove")
                self.state.media.remove_folder(index)
                self.state.prepare_media()
            elif control_id == ID_MEDIA_RESCAN:
                self.state.media.scan()
                self.state.prepare_media()
            elif control_id == ID_MEDIA_CLEAR:
                self.state.media.set_folders(())
                self.state.prepare_media()
            elif control_id == ID_APP_ADD:
                selected = self._choose_application()
                if selected:
                    self.state.applications.add(Path(selected))
            elif control_id == ID_APP_REMOVE:
                index = self._selected(self.controls["applications"])
                profiles = self.state.applications.profiles()
                if index >= 0 and index < len(profiles):
                    if not self.state.applications.remove(str(profiles[index]["id"])):
                        self._message("Close its pending or active session first.")
            elif control_id in (ID_APP_APPROVE, ID_APP_DENY):
                pending = self.state.applications.pending()
                if pending:
                    result = self.state.applications.decide(
                        str(pending[0]["id"]), control_id == ID_APP_APPROVE)
                    if result and control_id == ID_APP_APPROVE and result["state"] != "active":
                        self._message(str(result.get("reason", "Could not start")), True)
            elif control_id == ID_TRUST_ARM:
                checked = user32.SendMessageW(self.controls["trust_arm"], BM_GETCHECK, 0, 0)
                self.state.arm_trust(checked == BST_CHECKED)
            elif control_id == ID_TRUST_REVOKE:
                index = self._selected(self.controls["trusted"])
                trusted = self.state.trusted_decks()
                if index >= 0 and index < len(trusted):
                    self.state.revoke_trust(trusted[index][0])
            elif control_id == ID_SE_TOGGLE:
                checked = user32.SendMessageW(
                    self.controls["semiotic_toggle"], BM_GETCHECK, 0, 0)
                self.state.set_semiotic_enabled(checked == BST_CHECKED)
            elif control_id == ID_DIAGNOSE_MOVEMENT:
                self._start_movement_diagnostic()
            elif control_id == ID_DECK_DIAGNOSTIC:
                self._start_deck_diagnostics()
            elif control_id == ID_DECK_DIAGNOSTIC_CANCEL:
                if self._deck_runner:
                    self._deck_runner.cancel()
            with self._snapshot_lock:
                self._snapshot = self._status_snapshot()
            self._apply_snapshot()
        except (OSError, ValueError) as error:
            self._message(str(error), True)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._stop.set()
        self.runtime.stop()
        self.state.close()

    def window_procedure(self, hwnd: int, message: int, wparam: int, lparam: int) -> int:
        if message == WM_CREATE:
            self.hwnd = hwnd
            self._create_controls()
            return 0
        if message == WM_APP_STATUS:
            self._apply_snapshot()
            return 0
        if message == WM_TIMER and int(wparam) == DIAGNOSTIC_TIMER:
            if self._diagnostic_dragging:
                self._diagnostic_timer_times.append(time.perf_counter())
            return 0
        if message == WM_TIMER and int(wparam) == MOVE_WATCHDOG_TIMER:
            self._watch_physical_button()
            return 0
        if message == WM_ENTERSIZEMOVE:
            self._capture_drag_anchor()
            if self._diagnostic_active:
                self._begin_diagnostic_drag()
            else:
                self._start_optimized_move()
            return 0
        if message == WM_MOVING:
            if self._diagnostic_dragging:
                self._diagnostic_move_times.append(time.perf_counter())
            self._follow_live_pointer(int(lparam))
            return 1
        if message == WM_EXITSIZEMOVE:
            user32.KillTimer(self.hwnd, MOVE_WATCHDOG_TIMER)
            self._mouse_drag_active = False
            if self._diagnostic_active:
                self._finish_movement_diagnostic()
            else:
                self._finish_optimized_move()
            return 0
        if message == WM_PAINT and self._diagnostic_dragging:
            self._diagnostic_paints += 1
        elif message == WM_PAINT and self._moving_optimized:
            self._paint_movement_placeholder()
            return 0
        if message == WM_COMMAND:
            control_id = int(wparam) & 0xFFFF
            # Combo boxes emit several notifications; act only on selection change.
            if control_id != ID_AT_FIELD or (int(wparam) >> 16) & 0xFFFF == 1:
                self._command(control_id)
            return 0
        if message == WM_CLOSE:
            user32.DestroyWindow(hwnd)
            return 0
        if message == WM_DESTROY:
            self.close()
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, message, wparam, lparam)

    def run(self) -> None:
        global _window
        _window = self
        instance = kernel32.GetModuleHandleW(None)
        class_name = "GuideDesktopNodeNative0"
        window_class = WNDCLASSW()
        window_class.lpfnWndProc = _window_procedure
        window_class.hInstance = instance
        window_class.hCursor = user32.LoadCursorW(None, ctypes.c_void_p(IDC_ARROW))
        window_class.hbrBackground = user32.GetSysColorBrush(COLOR_BTNFACE)
        window_class.lpszClassName = class_name
        if not user32.RegisterClassW(ctypes.byref(window_class)):
            error = ctypes.get_last_error()
            if error != 1410:  # class already exists
                raise ctypes.WinError(error)
        hwnd = user32.CreateWindowExW(
            0, class_name, f"Guide Desktop Node — diagnostic build ({self.dpi} DPI)",
            WS_OVERLAPPEDWINDOW, CW_USEDEFAULT, CW_USEDEFAULT,
            self._px(700), self._px(880), None, None, instance, None,
        )
        if not hwnd:
            raise ctypes.WinError(ctypes.get_last_error())
        self.hwnd = hwnd
        try:
            self.runtime.start()
        except OSError as error:
            self._message(f"The Node could not start.\n\n{error}", True)
        self._worker = threading.Thread(
            target=self._refresh_worker, name="guide-node-native-status", daemon=True)
        self._worker.start()
        self._start_deck_discovery()
        user32.ShowWindow(hwnd, SW_SHOW)
        user32.UpdateWindow(hwnd)
        message = MSG()
        while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(message))
            user32.DispatchMessageW(ctypes.byref(message))
        self.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the native Guide desktop Node")
    parser.add_argument("--port", type=int, default=DEFAULT_HTTP_PORT)
    parser.add_argument("--discovery-port", type=int, default=DEFAULT_DISCOVERY_PORT)
    parser.add_argument("--media-folder", default="")
    parser.add_argument("--config", type=Path, default=None,
                        help="Use a separate settings file, for isolated testing or another Node profile")
    parser.add_argument("--deck-address", default="", help="Single Deck IPv4 address for diagnostics")
    parser.add_argument("--semiotic-engine", action="store_true", default=None,
                        help="Explicitly offer the separately installed local Semiotic Engine")
    arguments = parser.parse_args()
    NativeGuideNodeWindow(arguments.port, arguments.discovery_port,
                          arguments.media_folder, arguments.semiotic_engine,
                          arguments.config, arguments.deck_address).run()


if __name__ == "__main__":
    main()
