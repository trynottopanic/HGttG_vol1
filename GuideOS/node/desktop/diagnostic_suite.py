"""Asynchronous, fixed-operation Deck diagnostic suite for Desktop NDI."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
import subprocess
import threading
import time
from typing import Callable


@dataclass(frozen=True)
class SuiteStep:
    command_id: str
    action: str
    timeout_seconds: float = 45.0


DEFAULT_STEPS: tuple[SuiteStep, ...] = (
    SuiteStep("deck.health.initial", "Health"),
    SuiteStep("deck.report", "Report"),
    SuiteStep("deck.inspect", "Inspect"),
    SuiteStep("deck.audio_path", "Audio-Path"),
    SuiteStep("deck.health.final", "Health"),
    SuiteStep("deck.full_capture", "Capture", timeout_seconds=240.0),
)


@dataclass(frozen=True)
class StepResult:
    command_id: str
    action: str
    outcome: str
    started_at: float
    ended_at: float
    detail: str = ""


class DiagnosticSuiteRunner:
    """Runs only the fixed Guide-Link diagnostic sequence; never accepts shell input."""

    def __init__(self, guide_link_script: Path, deck_address: str,
                 steps: tuple[SuiteStep, ...] = DEFAULT_STEPS,
                 powershell: str = "powershell.exe") -> None:
        if not deck_address or any(ch in deck_address for ch in ";&|`$()<>\"'"):
            raise ValueError("invalid Deck address")
        self.guide_link_script = Path(guide_link_script)
        self.deck_address = deck_address
        self.steps = tuple(steps)
        self.powershell = powershell
        self._cancel = threading.Event()
        self._process: subprocess.Popen[str] | None = None

    def cancel(self) -> None:
        self._cancel.set()
        process = self._process
        if process and process.poll() is None:
            process.terminate()

    def run(self, on_step: Callable[[StepResult], None] | None = None) -> list[StepResult]:
        results: list[StepResult] = []
        for step in self.steps:
            if self._cancel.is_set():
                results.append(self._result(step, "cancelled", "cancelled before start"))
                continue
            started = time.time()
            outcome, detail = self._run_step(step)
            result = StepResult(step.command_id, step.action, outcome, started, time.time(), detail)
            results.append(result)
            if on_step:
                on_step(result)
        return results

    def _run_step(self, step: SuiteStep) -> tuple[str, str]:
        command = [self.powershell, "-NoProfile", "-ExecutionPolicy", "Bypass",
                   "-File", str(self.guide_link_script),
                   "-DeckAddress", self.deck_address, "-Action", step.action]
        try:
            self._process = subprocess.Popen(command, stdout=subprocess.PIPE,
                                             stderr=subprocess.STDOUT, text=True,
                                             encoding="utf-8", errors="replace",
                                             creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            output, _ = self._process.communicate(timeout=step.timeout_seconds)
            return_code = self._process.returncode
        except subprocess.TimeoutExpired:
            self._process.kill()
            self._process.communicate()
            return "timed_out", "Guide-Link operation exceeded its deadline"
        except OSError as error:
            return "unavailable", str(error)[:240]
        finally:
            self._process = None
        if self._cancel.is_set():
            return "cancelled", "cancelled by owner"
        if return_code != 0:
            return "failed", (output or "Guide-Link operation failed")[-1000:].strip()
        # Popen is cleared above, so retain only bounded output for diagnostics.
        return ("passed", output[-1000:].strip()) if output is not None else ("passed", "")

    @staticmethod
    def _result(step: SuiteStep, outcome: str, detail: str) -> StepResult:
        now = time.time()
        return StepResult(step.command_id, step.action, outcome, now, now, detail)

    @staticmethod
    def bundle(results: list[StepResult]) -> list[dict[str, object]]:
        return [asdict(result) for result in results]
