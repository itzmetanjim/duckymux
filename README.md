# Duckymux - Multitasking Manager for Python Scripts

Duckymux is a terminal-based application manager that allows you to run, monitor, and control multiple Python scripts simultaneously. It provides a curses-based interface with keyboard and mouse support.

## Features

- **Run multiple apps concurrently** - Background execution with process management
- **Serial monitor** - Interactive I/O with running applications
- **Keyboard shortcuts** - Vim-like navigation (j/k) and intuitive commands
- **Mouse support** - Click to select, right-click to run, double-click to monitor
- **Scroll wheel** - Navigate through app list
- **Foreground mode** - Run apps exclusively with Shift+R
- **Color support** - Automatic detection with graceful fallback

## Requirements

- Python 3.6+
- Linux/Unix environment (uses `curses`, `subprocess`, `select`)
- Terminal with curses support

## Installation

1. Clone or download this repository
2. Ensure the `apps/` directory exists with Python scripts
3. Make scripts executable (optional): `chmod +x apps/*.py`

## Usage

Run Duckymux from the project directory:

```bash
python3 main.py
```

### Keyboard Controls

| Key | Action |
|-----|--------|
| `q` | Quit Duckymux and terminate all running apps |
| `h` | Show/hide help screen |
| `↑`/`k` | Move selection up |
| `↓`/`j` | Move selection down |
| `r` | Run selected app in background |
| `R` (Shift+R) | Run app in foreground (exclusive mode, exits Duckymux) |
| `o` | Open serial monitor for selected app |
| `s` | Stop (terminate) selected app |

### Mouse Controls

| Action | Result |
|--------|--------|
| **Click** | Select app |
| **Right-click** | Run selected app in background |
| **Double-click** | Open serial monitor |
| **Scroll up** | Move selection up |
| **Scroll down** | Move selection down |

### Serial Monitor

When you open the serial monitor (`o` or double-click):
- Works exactly like `screen` - exits the curses UI and gives you direct terminal access
- The app's output goes directly to your terminal (no buffering or UI elements)
- You can send input to the app by typing normally
- Terminal is set to raw mode for full control
- **Ctrl+D then Ctrl+X**: Exit serial monitor and return to Duckymux
- **Ctrl+D twice**: Send Ctrl+D to the app (e.g., for EOF or exit)
- The app continues running in the background after you exit the monitor

## App Structure

Place your Python scripts in the `apps/` directory:

```
duckymux/
├── main.py
├── README.md
└── apps/
    ├── app1.py
    ├── app2.py
    └── app3.py
```

All `.py` files in the `apps/` directory will be automatically detected and displayed.

## Example Apps

Three sample apps are included:

1. **app1.py** - Counter that increments every second
2. **app2.py** - Echo server that repeats user input
3. **app3.py** - System info display with auto-exit

## Technical Details

### Process Management
- Background apps run as `subprocess.Popen` instances
- Each app maintains its own stdin/stdout/stderr pipes
- Process state is polled periodically (100ms intervals)
- Terminated apps are automatically cleaned up

### MicroPython Compatibility Notes
The current implementation uses standard Python libraries (`subprocess`, `select`). For MicroPython porting:
- Replace `subprocess` with `_thread` or async tasks
- Replace `select` with `uselect`
- Replace `os.execvp` with appropriate MicroPython mechanism
- Adapt file I/O for embedded filesystem

### Display Management
- Automatic scrolling when app list exceeds screen height
- Selected app highlighted with `>` prefix
- Running apps show `RUNNING` status
- Header bar with inverted colors (when supported)

## Troubleshooting

**"Terminal does not support colors"**
- Your terminal doesn't support color pairs. The app will work in monochrome mode.

**"No apps found in 'apps' directory"**
- Create the `apps/` directory and add `.py` files.

**Apps not starting**
- Verify scripts are Python 3 compatible
- Check file permissions
- Ensure Python 3 is in PATH as `python3`

**Serial monitor not working**
- Some apps may not flush output immediately. Add `sys.stdout.flush()` after print statements.
- Input/output buffering can cause delays.

## License

Open source - free to use and modify.

## Contributing

Contributions welcome! Areas for improvement:
- Better error handling and user feedback
- Configuration file support
- Log file viewing
- App restart on crash
- Custom command execution per app
