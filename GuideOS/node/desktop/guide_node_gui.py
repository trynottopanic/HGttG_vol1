"""Small, non-technical Windows control panel for the Guide desktop Node."""

from __future__ import annotations

import argparse
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog

from guide_node_core import DEFAULT_DISCOVERY_PORT, DEFAULT_HTTP_PORT, NodeState
from guide_node_server import NodeRuntime


class GuideNodeWindow:
    def __init__(self, root: tk.Tk, http_port: int, discovery_port: int,
                 media_folder: str = "", semiotic_enabled: bool | None = None) -> None:
        self.root = root
        self.root.title("Guide Desktop Node — fixed-layout build")
        self.root.geometry("640x780")
        self.root.minsize(600, 740)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self.state = NodeState(auto_prepare=True, semiotic_enabled=semiotic_enabled)
        if media_folder:
            self.state.media.set_folder(media_folder)
            self.state.prepare_media()
        self.runtime = NodeRuntime(self.state, http_port, discovery_port)

        # This control panel fits in one window. A Canvas forced Tcl/Tk to
        # recalculate an embedded window and scroll region while Windows was
        # moving or resizing the top-level window, producing severe drag lag on
        # the prototype desktop. Keep the ordinary controls in a direct frame.
        frame = tk.Frame(root, padx=28, pady=24)
        frame.pack(fill="both", expand=True)
        tk.Label(frame, text="GUIDE DESKTOP NODE", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        tk.Label(
            frame,
            text="Makes selected services on this computer available to a paired Deck.",
            font=("Segoe UI", 10), wraplength=450, justify="left"
        ).pack(anchor="w", pady=(5, 20))

        self.status = tk.StringVar(value="Starting…")
        tk.Label(frame, textvariable=self.status, font=("Segoe UI", 12, "bold"),
                 fg="#1f6f43").pack(anchor="w")
        self.address = tk.StringVar(value="")
        tk.Label(frame, textvariable=self.address, font=("Consolas", 10)).pack(anchor="w", pady=(4, 18))

        tk.Label(frame, text="PAIRING CODE", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.code = tk.StringVar(value=self.state.pairing_code)
        tk.Label(frame, textvariable=self.code, font=("Consolas", 30, "bold")).pack(anchor="w")
        tk.Label(frame, text="Show this code only to the person pairing a Deck. It expires in 10 minutes.",
                 font=("Segoe UI", 9), wraplength=450, justify="left").pack(anchor="w", pady=(2, 12))

        buttons = tk.Frame(frame)
        buttons.pack(anchor="w", pady=(3, 18))
        tk.Button(buttons, text="New pairing code", command=self.rotate, padx=12, pady=5).pack(side="left")
        tk.Button(buttons, text="Stop Node", command=self.stop, padx=12, pady=5).pack(side="left", padx=8)
        tk.Label(buttons, text="AT Field").pack(side="left")
        self.at_field_choice = tk.StringVar(value=self.state.at_field.mode.value.title())
        tk.OptionMenu(buttons, self.at_field_choice, "Closed", "Familiar", "Open",
                      command=self.change_at_field).pack(side="left")

        tk.Label(frame, text="MEDIA FOLDER", font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(2, 3))
        self.media_status = tk.StringVar(value="No folder selected")
        tk.Label(frame, textvariable=self.media_status, font=("Segoe UI", 9),
                 wraplength=490, justify="left").pack(anchor="w")
        media_buttons = tk.Frame(frame)
        media_buttons.pack(anchor="w", pady=(8, 18))
        tk.Button(media_buttons, text="Choose Media Folder", command=self.choose_media,
                  padx=12, pady=5).pack(side="left")
        tk.Button(media_buttons, text="Rescan", command=self.rescan_media,
                  padx=12, pady=5).pack(side="left", padx=8)
        tk.Button(media_buttons, text="Stop sharing", command=self.clear_media,
                  padx=12, pady=5).pack(side="left")

        tk.Label(frame, text="STREAMED APPLICATIONS", font=("Segoe UI", 9, "bold")).pack(
            anchor="w", pady=(2, 3))
        tk.Label(frame, text="Only applications you add here may be requested by a Deck.",
                 font=("Segoe UI", 9)).pack(anchor="w")
        application_row = tk.Frame(frame)
        application_row.pack(fill="x", anchor="w", pady=(5, 5))
        self.application_list = tk.Listbox(application_row, height=2, exportselection=False,
                                           font=("Segoe UI", 9))
        self.application_list.pack(side="left", fill="x", expand=True)
        application_buttons = tk.Frame(application_row)
        application_buttons.pack(side="left", padx=(8, 0))
        tk.Button(application_buttons, text="Add…", command=self.add_application,
                  padx=10, pady=3).pack(fill="x")
        tk.Button(application_buttons, text="Remove", command=self.remove_application,
                  padx=10, pady=3).pack(fill="x", pady=(4, 0))
        self.application_request = tk.StringVar(value="No application request waiting.")
        tk.Label(frame, textvariable=self.application_request, font=("Segoe UI", 9),
                 wraplength=510, justify="left").pack(anchor="w")
        approval_buttons = tk.Frame(frame)
        approval_buttons.pack(anchor="w", pady=(5, 14))
        self.approve_button = tk.Button(approval_buttons, text="Approve request",
                                        command=lambda: self.decide_application(True),
                                        padx=10, pady=3, state="disabled")
        self.approve_button.pack(side="left")
        self.deny_button = tk.Button(approval_buttons, text="Decline",
                                     command=lambda: self.decide_application(False),
                                     padx=10, pady=3, state="disabled")
        self.deny_button.pack(side="left", padx=7)

        tk.Label(frame, text="TRUSTED COMPANIONS", font=("Segoe UI", 9, "bold")).pack(
            anchor="w", pady=(2, 3))
        self.allow_trust = tk.BooleanVar(value=False)
        tk.Checkbutton(
            frame, variable=self.allow_trust, command=self.change_trust_permission,
            text="Allow the next paired Deck's trust request",
            font=("Segoe UI", 9)
        ).pack(anchor="w")
        tk.Label(
            frame,
            text="Both devices must approve. A trusted Deck may reconnect on this local network without a new code.",
            font=("Segoe UI", 9), wraplength=510, justify="left"
        ).pack(anchor="w", pady=(0, 5))
        trust_row = tk.Frame(frame)
        trust_row.pack(fill="x", anchor="w", pady=(0, 15))
        self.trusted_list = tk.Listbox(trust_row, height=2, exportselection=False,
                                       font=("Segoe UI", 9))
        self.trusted_list.pack(side="left", fill="x", expand=True)
        tk.Button(trust_row, text="Revoke selected", command=self.revoke_trusted,
                  padx=10, pady=5).pack(side="left", padx=(8, 0))

        tk.Label(
            frame,
            text="DEVELOPMENT LINK — local traffic is not encrypted yet. Use only on a trusted private network.",
            font=("Segoe UI", 9, "bold"), fg="#9b2c2c", wraplength=450, justify="left"
        ).pack(anchor="w")
        self.update_media_status()
        self.update_trusted_list()
        self.update_applications()
        self._refresh_stop = threading.Event()
        self._refresh_results: queue.Queue[dict[str, object]] = queue.Queue(maxsize=1)
        self._last_snapshot: dict[str, object] | None = None
        self._refresh_thread = threading.Thread(
            target=self._refresh_worker, name="guide-node-status", daemon=True)
        self._refresh_thread.start()
        self.root.after(100, self.start)
        self.root.after(500, self.refresh)

    def start(self) -> None:
        try:
            self.runtime.start()
        except OSError as error:
            self.status.set("Could not start")
            messagebox.showerror("Guide Node", f"The Node could not start.\n\n{error}")
            return
        self.status.set("Ready for a Deck")
        self.address.set(f"{self.runtime.address}:{self.runtime.http_port}  •  0 Decks paired")

    def stop(self) -> None:
        self.runtime.stop()
        self.status.set("Stopped")
        self.address.set("All Deck sessions have been revoked.")

    def rotate(self) -> None:
        self.code.set(self.state.rotate_pairing_code())

    def change_at_field(self, choice: str) -> None:
        try:
            if choice.lower() != self.state.at_field.mode.value:
                preview = self.state.preview_at_field(choice.lower())
                if messagebox.askyesno("AT Field", preview + "\n\nApply this setting?"):
                    self.state.set_at_field(choice.lower())
        except (OSError, ValueError) as error:
            messagebox.showerror("AT Field", f"Could not save the setting.\n\n{error}")
        finally:
            self.at_field_choice.set(self.state.at_field.mode.value.title())

    def choose_media(self) -> None:
        selected = filedialog.askdirectory(title="Choose the folder this Node may share")
        if not selected:
            return
        try:
            self.state.media.set_folder(selected)
            self.state.prepare_media()
        except (OSError, ValueError) as error:
            messagebox.showerror("Guide Node", f"That folder could not be used.\n\n{error}")
        self.update_media_status()

    def rescan_media(self) -> None:
        self.state.media.scan()
        self.state.prepare_media()
        self.update_media_status()

    def clear_media(self) -> None:
        try:
            self.state.media.set_folder(None)
            self.state.prepare_media()
        except OSError as error:
            messagebox.showerror("Guide Node", f"The saved setting could not be changed.\n\n{error}")
        self.update_media_status()

    def change_trust_permission(self) -> None:
        self.state.arm_trust(self.allow_trust.get())

    def add_application(self) -> None:
        selected = filedialog.askopenfilename(
            title="Choose an application the Deck may request",
            filetypes=(("Windows applications", "*.exe"),),
        )
        if not selected:
            return
        title = simpledialog.askstring(
            "Streamed application",
            "What title appears at the top of this application's window?\n"
            "This lets the Node share only that window.",
            initialvalue="",
            parent=self.root,
        )
        try:
            self.state.applications.add(Path(selected), window_title=title or "")
        except (OSError, ValueError) as error:
            messagebox.showerror("Guide Node", f"That application could not be added.\n\n{error}")
        self.update_applications()

    def remove_application(self) -> None:
        selection = self.application_list.curselection()
        profiles = self.state.applications.profiles()
        if selection and selection[0] < len(profiles):
            if not self.state.applications.remove(str(profiles[selection[0]]["id"])):
                messagebox.showinfo("Guide Node", "Close its pending or active session first.")
        self.update_applications()

    def decide_application(self, approved: bool) -> None:
        pending = self.state.applications.pending()
        if pending:
            result = self.state.applications.decide(str(pending[0]["id"]), approved)
            if result and approved and result["state"] != "active":
                messagebox.showerror("Guide Node", str(result.get("reason", "Could not start")))
        self.update_applications()

    def update_applications(self) -> None:
        selected = self.application_list.curselection()
        old = selected[0] if selected else 0
        self.application_list.delete(0, tk.END)
        profiles = self.state.applications.profiles()
        for profile in profiles:
            state = "ready" if profile["available"] else "file missing"
            self.application_list.insert(tk.END, f"{profile['name']}  •  {state}")
        if profiles:
            self.application_list.selection_set(min(old, len(profiles) - 1))
        pending = self.state.applications.pending()
        if pending:
            request = pending[0]
            self.application_request.set(
                f"{request['client_name']} asks to open {request['application']}. "
                "Approve only when you expect this request."
            )
            self.approve_button.configure(state="normal")
            self.deny_button.configure(state="normal")
        else:
            readiness = "Streaming tools ready." if self.state.applications.streaming_available else \
                        "FFmpeg is needed on this computer before video streaming can start."
            self.application_request.set("No application request waiting. " + readiness)
            self.approve_button.configure(state="disabled")
            self.deny_button.configure(state="disabled")

    def update_trusted_list(self) -> None:
        selected = self.trusted_list.curselection()
        old = selected[0] if selected else 0
        self.trusted_list.delete(0, tk.END)
        for client_id, name in self.state.trusted_decks():
            self.trusted_list.insert(tk.END, f"{name}  •  {client_id[:8]}")
        count = self.trusted_list.size()
        if count:
            self.trusted_list.selection_set(min(old, count - 1))
        if self.allow_trust.get() != self.state.trust_armed:
            self.allow_trust.set(self.state.trust_armed)

    def revoke_trusted(self) -> None:
        selection = self.trusted_list.curselection()
        trusted = self.state.trusted_decks()
        if selection and selection[0] < len(trusted):
            self.state.revoke_trust(trusted[selection[0]][0])
        self.update_trusted_list()

    def update_media_status(self) -> None:
        folder = self.state.media.folder
        if folder is None:
            self.media_status.set("No folder selected — no media is available to Decks.")
            return
        recognized = len(self.state.media.listing())
        count = len(self.state.media_listing())
        preparation = self.state.media_preparation()
        suffix = "file" if count == 1 else "files"
        message = f"{folder}\n{count} {suffix} ready for paired Decks; {recognized} recognized."
        active = int(preparation["queued"]) + int(preparation["preparing"])
        if active:
            message += f"\nPreparing {active} video file(s) automatically…"
        if preparation["error"]:
            message += f"\nPreparation problem: {preparation['last_error']}"
        if self.state.media.last_error:
            message += f"\nScan problem: {self.state.media.last_error}"
        self.media_status.set(message)

    def _status_snapshot(self) -> dict[str, object]:
        folder = self.state.media.folder
        return {
            "running": self.runtime.running,
            "sessions": self.state.session_count(),
            "trusted": tuple(self.state.trusted_decks()),
            "trust_armed": self.state.trust_armed,
            "media_folder": str(folder) if folder else "",
            "media_recognized": len(self.state.media.records()),
            "media_ready": len(self.state.media_listing()),
            "media_preparation": self.state.media_preparation(),
            "media_error": self.state.media.last_error,
            "applications": tuple(
                (str(profile["name"]), bool(profile["available"]))
                for profile in self.state.applications.profiles()),
            "pending": tuple(
                (str(item["client_name"]), str(item["application"]))
                for item in self.state.applications.pending()),
            "streaming_ready": self.state.applications.streaming_available,
        }

    def _refresh_worker(self) -> None:
        while not self._refresh_stop.is_set():
            try:
                snapshot = self._status_snapshot()
                try:
                    self._refresh_results.put_nowait(snapshot)
                except queue.Full:
                    try:
                        self._refresh_results.get_nowait()
                    except queue.Empty:
                        pass
                    self._refresh_results.put_nowait(snapshot)
            except (OSError, ValueError):
                pass
            self._refresh_stop.wait(1.0)

    @staticmethod
    def _replace_listbox(listbox: tk.Listbox, entries: tuple[str, ...]) -> None:
        if tuple(listbox.get(0, tk.END)) == entries:
            return
        selection = listbox.curselection()
        old = selection[0] if selection else 0
        listbox.delete(0, tk.END)
        for entry in entries:
            listbox.insert(tk.END, entry)
        if entries:
            listbox.selection_set(min(old, len(entries) - 1))

    def _apply_snapshot(self, snapshot: dict[str, object]) -> None:
        if snapshot["running"]:
            count = int(snapshot["sessions"])
            suffix = "Deck" if count == 1 else "Decks"
            self.address.set(
                f"{self.runtime.address}:{self.runtime.http_port}  •  {count} {suffix} paired")

        trusted = tuple(snapshot["trusted"])
        self._replace_listbox(
            self.trusted_list,
            tuple(f"{name}  •  {client_id[:8]}" for client_id, name in trusted),
        )
        if self.allow_trust.get() != bool(snapshot["trust_armed"]):
            self.allow_trust.set(bool(snapshot["trust_armed"]))

        folder = str(snapshot["media_folder"])
        if not folder:
            media_message = "No folder selected — no media is available to Decks."
        else:
            count = int(snapshot["media_ready"])
            recognized = int(snapshot["media_recognized"])
            suffix = "file" if count == 1 else "files"
            media_message = f"{folder}\n{count} {suffix} ready for paired Decks; {recognized} recognized."
            preparation = dict(snapshot["media_preparation"])
            active = int(preparation["queued"]) + int(preparation["preparing"])
            if active:
                media_message += f"\nPreparing {active} video file(s) automatically…"
            if preparation["error"]:
                media_message += f"\nPreparation problem: {preparation['last_error']}"
            if snapshot["media_error"]:
                media_message += f"\nScan problem: {snapshot['media_error']}"
        if self.media_status.get() != media_message:
            self.media_status.set(media_message)

        applications = tuple(snapshot["applications"])
        self._replace_listbox(
            self.application_list,
            tuple(f"{name}  •  {'ready' if available else 'file missing'}"
                  for name, available in applications),
        )
        pending = tuple(snapshot["pending"])
        if pending:
            client, application = pending[0]
            request = (f"{client} asks to open {application}. "
                       "Approve only when you expect this request.")
            button_state = "normal"
        else:
            readiness = ("Streaming tools ready." if snapshot["streaming_ready"] else
                         "FFmpeg is needed on this computer before video streaming can start.")
            request = "No application request waiting. " + readiness
            button_state = "disabled"
        if self.application_request.get() != request:
            self.application_request.set(request)
        self.approve_button.configure(state=button_state)
        self.deny_button.configure(state=button_state)

    def refresh(self) -> None:
        latest = None
        try:
            while True:
                latest = self._refresh_results.get_nowait()
        except queue.Empty:
            pass
        if latest is not None and latest != self._last_snapshot:
            self._apply_snapshot(latest)
            self._last_snapshot = latest
        if not self._refresh_stop.is_set():
            self.root.after(500, self.refresh)

    def close(self) -> None:
        self._refresh_stop.set()
        self._refresh_thread.join(timeout=1.5)
        self.runtime.stop()
        self.state.close()
        self.root.destroy()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Guide desktop Node")
    parser.add_argument("--port", type=int, default=DEFAULT_HTTP_PORT)
    parser.add_argument("--discovery-port", type=int, default=DEFAULT_DISCOVERY_PORT)
    parser.add_argument("--media-folder", default="",
                        help="Select and remember one media folder when the Node starts")
    parser.add_argument("--semiotic-engine", action="store_true", default=None,
                        help="Explicitly offer the separately installed local Semiotic Engine")
    args = parser.parse_args()
    root = tk.Tk()
    GuideNodeWindow(root, args.port, args.discovery_port, args.media_folder,
                    args.semiotic_engine)
    root.mainloop()


if __name__ == "__main__":
    main()
