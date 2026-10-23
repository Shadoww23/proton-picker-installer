# Proton Picker Setup

A small AppImage installer for [Proton Picker](https://brlinkin.itch.io/proton-picker).
It gives the alpha a double-click setup path instead of a terminal:

1. checks for native Steam and Python 3.10+
2. downloads the official archive from the pinned GitHub release
3. verifies the pinned SHA-256 checksum
4. extracts it to a temporary folder and runs the official `install.py`
5. offers an uninstall button that runs the official `uninstall.py`

No administrator password is needed. The installer contains no Proton Picker code,
does not redistribute it, and never talks to any server except the official GitHub
release URL.

> **Alpha.** Tested on desktop Linux build hosts only. SteamOS/Steam Deck Desktop Mode
> is not validated; the desktop path remains the supported one. Flatpak Steam and
> per-game overrides on a Deck are not covered.

## Install

1. Download `ProtonPickerSetup-0.1.1-x86_64.AppImage` from the
   [releases page](https://github.com/Shadoww23/proton-picker-installer/releases).
2. Make it executable: right-click → Properties → Permissions → **Allow executing file
   as a program**, or run `chmod +x ProtonPickerSetup-*.AppImage`.
3. Double-click it, or run `./ProtonPickerSetup-*.AppImage`.

The setup window explains what will change before it does anything. If Steam is open it
asks to close it first (save your game). After setup, start Steam and click Play as usual.

On systems without FUSE, run:

```sh
./ProtonPickerSetup-0.1.1-x86_64.AppImage --appimage-extract-and-run
```

### Debian/Ubuntu and Fedora

Native packages install the same setup window and add a desktop entry. They use
the system Python 3.10+ and Tk, so they are smaller than the AppImage:

```sh
# Debian/Ubuntu
sudo apt install ./proton-picker-setup_0.1.1-1_amd64.deb

# Fedora
sudo dnf install ./proton-picker-setup-0.1.1-1.x86_64.rpm
```

The AppImage remains the portable option for older distributions and SteamOS
desktop mode.

## Requirements

- x86_64 desktop Linux with glibc 2.31 or newer
- native Steam (Flatpak Steam is refused)
- Python 3.10 or newer on the host, used to run Proton Picker's official installer
- at least one Proton build installed in Steam

## Build

The AppImage is built inside Ubuntu 20.04 so it stays usable on older SteamOS releases.
Docker or Podman is required.

```sh
./build/build_appimage.sh
```

Output: `dist/ProtonPickerSetup-<version>-x86_64.AppImage` and `dist/SHA256SUMS`.
The workflow in `.github/workflows/ci.yml` produces the same artifact.

Build the Debian and RPM packages with [nfpm](https://nfpm.goreleaser.com/install/):

```sh
NFPM=/path/to/nfpm ./build/build_packages.sh
```

Output: `dist/packages/*.deb`, `dist/packages/*.rpm`, and
`dist/packages/SHA256SUMS-packages`.

Tests:

```sh
python3 -m unittest discover -s tests -v
```

## Security notes

- The archive URL and SHA-256 are constants in `core.py`; bump both together for a new
  Proton Picker release.
- Extraction rejects absolute paths, `..` traversal, links, and device entries.
- Steam is closed gracefully via `steam -shutdown`; the installer never kills processes.
- The installer does not run as root and does not write outside the user's home.

## License

Installer code: MIT, see [LICENSE](LICENSE). Proton Picker itself is proprietary
freeware and is **not** included in this repository or the AppImage. Not affiliated
with Valve Corporation.
