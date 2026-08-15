# Packaging SerialScope for Linux

SerialScope's Linux distribution is built in two layers: an inspectable
PyInstaller one-folder bundle, then a Debian package that installs that bundle
as a normal desktop application. The `.deb` targets native amd64
Debian-compatible systems, including suitably compatible Ubuntu and Linux Mint
releases. It is not an AppImage.

## Prerequisites

- A supported 64-bit Linux build host
- Python 3.10 or newer
- A project-local virtual environment at `.venv`
- Normal system libraries required by the installed PySide6/Qt wheel

Build on the oldest Linux distribution that the resulting bundle must support. PyInstaller bundles Python and application libraries, but it does not make the host C library backward-compatible with older distributions.

Create and activate the environment, then install application, test, and packaging dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev,packaging]"
```

PyInstaller is a packaging-only dependency. It is not installed for ordinary SerialScope runtime use.

The Debian build also requires the standard `dpkg`/`dpkg-deb` tools. If
`desktop-file-validate` is installed, the build uses it automatically.

## Build

From any working directory, run the repository script by path:

```bash
./scripts/build_linux.sh
```

The maintained configuration is `packaging/serialscope.spec`. It packages `src/serialscope/__main__.py`, which uses the same `serialscope.app.main()` startup function as `python -m serialscope`.

The output is:

```text
dist/SerialScope/
├── SerialScope
└── _internal/
    ├── assets/icons/serialscope.png
    └── bundled Python, Qt, PySide6, PyQtGraph, and PySerial files
```

`assets/icons/serialscope.png` is the authoritative application icon. Qt loads
it through SerialScope's packaging-safe resource lookup, so source and bundled
launches do not depend on the current working directory. PyInstaller includes
the same PNG under `_internal/assets/icons/` in the one-folder bundle.

PyInstaller cannot embed an icon in a Linux ELF executable. Complete desktop
menu/taskbar integration will therefore belong to a future `.desktop`/`.deb`
milestone, which should reuse this authoritative PNG in the hicolor hierarchy.
A future Windows build may derive an `.ico` from the same artwork without
changing application resource lookup.

## Build the Debian package

Run the maintained one-command build from the repository:

```bash
./scripts/build_linux_deb.sh
```

The script derives the Debian version directly from
`serialscope.__version__`, rebuilds the PyInstaller bundle, stages the package
under ignored `build/deb/`, validates it without root privileges, and writes:

```text
dist/serialscope_<version>_amd64.deb
```

The current version already conforms to Debian version syntax and is used
unchanged. A future incompatible version string causes a clear build failure
instead of silently introducing a second version source.

The installed layout is:

```text
/opt/serialscope/                         complete PyInstaller bundle
/usr/bin/serialscope                     command-line launcher
/usr/share/applications/serialscope.desktop
/usr/share/icons/hicolor/256x256/apps/serialscope.png
```

The 256×256 hicolor icon is generated during the build from the authoritative
`assets/icons/serialscope.png`; it is not a separately maintained source asset.

Install, launch, and remove the package with:

```bash
sudo apt install ./dist/serialscope_<version>_amd64.deb
serialscope
sudo apt remove serialscope
```

SerialScope also appears in a standards-compliant desktop application menu.
The desktop entry launches without a terminal and resolves the icon through
the hicolor hierarchy.

Package upgrades replace `/opt/serialscope` and the system launchers normally.
Application settings and Device Profiles remain in per-user configuration
locations, while recordings remain wherever the user chose to create them.
Removal and purge scripts never inspect or delete user home directories.

The packaged application still depends on a small set of normal system runtime
libraries: glibc 2.38 or newer, OpenGL/EGL loader libraries, and Wayland client
libraries. Python, Qt, PySide6, PyQtGraph, PySerial, and the remaining bundled
runtime are carried inside `/opt/serialscope`. The glibc baseline comes from
the current build environment and binary set, so this package is not compatible
with every historical Debian or Ubuntu release. Build on an older supported
baseline when broader backward compatibility is required.

Inspect an existing package without installing it:

```bash
./scripts/smoke_test_linux_deb.sh dist/serialscope_<version>_amd64.deb
dpkg-deb --info dist/serialscope_<version>_amd64.deb
dpkg-deb --contents dist/serialscope_<version>_amd64.deb
```

## Launch

Launch directly, without activating the virtual environment:

```bash
./dist/SerialScope/SerialScope
```

The executable does not depend on the current working directory. For example:

```bash
cd /tmp
/path/to/SerialScope/dist/SerialScope/SerialScope
```

The Linux build is a GUI application and does not open a terminal itself. For startup diagnostics, launch it from an existing terminal; dynamic-loader and PyInstaller bootloader failures remain visible there.

## Automated smoke test

After building:

```bash
./scripts/smoke_test_linux.sh
```

The smoke test launches the real bundled executable with Qt's offscreen platform from a temporary, unrelated working directory. It constructs the application and main window, then exits through a private packaging-test flag. It does not automate hardware or visual interaction.

Run the normal checks as well:

```bash
python -m pytest
python -m compileall -q src tests
git diff --check
```

## Manual application test

Use the built executable—not `python main.py`—for the following checks:

1. Start from an unrelated working directory and verify the displayed version.
2. Switch Light/Dark themes and inspect menus, About, Graphs, and Dashboard.
3. Confirm GitHub / Updates opens the repository in the normal browser.
4. Discover a serial device; connect, receive, transmit, disconnect, and reconnect.
5. Exercise CSV and JSON parsing, Data, live Graphs, and Dashboard tile dragging.
6. Record a named session and verify `session.json` and each device's `raw.log` and `data.csv`.
7. Open both a legacy single-device recording and a current multi-device recording in Replay.

## Clean generated output

The build script safely replaces only SerialScope's generated bundle and work directory. To clean manually from the repository root:

```bash
rm -rf build/SerialScope dist/SerialScope
```

Both top-level output directories are ignored by Git. The maintained `packaging/serialscope.spec` is explicitly not ignored.

## Serial-port permissions

Linux distributions commonly restrict `/dev/ttyUSB*` and `/dev/ttyACM*` access to a group such as `dialout` or `uucp`. SerialScope does not modify groups, device rules, or permissions and never invokes `sudo`. Configure access according to the distribution's documentation, log out/in if group membership changes, and retry. Permission failures remain concise connection errors in the UI.

## Known limitations

- The bundle is architecture- and Linux-ABI-specific. Build separately for each target architecture and sufficiently old target baseline.
- Some distributions may require host X11/XCB, Wayland, OpenGL, font, or graphics-driver libraries compatible with Qt.
- Hardware serial, browser integration, native file dialogs, and desktop drag/drop require manual testing on the target desktop.
- The `.deb` provides a desktop launcher and hicolor icon, but taskbar behavior
  can still vary between window managers. There is no MIME association, code
  signing, automatic updater, AppImage, RPM, or ARM package yet.
