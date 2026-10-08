"""Responsive native Windows control panel for the independent Semiotic Engine."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import sys
import threading
import time

from guide_se_controller import EngineController, human_size

GUIDEOS_ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]
NODE_DESKTOP = GUIDEOS_ROOT / "node" / "desktop"
if str(NODE_DESKTOP) not in sys.path:
    sys.path.insert(0, str(NODE_DESKTOP))
from windows_ui_performance import MovementGovernor

if not hasattr(ctypes, "WINFUNCTYPE"):
    raise RuntimeError("The native Semiotic Engine panel requires Windows")

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
try:
    user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
except (AttributeError, OSError):
    pass

LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT,
                            wintypes.WPARAM, wintypes.LPARAM)


class WNDCLASSW(ctypes.Structure):
    _fields_ = [("style", wintypes.UINT), ("lpfnWndProc", WNDPROC),
                ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
                ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HICON),
                ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HBRUSH),
                ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR)]


class MSG(ctypes.Structure):
    _fields_ = [("hwnd", wintypes.HWND), ("message", wintypes.UINT),
                ("wParam", wintypes.WPARAM), ("lParam", wintypes.LPARAM),
                ("time", wintypes.DWORD), ("pt", wintypes.POINT),
                ("lPrivate", wintypes.DWORD)]


WS_OVERLAPPEDWINDOW = 0x00CF0000
WS_VISIBLE, WS_CHILD = 0x10000000, 0x40000000
CW_USEDEFAULT = -2147483648
WM_CREATE, WM_DESTROY, WM_CLOSE = 1, 2, 0x10
WM_COMMAND, WM_TIMER, WM_SETFONT = 0x111, 0x113, 0x30
WM_MOUSEMOVE, WM_NCMOUSEMOVE = 0x200, 0xA0
WM_MOVING, WM_ENTERSIZEMOVE, WM_EXITSIZEMOVE = 0x216, 0x231, 0x232
WM_CANCELMODE, WM_APP_STATUS = 0x1F, 0x8001
PM_REMOVE, VK_LBUTTON = 1, 1
SW_HIDE, SW_SHOW = 0, 5
COLOR_BTNFACE, IDC_ARROW, DEFAULT_GUI_FONT = 15, 32512, 17
ID_START, ID_STOP, ID_CANCEL, ID_MOVE_TEST = 101, 102, 103, 104
STATUS_TIMER, MOVE_WATCHDOG_TIMER = 1, 2
MB_OK, MB_ICONINFORMATION, MB_ICONERROR = 0, 0x40, 0x10

user32.CreateWindowExW.restype = wintypes.HWND
user32.CreateWindowExW.argtypes = [
    wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wintypes.HWND, wintypes.HANDLE, wintypes.HINSTANCE, wintypes.LPVOID]
user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT,
                                  wintypes.WPARAM, wintypes.LPARAM]
user32.DefWindowProcW.restype = LRESULT
user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT,
                                wintypes.WPARAM, wintypes.LPARAM]
user32.SetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPCWSTR]
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.EnableWindow.argtypes = [wintypes.HWND, wintypes.BOOL]
user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.SetTimer.argtypes = [wintypes.HWND, wintypes.WPARAM, wintypes.UINT,
                            wintypes.LPVOID]
user32.KillTimer.argtypes = [wintypes.HWND, wintypes.WPARAM]
user32.PeekMessageW.argtypes = [ctypes.POINTER(MSG), wintypes.HWND,
                                wintypes.UINT, wintypes.UINT, wintypes.UINT]
user32.GetMessageW.argtypes = [ctypes.POINTER(MSG), wintypes.HWND,
                               wintypes.UINT, wintypes.UINT]
user32.GetMessageW.restype = wintypes.BOOL
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = ctypes.c_short
user32.LoadCursorW.argtypes = [wintypes.HINSTANCE, wintypes.HANDLE]
user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
user32.GetSysColorBrush.argtypes = [ctypes.c_int]
kernel32.GetModuleHandleW.restype = wintypes.HINSTANCE
gdi32.GetStockObject.restype = wintypes.HANDLE

_window: "SemioticEngineWindow | None" = None


@WNDPROC
def window_procedure(hwnd: int, message: int, wparam: int, lparam: int) -> int:
    if _window is not None:
        return _window.handle(hwnd, message, wparam, lparam)
    return user32.DefWindowProcW(hwnd, message, wparam, lparam)


class SemioticEngineWindow:
    def __init__(self) -> None:
        self.controller = EngineController()
        self.hwnd = 0
        self.controls: dict[str, int] = {}
        self.children: list[int] = []
        self.closed = False
        self.dpi = int(getattr(user32, "GetDpiForSystem", lambda: 96)()) or 96
        self.scale = self.dpi / 96.0
        self.governor = MovementGovernor(60)
        self.offset_x = self.offset_y = 0
        self.drag_active = False
        self.moving = False
        self.movement_test = False
        self.test_started = 0.0
        self.test_moves = self.test_discarded = 0
        self.test_max_stale = 0.0
        self._last: dict[str, str] = {}

    def px(self, value: int) -> int:
        return round(value * self.scale)

    def control(self, kind: str, text: str, x: int, y: int, width: int,
                height: int, identity: int = 0) -> int:
        handle = user32.CreateWindowExW(
            0, kind, text, WS_CHILD | WS_VISIBLE, self.px(x), self.px(y),
            self.px(width), self.px(height), self.hwnd,
            ctypes.c_void_p(identity), kernel32.GetModuleHandleW(None), None)
        user32.SendMessageW(handle, WM_SETFONT,
                            gdi32.GetStockObject(DEFAULT_GUI_FONT), 1)
        self.children.append(handle)
        return handle

    def create_controls(self) -> None:
        self.control("STATIC", "SEMIOTIC ENGINE", 26, 22, 500, 28)
        self.control("STATIC", "Optional local interpretation for Guide technology.",
                     26, 52, 560, 22)
        self.controls["state"] = self.control("STATIC", "Stopped", 26, 92, 570, 25)
        self.controls["detail"] = self.control("STATIC", "", 26, 120, 570, 42)
        self.control("STATIC", "LOCAL MODEL", 26, 178, 180, 20)
        self.controls["model"] = self.control("STATIC", "", 26, 202, 570, 38)
        self.control("STATIC", "CURRENT WORK", 26, 258, 180, 20)
        self.controls["jobs"] = self.control("STATIC", "No work in progress.", 26, 282, 570, 24)
        self.control("STATIC", "BOUNDARIES", 26, 326, 180, 20)
        self.control("STATIC", "No file access · no network access · no tools or device control\n"
                     "Request text is discarded after completion; status records expire after 15 minutes.",
                     26, 350, 580, 45)
        self.controls["memory"] = self.control("STATIC", "", 26, 410, 570, 24)
        self.controls["start"] = self.control("BUTTON", "Start Engine", 26, 454, 125, 32, ID_START)
        self.controls["stop"] = self.control("BUTTON", "Stop Engine", 162, 454, 125, 32, ID_STOP)
        self.controls["cancel"] = self.control("BUTTON", "Cancel current work", 298, 454, 145, 32, ID_CANCEL)
        self.control("BUTTON", "Movement check", 454, 454, 130, 32, ID_MOVE_TEST)
        self.control("STATIC", "The Node has its own persistent permission switch. Starting this Engine does not grant it access.",
                     26, 510, 570, 40)
        user32.SetTimer(self.hwnd, STATUS_TIMER, 500, None)
        self.refresh()

    def set_text(self, name: str, value: str) -> None:
        if self._last.get(name) != value:
            user32.SetWindowTextW(self.controls[name], value)
            self._last[name] = value

    def refresh(self) -> None:
        if self.moving or self.movement_test:
            return
        status = self.controller.status()
        state = str(status["state"])
        names = {"stopped": "Stopped", "starting": "Starting…", "ready": "Ready",
                 "stopping": "Stopping…", "failed": "Needs attention"}
        self.set_text("state", names.get(state, state.title()))
        self.set_text("detail", str(status["detail"]))
        model_state = "found" if status["model_found"] else "missing"
        runtime_state = "found" if status["runtime_found"] else "missing"
        self.set_text("model", f"{status['model']} ({human_size(int(status['model_bytes']))}; {model_state})\n"
                      f"Local llama.cpp runtime: {runtime_state}")
        jobs = status.get("jobs", {})
        active = int(jobs.get("queued", 0)) + int(jobs.get("running", 0)) if isinstance(jobs, dict) else 0
        completed = int(jobs.get("complete", 0)) if isinstance(jobs, dict) else 0
        self.set_text("jobs", f"{active} active · {completed} recently completed" if jobs else
                      "No work in progress.")
        backend = status.get("backend", {})
        memory = int(backend.get("working_set_bytes", 0)) if isinstance(backend, dict) else 0
        self.set_text("memory", f"Approximate model process memory: {human_size(memory)}" if memory else
                      "Model process memory: released")
        user32.EnableWindow(self.controls["start"], state in {"stopped", "failed"})
        user32.EnableWindow(self.controls["stop"], state in {"starting", "ready"})
        user32.EnableWindow(self.controls["cancel"], active > 0)

    def begin_move(self) -> None:
        point, rect = wintypes.POINT(), wintypes.RECT()
        if user32.GetCursorPos(ctypes.byref(point)) and user32.GetWindowRect(self.hwnd, ctypes.byref(rect)):
            self.offset_x, self.offset_y = point.x - rect.left, point.y - rect.top
        self.governor.begin(time.perf_counter())
        self.drag_active = bool(user32.GetAsyncKeyState(VK_LBUTTON) & 0x8000)
        self.moving = True
        for child in self.children:
            user32.ShowWindow(child, SW_HIDE)
        if self.drag_active:
            user32.SetTimer(self.hwnd, MOVE_WATCHDOG_TIMER, 8, None)

    @staticmethod
    def discard_moves() -> int:
        discarded, message = 0, MSG()
        for kind in (WM_MOUSEMOVE, WM_NCMOUSEMOVE):
            while discarded < 4096 and user32.PeekMessageW(
                    ctypes.byref(message), None, kind, kind, PM_REMOVE):
                discarded += 1
        return discarded

    def follow_pointer(self, address: int) -> None:
        if not address:
            return
        proposed = ctypes.cast(address, ctypes.POINTER(wintypes.RECT)).contents
        point, current = wintypes.POINT(), wintypes.RECT()
        if not user32.GetCursorPos(ctypes.byref(point)) or not user32.GetWindowRect(self.hwnd, ctypes.byref(current)):
            return
        decision = self.governor.decide(
            proposed_left=proposed.left, proposed_top=proposed.top,
            current_left=current.left, current_top=current.top,
            cursor_x=point.x, cursor_y=point.y, offset_x=self.offset_x,
            offset_y=self.offset_y, now=time.perf_counter())
        width, height = proposed.right - proposed.left, proposed.bottom - proposed.top
        proposed.left, proposed.top = decision.left, decision.top
        proposed.right, proposed.bottom = decision.left + width, decision.top + height
        discarded = self.discard_moves()
        if self.movement_test:
            self.test_moves += 1
            self.test_discarded += discarded
            self.test_max_stale = max(self.test_max_stale, decision.pointer_lag_px)

    def watch_release(self) -> None:
        if self.drag_active and not user32.GetAsyncKeyState(VK_LBUTTON) & 0x8000:
            self.drag_active = False
            user32.ReleaseCapture()
            user32.SendMessageW(self.hwnd, WM_CANCELMODE, 0, 0)

    def finish_move(self) -> None:
        user32.KillTimer(self.hwnd, MOVE_WATCHDOG_TIMER)
        self.moving = False
        for child in self.children:
            user32.ShowWindow(child, SW_SHOW)
        if self.movement_test:
            elapsed = max(time.perf_counter() - self.test_started, 0.001)
            result = ("Movement protection is active.\n\n"
                      f"Test time: {elapsed:.1f} seconds\n"
                      f"Incoming positions sampled: {self.test_moves}\n"
                      f"Superseded positions discarded: {self.test_discarded}\n"
                      f"Display-rate commits: {self.governor.committed}\n"
                      f"Largest stale-input distance: {self.test_max_stale:.0f} pixels")
            self.movement_test = False
            user32.MessageBoxW(self.hwnd, result, "Semiotic Engine movement check",
                               MB_OK | MB_ICONINFORMATION)
        self.refresh()

    def command(self, identity: int) -> None:
        if identity == ID_START:
            self.controller.start()
        elif identity == ID_STOP:
            self.controller.stop()
        elif identity == ID_CANCEL:
            self.controller.cancel_current()
        elif identity == ID_MOVE_TEST:
            self.movement_test = True
            self.test_started = time.perf_counter()
            self.test_moves = self.test_discarded = 0
            self.test_max_stale = 0.0
            user32.MessageBoxW(self.hwnd, "After closing this message, drag the Engine window continuously for at least five seconds, then release it.",
                               "Movement check", MB_OK | MB_ICONINFORMATION)
        self.refresh()

    def handle(self, hwnd: int, message: int, wparam: int, lparam: int) -> int:
        if message == WM_CREATE:
            self.hwnd = hwnd
            self.create_controls()
            return 0
        if message == WM_TIMER:
            if int(wparam) == STATUS_TIMER:
                self.refresh()
            elif int(wparam) == MOVE_WATCHDOG_TIMER:
                self.watch_release()
            return 0
        if message == WM_ENTERSIZEMOVE:
            self.begin_move()
            return 0
        if message == WM_MOVING:
            self.follow_pointer(int(lparam))
            return 1
        if message == WM_EXITSIZEMOVE:
            self.finish_move()
            return 0
        if message == WM_COMMAND:
            self.command(int(wparam) & 0xFFFF)
            return 0
        if message == WM_CLOSE:
            user32.DestroyWindow(hwnd)
            return 0
        if message == WM_DESTROY:
            self.closed = True
            self.controller.close()
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, message, wparam, lparam)

    def run(self) -> None:
        global _window
        _window = self
        instance = kernel32.GetModuleHandleW(None)
        class_name = "GuideSemioticEngineNative0"
        window_class = WNDCLASSW()
        window_class.lpfnWndProc = window_procedure
        window_class.hInstance = instance
        window_class.hCursor = user32.LoadCursorW(None, ctypes.c_void_p(IDC_ARROW))
        window_class.hbrBackground = user32.GetSysColorBrush(COLOR_BTNFACE)
        window_class.lpszClassName = class_name
        if not user32.RegisterClassW(ctypes.byref(window_class)):
            error = ctypes.get_last_error()
            if error != 1410:
                raise ctypes.WinError(error)
        self.hwnd = user32.CreateWindowExW(
            0, class_name, "Guide Semiotic Engine", WS_OVERLAPPEDWINDOW,
            CW_USEDEFAULT, CW_USEDEFAULT, self.px(650), self.px(610),
            None, None, instance, None)
        if not self.hwnd:
            raise ctypes.WinError(ctypes.get_last_error())
        user32.ShowWindow(self.hwnd, SW_SHOW)
        user32.UpdateWindow(self.hwnd)
        message = MSG()
        while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(message))
            user32.DispatchMessageW(ctypes.byref(message))


if __name__ == "__main__":
    SemioticEngineWindow().run()
