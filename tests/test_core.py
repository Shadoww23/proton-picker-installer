import io
import json
import os
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import core  # noqa: E402


def make_tar(path: Path, entries):
    with tarfile.open(path, "w:gz") as bundle:
        for name, kind, payload in entries:
            info = tarfile.TarInfo(name)
            if kind == "file":
                data = payload.encode() if isinstance(payload, str) else payload
                info.size = len(data)
                info.mode = 0o755
                bundle.addfile(info, io.BytesIO(data))
            elif kind == "symlink":
                info.type = tarfile.SYMTYPE
                info.linkname = payload
                bundle.addfile(info)
            elif kind == "dir":
                info.type = tarfile.DIRTYPE
                bundle.addfile(info)


class ChecksumTests(unittest.TestCase):
    def test_sha256_and_verify(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "file.bin"
            path.write_bytes(b"proton")
            import hashlib

            expected = hashlib.sha256(b"proton").hexdigest()
            self.assertEqual(core.sha256_file(path), expected)
            core.verify_checksum(path, expected)
            with self.assertRaises(core.InstallerError):
                core.verify_checksum(path, "0" * 64)


class ExtractTests(unittest.TestCase):
    def test_extracts_files_and_modes(self):
        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp)
            archive = temp / "ok.tar.gz"
            make_tar(archive, [("app/install.py", "file", "#!/usr/bin/env python3\n")])
            destination = core.safe_extract(archive, temp / "out")
            script = destination / "app/install.py"
            self.assertTrue(script.is_file())
            self.assertTrue(os.access(script, os.X_OK))

    def test_rejects_traversal(self):
        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp)
            archive = temp / "bad.tar.gz"
            make_tar(archive, [("../escape", "file", "nope")])
            with self.assertRaises(core.InstallerError):
                core.safe_extract(archive, temp / "out")
            self.assertFalse((temp / "escape").exists())

    def test_rejects_absolute_path(self):
        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp)
            archive = temp / "abs.tar.gz"
            make_tar(archive, [("/tmp/escape", "file", "nope")])
            with self.assertRaises(core.InstallerError):
                core.safe_extract(archive, temp / "out")

    def test_rejects_symlink(self):
        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp)
            archive = temp / "link.tar.gz"
            make_tar(archive, [("app/link", "symlink", "/etc/passwd")])
            with self.assertRaises(core.InstallerError):
                core.safe_extract(archive, temp / "out")


class SteamTests(unittest.TestCase):
    def test_find_steam_native(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            (home / ".local/share/Steam/steamapps").mkdir(parents=True)
            root = core.find_steam(home)
            self.assertEqual(root, (home / ".local/share/Steam").resolve())
            self.assertFalse(core.is_flatpak_steam(root))

    def test_find_steam_flatpak_only(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            flatpak = home / ".var/app/com.valvesoftware.Steam/data/Steam"
            (flatpak / "steamapps").mkdir(parents=True)
            root = core.find_steam(home)
            self.assertTrue(core.is_flatpak_steam(root))

    def test_installed_info_reads_state(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            app_dir = home / "app"
            app_dir.mkdir()
            (app_dir / "app.py").write_text('VERSION = "9.9.9-alpha"\n', encoding="utf-8")
            dispatcher = home / "dispatcher"
            dispatcher.mkdir()
            (dispatcher / "proton").write_text("#!/bin/sh\n", encoding="utf-8")
            state = home / ".config/proton-picker/state.json"
            state.parent.mkdir(parents=True)
            state.write_text(
                json.dumps(
                    {
                        "enabled": True,
                        "dispatcher_dir": str(dispatcher),
                        "installation": {"app_dir": str(app_dir)},
                    }
                ),
                encoding="utf-8",
            )
            info = core.installed_info(home)
            self.assertTrue(info["installed"])
            self.assertEqual(info["version"], "9.9.9-alpha")
            self.assertTrue(info["enabled"])

    def test_missing_state_is_safe(self):
        with tempfile.TemporaryDirectory() as temp:
            info = core.installed_info(Path(temp))
            self.assertFalse(info["installed"])
            self.assertIsNone(info["version"])


class RunTests(unittest.TestCase):
    def test_python_is_ready_here(self):
        python = core.find_python()
        self.assertTrue(core.python_ready(python))

    def test_download_from_file_url(self):
        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp)
            source = temp / "source.bin"
            source.write_bytes(b"abc" * 1000)
            seen = []
            target = core.download(source.as_uri(), temp / "downloaded.bin", lambda d, t: seen.append(d))
            self.assertEqual(target.read_bytes(), source.read_bytes())
            self.assertTrue(seen)

    def test_run_script_streams_output(self):
        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp)
            script = temp / "hello.py"
            script.write_text("print('hello from setup')\n", encoding="utf-8")
            lines = []
            code = core.run_script(core.find_python(), temp, "hello.py", on_line=lines.append)
            self.assertEqual(code, 0)
            self.assertEqual(lines, ["hello from setup"])

    def test_install_passes_override_flag(self):
        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp)
            archive = temp / "app.tar.gz"
            script = (
                "import pathlib, sys\n"
                "pathlib.Path('args.txt').write_text(' '.join(sys.argv[1:]))\n"
                "print('installed')\n"
            )
            make_tar(archive, [("install.py", "file", script)])
            workdir = temp / "work"
            workdir.mkdir()
            lines = []
            core.install(core.find_python(), archive, workdir, True, on_line=lines.append)
            self.assertEqual((workdir / "app/args.txt").read_text(), "--clear-overrides")
            self.assertIn("installed", lines)

    def test_uninstall_runs_app_uninstaller(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            app_dir = home / "app"
            app_dir.mkdir()
            (app_dir / "uninstall.py").write_text("print('removed')\n", encoding="utf-8")
            state = home / ".config/proton-picker/state.json"
            state.parent.mkdir(parents=True)
            state.write_text(
                json.dumps({"installation": {"app_dir": str(app_dir)}}), encoding="utf-8"
            )
            lines = []
            core.uninstall(core.find_python(), home, on_line=lines.append)
            self.assertEqual(lines, ["removed"])


if __name__ == "__main__":
    unittest.main()
