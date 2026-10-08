"""Owner-facing lifecycle control for the independent Semiotic Engine."""

from __future__ import annotations

from pathlib import Path
import sys
import threading
from typing import Callable

from guide_se_core import BackendProblem, EngineBackend, JobManager
from guide_se_service import DEFAULT_PORT, EngineServer, default_connection_path, load_or_create_connection
from llama_cpp_backend import LlamaCppBackend


_SOURCE_ROOT = Path(__file__).resolve().parent
_EXECUTABLE_ROOT = (Path(sys.executable).resolve().parent
                    if getattr(sys, "frozen", False) else _SOURCE_ROOT)
ENGINE_ROOT = (_EXECUTABLE_ROOT if (_EXECUTABLE_ROOT / "runtime").is_dir()
               else _EXECUTABLE_ROOT.parent
               if (_EXECUTABLE_ROOT.parent / "runtime").is_dir()
               else _SOURCE_ROOT)
DEFAULT_RUNTIME = ENGINE_ROOT / "runtime" / "llama-b10516-vulkan" / "llama-server.exe"
DEFAULT_MODEL = ENGINE_ROOT / "models" / "Qwen3-8B-Q4_K_M.gguf"


class EngineController:
    """Start and stop the model service while keeping the GUI responsive."""

    def __init__(self, *, port: int = DEFAULT_PORT,
                 runtime: Path = DEFAULT_RUNTIME, model: Path = DEFAULT_MODEL,
                 backend_factory: Callable[[Path, Path], EngineBackend] | None = None) -> None:
        self.port = port
        self.runtime = Path(runtime)
        self.model = Path(model)
        self.backend_factory = backend_factory or (
            lambda executable, model: LlamaCppBackend(executable, model))
        self._lock = threading.RLock()
        self._state = "stopped"
        self._detail = "Ready to start."
        self._manager: JobManager | None = None
        self._server: EngineServer | None = None
        self._service_thread: threading.Thread | None = None
        self._operation_thread: threading.Thread | None = None
        self._stop_requested = threading.Event()

    def prerequisites(self) -> dict[str, object]:
        return {
            "runtime_found": self.runtime.is_file(),
            "model_found": self.model.is_file(),
            "runtime": self.runtime.name,
            "model": self.model.name,
            "model_bytes": self.model.stat().st_size if self.model.is_file() else 0,
        }

    def status(self) -> dict[str, object]:
        with self._lock:
            value: dict[str, object] = {
                "state": self._state,
                "detail": self._detail,
                **self.prerequisites(),
            }
            if self._manager is not None:
                value.update(self._manager.status())
            return value

    def start(self) -> bool:
        with self._lock:
            if self._state not in {"stopped", "failed"}:
                return False
            prerequisites = self.prerequisites()
            if not prerequisites["runtime_found"] or not prerequisites["model_found"]:
                self._state = "failed"
                self._detail = "The local runtime or model file is missing."
                return False
            self._state = "starting"
            self._detail = "Loading the local model. This can take a little while."
            self._stop_requested.clear()
            self._operation_thread = threading.Thread(
                target=self._start_worker, name="guide-se-start", daemon=True)
            self._operation_thread.start()
            return True

    def _start_worker(self) -> None:
        manager: JobManager | None = None
        server: EngineServer | None = None
        try:
            backend = self.backend_factory(self.runtime, self.model)
            if self._stop_requested.is_set():
                backend.close()
                with self._lock:
                    self._state = "stopped"
                    self._detail = "Stopped. Model memory has been released."
                return
            manager = JobManager(backend)
            connection = load_or_create_connection(default_connection_path(), self.port)
            server = EngineServer(("127.0.0.1", self.port), manager,
                                  str(connection["token"]))
            service_thread = threading.Thread(
                target=server.serve_forever, name="guide-se-http", daemon=True)
            service_thread.start()
            with self._lock:
                self._manager = manager
                self._server = server
                self._service_thread = service_thread
                self._state = "ready"
                self._detail = "Ready for bounded local requests."
        except (BackendProblem, OSError, ValueError) as error:
            if server is not None:
                server.server_close()
            if manager is not None:
                manager.close()
            with self._lock:
                self._state = "failed"
                self._detail = str(error)[:240]

    def cancel_current(self) -> bool:
        with self._lock:
            manager = self._manager
        if manager is None:
            return False
        return manager.cancel_active() > 0

    def stop(self) -> bool:
        with self._lock:
            if self._state in {"stopped", "stopping"}:
                return False
            if self._state == "starting":
                self._stop_requested.set()
                self._state = "stopping"
                self._detail = "Stopping as soon as model loading can be released."
                return True
            self._state = "stopping"
            self._detail = "Stopping local work and releasing model memory."
            self._operation_thread = threading.Thread(
                target=self._stop_worker, name="guide-se-stop", daemon=True)
            self._operation_thread.start()
            return True

    def _stop_worker(self) -> None:
        with self._lock:
            server, manager, thread = self._server, self._manager, self._service_thread
        if server is not None:
            server.shutdown()
            server.server_close()
        if manager is not None:
            manager.close()
        if thread is not None:
            thread.join(timeout=2)
        with self._lock:
            self._server = None
            self._manager = None
            self._service_thread = None
            self._state = "stopped"
            self._detail = "Stopped. Model memory has been released."

    def close(self, timeout: float = 8.0) -> None:
        with self._lock:
            state = self._state
        if state not in {"stopped", "stopping"}:
            self.stop()
        thread = self._operation_thread
        if thread is not None:
            thread.join(timeout=timeout)


def human_size(value: int) -> str:
    size = float(max(0, value))
    for unit in ("bytes", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}" if unit != "bytes" else f"{int(size)} bytes"
        size /= 1024
    return "0 bytes"
