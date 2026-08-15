# Packaging SerialScope for Windows

SerialScope's Windows baseline is a native PyInstaller one-folder bundle. It
does not create an installer, MSI, or one-file executable.

## Requirements

- 64-bit Windows build host
- Python 3.10 or newer (Python 3.12 is the validated baseline)
- A project-local virtual environment at `.venv`
- Application, test, and packaging dependencies installed with:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev,packaging]"
```

No administrator privileges or global package installation are required.

## Build

From the repository root, or by invoking the script through an absolute path:

```powershell
.\scripts\build_windows.ps1
```

For a different project-local Python environment:

```powershell
.\scripts\build_windows.ps1 -PythonExecutable .packaging-venv\Scripts\python.exe
```

The script uses `packaging/serialscope_windows.spec` and replaces only the
generated Windows work directory and bundle. Output is:

```text
dist\SerialScope\
|-- SerialScope.exe
`-- _internal\
    |-- assets\icons\serialscope.png
    `-- bundled Python, Qt, PySide6, PyQtGraph, and PySerial files
```

`SerialScope.exe` uses the Windows GUI subsystem, so it does not create a
console window. Its Explorer/taskbar icon is embedded from
`assets/icons/serialscope.ico`. Qt continues to load the authoritative PNG at
runtime through the existing PyInstaller-safe resource resolver.

## Automated smoke test

After building:

```powershell
.\scripts\smoke_test_windows.ps1
```

The smoke test checks the executable, bundled PNG, GUI PE subsystem, and
embedded icon. It launches the real packaged executable from a temporary
working directory outside the repository, verifies that it remains alive for
three seconds, then closes or terminates only that test process. It does not
connect to serial hardware.

## Manual checklist

Launch `dist\SerialScope\SerialScope.exe` directly, without activating the
virtual environment, and verify:

1. No console window appears and the approved icon is shown.
2. Dark and Light themes render correctly.
3. Terminal, Data, Graphs, Dashboard, sidebar, and Device Profiles open.
4. Graph selection, scrolling, cursor values, statistics, zoom, and Reset Zoom work.
5. Open Session can browse to and replay an existing recording.
6. Available Windows COM ports appear.
7. With hardware available, connect, receive data, disconnect, and reconnect.
8. Start and stop a short recording and verify its session files.
9. Launch the absolute EXE path while the current directory is outside the repository.

## Known Windows considerations

- Builds are native to the Windows architecture and Python environment used.
- The bundle is intentionally unsigned during this infrastructure milestone;
  Windows reputation prompts may occur on other machines.
- Hardware serial access, native file dialogs, browser integration, and taskbar
  behavior require manual validation on target systems.
- Windows update asset selection and installation are not implemented yet. The
  existing Linux-oriented updater remains bundled unchanged.
- No installer, shortcuts, file associations, or automatic PATH changes are
  provided by the one-folder bundle.
