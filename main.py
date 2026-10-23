#!/usr/bin/env python3
"""Proton Picker Setup: a small AppImage installer for the official alpha."""
from __future__ import annotations

import queue
import shutil
import sys
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Optional

import core

APP_TITLE = "Proton Picker Setup"
WINDOW_SIZE = "720x660"
MUTED = "#5c6b68"
ERROR = "#b3261e"
OK = "#0f6b57"


def resource_path(name: str) -> Optional[Path]:
    base = getattr(sys, "_MEIPASS", None)
    candidates = [Path(base) / name] if base else []
    candidates.append(Path(__file__).resolve().parent / name)
    candidates.append(Path(__file__).resolve().parent / "build" / name)
    for path in candidates:
        if path.is_file():
            return path
    return None


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.events = queue.Queue()
        self.busy = False
        self.steam_root: Optional[Path] = None
        self.python: Optional[str] = None
        self.info = {}
        self.installed = False

        root.title(APP_TITLE)
        root.geometry(WINDOW_SIZE)
        root.minsize(660, 600)
        root.protocol("WM_DELETE_WINDOW", self.on_close)

        icon = resource_path("icon.png")
        if icon:
            try:
                self._icon = tk.PhotoImage(file=str(icon))
                root.iconphoto(True, self._icon)
            except tk.TclError:
                pass

        self._build()
        self.refresh()
        self.root.after(120, self._drain)

    def _build(self) -> None:
        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("Title.TLabel", font=("DejaVu Sans", 20, "bold"))
        style.configure("Sub.TLabel", foreground=MUTED, font=("DejaVu Sans", 10))
        style.configure("Head.TLabel", font=("DejaVu Sans", 11, "bold"))
        style.configure("Value.TLabel", font=("DejaVu Sans", 10))
        style.configure("Accent.TButton", font=("DejaVu Sans", 11, "bold"))

        outer = ttk.Frame(self.root, padding=20)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text=APP_TITLE, style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            outer,
            text="Installs the official Proton Picker alpha for your user. No administrator password.",
            style="Sub.TLabel",
            wraplength=660,
        ).pack(anchor="w", pady=(2, 14))

        checks = ttk.LabelFrame(outer, text="This computer", padding=12)
        checks.pack(fill="x")
        self.steam_label = self._check_row(checks, "Steam")
        self.python_label = self._check_row(checks, "Python")
        self.picker_label = self._check_row(checks, "Proton Picker")
        self.steam_label.configure(text="Checking...")

        options = ttk.LabelFrame(outer, text="Options", padding=12)
        options.pack(fill="x", pady=(12, 0))
        self.clear_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            options,
            text="Let Proton Picker choose the Proton build for every game (recommended)",
            variable=self.clear_var,
            command=self._update_option_note,
        ).pack(anchor="w")
        self.option_note = ttk.Label(options, text="", style="Sub.TLabel", wraplength=630)
        self.option_note.pack(anchor="w", pady=(4, 0))
        self._update_option_note()

        actions = ttk.Frame(outer)
        actions.pack(fill="x", pady=(14, 0))
        self.install_button = ttk.Button(
            actions, text="Install Proton Picker", style="Accent.TButton", command=self.on_install
        )
        self.install_button.pack(side="left")
        self.uninstall_button = ttk.Button(
            actions, text="Uninstall", command=self.on_uninstall, state="disabled"
        )
        self.uninstall_button.pack(side="left", padx=(8, 0))
        self.steam_button = ttk.Button(
            actions, text="Start Steam", command=self.on_start_steam, state="disabled"
        )
        self.steam_button.pack(side="right")

        self.progress = ttk.Progressbar(outer, mode="determinate", maximum=100)
        self.progress.pack(fill="x", pady=(14, 4))
        self.status = ttk.Label(outer, text="Ready.", style="Value.TLabel")
        self.status.pack(anchor="w")

        log_frame = ttk.Frame(outer)
        log_frame.pack(fill="both", expand=True, pady=(10, 0))
        self.log = tk.Text(
            log_frame,
            height=9,
            wrap="word",
            font=("DejaVu Sans Mono", 9),
            background="#f7faf9",
            relief="solid",
            borderwidth=1,
            state="disabled",
        )
        scroll = ttk.Scrollbar(log_frame, command=self.log.yview)
        self.log.configure(yscrollcommand=scroll.set)
        self.log.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        footer = ttk.Frame(outer)
        footer.pack(fill="x", pady=(10, 0))
        ttk.Label(
            footer,
            text="Downloads {:.0f} KB from GitHub and checks its SHA-256.".format(28.6),
            style="Sub.TLabel",
        ).pack(side="left")
        help_button = ttk.Button(footer, text="Troubleshooting", command=self.on_help)
        help_button.pack(side="right")
        alpha_button = ttk.Button(footer, text="About the alpha", command=self.on_about)
        alpha_button.pack(side="right", padx=(0, 6))

    def _check_row(self, parent: ttk.Widget, name: str) -> ttk.Label:
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=name, style="Head.TLabel", width=16).pack(side="left")
        value = ttk.Label(row, text="", style="Value.TLabel", wraplength=520)
        value.pack(side="left", fill="x", expand=True)
        return value

    def _update_option_note(self) -> None:
        if self.clear_var.get():
            text = (
                "Steam will use Proton Picker for every game. Existing per-game Proton "
                "overrides are removed and saved so uninstall can restore them."
            )
        else:
            text = (
                "Existing per-game Proton overrides stay in place. Proton Picker handles "
                "the games that do not have one."
            )
        self.option_note.configure(text=text)

    def log_line(self, text: str) -> None:
        self.events.put(("log", text))

    def refresh(self) -> None:
        home = core.manager_home()
        self.steam_root = core.find_steam(home)
        self.python = core.find_python()
        self.info = core.installed_info(home)
        self.installed = bool(self.info.get("installed"))

        if self.steam_root:
            where = str(self.steam_root)
            if core.is_flatpak_steam(self.steam_root):
                self.steam_label.configure(
                    text="Flatpak Steam found. This alpha only supports native Steam.",
                    foreground=ERROR,
                )
                self._set_install_enabled(False)
            else:
                self.steam_label.configure(text=where, foreground=OK)
                self._set_install_enabled(True)
        else:
            self.steam_label.configure(
                text="Not found. Install Steam, then reopen this setup.", foreground=ERROR
            )
            self._set_install_enabled(False)

        version = core.python_version(self.python) if self.python else None
        if core.python_ready(self.python):
            self.python_label.configure(
                text="{} ({}.{})".format(self.python, version[0], version[1]), foreground=OK
            )
        else:
            self.python_label.configure(
                text="Python 3.10 or newer is required. Found: {}".format(
                    "{}.{}".format(*version) if version else "none"
                ),
                foreground=ERROR,
            )
            self._set_install_enabled(False)

        if self.installed:
            self.picker_label.configure(
                text="Installed {}".format(self.info.get("version") or "(unknown version)"),
                foreground=OK,
            )
            self.install_button.configure(text="Update / reinstall")
            self.uninstall_button.configure(state="normal")
        else:
            self.picker_label.configure(text="Not installed", foreground=MUTED)
            self.install_button.configure(text="Install Proton Picker")
            self.uninstall_button.configure(state="disabled")

        if core.steam_running():
            self.status.configure(text="Steam is open. Setup will ask to close it.")
            self.steam_button.configure(state="disabled")
        else:
            self.status.configure(text="Ready.")
            if self.installed:
                self.steam_button.configure(state="normal")
            else:
                self.steam_button.configure(state="disabled")

    def _set_install_enabled(self, enabled: bool) -> None:
        if self.busy:
            return
        self.install_button.configure(state="normal" if enabled else "disabled")

    def _ask_close_steam(self) -> bool:
        if not core.steam_running():
            return True
        return messagebox.askyesno(
            "Close Steam?",
            "Steam must be closed before setup can change its configuration.\n\n"
            "Save your game and quit Steam now? Games can be reopened after setup.",
            parent=self.root,
        )

    def on_install(self) -> None:
        if self.busy:
            return
        if self.steam_root and core.is_flatpak_steam(self.steam_root):
            messagebox.showerror(
                APP_TITLE,
                "Flatpak Steam is not supported in this alpha. Install the native Steam "
                "package, then run setup again.",
                parent=self.root,
            )
            return
        if not core.python_ready(self.python):
            messagebox.showerror(
                APP_TITLE,
                "Python 3.10 or newer is required. Install it with your distribution's "
                "package manager, then run setup again.",
                parent=self.root,
            )
            return
        if not self._ask_close_steam():
            return
        clear = self.clear_var.get()
        if not messagebox.askokcancel(
            "Install Proton Picker",
            "Setup will:\n"
            "  1. Download the official {} archive from GitHub\n"
            "  2. Verify its SHA-256 checksum\n"
            "  3. Install it for your user\n\n"
            "Steam will be closed if it is open. Continue?".format(core.PICKER_VERSION),
            parent=self.root,
        ):
            return
        self._begin("Installing...")
        threading.Thread(target=self._install_worker, args=(clear,), daemon=True).start()

    def _install_worker(self, clear: bool) -> None:
        workdir = core.make_workdir()
        try:
            if core.steam_running():
                self.log_line("Closing Steam...")
                if not core.shutdown_steam():
                    raise core.InstallerError(
                        "Steam did not close. Close it manually, then click Install again."
                    )
            self.log_line("Downloading {}...".format(core.ARCHIVE_NAME))
            archive = core.download(
                core.ARCHIVE_URL,
                workdir / core.ARCHIVE_NAME,
                progress=lambda done, total: self.events.put(
                    ("progress", (done / total) if total else -1)
                ),
            )
            self.log_line("Verifying SHA-256 checksum...")
            core.verify_checksum(archive)
            self.log_line("Extracting...")
            core.install(self.python, archive, workdir, clear, on_line=self.log_line)
            self.events.put(("done", True, "install"))
        except core.InstallerError as exc:
            self.events.put(("done", False, str(exc)))
        except Exception as exc:  # keep the window usable
            self.events.put(("done", False, "Unexpected error: {}".format(exc)))
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    def on_uninstall(self) -> None:
        if self.busy:
            return
        if not messagebox.askyesno(
            "Uninstall Proton Picker?",
            "This removes Proton Picker and restores the Steam default and per-game "
            "overrides saved during setup. Steam must be closed.",
            parent=self.root,
        ):
            return
        if not self._ask_close_steam():
            return
        self._begin("Uninstalling...")
        threading.Thread(target=self._uninstall_worker, daemon=True).start()

    def _uninstall_worker(self) -> None:
        try:
            if core.steam_running():
                self.log_line("Closing Steam...")
                if not core.shutdown_steam():
                    raise core.InstallerError(
                        "Steam did not close. Close it manually, then click Uninstall again."
                    )
            core.uninstall(self.python, on_line=self.log_line)
            self.events.put(("done", True, "uninstall"))
        except core.InstallerError as exc:
            self.events.put(("done", False, str(exc)))
        except Exception as exc:
            self.events.put(("done", False, "Unexpected error: {}".format(exc)))

    def _begin(self, message: str) -> None:
        self.busy = True
        for button in (self.install_button, self.uninstall_button, self.steam_button):
            button.configure(state="disabled")
        self.progress.configure(mode="indeterminate")
        self.progress.start(12)
        self.status.configure(text=message)

    def _finish(self) -> None:
        self.busy = False
        self.progress.stop()
        self.progress.configure(mode="determinate")
        self.progress["value"] = 0
        self.refresh()

    def _drain(self) -> None:
        try:
            while True:
                event = self.events.get_nowait()
                kind = event[0]
                if kind == "log":
                    self._append_log(event[1])
                elif kind == "progress":
                    fraction = event[1]
                    if fraction is None or fraction < 0:
                        self.progress.configure(mode="indeterminate")
                        self.progress.start(12)
                    else:
                        self.progress.stop()
                        self.progress.configure(mode="determinate")
                        self.progress["value"] = max(0, min(100, fraction * 100))
                elif kind == "done":
                    ok, payload = event[1], event[2]
                    self._finish()
                    if ok:
                        if payload == "install":
                            self.status.configure(text="Installed. Start Steam when ready.")
                            self.steam_button.configure(state="normal")
                            messagebox.showinfo(
                                APP_TITLE,
                                "Proton Picker is installed.\n\nStart Steam and click Play "
                                "as usual. The first game launch may take a moment while "
                                "choices are prepared.",
                                parent=self.root,
                            )
                        else:
                            self.status.configure(text="Uninstalled.")
                            messagebox.showinfo(
                                APP_TITLE,
                                "Proton Picker was removed and Steam's previous settings "
                                "were restored.",
                                parent=self.root,
                            )
                    else:
                        self.status.configure(text="Setup stopped.")
                        self._append_log("ERROR: {}".format(payload))
                        messagebox.showerror(APP_TITLE, payload, parent=self.root)
        except queue.Empty:
            pass
        self.root.after(120, self._drain)

    def _append_log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text.rstrip() + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def on_start_steam(self) -> None:
        if core.start_steam():
            self.status.configure(text="Starting Steam...")
            self.steam_button.configure(state="disabled")
        else:
            messagebox.showerror(
                APP_TITLE, "Steam was not found in your PATH. Start it from your menu.", parent=self.root
            )

    def on_help(self) -> None:
        webbrowser.open(core.PROBLEMS_URL)

    def on_about(self) -> None:
        messagebox.showinfo(
            "About Proton Picker Setup",
            "Installer {} for Proton Picker {} (alpha).\n\n"
            "This installer downloads the official archive from GitHub, verifies its "
            "SHA-256 checksum, and runs the official installer. It contains no Proton "
            "Picker code and does not redistribute it.\n\n"
            "Proton Picker is proprietary freeware. Installer source is MIT licensed.\n\n"
            "Not affiliated with Valve Corporation.".format(core.VERSION, core.PICKER_VERSION),
            parent=self.root,
        )

    def on_close(self) -> None:
        if self.busy:
            if not messagebox.askyesno(
                "Setup is running",
                "Setup is still running. Quit anyway? This can leave a partial download.",
                parent=self.root,
            ):
                return
        self.root.destroy()


def main() -> int:
    if "--version" in sys.argv:
        print("Proton Picker Setup {}".format(core.VERSION))
        return 0
    root = tk.Tk()
    App(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
