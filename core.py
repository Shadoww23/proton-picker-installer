"""Installer logic with no GUI dependencies.

Downloads the official Proton Picker archive, verifies its pinned SHA-256,
extracts it, and runs the official installer or uninstaller.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Callable, Optional

VERSION = "0.1.1"
PICKER_VERSION = "0.1.0-alpha"
ARCHIVE_NAME = "ProtonPicker-{}.tar.gz".format(PICKER_VERSION)
ARCHIVE_URL = (
    "https://github.com/Shadoww23/proton-picker/releases/download/v{}/{}".format(
        PICKER_VERSION, ARCHIVE_NAME
    )
)
ARCHIVE_SHA256 = "8f447834972d6b7719fd86d70181f27c4d6104c8f750b60eaec1bc7ec48ad5b1"
PICKER_MIN_PYTHON = (3, 10)
DOWNLOAD_URL = "https://brlinkin.itch.io/proton-picker"
PROBLEMS_URL = "https://github.com/Shadoww23/proton-picker/blob/main/docs/PROBLEMS.md"

Progress = Callable[[int, int], None]
LogLine = Callable[[str], None]


class InstallerError(RuntimeError):
    pass


def steam_roots(home: Path) -> list:
    candidates = [
        home / ".local/share/Steam",
        home / ".steam/steam",
        home / ".steam/root",
        home / ".var/app/com.valvesoftware.Steam/data/Steam",
    ]
    roots = []
    for path in candidates:
        if not path.exists():
            continue
        resolved = path.resolve()
        if resolved not in roots:
            roots.append(resolved)
    return roots


def find_steam(home: Path) -> Optional[Path]:
    for root in steam_roots(home):
        if (root / "steamapps").is_dir() or (root / "config").is_dir():
            return root
    return None


def is_flatpak_steam(root: Optional[Path]) -> bool:
    return bool(root) and ".var/app" in str(root)


def manager_home(home: Optional[Path] = None) -> Path:
    return home if home is not None else Path.home()


def read_state(home: Path) -> dict:
    try:
        data = json.loads(
            (home / ".config/proton-picker/state.json").read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def installed_info(home: Optional[Path] = None) -> dict:
    home = manager_home(home)
    state = read_state(home)
    installation = state.get("installation") if isinstance(state.get("installation"), dict) else {}
    app_dir = Path(installation["app_dir"]) if installation.get("app_dir") else None
    dispatcher_value = state.get("dispatcher_dir")
    dispatcher = Path(dispatcher_value) if dispatcher_value else None
    installed = bool(dispatcher and (dispatcher / "proton").is_file())
    version = None
    if app_dir:
        try:
            text = (app_dir / "app.py").read_text(encoding="utf-8", errors="replace")
            match = re.search(r'^VERSION\s*=\s*"([^"]+)"', text, re.MULTILINE)
            version = match.group(1) if match else None
        except OSError:
            version = None
    return {
        "installed": installed,
        "app_dir": str(app_dir) if app_dir else None,
        "version": version,
        "enabled": bool(state.get("enabled")),
        "pending_setup": bool(state.get("pending_setup") or state.get("pending")),
    }


def steam_running() -> bool:
    proc = Path("/proc")
    try:
        entries = list(proc.iterdir())
    except OSError:
        return False
    for entry in entries:
        if not entry.name.isdigit():
            continue
        try:
            comm = (entry / "comm").read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            continue
        if comm.lower().startswith("steam"):
            return True
    return False


def find_steam_command() -> Optional[str]:
    for name in ("steam", "steam-native"):
        found = shutil.which(name)
        if found:
            return found
    return None


def shutdown_steam(timeout: float = 45.0, poll: float = 0.5) -> bool:
    if not steam_running():
        return True
    command = find_steam_command()
    if not command:
        return False
    try:
        subprocess.Popen(
            [command, "-shutdown"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError:
        return False
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not steam_running():
            return True
        time.sleep(poll)
    return not steam_running()


def find_python() -> Optional[str]:
    for name in ("python3", "python3.12", "python3.11", "python3.10"):
        found = shutil.which(name)
        if found:
            return found
    return None


def python_version(command: str) -> Optional[tuple]:
    try:
        result = subprocess.run(
            [command, "-c", "import sys; print('%d.%d' % sys.version_info[:2])"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    match = re.search(r"(\d+)\.(\d+)", result.stdout)
    return (int(match.group(1)), int(match.group(2))) if match else None


def python_ready(command: Optional[str]) -> bool:
    if not command:
        return False
    version = python_version(command)
    return bool(version and version >= PICKER_MIN_PYTHON)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, destination: Path, progress: Optional[Progress] = None) -> Path:
    request = urllib.request.Request(
        url, headers={"User-Agent": "ProtonPickerSetup/{}".format(VERSION)}
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            total = int(response.headers.get("Content-Length") or 0)
            destination.parent.mkdir(parents=True, exist_ok=True)
            done = 0
            with destination.open("wb") as stream:
                while True:
                    chunk = response.read(64 * 1024)
                    if not chunk:
                        break
                    stream.write(chunk)
                    done += len(chunk)
                    if progress:
                        progress(done, total)
    except OSError as exc:
        raise InstallerError("Download failed: {}".format(exc))
    return destination


def verify_checksum(path: Path, expected: str = ARCHIVE_SHA256) -> None:
    actual = sha256_file(path)
    if actual.lower() != expected.lower():
        raise InstallerError(
            "Checksum mismatch. Expected {}, got {}. The download was discarded.".format(
                expected, actual
            )
        )


def safe_extract(archive: Path, destination: Path) -> Path:
    destination = destination.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    try:
        with tarfile.open(archive, "r:gz") as bundle:
            for member in bundle.getmembers():
                target = (destination / member.name).resolve()
                if target != destination and destination not in target.parents:
                    raise InstallerError("Archive contains an unsafe path: {}".format(member.name))
                if member.issym() or member.islnk():
                    raise InstallerError(
                        "Archive contains a link; refusing to extract: {}".format(member.name)
                    )
                if member.isdev():
                    raise InstallerError(
                        "Archive contains a device entry; refusing to extract: {}".format(
                            member.name
                        )
                    )
            if hasattr(tarfile, "data_filter"):
                bundle.extractall(destination, filter="data")
            else:
                bundle.extractall(destination)
    except (tarfile.TarError, OSError) as exc:
        raise InstallerError("Could not extract the archive: {}".format(exc))
    return destination


def run_script(
    python: str,
    directory: Path,
    script: str,
    arguments: Optional[list] = None,
    on_line: Optional[LogLine] = None,
    timeout: float = 300.0,
) -> int:
    command = [python, str(directory / script)] + list(arguments or [])
    try:
        process = subprocess.Popen(
            command,
            cwd=str(directory),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except OSError as exc:
        raise InstallerError("Could not start {}: {}".format(script, exc))

    deadline = time.monotonic() + timeout
    assert process.stdout is not None
    stream = process.stdout
    try:
        for line in stream:
            if on_line and line.strip():
                on_line(line.rstrip())
            if time.monotonic() > deadline:
                process.kill()
                raise InstallerError("{} timed out".format(script))
    finally:
        stream.close()
    try:
        return process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        process.kill()
        raise InstallerError("{} did not finish".format(script))


def install(
    python: str,
    archive: Path,
    workdir: Path,
    clear_overrides: bool,
    on_line: Optional[LogLine] = None,
) -> None:
    extract_dir = workdir / "app"
    safe_extract(archive, extract_dir)
    arguments = ["--clear-overrides"] if clear_overrides else ["--keep-overrides"]
    code = run_script(python, extract_dir, "install.py", arguments, on_line)
    if code != 0:
        raise InstallerError(
            "Proton Picker setup exited with code {}. Nothing else was changed.".format(code)
        )


def uninstall(python: str, home: Optional[Path] = None, on_line: Optional[LogLine] = None) -> None:
    info = installed_info(home)
    app_dir = info.get("app_dir")
    if not app_dir or not (Path(app_dir) / "uninstall.py").is_file():
        raise InstallerError("Proton Picker's uninstaller was not found. Reinstall it first.")
    code = run_script(python, Path(app_dir), "uninstall.py", [], on_line)
    if code != 0:
        raise InstallerError("Uninstall exited with code {}.".format(code))


def start_steam() -> bool:
    command = find_steam_command()
    if not command:
        return False
    try:
        subprocess.Popen(
            [command],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
        return True
    except OSError:
        return False


def make_workdir() -> Path:
    return Path(tempfile.mkdtemp(prefix="proton-picker-setup-"))
