# Packaging SerialScope for Linux

SerialScope's first standalone Linux development package is a PyInstaller one-folder bundle. It is deliberately inspectable and easier to diagnose than a compressed one-file executable. It is not yet an AppImage or distribution package.

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
    └── bundled Python, Qt, PySide6, PyQtGraph, and PySerial files
```

No repository documentation or source-tree resource is required at runtime. SerialScope currently has no application icon asset, so this first bundle uses the default executable presentation.

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

## Manual package test

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

- This is a development bundle, not an installer, AppImage, `.deb`, or RPM.
- The bundle is architecture- and Linux-ABI-specific. Build separately for each target architecture and sufficiently old target baseline.
- Some distributions may require host X11/XCB, Wayland, OpenGL, font, or graphics-driver libraries compatible with Qt.
- Hardware serial, browser integration, native file dialogs, and desktop drag/drop require manual testing on the target desktop.
- There is no `.desktop` launcher, MIME association, application icon, code signing, or automatic updater yet.
