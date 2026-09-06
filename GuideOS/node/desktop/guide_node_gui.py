"""Small, non-technical Windows control panel for the Guide desktop Node."""

from __future__ import annotations

import argparse
import tkinter as tk
from tkinter import filedialog, messagebox

from guide_node_core import DEFAULT_DISCOVERY_PORT, DEFAULT_HTTP_PORT, NodeState
from guide_node_server import NodeRuntime


class GuideNodeWindow:
    def __init__(self, root: tk.Tk, http_port: int, discovery_port: int,
                 media_folder: str = "") -> None:
        self.root = root
        self.root.title("Guide Desktop Node")
        self.root.geometry("600x700")
        self.root.minsize(560, 650)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self.state = NodeState(auto_prepare=True)
        if media_folder:
            self.state.media.set_folder(media_folder)
            self.state.prepare_media()
        self.runtime = NodeRuntime(self.state, http_port, discovery_port)

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
        self.root.after(100, self.start)
        self.root.after(1000, self.refresh)
        self.update_media_status()
        self.update_trusted_list()

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

    def refresh(self) -> None:
        if self.runtime.running:
            count = self.state.session_count()
            suffix = "Deck" if count == 1 else "Decks"
            self.address.set(f"{self.runtime.address}:{self.runtime.http_port}  •  {count} {suffix} paired")
        self.update_trusted_list()
        self.update_media_status()
        self.root.after(1000, self.refresh)

    def close(self) -> None:
        self.runtime.stop()
        self.state.close()
        self.root.destroy()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Guide desktop Node")
    parser.add_argument("--port", type=int, default=DEFAULT_HTTP_PORT)
    parser.add_argument("--discovery-port", type=int, default=DEFAULT_DISCOVERY_PORT)
    parser.add_argument("--media-folder", default="",
                        help="Select and remember one media folder when the Node starts")
    args = parser.parse_args()
    root = tk.Tk()
    GuideNodeWindow(root, args.port, args.discovery_port, args.media_folder)
    root.mainloop()


if __name__ == "__main__":
    main()
